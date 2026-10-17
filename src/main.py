import sys
import os
import pkgutil
import PyQt6.sip
import traceback
import json
import socket
import threading
import webbrowser

# src 패키지 경로를 sys.path에 추가 (모듈 임포트용)
_src_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_src_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

try:
    from src.streaming.host_runner import HostRunner
    from src.streaming.guest_runner import GuestRunner
    from src.streaming.virtual_controller import KeymapManager, ViGEmBusInstaller
    from src.ui.keymap_dialog import KeymapDialog
    from src.network.signaling import SignalingHandler
    from src.streaming.screen_viewer import GameStreamViewerWindow
except ImportError:
    from streaming.host_runner import HostRunner
    from streaming.guest_runner import GuestRunner
    from streaming.virtual_controller import KeymapManager, ViGEmBusInstaller
    from ui.keymap_dialog import KeymapDialog
    from network.signaling import SignalingHandler
    from streaming.screen_viewer import GameStreamViewerWindow

# -------------------------------------------------------------
# Windows 환경 Qt6 DLL 및 플랫폼 플러그인(qwindows.dll) 경로 자동 바인딩
# -------------------------------------------------------------
if getattr(sys, 'frozen', False):
    base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    qt_plugins = os.path.join(base_dir, 'PyQt6', 'Qt6', 'plugins')
    if os.path.exists(qt_plugins):
        os.environ['QT_PLUGIN_PATH'] = qt_plugins
        platforms = os.path.join(qt_plugins, 'platforms')
        if os.path.exists(platforms):
            os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = platforms
else:
    for base_path in sys.path:
        plugins_dir = os.path.join(base_path, 'PyQt6', 'Qt6', 'plugins')
        if os.path.exists(plugins_dir):
            os.environ['QT_PLUGIN_PATH'] = plugins_dir
            platforms_dir = os.path.join(plugins_dir, 'platforms')
            if os.path.exists(platforms_dir):
                os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = platforms_dir
            bin_dir = os.path.join(base_path, 'PyQt6', 'Qt6', 'bin')
            if os.path.exists(bin_dir):
                try:
                    os.add_dll_directory(bin_dir)
                except Exception:
                    pass
            break

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QLabel, 
    QVBoxLayout, QHBoxLayout, QWidget, QStackedWidget, 
    QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
    QFrame, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QColor

DEFAULT_SERVER_HOST = "146.56.101.107"
DEFAULT_SERVER_PORT = 5555

def get_local_lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

# -------------------------------------------------------------
# 최고급 모던 게이밍 다크 QSS 스타일시트
# -------------------------------------------------------------
MODERN_STYLE_SHEET = """
QMainWindow {
    background-color: #0b0c14;
}

QWidget {
    font-family: 'Pretendard', 'Malgun Gothic', 'Segoe UI', sans-serif;
    color: #e2e8f0;
}

/* 사이드바 */
#SidebarWidget {
    background-color: #111320;
    border-right: 1px solid rgba(255, 255, 255, 0.07);
}

#SidebarTitle {
    color: #ffffff;
    font-size: 20px;
    font-weight: 800;
    letter-spacing: 1px;
    padding: 10px 0 5px 12px;
}

#SidebarSubTitle {
    color: #ff4d4d;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 2px;
    padding-left: 12px;
    margin-bottom: 20px;
}

/* 사이드바 메뉴 버튼 */
QPushButton.NavButton {
    background-color: transparent;
    color: #94a3b8;
    text-align: left;
    padding-left: 16px;
    border: 1px solid transparent;
    border-radius: 10px;
    font-size: 14px;
    font-weight: 600;
    margin: 2px 10px;
    min-height: 42px;
}

QPushButton.NavButton:hover {
    background-color: rgba(255, 255, 255, 0.05);
    color: #ffffff;
    border: 1px solid rgba(255, 255, 255, 0.1);
}

QPushButton.NavButton[active="true"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(255, 77, 77, 0.25), stop:1 rgba(255, 77, 77, 0.05));
    color: #ffffff;
    font-weight: 700;
    border: 1px solid rgba(255, 77, 77, 0.4);
    border-left: 3px solid #ff4d4d;
}

/* 하단 서버 상태 박스 */
#ServerStatusBox {
    background-color: #171a2d;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    margin: 12px;
    padding: 10px;
}

/* 메인 우측 컨테이너 */
#RightContainer {
    background-color: #0b0c14;
}

/* 홈 히어로 카드 */
#HeroCard {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #15182a, stop:1 #0f111e);
    border: 1px solid rgba(255, 77, 77, 0.25);
    border-radius: 20px;
    padding: 30px;
}

#HeroTitle {
    color: #ffffff;
    font-size: 26px;
    font-weight: 800;
    letter-spacing: -0.5px;
}

/* 메인 게임 시작 버튼 */
QPushButton#BtnLaunchGame {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ff4d4d, stop:1 #e11d48);
    color: #ffffff;
    font-size: 16px;
    font-weight: 800;
    border-radius: 12px;
    border: 1px solid rgba(255, 255, 255, 0.2);
    min-height: 52px;
    padding: 0 30px;
}

QPushButton#BtnLaunchGame:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ff6b6b, stop:1 #f43f5e);
}

QPushButton#BtnLaunchGame:pressed {
    background-color: #be123c;
}

/* 일반 버튼 */
QPushButton.PrimaryButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #38bdf8, stop:1 #0284c7);
    color: #ffffff;
    font-weight: 700;
    border-radius: 10px;
    border: 1px solid rgba(255, 255, 255, 0.15);
    min-height: 38px;
    padding: 0 16px;
}

QPushButton.PrimaryButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #60a5fa, stop:1 #0369a1);
}

QPushButton.SuccessButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10b981, stop:1 #059669);
    color: #ffffff;
    font-weight: 700;
    border-radius: 10px;
    border: 1px solid rgba(255, 255, 255, 0.15);
    min-height: 38px;
    padding: 0 16px;
}

QPushButton.SuccessButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #34d399, stop:1 #047857);
}

QPushButton.DangerButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ef4444, stop:1 #b91c1c);
    color: #ffffff;
    font-weight: 700;
    border-radius: 10px;
    border: 1px solid rgba(255, 255, 255, 0.15);
    min-height: 40px;
    padding: 0 20px;
}

QPushButton.DangerButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f87171, stop:1 #991b1b);
}

/* 인풋 필드 */
QLineEdit {
    background-color: #141624;
    color: #f8fafc;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 10px;
    padding: 8px 14px;
    font-size: 13px;
    selection-background-color: #ff4d4d;
}

QLineEdit:focus {
    border: 1px solid #38bdf8;
    background-color: #171a2c;
}

/* 리스트 위젯 (방 목록 & 채팅) */
QListWidget {
    background-color: #121422;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 8px;
    outline: none;
}

QListWidget::item {
    background-color: #181b2e;
    color: #f1f5f9;
    border-radius: 8px;
    padding: 12px 14px;
    margin: 3px 0;
    border: 1px solid rgba(255, 255, 255, 0.05);
}

QListWidget::item:hover {
    background-color: #22263f;
    border: 1px solid rgba(56, 189, 248, 0.3);
}

QListWidget::item:selected {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(56, 189, 248, 0.25), stop:1 rgba(56, 189, 248, 0.1));
    color: #ffffff;
    font-weight: bold;
    border: 1px solid #38bdf8;
}

/* 스크롤바 */
QScrollBar:vertical {
    border: none;
    background: #0b0c14;
    width: 6px;
    border-radius: 3px;
}

QScrollBar::handle:vertical {
    background: #272c44;
    border-radius: 3px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background: #3e466b;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    border: none;
    background: none;
}
"""

class NetworkSignalEmitter(QObject):
    connected = pyqtSignal()
    disconnected = pyqtSignal()
    room_list_updated = pyqtSignal(list, int)
    room_created = pyqtSignal(dict)
    room_joined = pyqtSignal(dict)
    peer_joined = pyqtSignal(str)
    peer_left = pyqtSignal(str)
    room_closed = pyqtSignal(str)
    chat_received = pyqtSignal(str, str)
    error_received = pyqtSignal(str)
    # 스트리밍 멀티 시그널
    room_ready_for_host = pyqtSignal(dict)
    session_started = pyqtSignal(dict)
    signal_exchanged = pyqtSignal(dict)

class SpikeLauncher(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("The Spike Cross - Stable Multiplayer")
        self.resize(980, 660)

        # 네트워크 변수
        self.server_host = DEFAULT_SERVER_HOST
        self.server_port = DEFAULT_SERVER_PORT
        self.sock = None
        self.send_lock = threading.Lock()
        self.is_connected = False
        self.is_connecting = False
        self.is_running = True
        self.my_client_id = ""
        self.my_name = "플레이어"
        self.current_room_id = None
        self.my_role = None

        # 스트리밍 멀티플레이 상태
        self.streaming_role = None  # 'streaming_host' or 'streaming_guest'
        self.host_runner = None
        self.guest_runner = None
        self.viewer_window = None
        self.keymap_manager = KeymapManager()
        self.signaling = SignalingHandler(self.send_json)

        self.signals = NetworkSignalEmitter()
        self.bind_signals()

        self.init_ui()
        self.connect_to_server()

        # 주기적 방 목록 자동 폴링 타이머 (2.5초 간격)
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.auto_refresh_tick)
        self.refresh_timer.start(2500)

    def init_ui(self):
        self.setStyleSheet(MODERN_STYLE_SHEET)

        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # =========================================================
        # 1. 좌측 사이드바
        # =========================================================
        sidebar = QWidget()
        sidebar.setObjectName("SidebarWidget")
        sidebar.setFixedWidth(210)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 20, 0, 16)

        title_lbl = QLabel("SPIKE CROSS")
        title_lbl.setObjectName("SidebarTitle")
        
        sub_title_lbl = QLabel("MULTIPLAYER")
        sub_title_lbl.setObjectName("SidebarSubTitle")

        sidebar_layout.addWidget(title_lbl)
        sidebar_layout.addWidget(sub_title_lbl)

        self.btn_home = QPushButton("🏠  홈 / 로비")
        self.btn_multi = QPushButton("⚔️  멀티플레이 (공방)")
        self.btn_settings = QPushButton("⚙️  설정")

        for btn in [self.btn_home, self.btn_multi, self.btn_settings]:
            btn.setProperty("class", "NavButton")
            sidebar_layout.addWidget(btn)

        sidebar_layout.addStretch()

        # 하단 서버 상태 박스
        server_status_box = QWidget()
        server_status_box.setObjectName("ServerStatusBox")
        ss_layout = QVBoxLayout(server_status_box)
        ss_layout.setContentsMargins(8, 8, 8, 8)
        ss_layout.setSpacing(4)

        self.lbl_sidebar_server_status = QLabel("🔴 서버 연결 중...")
        self.lbl_sidebar_server_status.setStyleSheet("color: #f87171; font-size: 12px; font-weight: bold;")
        self.lbl_sidebar_online_count = QLabel("접속자: 0명")
        self.lbl_sidebar_online_count.setStyleSheet("color: #94a3b8; font-size: 11px;")

        ss_layout.addWidget(self.lbl_sidebar_server_status)
        ss_layout.addWidget(self.lbl_sidebar_online_count)
        sidebar_layout.addWidget(server_status_box)

        main_layout.addWidget(sidebar)

        # =========================================================
        # 2. 우측 메인 콘텐츠 영역
        # =========================================================
        right_container = QWidget()
        right_container.setObjectName("RightContainer")
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(30, 30, 30, 30)

        self.stacked_widget = QStackedWidget()

        # ---------------------------------------------------------
        # [탭 1: 홈 / 로비]
        # ---------------------------------------------------------
        home_page = QWidget()
        home_layout = QVBoxLayout(home_page)
        home_layout.setSpacing(20)

        hero_card = QWidget()
        hero_card.setObjectName("HeroCard")
        hero_layout = QVBoxLayout(hero_card)
        hero_layout.setSpacing(16)

        lbl_hero = QLabel("더 스파이크 크로스 (The Spike Cross)")
        lbl_hero.setObjectName("HeroTitle")
        
        btn_box = QHBoxLayout()
        btn_box.setSpacing(12)

        self.btn_launch = QPushButton("게임 시작 (Steam)")
        self.btn_launch.setObjectName("BtnLaunchGame")
        self.btn_launch.clicked.connect(self.launch_game)

        self.btn_test_detect = QPushButton("🎯 게임 감지 테스트")
        self.btn_test_detect.setFixedHeight(44)
        self.btn_test_detect.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #38bdf8;
                font-weight: bold;
                border: 1px solid #0284c7;
                border-radius: 10px;
                padding: 0 16px;
            }
            QPushButton:hover {
                background-color: #0284c7;
                color: #ffffff;
            }
        """)
        self.btn_test_detect.clicked.connect(self.test_game_window_detection)

        btn_box.addWidget(self.btn_launch)
        btn_box.addWidget(self.btn_test_detect)

        self.lbl_status = QLabel("상태: 준비 완료")
        self.lbl_status.setStyleSheet("font-size: 13px; font-weight: bold; color: #10b981;")

        hero_layout.addWidget(lbl_hero)
        hero_layout.addLayout(btn_box)
        hero_layout.addWidget(self.lbl_status)

        home_layout.addWidget(hero_card)
        home_layout.addStretch()

        # ---------------------------------------------------------
        # [탭 2: 멀티플레이 공방 컨테이너]
        # ---------------------------------------------------------
        multi_page = QWidget()
        multi_layout = QVBoxLayout(multi_page)
        multi_layout.setContentsMargins(0, 0, 0, 0)
        multi_layout.setSpacing(14)

        self.multi_stacked = QStackedWidget()

        # --- [서브탭 A: 친선전 공방 화면] ---
        friendly_widget = QWidget()
        friendly_layout = QVBoxLayout(friendly_widget)
        friendly_layout.setContentsMargins(0, 0, 0, 0)
        friendly_layout.setSpacing(12)

        create_box = QHBoxLayout()
        create_box.setSpacing(10)

        self.input_room_name = QLineEdit()
        self.input_room_name.setPlaceholderText("개설할 방 제목 입력 (예: 고수만 오세요)")
        self.input_room_name.setFixedHeight(40)
        self.input_room_name.returnPressed.connect(self.create_room)
        
        self.btn_create_room = QPushButton("방 만들기")
        self.btn_create_room.setProperty("class", "SuccessButton")
        self.btn_create_room.setFixedHeight(40)
        self.btn_create_room.setFixedWidth(120)
        self.btn_create_room.clicked.connect(self.create_room)
        
        create_box.addWidget(self.input_room_name)
        create_box.addWidget(self.btn_create_room)
        friendly_layout.addLayout(create_box)

        # 방 목록 상단 헤더 + 수동 새로고침 버튼
        room_header_layout = QHBoxLayout()
        lbl_room_list = QLabel("📋 실시간 공개 방 목록 (PC & 모바일 실시간 연동)")
        lbl_room_list.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff; margin-top: 5px;")
        
        self.btn_refresh_rooms = QPushButton("🔄 새로고침")
        self.btn_refresh_rooms.setProperty("class", "PrimaryButton")
        self.btn_refresh_rooms.setFixedHeight(34)
        self.btn_refresh_rooms.setFixedWidth(110)
        self.btn_refresh_rooms.clicked.connect(self.request_room_list)

        room_header_layout.addWidget(lbl_room_list)
        room_header_layout.addStretch()
        room_header_layout.addWidget(self.btn_refresh_rooms)
        friendly_layout.addLayout(room_header_layout)

        self.room_list_widget = QListWidget()
        self.room_list_widget.itemDoubleClicked.connect(lambda _: self.join_selected_room())
        friendly_layout.addWidget(self.room_list_widget)

        self.btn_join_selected = QPushButton("선택한 방 입장하기")
        self.btn_join_selected.setProperty("class", "PrimaryButton")
        self.btn_join_selected.setFixedHeight(44)
        self.btn_join_selected.clicked.connect(self.join_selected_room)
        friendly_layout.addWidget(self.btn_join_selected)

        # --- [서브탭 B: 방 대기실 + 실시간 채팅 화면] ---
        room_waiting_widget = QWidget()
        room_waiting_layout = QVBoxLayout(room_waiting_widget)
        room_waiting_layout.setContentsMargins(0, 0, 0, 0)
        room_waiting_layout.setSpacing(10)

        self.lbl_current_room_title = QLabel("🏠 방 제목: [대기실]")
        self.lbl_current_room_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #38bdf8;")
        
        self.lbl_connection_status = QLabel("상태: 연결 대기 중...")
        self.lbl_connection_status.setStyleSheet("font-size: 13px; color: #10b981; font-weight: bold;")

        self.chat_display = QListWidget()

        chat_input_layout = QHBoxLayout()
        chat_input_layout.setSpacing(8)

        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("채팅을 입력하세요... (Enter 전송)")
        self.chat_input.setFixedHeight(40)
        self.chat_input.returnPressed.connect(self.send_chat_message)
        
        self.btn_send_chat = QPushButton("전송")
        self.btn_send_chat.setProperty("class", "PrimaryButton")
        self.btn_send_chat.setFixedHeight(40)
        self.btn_send_chat.setFixedWidth(80)
        self.btn_send_chat.clicked.connect(self.send_chat_message)

        chat_input_layout.addWidget(self.chat_input)
        chat_input_layout.addWidget(self.btn_send_chat)

        self.btn_claim_host = QPushButton("🚀 내가 호스트로 시작하기")
        self.btn_claim_host.setObjectName("BtnClaimHost")
        self.btn_claim_host.setStyleSheet("""
            QPushButton#BtnClaimHost {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f59e0b, stop:1 #ef4444);
                color: #ffffff;
                font-size: 15px;
                font-weight: 800;
                border-radius: 12px;
                min-height: 48px;
                border: 1px solid rgba(255, 255, 255, 0.25);
            }
            QPushButton#BtnClaimHost:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #fbbf24, stop:1 #f87171);
            }
            QPushButton#BtnClaimHost:disabled {
                background-color: #374151;
                color: #9ca3af;
                border: 1px solid #4b5563;
            }
        """)
        self.btn_claim_host.clicked.connect(self.claim_host)
        self.btn_claim_host.setVisible(False)

        self.lbl_streaming_status = QLabel("")
        self.lbl_streaming_status.setStyleSheet("font-size: 13px; color: #38bdf8; font-weight: bold;")
        self.lbl_streaming_status.setVisible(False)

        self.lbl_game_detect_status = QLabel("")
        self.lbl_game_detect_status.setStyleSheet("font-size: 12px; color: #10b981; font-weight: bold;")
        self.lbl_game_detect_status.setVisible(False)

        self.btn_room_leave = QPushButton("방 나가기")
        self.btn_room_leave.setProperty("class", "DangerButton")
        self.btn_room_leave.setFixedHeight(42)
        self.btn_room_leave.clicked.connect(self.leave_room)

        room_waiting_layout.addWidget(self.lbl_current_room_title)
        room_waiting_layout.addWidget(self.lbl_connection_status)
        room_waiting_layout.addWidget(self.btn_claim_host)
        room_waiting_layout.addWidget(self.lbl_streaming_status)
        room_waiting_layout.addWidget(self.lbl_game_detect_status)
        room_waiting_layout.addWidget(QLabel("💬 실시간 대화창"))
        room_waiting_layout.addWidget(self.chat_display)
        room_waiting_layout.addLayout(chat_input_layout)
        room_waiting_layout.addWidget(self.btn_room_leave)

        self.multi_stacked.addWidget(friendly_widget)
        self.multi_stacked.addWidget(room_waiting_widget)
        
        multi_layout.addWidget(self.multi_stacked)

        # ---------------------------------------------------------
        # [탭 3: 설정]
        # ---------------------------------------------------------
        settings_page = QWidget()
        settings_layout = QVBoxLayout(settings_page)
        settings_layout.setSpacing(16)

        lbl_settings = QLabel("⚙️ 런처 설정")
        lbl_settings.setStyleSheet("font-size: 20px; font-weight: bold; color: #ffffff;")
        settings_layout.addWidget(lbl_settings)

        form_box = QWidget()
        form_box.setStyleSheet("background-color: #121422; border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 14px; padding: 20px;")
        fb_layout = QVBoxLayout(form_box)
        fb_layout.setSpacing(14)

        fb_layout.addWidget(QLabel("중앙 서버 IP 주소:"))
        self.input_server_host = QLineEdit(self.server_host)
        self.input_server_host.setFixedHeight(38)
        fb_layout.addWidget(self.input_server_host)

        fb_layout.addWidget(QLabel("서버 포트 번호:"))
        self.input_server_port = QLineEdit(str(self.server_port))
        self.input_server_port.setFixedHeight(38)
        fb_layout.addWidget(self.input_server_port)

        self.btn_reconnect = QPushButton("서버 재연결")
        self.btn_reconnect.setProperty("class", "PrimaryButton")
        self.btn_reconnect.setFixedHeight(40)
        self.btn_reconnect.clicked.connect(self.reconnect_with_new_settings)
        fb_layout.addWidget(self.btn_reconnect)

        self.btn_install_vigem = QPushButton("🎮 가상 2P 패드 드라이버 (ViGEmBus) 원클릭 설치")
        self.btn_install_vigem.setProperty("class", "SuccessButton")
        self.btn_install_vigem.setFixedHeight(40)
        self.btn_install_vigem.clicked.connect(self.install_vigembus_driver_manual)
        fb_layout.addWidget(self.btn_install_vigem)

        self.btn_detect_test = QPushButton("🎯 게임 화면 감지 진단 테스트")
        self.btn_detect_test.setProperty("class", "SecondaryButton")
        self.btn_detect_test.setFixedHeight(40)
        self.btn_detect_test.clicked.connect(self.test_game_window_detection)
        fb_layout.addWidget(self.btn_detect_test)

        settings_layout.addWidget(form_box)
        settings_layout.addStretch()

        self.stacked_widget.addWidget(home_page)
        self.stacked_widget.addWidget(multi_page)
        self.stacked_widget.addWidget(settings_page)

        right_layout.addWidget(self.stacked_widget)
        main_layout.addWidget(right_container)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        # 사이드바 버튼 연결
        self.btn_home.clicked.connect(lambda: self.switch_page(0))
        self.btn_multi.clicked.connect(lambda: self.switch_page(1))
        self.btn_settings.clicked.connect(lambda: self.switch_page(2))

        self.switch_page(0)

    def switch_page(self, idx):
        self.stacked_widget.setCurrentIndex(idx)
        buttons = [self.btn_home, self.btn_multi, self.btn_settings]
        for i, btn in enumerate(buttons):
            btn.setProperty("active", "true" if i == idx else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        # 멀티플레이(공방) 탭 진입 시 즉시 방 목록 갱신 요청
        if idx == 1 and self.current_room_id is None:
            self.request_room_list()

    def auto_refresh_tick(self):
        if self.is_connected and self.current_room_id is None:
            self.request_room_list()

        # 호스트 스트리밍 중 실시간 게임 창 감지 상태 갱신
        if self.streaming_role == 'streaming_host' and self.host_runner:
            try:
                is_det, info = self.host_runner.get_game_detection_status()
                self.lbl_game_detect_status.setVisible(True)
                if is_det and info:
                    self.lbl_game_detect_status.setText(
                        f"🎯 게임 감지 완료: [{info.get('proc')}] {info.get('title')} ({info.get('width')}x{info.get('height')}) 단독 공유 중"
                    )
                    self.lbl_game_detect_status.setStyleSheet("color: #10b981; font-size: 12px; font-weight: bold;")
                else:
                    self.lbl_game_detect_status.setText(
                        "🖥️ 게임 대기 중: The Spike 미실행 (전체 데스크톱 임시 공유 중 - 실행 시 자동 감지)"
                    )
                    self.lbl_game_detect_status.setStyleSheet("color: #f59e0b; font-size: 12px; font-weight: bold;")
            except Exception:
                pass

    def bind_signals(self):
        self.signals.connected.connect(self.on_server_connected)
        self.signals.disconnected.connect(self.on_server_disconnected)
        self.signals.room_list_updated.connect(self.update_room_list_ui)
        self.signals.room_created.connect(self.on_room_created)
        self.signals.room_joined.connect(self.on_room_joined)
        self.signals.peer_joined.connect(self.on_peer_joined)
        self.signals.peer_left.connect(self.on_peer_left)
        self.signals.room_closed.connect(self.on_room_closed)
        self.signals.chat_received.connect(self.on_chat_received)
        self.signals.error_received.connect(lambda msg: QMessageBox.warning(self, "안내", msg))
        # 스트리밍 멀티플레이 시그널
        self.signals.room_ready_for_host.connect(self.on_room_ready_for_host)
        self.signals.session_started.connect(self.on_session_started)
        self.signals.signal_exchanged.connect(self.on_signal_exchanged)

    # =========================================================
    # 네트워크 통신 루프
    # =========================================================
    def connect_to_server(self):
        if self.is_connecting:
            return
        self.is_connecting = True

        def worker():
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                s.settimeout(5.0)
                s.connect((self.server_host, self.server_port))
                s.settimeout(None)

                self.sock = s
                self.is_connected = True
                self.is_connecting = False
                self.signals.connected.emit()

                buffer = ""
                while self.is_running and self.is_connected:
                    data = s.recv(4096)
                    if not data:
                        break
                    buffer += data.decode('utf-8', errors='ignore')
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        line = line.strip()
                        if line:
                            self.handle_server_message(line)

            except Exception:
                pass
            finally:
                self.is_connected = False
                self.is_connecting = False
                self.signals.disconnected.emit()

        threading.Thread(target=worker, daemon=True).start()

    def send_json(self, data):
        if not self.is_connected or not self.sock:
            return
        try:
            payload = (json.dumps(data, ensure_ascii=False) + '\n').encode('utf-8')
            with self.send_lock:
                self.sock.sendall(payload)
        except Exception:
            self.is_connected = False

    def handle_server_message(self, line):
        try:
            msg = json.loads(line)
        except Exception:
            return

        mtype = msg.get('type') or msg.get('action', '').lower()
        if mtype == 'welcome':
            self.my_client_id = msg.get('client_id', '')
            self.my_name = msg.get('name', '플레이어')

        elif mtype == 'room_list':
            rooms = msg.get('rooms', [])
            online_count = msg.get('online_count', 1)
            self.signals.room_list_updated.emit(rooms, online_count)

        elif mtype == 'room_created':
            self.signals.room_created.emit(msg)

        elif mtype == 'room_joined':
            self.signals.room_joined.emit(msg)

        elif mtype == 'peer_joined':
            self.signals.peer_joined.emit(msg.get('peer_name', '상대방'))

        elif mtype == 'peer_left':
            self.signals.peer_left.emit(msg.get('reason', '상대방이 퇴장했습니다.'))

        elif mtype == 'room_closed':
            self.signals.room_closed.emit(msg.get('reason', '방이 닫혔습니다.'))

        elif mtype == 'chat_message':
            self.signals.chat_received.emit(msg.get('sender', '상대방'), msg.get('message', ''))

        elif mtype == 'room_ready_for_host':
            self.signals.room_ready_for_host.emit(msg)

        elif mtype == 'session_started':
            self.signals.session_started.emit(msg)

        elif mtype == 'signal_exchange':
            self.signals.signal_exchanged.emit(msg)

        elif mtype == 'error':
            self.signals.error_received.emit(msg.get('message', '오류가 발생했습니다.'))

    # =========================================================
    # UI 이벤트 핸들러
    # =========================================================
    def on_server_connected(self):
        self.lbl_sidebar_server_status.setText("🟢 서버 정상 연결")
        self.lbl_sidebar_server_status.setStyleSheet("color: #10b981; font-size: 12px; font-weight: bold;")
        self.request_room_list()

    def on_server_disconnected(self):
        self.lbl_sidebar_server_status.setText("🔴 서버 연결 끊김")
        self.lbl_sidebar_server_status.setStyleSheet("color: #f87171; font-size: 12px; font-weight: bold;")
        self.lbl_sidebar_online_count.setText("재연결 대기 중...")
        if self.is_running:
            QTimer.singleShot(3000, self.connect_to_server)

    def update_room_list_ui(self, rooms, online_count):
        self.lbl_sidebar_online_count.setText(f"접속자: {online_count}명")

        # 현재 선택되어 있던 방 ID 보존
        selected_room_id = None
        curr_item = self.room_list_widget.currentItem()
        if curr_item:
            selected_room_id = curr_item.data(Qt.ItemDataRole.UserRole)

        self.room_list_widget.clear()

        if not rooms:
            item = QListWidgetItem("현재 개설된 방이 없습니다. 상단에서 첫 번째 방을 만들어보세요!")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.room_list_widget.addItem(item)
            return

        for r in rooms:
            r_id = r.get('room_id') or r.get('code', '')
            r_name = r.get('room_name') or r.get('title', '친선 방')
            h_name = r.get('host_name', '방장')
            u_cnt = r.get('user_count', r.get('players', 1))
            max_u = r.get('max_users', 2)

            status_badge = f"대기 중 ({u_cnt}/{max_u})" if u_cnt < max_u else f"진행 중 ({u_cnt}/{max_u})"
            display = f"🏠 {r_name}   |   코드: {r_id}   |   방장: {h_name}   |   [{status_badge}]"
            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, r_id)
            self.room_list_widget.addItem(item)

            if selected_room_id and r_id == selected_room_id:
                self.room_list_widget.setCurrentItem(item)

    def request_room_list(self):
        self.send_json({'action': 'get_rooms'})

    def create_room(self):
        if not self.is_connected:
            QMessageBox.warning(self, "서버 오류", "서버에 연결되어 있지 않습니다.")
            return

        room_name = self.input_room_name.text().strip()
        if not room_name:
            room_name = "나의 친선 방"

        local_ip = get_local_lan_ip()
        self.send_json({
            'action': 'create_room',
            'room_name': room_name,
            'local_ip': local_ip
        })

    def on_room_created(self, data):
        self.cleanup_streaming()
        self.current_room_id = data['room_id']
        self.my_role = 'host'
        room_name = data['room_name']

        self.lbl_current_room_title.setText(f"🏠 방 제목: [{room_name}] (코드: {self.current_room_id})")
        self.lbl_connection_status.setText("상태: 상대방(PC 또는 모바일)의 입장을 기다리는 중...")
        self.lbl_connection_status.setStyleSheet("color: #10b981; font-size: 13px; font-weight: bold;")
        self.chat_display.clear()
        self.chat_display.addItem(f"[안내] 방이 개설되었습니다! (방 코드: {self.current_room_id})")
        self.chat_display.addItem("[안내] PC 또는 모바일 앱에서 방 목록을 클릭하거나 코드를 입력해 입장할 수 있습니다.")
        self.multi_stacked.setCurrentIndex(1)

    def join_selected_room(self):
        if not self.is_connected:
            QMessageBox.warning(self, "연결 오류", "서버에 연결되어 있지 않습니다.")
            return

        current_item = self.room_list_widget.currentItem()
        if not current_item:
            QMessageBox.warning(self, "선택 오류", "입장할 방을 목록에서 선택해주세요.")
            return

        room_id = current_item.data(Qt.ItemDataRole.UserRole)
        if not room_id:
            return

        self.send_json({'action': 'join_room', 'room_id': room_id})

    def on_room_joined(self, data):
        self.cleanup_streaming()
        self.current_room_id = data['room_id']
        self.my_role = 'guest'
        room_name = data['room_name']
        host_name = data.get('host_name', '방장')

        self.lbl_current_room_title.setText(f"🏠 방 입장: {room_name} (코드: {self.current_room_id})")
        self.lbl_connection_status.setText(f"상태: 🟢 방장({host_name})과 연결되었습니다! 대화가 가능합니다.")
        self.lbl_connection_status.setStyleSheet("color: #10b981; font-size: 13px; font-weight: bold;")
        self.chat_display.clear()
        self.chat_display.addItem(f"[시스템] 🏠 {room_name} 방에 성공적으로 입장했습니다!")
        self.multi_stacked.setCurrentIndex(1)

    def on_peer_joined(self, peer_name):
        self.lbl_connection_status.setText(f"상태: 🟢 {peer_name} 접속 완료! 대화가 가능합니다.")
        self.lbl_connection_status.setStyleSheet("color: #10b981; font-size: 13px; font-weight: bold;")
        self.chat_display.addItem(f"[시스템] {peer_name}님이 입장하셨습니다.")

    def cleanup_streaming(self):
        if self.viewer_window:
            try:
                self.viewer_window.close()
            except Exception:
                pass
            self.viewer_window = None

        if self.host_runner:
            try:
                self.host_runner.stop_session()
            except Exception:
                pass
            self.host_runner = None

        if self.guest_runner:
            try:
                self.guest_runner.stop_session()
            except Exception:
                pass
            self.guest_runner = None

        self.streaming_role = None
        self.btn_claim_host.setVisible(False)
        self.btn_claim_host.setEnabled(True)
        self.btn_claim_host.setText("🚀 내가 호스트로 시작하기")
        self.lbl_streaming_status.setVisible(False)
        self.lbl_streaming_status.setText("")
        self.lbl_game_detect_status.setVisible(False)
        self.lbl_game_detect_status.setText("")

    def on_peer_left(self, reason):
        self.cleanup_streaming()
        self.lbl_connection_status.setText("상태: 상대방의 입장을 기다리는 중...")
        self.chat_display.addItem(f"[시스템] {reason}")

    def on_room_closed(self, reason):
        self.cleanup_streaming()
        QMessageBox.information(self, "퇴장 안내", reason)
        self.current_room_id = None
        self.my_role = None
        self.multi_stacked.setCurrentIndex(0)
        self.request_room_list()

    def send_chat_message(self):
        msg = self.chat_input.text().strip()
        if not msg:
            return

        self.send_json({'action': 'chat', 'message': msg})
        self.chat_display.addItem(f"나: {msg}")
        self.chat_display.scrollToItem(self.chat_display.item(self.chat_display.count() - 1))
        self.chat_input.clear()

    def on_chat_received(self, sender, msg):
        self.chat_display.addItem(f"{sender}: {msg}")
        self.chat_display.scrollToItem(self.chat_display.item(self.chat_display.count() - 1))

    def leave_room(self):
        self.cleanup_streaming()
        self.send_json({'action': 'leave_room'})
        self.current_room_id = None
        self.my_role = None
        self.multi_stacked.setCurrentIndex(0)
        self.request_room_list()

    # =========================================================
    # 스트리밍 멀티플레이 핸들러
    # =========================================================
    def on_room_ready_for_host(self, data):
        self.btn_claim_host.setVisible(True)
        self.btn_claim_host.setEnabled(True)
        self.btn_claim_host.setText("🚀 내가 호스트로 시작하기")
        self.chat_display.addItem("[안내] 2명이 모두 모였습니다! [내가 호스트로 시작하기] 버튼을 누르면 멀티플레이가 시작됩니다.")
        self.chat_display.scrollToItem(self.chat_display.item(self.chat_display.count() - 1))

    def claim_host(self):
        if not self.current_room_id:
            return
        self.btn_claim_host.setEnabled(False)
        self.btn_claim_host.setText("⏳ 호스트 환경 준비 요청 중...")
        self.send_json({
            'action': 'claim_host',
            'room_id': self.current_room_id,
            'host_ip': get_local_lan_ip()
        })

    def prompt_vigembus_install(self) -> bool:
        """ViGEmBus 미설치 시 사용자에게 원클릭 설치 여부를 물어봅니다."""
        reply = QMessageBox.question(
            self,
            "가상 2P 패드 드라이버(ViGEmBus) 설치 안내",
            "호스트 PC에 가상 Xbox 360 컨트롤러 드라이버(ViGEmBus)가 설치되어 있지 않습니다.\n\n"
            "• [예(Yes)] 클릭 시: 공식 드라이버를 자동으로 다운로드 및 설치합니다. (권장)\n"
            "• [아니오(No)] 클릭 시: 설치 없이 '키보드 시뮬레이션(2P 폴백) 모드'로 즉시 시작합니다.\n\n"
            "지금 ViGEmBus 드라이버를 자동 설치하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        return reply == QMessageBox.StandardButton.Yes

    def install_vigembus_driver_manual(self):
        """설정 탭에서 수동으로 ViGEmBus 원클릭 설치를 실행."""
        ok = ViGEmBusInstaller.download_and_install()
        if ok:
            QMessageBox.information(self, "설치 완료", "ViGEmBus 가상 패드 드라이버 설치가 완료되었습니다!")
        else:
            QMessageBox.warning(
                self,
                "설치 안내",
                "자동 설치가 취소되었거나 실패했습니다.\n"
                "호스트 시작 시 키보드 폴백 모드로는 계속 플레이할 수 있습니다."
            )

    def on_session_started(self, data):
        role = data.get('role')
        host_name = data.get('host', '호스트')
        guest_name = data.get('guest', '게스트')
        self.btn_claim_host.setVisible(False)
        self.lbl_streaming_status.setVisible(True)

        if role == 'streaming_host':
            self.streaming_role = 'streaming_host'
            self.lbl_streaming_status.setText(f"👑 내가 호스트입니다 (게스트: {guest_name})")
            self.lbl_streaming_status.setStyleSheet("color: #f59e0b; font-size: 13px; font-weight: bold;")
            self.chat_display.addItem("[시스템] 내가 호스트로 선정되었습니다! 게임 및 화면 공유를 시작합니다.")
            self.chat_display.scrollToItem(self.chat_display.item(self.chat_display.count() - 1))

            def host_status_cb(text):
                self.chat_display.addItem(f"[호스트] {text}")
                self.chat_display.scrollToItem(self.chat_display.item(self.chat_display.count() - 1))

            self.host_runner = HostRunner(
                status_callback=host_status_cb,
                driver_prompt_callback=self.prompt_vigembus_install
            )
            ok, msg = self.host_runner.start_session()
            if ok:
                conn_info = self.host_runner.get_connection_info()
                host_ip = conn_info.get('host_ip') or get_local_lan_ip()
                self.signaling.send_host_info(
                    self.current_room_id,
                    host_ip,
                    conn_info['input_port'],
                    conn_info.get('stream_port', 47998)
                )
                self.chat_display.addItem(f"[안내] 게스트에게 화면 공유 및 연결 정보({host_ip})를 전송했습니다.")
            else:
                self.chat_display.addItem(f"[오류] 호스트 시작 실패: {msg}")
            self.chat_display.scrollToItem(self.chat_display.item(self.chat_display.count() - 1))

        elif role == 'streaming_guest':
            self.streaming_role = 'streaming_guest'
            self.lbl_streaming_status.setText(f"🎮 내가 게스트(2P)입니다 (호스트: {host_name})")
            self.lbl_streaming_status.setStyleSheet("color: #38bdf8; font-size: 13px; font-weight: bold;")
            self.chat_display.addItem(f"[시스템] {host_name}님이 호스트로 시작했습니다. 화면 스트림 연결을 준비 중입니다...")
            self.chat_display.scrollToItem(self.chat_display.item(self.chat_display.count() - 1))

    def on_signal_exchanged(self, data):
        payload = data.get('payload', {})
        ptype = payload.get('type')
        if ptype == 'host_info' and self.streaming_role == 'streaming_guest':
            host_ip = payload.get('host_ip', '127.0.0.1')
            input_port = payload.get('input_port', 47990)
            stream_port = payload.get('stream_port', 47998)
            self.chat_display.addItem(f"[시스템] 호스트 연결 정보 수신 완료 (화면 공유 포트: {stream_port})")

            def guest_status_cb(text):
                self.chat_display.addItem(f"[게스트] {text}")
                self.chat_display.scrollToItem(self.chat_display.item(self.chat_display.count() - 1))

            self.guest_runner = GuestRunner(host_ip, input_port, status_callback=guest_status_cb)
            ok, msg = self.guest_runner.start_session()
            if ok:
                self.chat_display.addItem("[안내] 2P 키보드 입력이 호스트로 실시간 전송됩니다!")

            # 실시간 게임 화면 공유 뷰어 창 팝업!
            if self.viewer_window:
                try:
                    self.viewer_window.close()
                except Exception:
                    pass
            self.viewer_window = GameStreamViewerWindow(host_ip, stream_port, guest_runner=self.guest_runner)
            self.viewer_window.show()
            self.chat_display.addItem("[안내] 📺 실시간 게임 화면 창이 열렸습니다! 창에서 바로 2P 플레이가 가능합니다.")
            self.chat_display.scrollToItem(self.chat_display.item(self.chat_display.count() - 1))

    def _qt_key_to_string(self, key):
        special_keys = {
            Qt.Key.Key_Escape: "Escape",
            Qt.Key.Key_Space: "Space",
            Qt.Key.Key_Tab: "Tab",
            Qt.Key.Key_Return: "Enter",
            Qt.Key.Key_Enter: "Enter",
            Qt.Key.Key_Up: "Up",
            Qt.Key.Key_Down: "Down",
            Qt.Key.Key_Left: "Left",
            Qt.Key.Key_Right: "Right",
            Qt.Key.Key_Shift: "Shift",
            Qt.Key.Key_Control: "Ctrl",
        }
        if key in special_keys:
            return special_keys[key]
        if 0x20 <= key <= 0x7E:
            return chr(key).upper()
        return None

    def keyPressEvent(self, event):
        if self.streaming_role == 'streaming_guest' and self.guest_runner:
            if not self.chat_input.hasFocus():
                k_str = self._qt_key_to_string(event.key())
                if k_str:
                    self.guest_runner.send_key_input(k_str, True)
                    return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if self.streaming_role == 'streaming_guest' and self.guest_runner:
            if not self.chat_input.hasFocus():
                k_str = self._qt_key_to_string(event.key())
                if k_str:
                    self.guest_runner.send_key_input(k_str, False)
                    return
        super().keyReleaseEvent(event)

    def launch_game(self):
        try:
            webbrowser.open("steam://rungameid/3983810")
            self.lbl_status.setText("상태: 스팀 실행 명령 전달됨")
        except Exception as e:
            self.lbl_status.setText(f"상태: 실행 오류 ({e})")

    def test_game_window_detection(self):
        """사용자가 직접 The Spike 게임 창이 정상적으로 감지되는지 즉시 테스트합니다."""
        try:
            from src.streaming.screen_streamer import ScreenStreamer
        except ImportError:
            from streaming.screen_streamer import ScreenStreamer

        streamer = ScreenStreamer()
        detected, info = streamer.get_detection_status()
        if detected and info:
            QMessageBox.information(
                self,
                "게임 창 감지 성공",
                f"🎉 The Spike 게임 창이 성공적으로 감지되었습니다!\n\n"
                f"• 프로세스명: {info.get('proc')}\n"
                f"• 윈도우 제목: {info.get('title')}\n"
                f"• 창 해상도:  {info.get('width')} x {info.get('height')}\n"
                f"• 윈도우 HWND: {info.get('hwnd')}\n\n"
                f"✅ 호스트 세션 진행 시 게스트에게 The Spike 게임 화면만 선명하게 단독 공유됩니다!"
            )
        else:
            QMessageBox.information(
                self,
                "게임 창 미감지 안내",
                "ℹ️ 현재 실행 중인 'The Spike' 게임 창이 감지되지 않았습니다.\n\n"
                "• 이유 1: 아직 게임(스팀)을 실행하지 않았습니다.\n"
                "• 이유 2: 게임 창이 작업표시줄로 '최소화(_)' 상태입니다.\n\n"
                "💡 걱정하지 마세요:\n"
                "게임이 아직 실행되지 않은 상태에서 호스트를 시작하더라도,\n"
                "1) 먼저 전체 데스크톱 화면이 안전하게 공유되고\n"
                "2) 게임을 실행하는 즉시 The Spike 게임 화면으로 1초 만에 자동 전환됩니다!"
            )

    def reconnect_with_new_settings(self):
        new_host = self.input_server_host.text().strip()
        new_port_str = self.input_server_port.text().strip()
        try:
            new_port = int(new_port_str)
            self.server_host = new_host
            self.server_port = new_port
            if self.sock:
                try:
                    self.sock.close()
                except Exception:
                    pass
            self.is_connected = False
            self.connect_to_server()
            QMessageBox.information(self, "설정 완료", f"서버 주소가 {new_host}:{new_port}로 변경되었습니다.")
        except ValueError:
            QMessageBox.warning(self, "입력 오류", "포트 번호는 숫자여야 합니다.")

    def closeEvent(self, event):
        self.is_running = False
        self.refresh_timer.stop()
        self.cleanup_streaming()
        try:
            if self.current_room_id:
                self.send_json({'action': 'leave_room'})
            if self.sock:
                self.sock.close()
        except Exception:
            pass
        event.accept()

if __name__ == '__main__':
    try:
        app = QApplication(sys.argv)
        app.setStyle('Fusion')
        window = SpikeLauncher()
        window.show()
        sys.exit(app.exec())
    except Exception:
        app = QApplication(sys.argv) if not QApplication.instance() else QApplication.instance()
        QMessageBox.critical(None, "실행 오류 발생", f"다음 에러로 인해 프로그램이 종료됩니다:\n\n{traceback.format_exc()}")
        sys.exit(1)
