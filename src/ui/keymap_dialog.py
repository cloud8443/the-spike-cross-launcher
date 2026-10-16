"""
keymap_dialog.py
PyQt6 기반 키 매핑 설정 다이얼로그.
사용자가 2P 입력 키를 커스텀할 수 있도록 하는 모달 창.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGridLayout, QWidget, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeyEvent

import sys
import os

# 상위 모듈 import 경로
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from streaming.virtual_controller import KeymapManager


class KeyCaptureButton(QPushButton):
    """
    클릭하면 '키 입력 대기 중...' 상태가 되고,
    다음에 누른 키를 캡처하여 표시하는 버튼.
    """
    key_captured = pyqtSignal(str)  # 캡처된 키 이름

    def __init__(self, current_key, parent=None):
        super().__init__(current_key, parent)
        self._capturing = False
        self.current_key = current_key
        self.setFixedHeight(36)
        self.setFixedWidth(120)
        self._update_style(False)
        self.clicked.connect(self._start_capture)

    def _start_capture(self):
        self._capturing = True
        self.setText("키 입력 대기...")
        self._update_style(True)
        self.setFocus()

    def keyPressEvent(self, event: QKeyEvent):
        if not self._capturing:
            super().keyPressEvent(event)
            return

        key = event.key()
        # Qt 키 코드를 사람이 읽을 수 있는 이름으로 변환
        key_name = self._qt_key_to_name(key)
        if key_name:
            self.current_key = key_name
            self.setText(key_name)
            self.key_captured.emit(key_name)
        else:
            self.setText(self.current_key)

        self._capturing = False
        self._update_style(False)

    def focusOutEvent(self, event):
        if self._capturing:
            self._capturing = False
            self.setText(self.current_key)
            self._update_style(False)
        super().focusOutEvent(event)

    def _update_style(self, capturing):
        if capturing:
            self.setStyleSheet(
                "background-color: #ff4d4d; color: #fff; font-weight: bold; "
                "border-radius: 8px; border: 2px solid #ff6b6b; font-size: 12px;"
            )
        else:
            self.setStyleSheet(
                "background-color: #1e2140; color: #e2e8f0; font-weight: bold; "
                "border-radius: 8px; border: 1px solid rgba(255,255,255,0.15); font-size: 13px;"
            )

    @staticmethod
    def _qt_key_to_name(key):
        """Qt 키 코드를 문자열 이름으로 변환."""
        special_keys = {
            Qt.Key.Key_Escape: "Escape",
            Qt.Key.Key_Tab: "Tab",
            Qt.Key.Key_Space: "Space",
            Qt.Key.Key_Return: "Enter",
            Qt.Key.Key_Enter: "Enter",
            Qt.Key.Key_Backspace: "Backspace",
            Qt.Key.Key_Shift: "Shift",
            Qt.Key.Key_Control: "Ctrl",
            Qt.Key.Key_Alt: "Alt",
            Qt.Key.Key_Up: "Up",
            Qt.Key.Key_Down: "Down",
            Qt.Key.Key_Left: "Left",
            Qt.Key.Key_Right: "Right",
            Qt.Key.Key_F1: "F1", Qt.Key.Key_F2: "F2", Qt.Key.Key_F3: "F3",
            Qt.Key.Key_F4: "F4", Qt.Key.Key_F5: "F5", Qt.Key.Key_F6: "F6",
            Qt.Key.Key_F7: "F7", Qt.Key.Key_F8: "F8", Qt.Key.Key_F9: "F9",
            Qt.Key.Key_F10: "F10", Qt.Key.Key_F11: "F11", Qt.Key.Key_F12: "F12",
        }
        if key in special_keys:
            return special_keys[key]
        # 일반 문자 키 (A-Z, 0-9 등)
        if 0x20 <= key <= 0x7E:
            return chr(key).upper()
        return None


class KeymapDialog(QDialog):
    """2P 키 매핑 설정 모달 다이얼로그."""

    def __init__(self, keymap_manager: KeymapManager, parent=None):
        super().__init__(parent)
        self.keymap_manager = keymap_manager
        self._capture_buttons = {}  # action -> KeyCaptureButton
        self.setWindowTitle("🎮 2P 키 매핑 설정")
        self.setFixedSize(480, 500)
        self.setStyleSheet("""
            QDialog {
                background-color: #0f111e;
                color: #e2e8f0;
            }
            QLabel {
                color: #e2e8f0;
                font-size: 13px;
            }
        """)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # 제목
        title = QLabel("🎮 2P 키보드 매핑 설정")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #ffffff; margin-bottom: 8px;")
        layout.addWidget(title)

        desc = QLabel("각 항목을 클릭한 뒤, 매핑하고 싶은 키를 눌러주세요.")
        desc.setStyleSheet("font-size: 12px; color: #94a3b8; margin-bottom: 12px;")
        layout.addWidget(desc)

        # 매핑 그리드
        grid = QGridLayout()
        grid.setSpacing(10)

        actions = list(self.keymap_manager.action_map.keys())
        for row, action in enumerate(actions):
            display_name = self.keymap_manager.get_display_name(action)
            current_key = self.keymap_manager.action_map[action]

            label = QLabel(display_name)
            label.setStyleSheet("font-size: 14px; font-weight: 600;")

            btn = KeyCaptureButton(current_key)
            btn.key_captured.connect(lambda key, a=action: self._on_key_captured(a, key))
            self._capture_buttons[action] = btn

            grid.addWidget(label, row, 0, Qt.AlignmentFlag.AlignLeft)
            grid.addWidget(btn, row, 1, Qt.AlignmentFlag.AlignRight)

        layout.addLayout(grid)
        layout.addStretch()

        # 하단 버튼
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        btn_reset = QPushButton("기본값으로 복원")
        btn_reset.setStyleSheet(
            "background-color: #374151; color: #e2e8f0; font-weight: bold; "
            "border-radius: 8px; min-height: 38px; padding: 0 16px; "
            "border: 1px solid rgba(255,255,255,0.1);"
        )
        btn_reset.clicked.connect(self._reset_defaults)

        btn_save = QPushButton("저장하고 닫기")
        btn_save.setStyleSheet(
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10b981, stop:1 #059669); "
            "color: #ffffff; font-weight: bold; border-radius: 8px; min-height: 38px; "
            "padding: 0 20px; border: 1px solid rgba(255,255,255,0.15);"
        )
        btn_save.clicked.connect(self._save_and_close)

        btn_layout.addWidget(btn_reset)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_save)

        layout.addLayout(btn_layout)

    def _on_key_captured(self, action, key):
        """키 캡처 완료 시 매핑 업데이트."""
        # 중복 키 검사
        for other_action, other_btn in self._capture_buttons.items():
            if other_action != action and other_btn.current_key == key:
                QMessageBox.warning(
                    self, "키 중복",
                    f"'{key}' 키는 이미 '{self.keymap_manager.get_display_name(other_action)}'에 "
                    f"매핑되어 있습니다. 다른 키를 선택해주세요."
                )
                # 원래 키로 복원
                btn = self._capture_buttons[action]
                btn.current_key = self.keymap_manager.action_map[action]
                btn.setText(btn.current_key)
                return

        self.keymap_manager.set_mapping(action, key)

    def _reset_defaults(self):
        """기본 매핑으로 복원."""
        for action, default_key in KeymapManager.DEFAULT_MAP.items():
            self.keymap_manager.set_mapping(action, default_key)
            if action in self._capture_buttons:
                self._capture_buttons[action].current_key = default_key
                self._capture_buttons[action].setText(default_key)

    def _save_and_close(self):
        """저장 후 다이얼로그 종료."""
        self.keymap_manager.save()
        self.accept()
