"""
virtual_controller.py
호스트 PC에서 ViGEmBus 가상 Xbox 360 패드를 생성하고,
게스트 입력 패킷을 2P 컨트롤러에 실시간 주입하는 모듈.
"""

import json
import os
import sys
import logging

logger = logging.getLogger("VirtualController")


def resource_path(relative_path):
    """PyInstaller 번들 / 개발 환경 양쪽에서 리소스 경로를 올바르게 반환."""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


# 키보드 키 이름 -> Xbox 360 패드 버튼 이름 역방향 매핑을 런타임에 생성
# keymap.json 형식: { "게임액션": "키보드키" }
# 게임액션 -> Xbox 버튼 고정 매핑:
ACTION_TO_XBOX = {
    "UP":            "DPAD_UP",
    "DOWN":          "DPAD_DOWN",
    "LEFT":          "DPAD_LEFT",
    "RIGHT":         "DPAD_RIGHT",
    "RECEIVE_SLIDE": "A",
    "JUMP_SPIKE":    "X",
    "BLOCK":         "Y",
    "SPECIAL_TOSS":  "B",
    "PAUSE":         "START",
}


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
        self.action_map = dict(self.DEFAULT_MAP)  # action -> keyboard key
        self._key_to_xbox = {}  # keyboard key -> xbox button name
        self.load()

    def load(self):
        """설정 파일에서 키 매핑을 로드."""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for action in self.DEFAULT_MAP:
                    if action in data:
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
        self._key_to_xbox = {}
        for action, key in self.action_map.items():
            xbox_btn = ACTION_TO_XBOX.get(action)
            if xbox_btn:
                self._key_to_xbox[key.upper()] = xbox_btn

    def key_to_xbox_button(self, key_name):
        """키보드 키 이름을 Xbox 버튼 이름으로 변환. 매핑에 없으면 None."""
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
    """ViGEmBus 가상 Xbox 360 패드를 관리."""

    def __init__(self):
        self.gamepad = None
        self._vgamepad = None  # lazy import

    def initialize(self):
        """가상 Xbox 360 컨트롤러를 생성. (성공여부, 메시지) 튜플 반환."""
        try:
            import vgamepad as vg
            self._vgamepad = vg
            self.gamepad = vg.VX360Gamepad()
            logger.info("ViGEmBus 가상 Xbox 360 패드 생성 완료")
            return True, "가상 Xbox 360 패드가 정상적으로 생성되었습니다."
        except ImportError:
            return False, ("vgamepad 패키지가 설치되지 않았습니다.\n"
                           "pip install vgamepad 으로 설치해주세요.")
        except Exception as e:
            return False, (f"ViGEmBus 드라이버 오류: {e}\n"
                           "ViGEmBus 드라이버가 설치되어 있는지 확인해주세요.\n"
                           "https://github.com/nefarius/ViGEmBus/releases")

    def update_input(self, xbox_button_name, is_pressed):
        """Xbox 버튼 이름(문자열)으로 가상 패드 입력을 갱신."""
        if not self.gamepad or not self._vgamepad:
            return

        vg = self._vgamepad
        button_map = {
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

        btn = button_map.get(xbox_button_name)
        if btn is None:
            return

        if is_pressed:
            self.gamepad.press_button(button=btn)
        else:
            self.gamepad.release_button(button=btn)
        self.gamepad.update()

    def release_all(self):
        """모든 버튼을 릴리즈 (중립 상태로 복귀)."""
        if self.gamepad:
            self.gamepad.reset()
            self.gamepad.update()

    def cleanup(self):
        """가상 패드를 제거하고 리소스를 해제."""
        if self.gamepad:
            try:
                self.release_all()
            except Exception:
                pass
            self.gamepad = None
            self._vgamepad = None
            logger.info("가상 패드 해제 완료")
