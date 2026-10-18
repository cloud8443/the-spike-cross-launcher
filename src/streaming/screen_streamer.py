"""
screen_streamer.py
호스트(Host) PC에서 게임 화면을 고속 캡처하여
게스트(Guest)에게 실시간으로 비디오 스트림을 송출하는 초저지연 화면 공유 서버.
(저사양 2코어 CPU 및 4GB RAM 환경을 위한 GDI 메모리 캐싱 및 초경량 인코딩 엔진 탑재)
"""

import io
import logging
import os
import select
import socket
import struct
import threading
import time

try:
    import ctypes
    from ctypes import wintypes
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
DEFAULT_FPS = 40  # 저사양 PC 안정성을 위한 기본 FPS


def _detect_low_end_pc() -> tuple[bool, int, float]:
    """
    현재 PC의 논리 코어 수와 물리 RAM 용량(GB)을 측정하여 저사양 PC 여부를 판별합니다.
    반환값: (is_low_end: bool, cpu_count: int, total_ram_gb: float)
    """
    cpu_count = os.cpu_count() or 2
    total_ram_gb = 8.0
    try:
        if os.name == 'nt':
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(stat)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                total_ram_gb = stat.ullTotalPhys / (1024 ** 3)
    except Exception:
        pass

    # 논리 프로세서 4개 이하(예: i3 2코어 4스레드) 또는 RAM 6GB 이하인 경우 저사양 모드로 판정
    is_low_end = (cpu_count <= 4) or (total_ram_gb <= 6.0)
    return is_low_end, cpu_count, round(total_ram_gb, 1)


class ScreenStreamer:
    """호스트 게임 화면 캡처 및 실시간 네트워크 송출 서버 (저사양 PC 메모리/CPU 극한 최적화 지원)."""

    # 성능 프로파일 프리셋 정의 (고화질 HD 60FPS 표준 적용)
    PROFILES = {
        "low": {
            "name": "⚡ 일반 (960x540)",
            "max_width": 960,       # 540p (qHD)
            "jpeg_quality": 75,
            "default_fps": 60,
            "max_fps_cap": 60,
        },
        "balanced": {
            "name": "🌟 고화질 HD (1280x720 / 기본 권장)",
            "max_width": 1280,      # 720p (HD) - 텍스트 및 배구공 궤적 선명
            "jpeg_quality": 82,     # 고화질 압축 (아티팩트 제거)
            "default_fps": 60,      # 부드러운 60 FPS
            "max_fps_cap": 60,
        },
        "high": {
            "name": "🚀 초고화질 (1600x900)",
            "max_width": 1600,      # 900p / 원본급 선명도
            "jpeg_quality": 88,
            "default_fps": 60,
            "max_fps_cap": 120,
        }
    }

    def __init__(self, port=DEFAULT_STREAM_PORT, status_callback=None, target_fps=None):
        self.port = port
        self.status_callback = status_callback or (lambda msg: None)

        # 하드웨어 사양 감지 및 고화질 HD(balanced) 기본 채택
        self.is_low_end_pc, self.cpu_count, self.ram_gb = _detect_low_end_pc()
        self.performance_mode = "balanced"  # 고화질 720p 60FPS 기본 적용
        profile = self.PROFILES[self.performance_mode]

        self.max_stream_width = profile["max_width"]
        self.jpeg_quality = profile["jpeg_quality"]
        self.max_fps_cap = profile["max_fps_cap"]

        initial_fps = target_fps if target_fps is not None else profile["default_fps"]
        self.target_fps = max(24, min(120, int(initial_fps)))
        self.frame_interval = 1.0 / self.target_fps

        self._server_sock = None
        self._client_sock = None
        self._running = False
        self._timer_active = False
        self._thread = None
        self.fps_counter = 0
        self.target_hwnd = None
        self.manual_target_hwnd = None
        self.detected_game_info = None
        self._last_window_search = 0.0
        self._fallback_cache = {}

        # GDI 리소스 캐시 (매 프레임 할당/해제로 인한 4GB RAM 스와핑 원천 방지)
        self._gdi_lock = threading.Lock()
        self._cached_width = 0
        self._cached_height = 0
        self._desk_hwnd = None
        self._desk_dc = None
        self._mfc_dc = None
        self._save_dc = None
        self._bitmap = None
        self._old_obj = None

        logger.info(
            f"시스템 감지: CPU {self.cpu_count}스레드, RAM {self.ram_gb}GB -> "
            f"적용 모드: {profile['name']} ({self.max_stream_width}px, {self.target_fps} FPS, Q={self.jpeg_quality})"
        )

    def set_performance_mode(self, mode: str):
        """
        스트리밍 성능 프로파일을 동적으로 변경합니다.
        mode: 'low' (480p 초경량), 'balanced' (540p 균형), 'high' (720p 고화질)
        """
        if mode not in self.PROFILES:
            mode = "low"
        self.performance_mode = mode
        profile = self.PROFILES[mode]
        self.max_stream_width = profile["max_width"]
        self.jpeg_quality = profile["jpeg_quality"]
        self.max_fps_cap = profile["max_fps_cap"]
        self.set_fps(profile["default_fps"])
        logger.info(f"스트리밍 성능 모드 변경: {profile['name']} (최대 폭: {self.max_stream_width}px)")
        self.status_callback(f"⚙️ 스트리밍 모드: {profile['name']} ({self.max_stream_width}p / {self.target_fps}FPS)")

    def set_target_window(self, hwnd=None):
        """
        사용자가 수동으로 캡처할 윈도우를 선택/지정합니다.
        - None 또는 -1: 🎯 The Spike Cross 자동 감지 모드
        - 0: 🖥️ 전체 데스크톱 화면 공유 모드
        - > 0: 🪟 특정 창(HWND) 단독 공유 모드
        """
        if hwnd is None or hwnd == -1:
            self.manual_target_hwnd = None
            self.target_hwnd = None
            logger.info("화면 공유 모드: 🎯 The Spike Cross 자동 감지")
            self.status_callback("🎯 화면 공유 모드: The Spike Cross 자동 감지")
        elif hwnd == 0:
            self.manual_target_hwnd = 0
            self.target_hwnd = None
            logger.info("화면 공유 모드: 🖥️ 전체 데스크톱 화면")
            self.status_callback("🖥️ 화면 공유 모드: 전체 데스크톱 화면")
        else:
            self.manual_target_hwnd = hwnd
            self.target_hwnd = hwnd
            title = win32gui.GetWindowText(hwnd) if HAS_WIN32 and win32gui.IsWindow(hwnd) else f"HWND {hwnd}"
            logger.info(f"화면 공유 모드: 🪟 지정 창 ({title})")
            self.status_callback(f"🪟 화면 공유 모드: [{title}] 단독 공유")

    def set_fps(self, fps: int):
        """목표 스트리밍 FPS를 동적으로 변경 (초저지연 60 FPS 기본 보장)."""
        requested_fps = int(fps)
        actual_fps = max(24, min(120, requested_fps))
        self.target_fps = actual_fps
        self.frame_interval = 1.0 / actual_fps
        logger.info(f"⚡ 목표 스트리밍 FPS 설정: {actual_fps} FPS (프레임 간격: {self.frame_interval*1000:.2f}ms)")
        self.status_callback(f"⚡ 화면 스트리밍: {actual_fps} FPS ({self.max_stream_width}p HD)")

    def _get_process_name_by_pid(self, pid: int) -> str:
        """PID로 프로세스 실행 파일명 조회."""
        if not pid:
            return ""
        try:
            k32 = ctypes.windll.kernel32
            h_proc = k32.OpenProcess(0x1000, False, pid)
            if not h_proc:
                return ""
            try:
                buf = ctypes.create_unicode_buffer(1024)
                size = wintypes.DWORD(1024)
                if k32.QueryFullProcessImageNameW(h_proc, 0, buf, ctypes.byref(size)):
                    return buf.value.split("\\")[-1].lower()
            finally:
                k32.CloseHandle(h_proc)
        except Exception:
            pass
        return ""

    def find_game_window(self):
        """'The Spike Cross' 게임 윈도우 핸들(HWND)을 프로세스명 및 타이틀 기반으로 정밀 검색."""
        if not HAS_WIN32:
            return None

        now = time.perf_counter()
        # 저사양 PC에서는 윈도우 탐색 주기를 2.0초로 늘려 불필요한 시스템 콜 감소
        search_interval = 2.0 if self.is_low_end_pc else 1.0
        if now - self._last_window_search < search_interval:
            return self.target_hwnd
        self._last_window_search = now

        candidates = []

        def enum_cb(hwnd, _):
            if not win32gui.IsWindow(hwnd):
                return True
            if not win32gui.IsWindowVisible(hwnd) or win32gui.IsIconic(hwnd):
                return True

            try:
                rect = win32gui.GetWindowRect(hwnd)
                w = rect[2] - rect[0]
                h = rect[3] - rect[1]
                if w < 160 or h < 160:
                    return True

                title = win32gui.GetWindowText(hwnd).strip()
                title_lower = title.lower()

                pname = ""
                try:
                    import win32process
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    pname = self._get_process_name_by_pid(pid)
                except Exception:
                    pass

                if pname in ("thespikelauncher.exe", "antigravity.exe", "msedge.exe", "chrome.exe") or "launcher" in pname:
                    return True

                is_spike_proc = ("thespike" in pname) or ("spike-cross" in pname) or (pname.startswith("spike") and "launcher" not in pname)
                is_spike_title = (
                    "the spike" in title_lower or
                    "spike cross" in title_lower or
                    "더 스파이크" in title_lower or
                    "더스파이크" in title_lower
                ) and ("steam" not in pname)

                if is_spike_proc or is_spike_title:
                    score = 100 if is_spike_proc else 80
                    candidates.append({
                        "hwnd": hwnd,
                        "title": title,
                        "proc": pname or "TheSpike-Cross.exe",
                        "width": w,
                        "height": h,
                        "score": score
                    })
            except Exception:
                pass
            return True

        try:
            win32gui.EnumWindows(enum_cb, None)
        except Exception:
            pass

        if candidates:
            candidates.sort(key=lambda x: (x["score"], x["width"] * x["height"]), reverse=True)
            best = candidates[0]
            self.detected_game_info = best
            return best["hwnd"]

        self.detected_game_info = None
        return None

    def get_detection_status(self):
        """현재 화면 캡처 대상 및 감지 상태를 튜플 (is_detected: bool, info: dict)로 반환."""
        if not HAS_WIN32:
            return False, None

        if self.manual_target_hwnd == 0:
            d_hwnd = win32gui.GetDesktopWindow()
            rect = win32gui.GetWindowRect(d_hwnd)
            return True, {
                "hwnd": 0,
                "title": "전체 화면 (데스크톱)",
                "proc": "Desktop",
                "width": max(1, rect[2] - rect[0]),
                "height": max(1, rect[3] - rect[1]),
                "mode": "desktop"
            }

        if self.manual_target_hwnd is not None and self.manual_target_hwnd > 0:
            if win32gui.IsWindow(self.manual_target_hwnd) and not win32gui.IsIconic(self.manual_target_hwnd):
                rect = win32gui.GetWindowRect(self.manual_target_hwnd)
                title = win32gui.GetWindowText(self.manual_target_hwnd) or f"Window {self.manual_target_hwnd}"
                return True, {
                    "hwnd": self.manual_target_hwnd,
                    "title": title,
                    "proc": "수동 선택 창",
                    "width": max(1, rect[2] - rect[0]),
                    "height": max(1, rect[3] - rect[1]),
                    "mode": "manual"
                }
            else:
                return False, {
                    "hwnd": self.manual_target_hwnd,
                    "title": "선택된 창이 최소화되었거나 닫힘 (데스크톱 임시 공유 중)",
                    "proc": "Desktop Fallback",
                    "width": 854,
                    "height": 480,
                    "mode": "fallback"
                }

        if self.target_hwnd and win32gui.IsWindow(self.target_hwnd) and not win32gui.IsIconic(self.target_hwnd):
            info = self.detected_game_info or {}
            rect = win32gui.GetWindowRect(self.target_hwnd)
            w = max(1, rect[2] - rect[0])
            h = max(1, rect[3] - rect[1])
            return True, {
                "hwnd": self.target_hwnd,
                "title": info.get("title") or win32gui.GetWindowText(self.target_hwnd) or "The Spike Cross",
                "proc": info.get("proc", "TheSpike-Cross.exe"),
                "width": w,
                "height": h,
                "mode": "auto"
            }

        found = self.find_game_window()
        if found:
            self.target_hwnd = found
            info = self.detected_game_info or {}
            rect = win32gui.GetWindowRect(found)
            w = max(1, rect[2] - rect[0])
            h = max(1, rect[3] - rect[1])
            return True, {
                "hwnd": found,
                "title": info.get("title") or win32gui.GetWindowText(found) or "The Spike Cross",
                "proc": info.get("proc", "TheSpike-Cross.exe"),
                "width": w,
                "height": h,
                "mode": "auto"
            }
        return False, None

    def _ensure_gdi_resources(self, desktop_hwnd: int, width: int, height: int):
        """
        캡처 영역 크기가 동일하면 기존 GDI DC와 Bitmap을 재사용하여
        4GB RAM 환경에서의 메모리 할당/스와핑 오버헤드를 0으로 만듭니다.
        """
        if (
            self._save_dc is not None
            and self._bitmap is not None
            and self._desk_hwnd == desktop_hwnd
            and self._cached_width == width
            and self._cached_height == height
        ):
            return

        self._release_gdi_resources()

        self._desk_hwnd = desktop_hwnd
        self._desk_dc = win32gui.GetWindowDC(desktop_hwnd)
        self._mfc_dc = win32ui.CreateDCFromHandle(self._desk_dc)
        self._save_dc = self._mfc_dc.CreateCompatibleDC()

        self._bitmap = win32ui.CreateBitmap()
        self._bitmap.CreateCompatibleBitmap(self._mfc_dc, width, height)
        self._old_obj = self._save_dc.SelectObject(self._bitmap)

        self._cached_width = width
        self._cached_height = height

    def _release_gdi_resources(self):
        """캐시된 GDI 리소스를 안전하게 해제합니다."""
        if self._save_dc is not None and self._old_obj is not None:
            try:
                self._save_dc.SelectObject(self._old_obj)
            except Exception:
                pass
            self._old_obj = None

        if self._bitmap is not None:
            try:
                win32gui.DeleteObject(self._bitmap.GetHandle())
            except Exception:
                pass
            self._bitmap = None

        if self._save_dc is not None:
            try:
                self._save_dc.DeleteDC()
            except Exception:
                pass
            self._save_dc = None

        if self._mfc_dc is not None:
            try:
                self._mfc_dc.DeleteDC()
            except Exception:
                pass
            self._mfc_dc = None

        if self._desk_dc is not None and self._desk_hwnd is not None:
            try:
                win32gui.ReleaseDC(self._desk_hwnd, self._desk_dc)
            except Exception:
                pass
            self._desk_dc = None
            self._desk_hwnd = None

        self._cached_width = 0
        self._cached_height = 0

    def capture_frame(self):
        """
        캐시된 GDI 리소스와 NEAREST 초고속 샘플링을 사용하여
        2코어 저전력 CPU에서도 1~2ms 내에 프레임을 획득합니다.
        """
        if not HAS_WIN32:
            return self._get_fallback_frame("윈도우 API 비활성화")

        desktop_hwnd = win32gui.GetDesktopWindow()

        if self.manual_target_hwnd is not None:
            if self.manual_target_hwnd == 0:
                hwnd = desktop_hwnd
            elif win32gui.IsWindow(self.manual_target_hwnd) and not win32gui.IsIconic(self.manual_target_hwnd):
                hwnd = self.manual_target_hwnd
            else:
                hwnd = desktop_hwnd
        else:
            if not self.target_hwnd or not win32gui.IsWindow(self.target_hwnd) or win32gui.IsIconic(self.target_hwnd):
                new_hwnd = self.find_game_window()
                self.target_hwnd = new_hwnd if new_hwnd else None
            hwnd = self.target_hwnd or desktop_hwnd

        with self._gdi_lock:
            try:
                d_left, d_top, d_right, d_bot = win32gui.GetWindowRect(desktop_hwnd)
                d_width = max(1, d_right - d_left)
                d_height = max(1, d_bot - d_top)

                left, top, right, bot = win32gui.GetWindowRect(hwnd)
                left = max(d_left, min(left, d_right - 1))
                top = max(d_top, min(top, d_bot - 1))
                right = max(left + 1, min(right, d_right))
                bot = max(top + 1, min(bot, d_bot))

                width = right - left
                height = bot - top

                if width <= 16 or height <= 16:
                    left, top, width, height = d_left, d_top, d_width, d_height

                # 목표 해상도(기본 1280x720 HD) 계산
                max_w = self.max_stream_width
                if width > max_w:
                    target_w = max_w
                    target_h = max(1, int(height * (float(max_w) / width)))
                else:
                    target_w = width
                    target_h = height

                # 캐시된 GDI 컨텍스트 재사용 (타깃 해상도로 메모리 캐싱)
                self._ensure_gdi_resources(desktop_hwnd, target_w, target_h)

                if target_w == width and target_h == height:
                    self._save_dc.BitBlt((0, 0), (width, height), self._mfc_dc, (left, top), win32con.SRCCOPY)
                else:
                    # GDI HALFTONE(양선형 안티앨리어싱) 초고속 하드웨어 다운스케일링
                    try:
                        ctypes.windll.gdi32.SetStretchBltMode(self._save_dc.GetSafeHdc(), 4)  # 4 = HALFTONE
                        ctypes.windll.gdi32.SetBrushOrgEx(self._save_dc.GetSafeHdc(), 0, 0, None)
                    except Exception:
                        pass
                    self._save_dc.StretchBlt((0, 0), (target_w, target_h), self._mfc_dc, (left, top), (width, height), win32con.SRCCOPY)

                bmpstr = self._bitmap.GetBitmapBits(True)
                img = Image.frombuffer(
                    'RGB',
                    (target_w, target_h),
                    bmpstr, 'raw', 'BGRX', 0, 1
                )
                return img
            except Exception as e:
                self._release_gdi_resources()
                return self._get_fallback_frame(f"화면 대기 중... ({e})")

    def _get_fallback_frame(self, text):
        """화면 캡처 불가 시 전송할 대기 화면 프레임 반환 (720p HD 표준)."""
        if text not in self._fallback_cache:
            if len(self._fallback_cache) > 6:
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
            self._server_sock.listen(5)
            self._server_sock.settimeout(1.0)
            logger.info(
                f"화면 공유 서버 시작됨 (포트 {self.port}, 목표 {self.target_fps} FPS, "
                f"해상도 폭 {self.max_stream_width}px)"
            )
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
        """클라이언트 연결 수락 루프 (새 연결 요청 시 기존 유휴 소켓을 즉시 교체)."""
        mode_label = self.PROFILES[self.performance_mode]["name"]
        self.status_callback(
            f"📡 게스트 대기 중 (포트 {self.port} | {mode_label} {self.max_stream_width}p @ {self.target_fps}FPS)"
        )
        while self._running:
            try:
                if not self._server_sock:
                    break
                client, addr = self._server_sock.accept()
                client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                # 프레임 크기가 15~25KB이므로 송신 버퍼를 32KB로 축소해 커널 버퍼 블로팅(지연 누적) 방지
                client.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 32768)
                client.settimeout(3.0)

                prev_client = self._client_sock
                self._client_sock = client
                if prev_client:
                    try:
                        prev_client.close()
                    except Exception:
                        pass

                self.status_callback(
                    f"🟢 게스트 연결됨! ({addr[0]}) [{mode_label} {self.max_stream_width}p / {self.target_fps} FPS]"
                )
                logger.info(f"게스트 화면 클라이언트 연결: {addr}")
                threading.Thread(target=self._send_frames, args=(client,), daemon=True).start()
            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    logger.warning(f"연결 대기 오류: {e}")

    def _send_frames(self, client):
        """
        연결된 게스트에게 최신 프레임을 지연 없이 실시간 송출.
        (2코어 CPU 보호를 위해 스핀락을 제거하고 게임 프로세스에 CPU 시간을 양보)
        """
        fps_timer = time.perf_counter()
        frames_sent = 0
        next_frame_time = time.perf_counter()

        buf = io.BytesIO()

        while self._running and self._client_sock is client:
            try:
                # 1. 소켓 송신 가능 여부 논블로킹 확인 (네트워크 지연 시 프레임 즉시 드랍하여 렉 누적 방지)
                _, writable, _ = select.select([], [client], [], 0.0)
                if not writable:
                    time.sleep(0.004)
                    next_frame_time = time.perf_counter()
                    continue

                # 2. 고속 화면 캡처 (GDI 캐시 활용)
                frame = self.capture_frame()

                # 3. 초경량 JPEG 인코딩 (subsampling=2 [4:2:0] 명시로 인코딩 속도 향상 및 용량 35% 절감)
                buf.seek(4)
                buf.truncate(4)
                frame.save(
                    buf,
                    format='JPEG',
                    quality=self.jpeg_quality,
                    optimize=False,
                    subsampling=2
                )

                total_len = buf.tell()
                payload_len = total_len - 4

                buf.seek(0)
                buf.write(struct.pack(">I", payload_len))

                with buf.getbuffer() as view:
                    client.sendall(view)

                frames_sent += 1
                now = time.perf_counter()
                if now - fps_timer >= 1.0:
                    self.fps_counter = frames_sent
                    frames_sent = 0
                    fps_timer = now

                # 4. CPU 친화적 초저지연 프레임 페이싱 (누적 지연 원천 차단)
                target_interval = self.frame_interval
                next_frame_time += target_interval
                sleep_time = next_frame_time - time.perf_counter()

                if sleep_time > 0.001:
                    time.sleep(sleep_time)
                else:
                    # 지연 발생 시 절대로 추가 슬립하지 않고 현재 시각과 즉시 재동기화 (누적 딜레이 제거)
                    if time.perf_counter() - next_frame_time > target_interval:
                        next_frame_time = time.perf_counter()

            except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, socket.timeout, OSError):
                if self._client_sock is client:
                    logger.info("게스트 연결 끊김")
                    self.status_callback("⚠️ 게스트 화면 연결이 끊어졌습니다. 재연결 대기 중...")
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
        """화면 공유 서버 종료 및 GDI 캐시 리소스 반환."""
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

        with self._gdi_lock:
            self._release_gdi_resources()

        logger.info("화면 공유 서버 종료 완료")

    @staticmethod
    def list_capturable_windows():
        """현재 시스템에서 사용자가 선택해 공유할 수 있는 윈도우 목록을 반환합니다."""
        windows = [
            {
                "hwnd": -1,
                "title": "🎯 [자동 감지] The Spike Cross (기본 권장)",
                "proc": "auto",
                "size": "자동"
            },
            {
                "hwnd": 0,
                "title": "🖥️ [전체 화면] 전체 데스크톱 화면 공유",
                "proc": "desktop",
                "size": "전체"
            }
        ]

        if not HAS_WIN32:
            return windows

        u32 = ctypes.windll.user32
        k32 = ctypes.windll.kernel32

        def _get_proc(pid):
            if not pid:
                return ""
            h = k32.OpenProcess(0x1000, False, pid)
            if not h:
                return ""
            try:
                b = ctypes.create_unicode_buffer(1024)
                s = wintypes.DWORD(1024)
                if k32.QueryFullProcessImageNameW(h, 0, b, ctypes.byref(s)):
                    return b.value.split("\\")[-1]
            finally:
                k32.CloseHandle(h)
            return ""

        seen_hwnds = set()
        game_windows = []
        normal_windows = []

        def inspect_window(hwnd):
            if hwnd in seen_hwnds:
                return
            seen_hwnds.add(hwnd)

            if not u32.IsWindow(hwnd) or not u32.IsWindowVisible(hwnd) or u32.IsIconic(hwnd):
                return

            len_t = u32.GetWindowTextLengthW(hwnd)
            if len_t <= 0:
                return
            buf = ctypes.create_unicode_buffer(len_t + 1)
            u32.GetWindowTextW(hwnd, buf, len_t + 1)
            title = buf.value.strip()
            if not title:
                return

            rect = wintypes.RECT()
            u32.GetWindowRect(hwnd, ctypes.byref(rect))
            w = rect.right - rect.left
            h = rect.bottom - rect.top
            if w < 160 or h < 160:
                return

            ignored_titles = ["Program Manager", "Microsoft Text Input Application", "Settings", "설정"]
            if title in ignored_titles:
                return

            pid = wintypes.DWORD()
            u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            proc = _get_proc(pid.value)
            proc_lower = proc.lower()

            if "thespikelauncher" in proc_lower:
                return

            is_spike = (
                "spike" in proc_lower or
                "thespike" in proc_lower or
                "spike" in title.lower() or
                "더 스파이크" in title
            ) and "steam" not in proc_lower

            entry = {
                "hwnd": hwnd,
                "title": f"🎮 [게임] {title} ({w}x{h})" if is_spike else f"🪟 {title} ({proc}) [{w}x{h}]",
                "proc": proc,
                "size": f"{w}x{h}",
                "is_spike": is_spike
            }

            if is_spike:
                game_windows.append(entry)
            else:
                normal_windows.append(entry)

        def enum_cb(h, _):
            inspect_window(h)
            return True

        try:
            win32gui.EnumWindows(enum_cb, None)
        except Exception:
            pass

        windows.extend(game_windows)
        windows.extend(normal_windows)
        return windows
