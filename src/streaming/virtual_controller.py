"""
virtual_controller.py
호스트 PC에서 ViGEmBus 가상 Xbox 360 패드를 생성하고,
게스트 입력 패킷을 2P 컨트롤러에 실시간 주입하는 모듈.
- ViGEmBus 미설치 시 공식 드라이버 원클릭 자동 다운로드/설치 지원
- 드라이버 설치 불가/거부 시에도 세션이 중단되지 않도록 Win32 Hardware ScanCode(DirectInput) 키보드 폴백 지원
"""

import ctypes
from ctypes import wintypes
import json
import logging
import os
import sys
import tempfile
import threading
import time
import urllib.request

logger = logging.getLogger("VirtualController")

VIGEMBUS_INSTALLER_URL = (
    "https://github.com/nefarius/ViGEmBus/releases/download/v1.22.0/"
    "ViGEmBus_1.22.0_x64_x86_arm64.exe"
)


def resource_path(relative_path):
    """PyInstaller 번들 / 개발 환경 양쪽에서 리소스 경로를 올바르게 반환."""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


ACTION_TO_XBOX = {
    "UP":            "DPAD_UP",
    "DOWN":          "DPAD_DOWN",
    "LEFT":          "DPAD_LEFT",
    "RIGHT":         "DPAD_RIGHT",
    "RECEIVE_SLIDE": "X",
    "JUMP_SPIKE":    "A",
    "BLOCK":         "B",
    "SPECIAL_TOSS":  "Y",
    "PAUSE":         "START",
}

FALLBACK_KEY_TO_XBOX = {
    "UP":    "DPAD_UP",
    "DOWN":  "DPAD_DOWN",
    "LEFT":  "DPAD_LEFT",
    "RIGHT": "DPAD_RIGHT",
}


class ViGEmBusInstaller:
    """ViGEmBus 드라이버 자동 다운로드 및 설치 헬퍼."""

    @staticmethod
    def download_and_install(status_callback=None) -> bool:
        """
        공식 ViGEmBus 설치 파일을 다운로드하고 관리자 권한(runas)으로 실행합니다.
        설치 프로세스가 종료될 때까지 대기 후 성공 여부를 반환합니다.
        """
        if sys.platform != "win32":
            return False

        cb = status_callback or (lambda msg: None)
        try:
            # 1. 번들된 로컬 설치 파일이 있는지 먼저 확인
            bundled_path = resource_path(os.path.join("tools", "ViGEmBus_Setup.exe"))
            if os.path.exists(bundled_path):
                installer_path = bundled_path
            else:
                installer_path = os.path.join(tempfile.gettempdir(), "ViGEmBus_1.22.0_Setup.exe")
                if not os.path.exists(installer_path) or os.path.getsize(installer_path) < 1_000_000:
                    cb("📥 ViGEmBus 공식 드라이버를 다운로드하는 중...")
                    urllib.request.urlretrieve(VIGEMBUS_INSTALLER_URL, installer_path)

            cb("🛡️ 관리자 권한으로 ViGEmBus 드라이버 설치를 시작합니다. (권한 승인 창이 뜨면 '예'를 눌러주세요)")

            # ShellExecuteExW를 사용하여 관리자 권한(runas) 실행 및 프로세스 종료 대기
            SEE_MASK_NOCLOSEPROCESS = 0x00000040
            SW_SHOWNORMAL = 1

            class SHELLEXECUTEINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.DWORD),
                    ("fMask", wintypes.ULONG),
                    ("hwnd", wintypes.HWND),
                    ("lpVerb", wintypes.LPCWSTR),
                    ("lpFile", wintypes.LPCWSTR),
                    ("lpParameters", wintypes.LPCWSTR),
                    ("lpDirectory", wintypes.LPCWSTR),
                    ("nShow", ctypes.c_int),
                    ("hInstApp", wintypes.HINSTANCE),
                    ("lpIDList", ctypes.c_void_p),
                    ("lpClass", wintypes.LPCWSTR),
                    ("hkeyClass", wintypes.HKEY),
                    ("dwHotKey", wintypes.DWORD),
                    ("hIconOrMonitor", wintypes.HANDLE),
                    ("hProcess", wintypes.HANDLE),
                ]

            sei = SHELLEXECUTEINFO()
            sei.cbSize = ctypes.sizeof(sei)
            sei.fMask = SEE_MASK_NOCLOSEPROCESS
            sei.lpVerb = "runas"
            sei.lpFile = installer_path
            sei.lpParameters = "/passive /norestart"
            sei.nShow = SW_SHOWNORMAL

            if not ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(sei)):
                cb("⚠️ 드라이버 설치 권한 요청이 취소되었거나 실패했습니다.")
                return False

            if sei.hProcess:
                INFINITE = 0xFFFFFFFF
                ctypes.windll.kernel32.WaitForSingleObject(sei.hProcess, INFINITE)
                ctypes.windll.kernel32.CloseHandle(sei.hProcess)

            # 드라이버 버스 서비스가 올라올 시간을 잠시 대기
            time.sleep(1.5)
            cb("✅ ViGEmBus 드라이버 설치 프로세스가 완료되었습니다.")
            return True

        except Exception as e:
            logger.warning(f"ViGEmBus 자동 설치 중 오류: {e}")
            cb(f"⚠️ 자동 설치 오류: {e}")
            return False


class Win32KeyboardFallback:
    """
    ViGEmBus 드라이버가 없을 때 Windows SendInput(DirectInput 하드웨어 스캔코드)을 통해
    Xbox 버튼 입력을 2P 키보드 키로 에뮬레이션하는 폴백 엔진.
    """

    # DirectInput / 게임 엔진 호환 하드웨어 스캔코드 및 Virtual-Key 매핑
    # (VK, ScanCode, IsExtendedKey)
    XBOX_TO_KEYCODE = {
        "DPAD_UP":    (0x26, 0x48, True),   # Up Arrow
        "DPAD_DOWN":  (0x28, 0x50, True),   # Down Arrow
        "DPAD_LEFT":  (0x25, 0x4B, True),   # Left Arrow
        "DPAD_RIGHT": (0x27, 0x4D, True),   # Right Arrow
        "A":          (0x4C, 0x26, False),  # 'L' (스파이크)
        "X":          (0x4B, 0x25, False),  # 'K' (리시브)
        "B":          (0x49, 0x17, False),  # 'I' (블로킹)
        "Y":          (0x4A, 0x24, False),  # 'J' (슬라이딩)
        "START":      (0x1B, 0x01, False),  # Escape (일시정지)
    }

    def __init__(self):
        self._supported = (sys.platform == "win32")

    def send_button(self, xbox_button_name: str, is_pressed: bool):
        if not self._supported:
            return
        mapping = self.XBOX_TO_KEYCODE.get(xbox_button_name)
        if not mapping:
            return
        vk, scan, is_ext = mapping
        self._send_key_scancode(vk, scan, is_ext, is_pressed)

    def _send_key_scancode(self, vk: int, scan: int, is_extended: bool, is_pressed: bool):
        try:
            KEYEVENTF_EXTENDEDKEY = 0x0001
            KEYEVENTF_KEYUP = 0x0002
            KEYEVENTF_SCANCODE = 0x0008

            flags = KEYEVENTF_SCANCODE
            if is_extended:
                flags |= KEYEVENTF_EXTENDEDKEY
            if not is_pressed:
                flags |= KEYEVENTF_KEYUP

            ctypes.windll.user32.keybd_event(vk, scan, flags, 0)
        except Exception as e:
            logger.debug(f"Win32 키보드 폴백 입력 오류: {e}")


class KeymapManager:
    """keymap.json 로드/저장 및 키 -> Xbox 버튼 변환을 담당."""

    DEFAULT_MAP = {
        "UP": "W",
        "DOWN": "S",
        "LEFT": "A",
        "RIGHT": "D",
        "RECEIVE_SLIDE": "K",
        "JUMP_SPIKE": "L",
        "BLOCK": "I",
        "SPECIAL_TOSS": "J",
        "PAUSE": "Escape",
    }

    def __init__(self, config_path=None):
        if config_path is None:
            config_path = resource_path(os.path.join("config", "keymap.json"))
        self.config_path = config_path
        self.action_map = dict(self.DEFAULT_MAP)
        self._key_to_xbox = {}
        self.load()

    def load(self):
        """설정 파일에서 키 매핑을 로드."""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for action in self.DEFAULT_MAP:
                    if action in data and isinstance(data[action], str):
                        self.action_map[action] = data[action]
        except Exception as e:
            logger.warning(f"keymap.json 로드 실패, 기본값 사용: {e}")
        self._rebuild_reverse_map()

    def save(self):
        """현재 매핑을 설정 파일에 저장."""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.action_map, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"keymap.json 저장 실패: {e}")

    def _rebuild_reverse_map(self):
        """keyboard key -> xbox button name 역방향 매핑 재구축."""
        self._key_to_xbox = dict(FALLBACK_KEY_TO_XBOX)
        for action, key in self.action_map.items():
            xbox_btn = ACTION_TO_XBOX.get(action)
            if xbox_btn and key:
                self._key_to_xbox[key.upper()] = xbox_btn

    def key_to_xbox_button(self, key_name):
        """키보드 키 이름을 Xbox 버튼 이름으로 변환. 매핑에 없으면 None."""
        if not key_name:
            return None
        return self._key_to_xbox.get(key_name.upper())

    def set_mapping(self, action, key):
        """특정 액션의 키 매핑을 변경."""
        if action in self.action_map:
            self.action_map[action] = key
            self._rebuild_reverse_map()

    def get_display_name(self, action):
        """사용자에게 보여줄 액션 한국어 이름."""
        names = {
            "UP": "↑ 위로 이동",
            "DOWN": "↓ 아래 이동",
            "LEFT": "← 좌측 이동",
            "RIGHT": "→ 우측 이동",
            "RECEIVE_SLIDE": "🏐 리시브 / 슬라이딩",
            "JUMP_SPIKE": "⬆️ 점프 / 스파이크",
            "BLOCK": "🛡️ 블로킹",
            "SPECIAL_TOSS": "⭐ 특수기 / 토스",
            "PAUSE": "⏸️ 일시정지",
        }
        return names.get(action, action)


class VirtualGamepadManager:
    """
    ViGEmBus 가상 Xbox 360 패드를 스레드 안전하게 관리하며,
    ViGEmBus 미설치 시 Win32 키보드 에뮬레이션 모드로 자동 폴백합니다.
    """

    def __init__(self):
        self.gamepad = None
        self._vgamepad = None
        self._button_map = {}
        self._pressed_buttons = set()
        self._lock = threading.Lock()
        self.fallback_mode = False
        self._kb_fallback = Win32KeyboardFallback()

    def initialize(self, allow_fallback=True):
        """
        가상 Xbox 360 컨트롤러를 생성.
        반환값: (성공여부: bool, 메시지: str)
        allow_fallback=True 인 경우 ViGEmBus가 없어도 키보드 폴백 모드로 활성화하여 True를 반환.
        """
        try:
            import vgamepad as vg
            self._vgamepad = vg
            self.gamepad = vg.VX360Gamepad()
            self._button_map = {
                "A":          vg.XUSB_BUTTON.XUSB_GAMEPAD_A,
                "B":          vg.XUSB_BUTTON.XUSB_GAMEPAD_B,
                "X":          vg.XUSB_BUTTON.XUSB_GAMEPAD_X,
                "Y":          vg.XUSB_BUTTON.XUSB_GAMEPAD_Y,
                "START":      vg.XUSB_BUTTON.XUSB_GAMEPAD_START,
                "BACK":       vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK,
                "DPAD_UP":    vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP,
                "DPAD_DOWN":  vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN,
                "DPAD_LEFT":  vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT,
                "DPAD_RIGHT": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT,
                "LB":         vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER,
                "RB":         vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER,
            }
            self.fallback_mode = False
            self._pressed_buttons.clear()
            logger.info("ViGEmBus 가상 Xbox 360 패드 생성 완료")
            return True, "가상 Xbox 360 패드(ViGEmBus)가 정상적으로 생성되었습니다."

        except Exception as e:
            logger.warning(f"ViGEmBus 초기화 실패 ({e})")
            if allow_fallback:
                self.gamepad = None
                self.fallback_mode = True
                self._pressed_buttons.clear()
                return True, (
                    f"ViGEmBus 드라이버 미감지 ({e}) → "
                    "키보드 시뮬레이션(DirectInput 폴백) 모드로 동작합니다."
                )
            return False, (
                f"ViGEmBus 드라이버 오류: {e}\n"
                "ViGEmBus 드라이버가 설치되어 있는지 확인해주세요.\n"
                "https://github.com/nefarius/ViGEmBus/releases"
            )

    def try_auto_install_and_reinit(self, status_callback=None) -> bool:
        """ViGEmBus 자동 설치 후 가상 패드 재생성을 시도합니다."""
        installed = ViGEmBusInstaller.download_and_install(status_callback=status_callback)
        if installed:
            ok, _ = self.initialize(allow_fallback=False)
            if ok:
                return True
        return False

    def update_input(self, xbox_button_name, is_pressed):
        """Xbox 버튼 이름(문자열)으로 가상 패드 또는 폴백 키보드 입력을 갱신."""
        with self._lock:
            if self.fallback_mode:
                if is_pressed:
                    if xbox_button_name in self._pressed_buttons:
                        return
                    self._pressed_buttons.add(xbox_button_name)
                    self._kb_fallback.send_button(xbox_button_name, True)
                else:
                    if xbox_button_name not in self._pressed_buttons:
                        return
                    self._pressed_buttons.discard(xbox_button_name)
                    self._kb_fallback.send_button(xbox_button_name, False)
                return

            if not self.gamepad:
                return
            btn = self._button_map.get(xbox_button_name)
            if btn is None:
                return

            if is_pressed:
                if xbox_button_name in self._pressed_buttons:
                    return
                self._pressed_buttons.add(xbox_button_name)
                self.gamepad.press_button(button=btn)
            else:
                if xbox_button_name not in self._pressed_buttons:
                    return
                self._pressed_buttons.discard(xbox_button_name)
                self.gamepad.release_button(button=btn)
            self.gamepad.update()

    def sync_pressed_buttons(self, active_button_names: set):
        """게스트의 현재 눌린 버튼 집합과 호스트 패드/키보드 상태를 동기화 (패킷 유실 복구)."""
        with self._lock:
            if self.fallback_mode:
                for btn_name in list(self._pressed_buttons):
                    if btn_name not in active_button_names:
                        self._kb_fallback.send_button(btn_name, False)
                        self._pressed_buttons.discard(btn_name)
                for btn_name in active_button_names:
                    if btn_name not in self._pressed_buttons:
                        self._kb_fallback.send_button(btn_name, True)
                        self._pressed_buttons.add(btn_name)
                return

            if not self.gamepad:
                return
            changed = False

            for btn_name in list(self._pressed_buttons):
                if btn_name not in active_button_names:
                    btn = self._button_map.get(btn_name)
                    if btn is not None:
                        self.gamepad.release_button(button=btn)
                        changed = True
                    self._pressed_buttons.discard(btn_name)

            for btn_name in active_button_names:
                if btn_name not in self._pressed_buttons:
                    btn = self._button_map.get(btn_name)
                    if btn is not None:
                        self.gamepad.press_button(button=btn)
                        self._pressed_buttons.add(btn_name)
                        changed = True

            if changed:
                self.gamepad.update()

    def release_all(self):
        """모든 버튼을 릴리즈 (중립 상태로 복귀)."""
        with self._lock:
            if self.fallback_mode:
                for btn_name in list(self._pressed_buttons):
                    self._kb_fallback.send_button(btn_name, False)
                self._pressed_buttons.clear()
                return

            if self.gamepad and self._pressed_buttons:
                self._pressed_buttons.clear()
                self.gamepad.reset()
                self.gamepad.update()

    def cleanup(self):
        """가상 패드를 제거하고 리소스를 해제."""
        with self._lock:
            if self.fallback_mode:
                for btn_name in list(self._pressed_buttons):
                    self._kb_fallback.send_button(btn_name, False)
                self._pressed_buttons.clear()
                self.fallback_mode = False
                return

            if self.gamepad:
                try:
                    self._pressed_buttons.clear()
                    self.gamepad.reset()
                    self.gamepad.update()
                except Exception:
                    pass
                self.gamepad = None
                self._vgamepad = None
                self._button_map.clear()
                logger.info("가상 패드 해제 완료")
