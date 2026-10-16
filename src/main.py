import sys
import os
import pkgutil
import PyQt6.sip
import traceback
import json
import socket
import threading
import webbrowser

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

class SpikeLauncher(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("The Spike Cross - Stable Multiplayer")
        self.resize(980, 660)

        # 네트워크 변수
        self.server_host = DEFAULT_SERVER_HOST
        self.server_port = DEFAULT_SERVER_PORT
        self.sock = None
        self.is_connected = False
        self.is_running = True
        self.my_client_id = ""
        self.my_name = "플레이어"
        self.current_room_id = None
        self.my_role = None

        self.signals = NetworkSignalEmitter()
        self.bind_signals()

        self.init_ui()
        self.connect_to_server()

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
        
        self.btn_launch = QPushButton("게임 시작 (Steam)")
        self.btn_launch.setObjectName("BtnLaunchGame")
        self.btn_launch.clicked.connect(self.launch_game)

        self.lbl_status = QLabel("상태: 준비 완료")
        self.lbl_status.setStyleSheet("font-size: 13px; font-weight: bold; color: #10b981;")

        hero_layout.addWidget(lbl_hero)
        hero_layout.addWidget(self.btn_launch)
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
        
        self.btn_create_room = QPushButton("방 만들기")
        self.btn_create_room.setProperty("class", "SuccessButton")
        self.btn_create_room.setFixedHeight(40)
        self.btn_create_room.setFixedWidth(120)
        self.btn_create_room.clicked.connect(self.create_room)
        
        create_box.addWidget(self.input_room_name)
        create_box.addWidget(self.btn_create_room)
        friendly_layout.addLayout(create_box)

        lbl_room_list = QLabel("📋 실시간 공개 방 목록 (자동 검색)")
        lbl_room_list.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff; margin-top: 5px;")
        friendly_layout.addWidget(lbl_room_list)

        self.room_list_widget = QListWidget()
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

        self.btn_room_leave = QPushButton("방 나가기")
        self.btn_room_leave.setProperty("class", "DangerButton")
        self.btn_room_leave.setFixedHeight(42)
        self.btn_room_leave.clicked.connect(self.leave_room)

        room_waiting_layout.addWidget(self.lbl_current_room_title)
        room_waiting_layout.addWidget(self.lbl_connection_status)
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

    # =========================================================
    # 네트워크 통신 루프
    # =========================================================
    def connect_to_server(self):
        def worker():
            try:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.connect((self.server_host, self.server_port))
                self.is_connected = True
                self.signals.connected.emit()

                buffer = ""
                while self.is_running and self.is_connected:
                    data = self.sock.recv(4096)
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
                self.signals.disconnected.emit()

        threading.Thread(target=worker, daemon=True).start()

    def send_json(self, data):
        if not self.is_connected or not self.sock:
            return
        try:
            payload = (json.dumps(data, ensure_ascii=False) + '\n').encode('utf-8')
            self.sock.sendall(payload)
        except Exception:
            pass

    def handle_server_message(self, line):
        try:
            msg = json.loads(line)
        except Exception:
            return

        mtype = msg.get('type')
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
        self.room_list_widget.clear()

        if not rooms:
            item = QListWidgetItem("현재 개설된 방이 없습니다. 상단에서 첫 번째 방을 만들어보세요!")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.room_list_widget.addItem(item)
            return

        for r in rooms:
            status_badge = "대기 중 (1/2)" if r['user_count'] < r['max_users'] else "진행 중 (2/2)"
            display = f"🏠 {r['room_name']}   |   방장: {r['host_name']}   |   [{status_badge}]"
            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, r['room_id'])
            self.room_list_widget.addItem(item)

    def request_room_list(self):
        self.send_json({'action': 'get_rooms'})

    def create_room(self):
        if not self.is_connected:
            QMessageBox.warning(self, "서버 오류", "서버에 연결되어 있지 않습니다.")
            return

        room_name = self.input_room_name.text().strip()
        if not room_name:
            room_name = "나의 친선 방"

        self.send_json({'action': 'create_room', 'room_name': room_name})

    def on_room_created(self, data):
        self.current_room_id = data['room_id']
        self.my_role = 'host'
        room_name = data['room_name']

        self.lbl_current_room_title.setText(f"🏠 방 제목: [{room_name}] (방장)")
        self.lbl_connection_status.setText("상태: 상대방의 입장을 기다리는 중...")
        self.lbl_connection_status.setStyleSheet("color: #10b981; font-size: 13px; font-weight: bold;")
        self.chat_display.clear()
        self.chat_display.addItem("[안내] 방이 개설되었습니다. 상대를 기다리는 중입니다.")
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
        self.current_room_id = data['room_id']
        self.my_role = 'guest'
        room_name = data['room_name']
        host_name = data.get('host_name', '방장')

        self.lbl_current_room_title.setText(f"🏠 방 입장: 🏠 {room_name}")
        self.lbl_connection_status.setText(f"상태: 🟢 방장과 연결되었습니다! 대화가 가능합니다.")
        self.lbl_connection_status.setStyleSheet("color: #10b981; font-size: 13px; font-weight: bold;")
        self.chat_display.clear()
        self.chat_display.addItem(f"[시스템] 🏠 {room_name} 방에 성공적으로 입장했습니다!")
        self.multi_stacked.setCurrentIndex(1)

    def on_peer_joined(self, peer_name):
        self.lbl_connection_status.setText(f"상태: 🟢 {peer_name} 접속 완료! 대화가 가능합니다.")
        self.lbl_connection_status.setStyleSheet("color: #10b981; font-size: 13px; font-weight: bold;")
        self.chat_display.addItem(f"[시스템] {peer_name}님이 입장하셨습니다.")

    def on_peer_left(self, reason):
        self.lbl_connection_status.setText("상태: 상대방의 입장을 기다리는 중...")
        self.chat_display.addItem(f"[시스템] {reason}")

    def on_room_closed(self, reason):
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
        self.chat_display.addItem(f"상대방: {msg}")
        self.chat_display.scrollToItem(self.chat_display.item(self.chat_display.count() - 1))

    def leave_room(self):
        self.send_json({'action': 'leave_room'})
        self.current_room_id = None
        self.my_role = None
        self.multi_stacked.setCurrentIndex(0)
        self.request_room_list()

    def launch_game(self):
        try:
            webbrowser.open("steam://rungameid/3983810")
            self.lbl_status.setText("상태: 스팀 실행 명령 전달됨")
        except Exception as e:
            self.lbl_status.setText(f"상태: 실행 오류 ({e})")

    def reconnect_with_new_settings(self):
        new_host = self.input_server_host.text().strip()
        new_port_str = self.input_server_port.text().strip()
        try:
            new_port = int(new_port_str)
            self.server_host = new_host
            self.server_port = new_port
            if self.sock:
                self.sock.close()
            self.connect_to_server()
            QMessageBox.information(self, "설정 완료", f"서버 주소가 {new_host}:{new_port}로 변경되었습니다.")
        except ValueError:
            QMessageBox.warning(self, "입력 오류", "포트 번호는 숫자여야 합니다.")

    def closeEvent(self, event):
        self.is_running = False
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
