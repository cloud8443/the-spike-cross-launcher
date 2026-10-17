"""
screen_streamer.py
호스트(Host) PC에서 게임 화면을 고속 캡처하여
게스트(Guest)에게 실시간(최대 120 FPS)으로 비디오 스트림을 송출하는 초저지연 화면 공유 서버.
"""

import io
import logging
import socket
import struct
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

from PIL import Image, ImageDraw

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
        self._timer_active = False
        self._thread = None
        self.fps_counter = 0
        self.target_hwnd = None
        self._last_window_search = 0.0
        self._fallback_cache = {}

    def set_fps(self, fps: int):
        """목표 스트리밍 FPS를 동적으로 변경 (예: 60 또는 120)."""
        fps = max(30, min(144, int(fps)))
        self.target_fps = fps
        self.frame_interval = 1.0 / fps
        logger.info(f"⚡ 목표 스트리밍 FPS 변경: {fps} FPS (프레임 간격: {self.frame_interval*1000:.2f}ms)")
        self.status_callback(f"⚡ 화면 스트리밍 FPS가 {fps} FPS로 변경되었습니다.")

    def find_game_window(self):
        """'The Spike' 게임 윈도우 핸들(HWND)을 검색 (1초 쿨다운으로 오버헤드 방지)."""
        if not HAS_WIN32:
            return None

        now = time.perf_counter()
        if now - self._last_window_search < 1.0:
            return None
        self._last_window_search = now

        found_hwnd = None

        def enum_cb(hwnd, _):
            nonlocal found_hwnd
            if win32gui.IsWindowVisible(hwnd) and not win32gui.IsIconic(hwnd):
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
        GDI 핸들 누수 방지를 위해 엄격한 try-finally 블록 적용.
        """
        if not HAS_WIN32:
            return self._get_fallback_frame("윈도우 API 비활성화")

        # 유효한 게임 윈도우 확인 (최소화 상태이거나 닫혔으면 재탐색)
        if not self.target_hwnd or not win32gui.IsWindow(self.target_hwnd) or win32gui.IsIconic(self.target_hwnd):
            self.target_hwnd = self.find_game_window()

        hwnd = self.target_hwnd or win32gui.GetDesktopWindow()

        hwnd_dc = None
        mfc_dc = None
        save_dc = None
        bitmap = None
        old_obj = None

        try:
            left, top, right, bot = win32gui.GetWindowRect(hwnd)
            width = right - left
            height = bot - top

            if width <= 0 or height <= 0:
                hwnd = win32gui.GetDesktopWindow()
                left, top, right, bot = win32gui.GetWindowRect(hwnd)
                width = max(1, right - left)
                height = max(1, bot - top)

            hwnd_dc = win32gui.GetWindowDC(hwnd)
            mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
            save_dc = mfc_dc.CreateCompatibleDC()

            bitmap = win32ui.CreateBitmap()
            bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
            old_obj = save_dc.SelectObject(bitmap)

            # 고속 화면 복사 (BitBlt)
            save_dc.BitBlt((0, 0), (width, height), mfc_dc, (0, 0), win32con.SRCCOPY)

            bmpinfo = bitmap.GetInfo()
            bmpstr = bitmap.GetBitmapBits(True)
            img = Image.frombuffer(
                'RGB',
                (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
                bmpstr, 'raw', 'BGRX', 0, 1
            )

            # 해상도 최적화 (1280x720 이상일 경우 가로 1280 기준으로 리사이즈하여 전송 지연 극소화)
            if width > 1280:
                new_h = max(1, int(height * (1280.0 / width)))
                img = img.resize((1280, new_h), Image.Resampling.BILINEAR)

            return img
        except Exception as e:
            return self._get_fallback_frame(f"화면 대기 중... ({e})")
        finally:
            # GDI 리소스 역순 완벽 해제 (핸들 누수 원천 차단)
            if save_dc is not None and old_obj is not None:
                try:
                    save_dc.SelectObject(old_obj)
                except Exception:
                    pass
            if bitmap is not None:
                try:
                    win32gui.DeleteObject(bitmap.GetHandle())
                except Exception:
                    pass
            if save_dc is not None:
                try:
                    save_dc.DeleteDC()
                except Exception:
                    pass
            if mfc_dc is not None:
                try:
                    mfc_dc.DeleteDC()
                except Exception:
                    pass
            if hwnd_dc is not None:
                try:
                    win32gui.ReleaseDC(hwnd, hwnd_dc)
                except Exception:
                    pass

    def _get_fallback_frame(self, text):
        """화면 캡처 불가 시 전송할 대기 화면 프레임 반환 (캐싱 적용)."""
        if text not in self._fallback_cache:
            if len(self._fallback_cache) > 10:
                self._fallback_cache.clear()
            img = Image.new('RGB', (1280, 720), color=(15, 17, 30))
            draw = ImageDraw.Draw(img)
            draw.text((450, 320), "The Spike Cross - 원격 화면 대기 중", fill=(255, 255, 255))
            draw.text((450, 360), text, fill=(150, 160, 180))
            self._fallback_cache[text] = img
        return self._fallback_cache[text]

    def start_streaming(self):
        """화면 공유 서버를 백그라운드 스레드로 시작."""
        if self._running:
            return True

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
            if self._server_sock:
                try:
                    self._server_sock.close()
                except Exception:
                    pass
                self._server_sock = None
            return False

        self._running = True

        # Windows 멀티미디어 1ms 고정밀 타이머 활성화 (소켓 바인딩 성공 후 활성화)
        if HAS_WINMM and not self._timer_active:
            try:
                winmm.timeBeginPeriod(1)
                self._timer_active = True
            except Exception:
                pass

        self._thread = threading.Thread(target=self._stream_loop, daemon=True)
        self._thread.start()
        return True

    def _stream_loop(self):
        """클라이언트 연결 대기 및 고주사율 프레임 송출 루프."""
        self.status_callback(f"📡 게스트 화면 연결 대기 중 (포트 {self.port}, 최대 {self.target_fps} FPS)...")
        while self._running:
            try:
                if not self._server_sock:
                    break
                client, addr = self._server_sock.accept()
                client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                client.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 262144)  # 256KB 버퍼
                client.settimeout(5.0)
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
        """연결된 게스트에게 프레임을 실시간으로 연속 송출 (단일 버퍼 재사용 최적화)."""
        fps_timer = time.perf_counter()
        frames_sent = 0
        next_frame_time = time.perf_counter()

        # 단일 BytesIO 버퍼 재사용으로 120 FPS 메모리 재할당 및 복사 방지
        buf = io.BytesIO()

        while self._running:
            try:
                frame = self.capture_frame()

                # 앞 4바이트는 길이 헤더 공간으로 비워두고 JPEG 인코딩 수행
                buf.seek(4)
                buf.truncate(4)
                frame.save(buf, format='JPEG', quality=70)

                total_len = buf.tell()
                payload_len = total_len - 4

                # 앞 4바이트 위치에 페이로드 길이 기록
                buf.seek(0)
                buf.write(struct.pack(">I", payload_len))

                # memoryview를 사용해 추가 메모리 복사 없이 즉시 전송
                with buf.getbuffer() as view:
                    client.sendall(view)

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

            except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, socket.timeout):
                logger.info("게스트 연결 끊김")
                self.status_callback("⚠️ 게스트 화면 연결이 끊어졌습니다.")
                break
            except Exception as e:
                logger.debug(f"프레임 전송 예외: {e}")
                break

        try:
            client.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        try:
            client.close()
        except Exception:
            pass
        if self._client_sock is client:
            self._client_sock = None

    def stop_streaming(self):
        """화면 공유 서버 종료."""
        self._running = False
        if HAS_WINMM and self._timer_active:
            try:
                winmm.timeEndPeriod(1)
            except Exception:
                pass
            self._timer_active = False

        if self._client_sock:
            try:
                self._client_sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
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
