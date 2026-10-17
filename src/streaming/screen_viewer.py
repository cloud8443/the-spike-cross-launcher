"""
screen_viewer.py
게스트(Guest) PC에서 호스트의 게임 화면을 수신하여
초저지연으로 화면에 렌더링하고, 2P 키보드 입력을 즉시 캡처하여 전달하는 전용 원격 플레이어 창.
"""

import logging
import socket
import struct
import threading
import time

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QImage, QPixmap, QPainter, QKeyEvent, QColor, QFont, QFocusEvent

logger = logging.getLogger("ScreenViewer")

MAX_FRAME_SIZE = 5 * 1024 * 1024  # 5MB 비정상 패킷 방어 상한선


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
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 262144)
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

                if len(payload_buf) < payload_len:
                    payload_buf = bytearray(payload_len)

                # 2. JPEG 데이터 Zero-Copy 수신
                if not self._recv_into_exact(payload_buf, payload_len):
                    break

                # 3. 백그라운드 스레드에서 즉시 QImage 디코딩 (GUI 스레드 병목 제거)
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
    """QPainter를 이용해 화면에 프레임을 비율 유지하며 초고속 렌더링하는 위젯."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_pixmap = None
        self._scaled_pixmap = None
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background-color: #05060a;")
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)

    def update_image(self, image: QImage):
        if image and not image.isNull():
            self.current_pixmap = QPixmap.fromImage(image)
            self._rebuild_scaled_pixmap()
            self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rebuild_scaled_pixmap()

    def _rebuild_scaled_pixmap(self):
        """새 프레임 수신 또는 창 리사이즈 시에만 스케일링 연산 수행."""
        if self.current_pixmap and not self.current_pixmap.isNull() and not self.size().isEmpty():
            self._scaled_pixmap = self.current_pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation
            )

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#05060a"))

        if self._scaled_pixmap and not self._scaled_pixmap.isNull():
            x = (self.width() - self._scaled_pixmap.width()) // 2
            y = (self.height() - self._scaled_pixmap.height()) // 2
            painter.drawPixmap(x, y, self._scaled_pixmap)
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
        if self.guest_runner:
            self.guest_runner.release_all_keys()
        if self._receiver:
            self._receiver.stop()
        event.accept()
