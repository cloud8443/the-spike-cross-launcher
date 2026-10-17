"""
screen_streamer.py
호스트(Host) PC에서 게임 화면을 고속 캡처하여
게스트(Guest)에게 실시간(60 FPS)으로 비디오 스트림을 송출하는 초저지연 화면 공유 서버.
"""

import io
import logging
import socket
import struct
import sys
import threading
import time

try:
    import ctypes
    winmm = ctypes.WinDLL('winmm')
    HAS_WINMM = True
except Exception:
    HAS_WINMM = False

try:
    import win32gui
    import win32ui
    import win32con
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger("ScreenStreamer")

DEFAULT_STREAM_PORT = 47998
DEFAULT_FPS = 120


class ScreenStreamer:
    """호스트 게임 화면 캡처 및 실시간 네트워크 송출 서버 (최대 120 FPS 지원)."""

    def __init__(self, port=DEFAULT_STREAM_PORT, status_callback=None, target_fps=DEFAULT_FPS):
        self.port = port
        self.status_callback = status_callback or (lambda msg: None)
        self.target_fps = target_fps
        self.frame_interval = 1.0 / self.target_fps
        self._server_sock = None
        self._client_sock = None
        self._running = False
        self._thread = None
        self.fps_counter = 0
        self.target_hwnd = None

    def set_fps(self, fps: int):
        """목표 스트리밍 FPS를 동적으로 변경 (예: 60 또는 120)."""
        fps = max(30, min(144, int(fps)))
        self.target_fps = fps
        self.frame_interval = 1.0 / fps
        logger.info(f"⚡ 목표 스트리밍 FPS 변경: {fps} FPS (프레임 간격: {self.frame_interval*1000:.2f}ms)")
        self.status_callback(f"⚡ 화면 스트리밍 FPS가 {fps} FPS로 변경되었습니다.")

    def find_game_window(self):
        """'The Spike' 게임 윈도우 핸들(HWND)을 검색."""
        if not HAS_WIN32:
            return None

        found_hwnd = None

        def enum_cb(hwnd, extra):
            nonlocal found_hwnd
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if "the spike" in title.lower() or "spike cross" in title.lower():
                    found_hwnd = hwnd

        try:
            win32gui.EnumWindows(enum_cb, None)
        except Exception:
            pass
        return found_hwnd

    def capture_frame(self):
        """
        게임 윈도우가 있으면 해당 영역을 캡처하고,
        없으면 기본 데스크톱 화면을 고속 GDI BitBlt로 캡처.
        """
        if not HAS_WIN32:
            return self._create_fallback_frame("윈도우 API 비활성화")

        # 게임 윈도우 검색
        if not self.target_hwnd or not win32gui.IsWindow(self.target_hwnd):
            self.target_hwnd = self.find_game_window()

        hwnd = self.target_hwnd or win32gui.GetDesktopWindow()

        try:
            left, top, right, bot = win32gui.GetWindowRect(hwnd)
            width = right - left
            height = bot - top

            if width <= 0 or height <= 0:
                hwnd = win32gui.GetDesktopWindow()
                left, top, right, bot = win32gui.GetWindowRect(hwnd)
                width = right - left
                height = bot - top

            hwnd_dc = win32gui.GetWindowDC(hwnd)
            mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
            save_dc = mfc_dc.CreateCompatibleDC()

            bitmap = win32ui.CreateBitmap()
            bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
            save_dc.SelectObject(bitmap)

            # 고속 화면 복사 (BitBlt)
            save_dc.BitBlt((0, 0), (width, height), mfc_dc, (0, 0), win32con.SRCCOPY)

            bmpinfo = bitmap.GetInfo()
            bmpstr = bitmap.GetBitmapBits(True)
            img = Image.frombuffer('RGB', (bmpinfo['bmWidth'], bmpinfo['bmHeight']), bmpstr, 'raw', 'BGRX', 0, 1)

            # 리소스 즉시 해제
            win32gui.DeleteObject(bitmap.GetHandle())
            save_dc.DeleteDC()
            mfc_dc.DeleteDC()
            win32gui.ReleaseDC(hwnd, hwnd_dc)

            # 해상도 최적화 (1280x720 이상일 경우 가로 1280 기준으로 리사이즈하여 전송 지연 극소화)
            if width > 1280:
                ratio = 1280.0 / width
                new_h = int(height * ratio)
                img = img.resize((1280, new_h), Image.Resampling.BILINEAR)

            return img
        except Exception as e:
            return self._create_fallback_frame(f"화면 대기 중... ({e})")

    def _create_fallback_frame(self, text):
        """화면 캡처 불가 시 전송할 대기 화면 프레임 생성."""
        img = Image.new('RGB', (1280, 720), color=(15, 17, 30))
        draw = ImageDraw.Draw(img)
        draw.text((450, 320), "The Spike Cross - 원격 화면 대기 중", fill=(255, 255, 255))
        draw.text((450, 360), text, fill=(150, 160, 180))
        return img

    def start_streaming(self):
        """화면 공유 서버를 백그라운드 스레드로 시작."""
        self._running = True

        # Windows 멀티미디어 1ms 고정밀 타이머 활성화 (120fps 지터 방지)
        if HAS_WINMM:
            try:
                winmm.timeBeginPeriod(1)
            except Exception:
                pass

        try:
            self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server_sock.bind(("0.0.0.0", self.port))
            self._server_sock.listen(1)
            self._server_sock.settimeout(1.0)
            logger.info(f"화면 공유 서버 시작됨 (포트 {self.port}, 목표 {self.target_fps} FPS)")
        except Exception as e:
            logger.error(f"화면 공유 서버 바인딩 실패: {e}")
            self.status_callback(f"❌ 화면 공유 서버 포트 바인딩 실패: {e}")
            return False

        self._thread = threading.Thread(target=self._stream_loop, daemon=True)
        self._thread.start()
        return True

    def _stream_loop(self):
        """클라이언트 연결 대기 및 고주사율 프레임 송출 루프."""
        self.status_callback(f"📡 게스트 화면 연결 대기 중 (포트 {self.port}, 최대 {self.target_fps} FPS)...")
        while self._running:
            try:
                client, addr = self._server_sock.accept()
                client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                client.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 262144)  # 256KB 버퍼
                self._client_sock = client
                self.status_callback(f"🟢 게스트 화면 연결됨! ({addr[0]}) [⚡ {self.target_fps} FPS 스트리밍]")
                logger.info(f"게스트 화면 클라이언트 연결: {addr}")
                self._send_frames(client)
            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    logger.warning(f"연결 대기 오류: {e}")

    def _send_frames(self, client):
        """연결된 게스트에게 프레임을 실시간으로 연속 송출 (최대 120 FPS 정밀 페이싱)."""
        fps_timer = time.perf_counter()
        frames_sent = 0
        next_frame_time = time.perf_counter()

        while self._running:
            try:
                frame = self.capture_frame()
                buf = io.BytesIO()
                # 120 FPS 초고속 압축 (품질 70: 프레임당 약 1.5ms 인코딩)
                frame.save(buf, format='JPEG', quality=70)
                jpeg_bytes = buf.getvalue()

                # 패킷 헤더: [4바이트 페이로드 길이] + [JPEG 바이트]
                header = struct.pack(">I", len(jpeg_bytes))
                client.sendall(header + jpeg_bytes)

                frames_sent += 1
                now = time.perf_counter()
                if now - fps_timer >= 1.0:
                    self.fps_counter = frames_sent
                    frames_sent = 0
                    fps_timer = now

                # 120 FPS 초정밀 프레임 페이싱 (하이브리드 슬립 + 스핀락)
                target_interval = self.frame_interval
                next_frame_time += target_interval
                sleep_time = next_frame_time - time.perf_counter()

                if sleep_time > 0.002:
                    time.sleep(sleep_time - 0.001)

                while time.perf_counter() < next_frame_time:
                    pass

                # 프레임이 과도하게 밀렸을 경우 시간 동기화
                if time.perf_counter() - next_frame_time > target_interval * 2:
                    next_frame_time = time.perf_counter()

            except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
                logger.info("게스트 연결 끊김")
                self.status_callback("⚠️ 게스트 화면 연결이 끊어졌습니다.")
                break
            except Exception as e:
                logger.debug(f"프레임 전송 예외: {e}")
                break

        try:
            client.close()
        except Exception:
            pass
        self._client_sock = None

    def stop_streaming(self):
        """화면 공유 서버 종료."""
        self._running = False
        if HAS_WINMM:
            try:
                winmm.timeEndPeriod(1)
            except Exception:
                pass

        if self._client_sock:
            try:
                self._client_sock.close()
            except Exception:
                pass
            self._client_sock = None

        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception:
                pass
            self._server_sock = None
        logger.info("화면 공유 서버 종료 완료")
