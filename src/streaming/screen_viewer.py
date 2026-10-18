"""
screen_viewer.py
게스트(Guest) PC에서 호스트의 게임 화면을 수신하여
초저지연으로 화면에 렌더링하고, 2P 키보드 입력을 즉시 캡처하여 전달하는 전용 원격 플레이어 창.
"""

import ctypes
import logging
import socket
import struct
import threading
import time

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QRect
from PyQt6.QtGui import QImage, QPixmap, QPainter, QKeyEvent, QColor, QFont, QFocusEvent

logger = logging.getLogger("ScreenViewer")

MAX_FRAME_SIZE = 5 * 1024 * 1024  # 5MB 비정상 패킷 방어 상한선

# XInput 버튼 플래그 상수
XINPUT_GAMEPAD_DPAD_UP = 0x0001
XINPUT_GAMEPAD_DPAD_DOWN = 0x0002
XINPUT_GAMEPAD_DPAD_LEFT = 0x0004
XINPUT_GAMEPAD_DPAD_RIGHT = 0x0008
XINPUT_GAMEPAD_START = 0x0010
XINPUT_GAMEPAD_BACK = 0x0020
XINPUT_GAMEPAD_LEFT_THUMB = 0x0040
XINPUT_GAMEPAD_RIGHT_THUMB = 0x0080
XINPUT_GAMEPAD_LEFT_SHOULDER = 0x0100
XINPUT_GAMEPAD_RIGHT_SHOULDER = 0x0200
XINPUT_GAMEPAD_A = 0x1000
XINPUT_GAMEPAD_B = 0x2000
XINPUT_GAMEPAD_X = 0x4000
XINPUT_GAMEPAD_Y = 0x8000


class XINPUT_GAMEPAD(ctypes.Structure):
    _fields_ = [
        ('wButtons', ctypes.c_ushort),
        ('bLeftTrigger', ctypes.c_ubyte),
        ('bRightTrigger', ctypes.c_ubyte),
        ('sThumbLX', ctypes.c_short),
        ('sThumbLY', ctypes.c_short),
        ('sThumbRX', ctypes.c_short),
        ('sThumbRY', ctypes.c_short),
    ]


class XINPUT_STATE(ctypes.Structure):
    _fields_ = [
        ('dwPacketNumber', ctypes.c_ulong),
        ('Gamepad', XINPUT_GAMEPAD),
    ]


class PhysicalGamepadPoller(QObject):
    """
    게스트 PC에 연결된 물리 게임패드(Xbox One/Series, PS4/PS5, 8BitDo 등)를
    120Hz 주기로 폴링하여 호스트 2P 패드로 실시간 무지연 전달하는 백그라운드 엔진.
    """
    status_changed = pyqtSignal(str)

    def __init__(self, guest_runner=None):
        super().__init__()
        self.guest_runner = guest_runner
        self._running = False
        self._xinput = None
        self._connected = False
        self._active_index = -1
        self._init_xinput()

    def _init_xinput(self):
        for dll in ['xinput1_4.dll', 'xinput1_3.dll', 'xinput9_1_0.dll']:
            try:
                self._xinput = ctypes.windll.LoadLibrary(dll)
                break
            except Exception:
                pass

    def start(self):
        if not self._xinput:
            logger.info("XInput DLL 로드 실패 (물리 패드 비활성화)")
            return
        self._running = True
        threading.Thread(target=self._poll_loop, daemon=True).start()

    def stop(self):
        self._running = False

    def _poll_loop(self):
        state = XINPUT_STATE()
        last_buttons = 0
        last_lx_dir = 0
        last_ly_dir = 0
        last_heartbeat = time.perf_counter()

        while self._running:
            found_controller = False
            for user_idx in range(4):
                res = self._xinput.XInputGetState(user_idx, ctypes.byref(state))
                if res == 0:
                    found_controller = True
                    if not self._connected or self._active_index != user_idx:
                        self._connected = True
                        self._active_index = user_idx
                        self.status_changed.emit(f"🎮 패드 #{user_idx + 1} 연결됨")
                        logger.info(f"게스트 물리 게임패드 감지 (슬롯 #{user_idx + 1})")

                    gp = state.Gamepad
                    wButtons = gp.wButtons
                    sThumbLX = gp.sThumbLX
                    sThumbLY = gp.sThumbLY
                    bLeftTrigger = gp.bLeftTrigger
                    bRightTrigger = gp.bRightTrigger

                    # 데드존 (32767 중 약 25% = 8000)
                    DEADZONE = 8000
                    left = bool((wButtons & XINPUT_GAMEPAD_DPAD_LEFT != 0) or (sThumbLX < -DEADZONE))
                    right = bool((wButtons & XINPUT_GAMEPAD_DPAD_RIGHT != 0) or (sThumbLX > DEADZONE))
                    up = bool((wButtons & XINPUT_GAMEPAD_DPAD_UP != 0) or (sThumbLY > DEADZONE))
                    down = bool((wButtons & XINPUT_GAMEPAD_DPAD_DOWN != 0) or (sThumbLY < -DEADZONE))

                    # 액션 버튼
                    spike = bool((wButtons & XINPUT_GAMEPAD_A != 0) or (wButtons & XINPUT_GAMEPAD_RIGHT_SHOULDER != 0) or (bRightTrigger > 30))
                    receive = bool((wButtons & XINPUT_GAMEPAD_X != 0) or (wButtons & XINPUT_GAMEPAD_LEFT_SHOULDER != 0) or (bLeftTrigger > 30))
                    block = bool(wButtons & XINPUT_GAMEPAD_B != 0)
                    slide = bool(wButtons & XINPUT_GAMEPAD_Y != 0)
                    pause = bool(wButtons & XINPUT_GAMEPAD_START != 0)

                    now = time.perf_counter()
                    # 상태 변화 감지 또는 30ms 주기 하트비트 전송
                    if (wButtons != last_buttons or left != (last_lx_dir < 0) or right != (last_lx_dir > 0)
                            or up != (last_ly_dir > 0) or down != (last_ly_dir < 0)
                            or (now - last_heartbeat >= 0.03)):
                        last_buttons = wButtons
                        last_lx_dir = -1 if left else (1 if right else 0)
                        last_ly_dir = 1 if up else (-1 if down else 0)
                        last_heartbeat = now

                        if self.guest_runner:
                            self.guest_runner.send_gamepad_state(
                                left=left, right=right, up=up, down=down,
                                spike=spike, receive=receive, block=block, slide=slide,
                                pause=pause
                            )
                    break

            if not found_controller:
                if self._connected:
                    self._connected = False
                    self._active_index = -1
                    self.status_changed.emit("⌨️ 키보드 모드 (패드 없음)")
                    logger.info("게스트 물리 게임패드 연결 해제됨")
                time.sleep(0.5)
            else:
                time.sleep(0.008)  # 120Hz 고속 폴링


class StreamReceiverThread(QObject):
    """백그라운드에서 호스트의 영상 스트림을 수신 및 디코딩하는 래퍼."""
    frame_ready = pyqtSignal()
    fps_updated = pyqtSignal(int)
    disconnected = pyqtSignal(str)

    def __init__(self, host_ip, stream_port=47998):
        super().__init__()
        self.host_ip = host_ip
        self.stream_port = stream_port
        self._running = False
        self._sock = None
        self._frame_lock = threading.Lock()
        self._latest_image = None
        self._frame_pending = False

    def get_latest_image(self):
        """UI 스레드가 가장 최근에 디코딩된 QImage를 가져감 (구형 프레임 자동 드랍)."""
        with self._frame_lock:
            self._frame_pending = False
            return self._latest_image

    def start(self):
        self._running = True
        t = threading.Thread(target=self._recv_loop, daemon=True)
        t.start()

    def _recv_loop(self):
        retry_count = 0
        while self._running:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)  # 저지연 버퍼 최적화
                sock.settimeout(4.0)
                sock.connect((self.host_ip, self.stream_port))
                self._sock = sock
                logger.info(f"호스트 화면 스트림 연결 성공: {self.host_ip}:{self.stream_port}")
                break
            except Exception as e:
                retry_count += 1
                if retry_count > 10 or not self._running:
                    self.disconnected.emit(f"호스트 화면 연결 실패: {e}")
                    return
                time.sleep(1.0)

        fps_timer = time.perf_counter()
        frames_count = 0

        # Windows 소켓 버퍼 검사용 ioctl 준비
        ws2_32 = getattr(ctypes.windll, 'ws2_32', None) if hasattr(ctypes, 'windll') else None
        FIONREAD = 0x4004667f
        avail = ctypes.c_ulong(0)

        # 수신 버퍼 사전 할당 (재할당 방지)
        header_buf = bytearray(4)
        payload_buf = bytearray(512 * 1024)  # 초기 512KB

        while self._running and self._sock:
            try:
                # 1. 헤더(4바이트 길이) 수신
                if not self._recv_into_exact(header_buf, 4):
                    break
                payload_len = struct.unpack(">I", header_buf)[0]

                if payload_len <= 0 or payload_len > MAX_FRAME_SIZE:
                    logger.warning(f"비정상 프레임 크기 감지: {payload_len} bytes")
                    break

                # 2. 초저지연 프레임 패스트포워드 (지연 누적 원천 제거)
                # 소켓 버퍼에 후속 프레임 데이터가 이미 들어와 있는 경우,
                # 낡은 프레임을 디코딩하지 않고 폐기한 뒤 가장 최신의 프레임으로 직행합니다.
                if ws2_32 is not None:
                    while self._running:
                        ws2_32.ioctlsocket(self._sock.fileno(), FIONREAD, ctypes.byref(avail))
                        if avail.value >= payload_len + 4:
                            if not self._recv_into_exact(payload_buf, payload_len):
                                break
                            if not self._recv_into_exact(header_buf, 4):
                                break
                            payload_len = struct.unpack(">I", header_buf)[0]
                            if payload_len <= 0 or payload_len > MAX_FRAME_SIZE:
                                break
                            continue
                        break

                if len(payload_buf) < payload_len:
                    payload_buf = bytearray(payload_len)

                # 3. 최신 JPEG 데이터 Zero-Copy 수신
                if not self._recv_into_exact(payload_buf, payload_len):
                    break

                # 4. 백그라운드 스레드에서 즉시 QImage 디코딩 (GUI 스레드 병목 제거)
                img = QImage()
                if img.loadFromData(memoryview(payload_buf)[:payload_len], "JPEG"):
                    emit_needed = False
                    with self._frame_lock:
                        self._latest_image = img
                        if not self._frame_pending:
                            self._frame_pending = True
                            emit_needed = True
                    if emit_needed:
                        self.frame_ready.emit()

                frames_count += 1
                now = time.perf_counter()
                if now - fps_timer >= 1.0:
                    self.fps_updated.emit(frames_count)
                    frames_count = 0
                    fps_timer = now

            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    logger.warning(f"스트림 수신 오류: {e}")
                break

        if self._running:
            self.disconnected.emit("호스트와의 화면 연결이 종료되었습니다.")

    def _recv_into_exact(self, buf: bytearray, num_bytes: int) -> bool:
        """memoryview와 recv_into를 이용해 메모리 재할당 없이 정확히 num_bytes만큼 수신."""
        view = memoryview(buf)[:num_bytes]
        total_received = 0
        while total_received < num_bytes and self._running:
            try:
                n = self._sock.recv_into(view[total_received:], num_bytes - total_received)
                if n == 0:
                    return False
                total_received += n
            except socket.timeout:
                continue
            except Exception:
                return False
        return total_received == num_bytes

    def stop(self):
        self._running = False
        if self._sock:
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None


class VideoDisplayWidget(QWidget):
    """QPainter를 이용해 화면에 프레임을 비율 유지하며 하드웨어 가속 초고속 렌더링하는 위젯."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_pixmap = None
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background-color: #05060a;")
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)

    def update_image(self, image: QImage):
        if image and not image.isNull():
            self.current_pixmap = QPixmap.fromImage(image)
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#05060a"))

        if self.current_pixmap and not self.current_pixmap.isNull():
            # 16:9 비율 유지 중앙 정렬 렌더링 (안티앨리어싱 부드러운 스케일링)
            w = self.width()
            h = self.height()
            pix_w = self.current_pixmap.width()
            pix_h = self.current_pixmap.height()

            scale = min(w / pix_w, h / pix_h)
            target_w = max(1, int(pix_w * scale))
            target_h = max(1, int(pix_h * scale))
            x = (w - target_w) // 2
            y = (h - target_h) // 2

            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            painter.drawPixmap(QRect(x, y, target_w, target_h), self.current_pixmap)
        else:
            painter.setPen(QColor("#64748b"))
            painter.setFont(QFont("Malgun Gothic", 14))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "호스트 게임 화면을 기다리는 중...")


class GameStreamViewerWindow(QWidget):
    """게스트 전용 원격 플레이 뷰어 창 (최대 120 FPS 지원)."""

    def __init__(self, host_ip, stream_port, guest_runner=None, parent=None):
        super().__init__(parent)
        self.host_ip = host_ip
        self.stream_port = stream_port
        self.guest_runner = guest_runner
        self._receiver = None
        self._is_fullscreen = False
        self.current_fps_mode = 120

        self.setWindowTitle("🏐 더 스파이크 크로스 - 원격 2P 플레이어 (120 FPS)")
        self.resize(1100, 680)
        self.setStyleSheet("""
            QWidget {
                background-color: #0b0c14;
                color: #e2e8f0;
                font-family: 'Malgun Gothic', 'Segoe UI', sans-serif;
            }
        """)

        self._init_ui()
        self._start_stream()

        # 물리 게임패드 폴러 시작
        self._gamepad_poller = PhysicalGamepadPoller(self.guest_runner)
        self._gamepad_poller.status_changed.connect(self._on_pad_status)
        self._gamepad_poller.start()

    def _on_pad_status(self, text: str):
        self.lbl_pad.setText(text)
        if "패드 #" in text:
            self.lbl_pad.setStyleSheet("font-size: 11px; color: #34d399; font-weight: bold;")
        else:
            self.lbl_pad.setStyleSheet("font-size: 11px; color: #94a3b8;")

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 상단 HUD 바
        top_bar = QWidget()
        top_bar.setFixedHeight(44)
        top_bar.setStyleSheet("""
            background-color: #121422;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        """)
        tb_layout = QHBoxLayout(top_bar)
        tb_layout.setContentsMargins(16, 0, 16, 0)

        self.lbl_title = QLabel("🏐 THE SPIKE CROSS (2P 원격 조작 화면)")
        self.lbl_title.setStyleSheet("font-weight: 800; font-size: 13px; color: #ff4d4d;")

        self.lbl_status = QLabel("🟢 화면 연결 중...")
        self.lbl_status.setStyleSheet("font-weight: bold; font-size: 12px; color: #10b981;")

        self.lbl_pad = QLabel("🎮 패드 감지 대기 중...")
        self.lbl_pad.setStyleSheet("font-size: 11px; color: #94a3b8;")

        self.lbl_fps = QLabel("FPS: 측정 중 | 딜레이: 초저지연 (<8ms)")
        self.lbl_fps.setStyleSheet("font-size: 11px; color: #94a3b8;")

        # 120 FPS / 60 FPS 토글 버튼 (버튼 클릭 시 키보드 포커스 뺏기 방지)
        self.btn_fps_mode = QPushButton("⚡ 120 FPS (고주사율)")
        self.btn_fps_mode.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_fps_mode.setStyleSheet("""
            background-color: #047857;
            color: #a7f3d0;
            border-radius: 6px;
            padding: 4px 10px;
            font-size: 11px;
            font-weight: bold;
        """)
        self.btn_fps_mode.setToolTip("클릭하여 120 FPS와 60 FPS 모드를 전환합니다.")
        self.btn_fps_mode.clicked.connect(self.toggle_fps_mode)

        self.btn_fullscreen = QPushButton("전체화면 (F11)")
        self.btn_fullscreen.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_fullscreen.setStyleSheet("""
            background-color: #1e293b;
            color: #ffffff;
            border-radius: 6px;
            padding: 4px 12px;
            font-size: 11px;
            font-weight: bold;
        """)
        self.btn_fullscreen.clicked.connect(self.toggle_fullscreen)

        tb_layout.addWidget(self.lbl_title)
        tb_layout.addWidget(self.lbl_status)
        tb_layout.addWidget(self.lbl_pad)
        tb_layout.addStretch()
        tb_layout.addWidget(self.lbl_fps)
        tb_layout.addWidget(self.btn_fps_mode)
        tb_layout.addWidget(self.btn_fullscreen)

        layout.addWidget(top_bar)

        # 비디오 표시 위젯
        self.video_widget = VideoDisplayWidget()
        layout.addWidget(self.video_widget)

        # 키보드 포커스 설정
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def toggle_fps_mode(self):
        """120 FPS와 60 FPS 모드를 상호 전환하고 호스트에 즉시 적용."""
        if self.current_fps_mode == 120:
            self.current_fps_mode = 60
            self.btn_fps_mode.setText("🔋 60 FPS (표준)")
            self.btn_fps_mode.setStyleSheet("""
                background-color: #334155;
                color: #94a3b8;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: bold;
            """)
        else:
            self.current_fps_mode = 120
            self.btn_fps_mode.setText("⚡ 120 FPS (고주사율)")
            self.btn_fps_mode.setStyleSheet("""
                background-color: #047857;
                color: #a7f3d0;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: bold;
            """)

        if self.guest_runner:
            self.guest_runner.send_set_fps(self.current_fps_mode)
        self.setFocus()

    def _start_stream(self):
        self._receiver = StreamReceiverThread(self.host_ip, self.stream_port)
        self._receiver.frame_ready.connect(self._on_frame_ready)
        self._receiver.fps_updated.connect(lambda fps: self.lbl_fps.setText(f"FPS: {fps} | 딜레이: 초저지연 (<8ms)"))
        self._receiver.disconnected.connect(self._on_disconnected)
        self._receiver.start()

    def _on_frame_ready(self):
        if self._receiver:
            img = self._receiver.get_latest_image()
            if img is not None:
                self.video_widget.update_image(img)

    def _on_disconnected(self, reason):
        self.lbl_status.setText(f"🔴 {reason}")
        self.lbl_status.setStyleSheet("color: #ef4444; font-weight: bold;")

    def toggle_fullscreen(self):
        if self._is_fullscreen:
            self.showNormal()
            self._is_fullscreen = False
            self.btn_fullscreen.setText("전체화면 (F11)")
        else:
            self.showFullScreen()
            self._is_fullscreen = True
            self.btn_fullscreen.setText("창모드 (F11)")
        self.setFocus()

    # =========================================================
    # 키보드 입력 직접 캡처 -> 호스트 가상 패드로 UDP 송신
    # =========================================================
    def _key_to_name(self, key: int):
        special_mapping = {
            Qt.Key.Key_Up: "Up",
            Qt.Key.Key_Down: "Down",
            Qt.Key.Key_Left: "Left",
            Qt.Key.Key_Right: "Right",
            Qt.Key.Key_Escape: "Escape",
            Qt.Key.Key_Space: "Space",
            Qt.Key.Key_Return: "Enter",
            Qt.Key.Key_Enter: "Enter",
            Qt.Key.Key_Shift: "Shift",
            Qt.Key.Key_Control: "Ctrl",
            Qt.Key.Key_Tab: "Tab",
        }
        if key in special_mapping:
            return special_mapping[key]
        if Qt.Key.Key_A <= key <= Qt.Key.Key_Z or Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
            return chr(key)
        return None

    def keyPressEvent(self, event: QKeyEvent):
        # OS 키 반복(Auto-Repeat)으로 인한 가짜 연타 이벤트 무시
        if event.isAutoRepeat():
            return

        if event.key() == Qt.Key.Key_F11:
            self.toggle_fullscreen()
            return

        k_name = self._key_to_name(event.key())
        if k_name and self.guest_runner:
            self.guest_runner.send_key_input(k_name, True)
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent):
        # OS 키 반복(Auto-Repeat)으로 인한 가짜 릴리즈 이벤트 무시 (무한 눌림/끊김 방지 핵심)
        if event.isAutoRepeat():
            return

        k_name = self._key_to_name(event.key())
        if k_name and self.guest_runner:
            self.guest_runner.send_key_input(k_name, False)
            event.accept()
            return
        super().keyReleaseEvent(event)

    def focusOutEvent(self, event: QFocusEvent):
        """창 포커스를 잃을 때(Alt+Tab 등) 눌려있던 모든 키를 즉시 해제하여 무한 이동 방지."""
        if self.guest_runner:
            self.guest_runner.release_all_keys()
        super().focusOutEvent(event)

    def closeEvent(self, event):
        if hasattr(self, '_gamepad_poller') and self._gamepad_poller:
            self._gamepad_poller.stop()
        if self.guest_runner:
            self.guest_runner.release_all_keys()
        if self._receiver:
            self._receiver.stop()
        event.accept()
