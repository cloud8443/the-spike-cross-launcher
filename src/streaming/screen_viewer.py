"""
screen_viewer.py
게스트(Guest) PC에서 호스트의 게임 화면을 수신하여
초저지연으로 화면에 렌더링하고, 2P 키보드 입력을 즉시 캡처하여 전달하는 전용 원격 플레이어 창.
"""

import io
import logging
import socket
import struct
import sys
import threading
import time

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QImage, QPixmap, QPainter, QKeyEvent, QColor, QFont

logger = logging.getLogger("ScreenViewer")


class StreamReceiverThread(QObject):
    """백그라운드에서 호스트의 영상 스트림을 수신하는 QThread/스레드 래퍼."""
    frame_ready = pyqtSignal(bytes)
    fps_updated = pyqtSignal(int)
    disconnected = pyqtSignal(str)

    def __init__(self, host_ip, stream_port=47998):
        super().__init__()
        self.host_ip = host_ip
        self.stream_port = stream_port
        self._running = False
        self._sock = None

    def start(self):
        self._running = True
        t = threading.Thread(target=self._recv_loop, daemon=True)
        t.start()

    def _recv_loop(self):
        retry_count = 0
        while self._running:
            try:
                self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                self._sock.settimeout(4.0)
                self._sock.connect((self.host_ip, self.stream_port))
                logger.info(f"호스트 화면 스트림 연결 성공: {self.host_ip}:{self.stream_port}")
                break
            except Exception as e:
                retry_count += 1
                if retry_count > 10 or not self._running:
                    self.disconnected.emit(f"호스트 화면 연결 실패: {e}")
                    return
                time.sleep(1.0)

        fps_timer = time.time()
        frames_count = 0

        while self._running and self._sock:
            try:
                # 1. 헤더(4바이트 길이) 수신
                header = self._recv_exact(4)
                if not header:
                    break
                payload_len = struct.unpack(">I", header)[0]

                # 2. JPEG 데이터 수신
                jpeg_data = self._recv_exact(payload_len)
                if not jpeg_data:
                    break

                self.frame_ready.emit(jpeg_data)

                frames_count += 1
                if time.time() - fps_timer >= 1.0:
                    self.fps_updated.emit(frames_count)
                    frames_count = 0
                    fps_timer = time.time()

            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    logger.warning(f"스트림 수신 오류: {e}")
                break

        if self._running:
            self.disconnected.emit("호스트와의 화면 연결이 종료되었습니다.")

    def _recv_exact(self, num_bytes):
        data = bytearray()
        while len(data) < num_bytes and self._running:
            try:
                packet = self._sock.recv(num_bytes - len(data))
                if not packet:
                    return None
                data.extend(packet)
            except socket.timeout:
                continue
            except Exception:
                return None
        return bytes(data)

    def stop(self):
        self._running = False
        if self._sock:
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
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background-color: #05060a;")
        # 120 FPS 고주사율 무지연/무깜빡임 하드웨어 렌더링 최적화
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)

    def update_frame(self, jpeg_bytes):
        image = QImage()
        if image.loadFromData(jpeg_bytes, "JPEG"):
            self.current_pixmap = QPixmap.fromImage(image)
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#05060a"))

        if self.current_pixmap and not self.current_pixmap.isNull():
            # 비율 유지하며 화면 가득 채움
            scaled = self.current_pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation
            )
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
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

        # 120 FPS / 60 FPS 토글 버튼
        self.btn_fps_mode = QPushButton("⚡ 120 FPS (고주사율)")
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

    def _start_stream(self):
        self._receiver = StreamReceiverThread(self.host_ip, self.stream_port)
        self._receiver.frame_ready.connect(self.video_widget.update_frame)
        self._receiver.fps_updated.connect(lambda fps: self.lbl_fps.setText(f"FPS: {fps} | 딜레이: 초저지연 (<8ms)"))
        self._receiver.disconnected.connect(self._on_disconnected)
        self._receiver.start()

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

    # =========================================================
    # 키보드 입력 직접 캡처 -> 호스트 가상 패드로 UDP 송신
    # =========================================================
    def _key_to_name(self, key):
        mapping = {
            Qt.Key.Key_W: "W", Qt.Key.Key_Up: "Up",
            Qt.Key.Key_S: "S", Qt.Key.Key_Down: "Down",
            Qt.Key.Key_A: "A", Qt.Key.Key_Left: "Left",
            Qt.Key.Key_D: "D", Qt.Key.Key_Right: "Right",
            Qt.Key.Key_K: "K",  # 리시브 / 슬라이딩
            Qt.Key.Key_L: "L",  # 점프 / 스파이크
            Qt.Key.Key_I: "I",  # 블로킹
            Qt.Key.Key_J: "J",  # 특수기 / 토스
            Qt.Key.Key_Escape: "Escape",  # 일시정지
            Qt.Key.Key_Space: "Space",
        }
        return mapping.get(key)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_F11:
            self.toggle_fullscreen()
            return

        k_name = self._key_to_name(event.key())
        if k_name and self.guest_runner:
            self.guest_runner.send_key_input(k_name, True)
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent):
        k_name = self._key_to_name(event.key())
        if k_name and self.guest_runner:
            self.guest_runner.send_key_input(k_name, False)
            return
        super().keyReleaseEvent(event)

    def closeEvent(self, event):
        if self._receiver:
            self._receiver.stop()
        event.accept()
