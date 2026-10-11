import sys
import os
import pkgutil
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
    QLineEdit, QListWidget, QListWidgetItem, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject

DEFAULT_SERVER_HOST = "146.56.101.107"
DEFAULT_SERVER_PORT = 5555

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
        self.setWindowTitle("The Spike Cross - 온라인 멀티플레이어 런처")
        self.resize(1000, 680)

        # 네트워크 변수
        self.server_host = DEFAULT_SERVER_HOST
        self.server_port = DEFAULT_SERVER_PORT
        self.sock = None
        self.is_connected = False
        self.is_running = True
        self.my_client_id = ""
        self.my_name = "플레이어"
        self.current_room_id = None
        self.my_role = None  # 'host' or 'guest'

        self.signals = NetworkSignalEmitter()
        self.bind_signals()

        self.init_ui()
        self.connect_to_server()

    def init_ui(self):
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # =========================================================
        # 1. 좌측 사이드바
        # =========================================================
        sidebar = QWidget()
        sidebar.setFixedWidth(220)
        sidebar.setStyleSheet("""
            QWidget {
                background-color: #1e1e2e;
                border-right: 1px solid #313244;
            }
            QPushButton {
                color: #cdd6f4;
                text-align: left;
                padding-left: 15px;
                border: none;
                font-size: 14px;
                border-radius: 8px;
                margin: 3px 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #313244;
                color: #ffffff;
            }
        """)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 25, 0, 20)

        title_lbl = QLabel("  SPIKE CROSS")
        title_lbl.setStyleSheet("color: #89b4fa; font-size: 18px; font-weight: bold; margin-left: 10px;")
        sub_lbl = QLabel("   Multiplayer Edition")
        sub_lbl.setStyleSheet("color: #6c7086; font-size: 11px; margin-left: 12px; margin-bottom: 20px;")
        
        sidebar_layout.addWidget(title_lbl)
        sidebar_layout.addWidget(sub_lbl)

        self.btn_home = QPushButton("🏠  홈 / 로비")
        self.btn_multi = QPushButton("⚔️  멀티플레이 (공방)")
        self.btn_settings = QPushButton("⚙️  설정")

        for btn in [self.btn_home, self.btn_multi, self.btn_settings]:
            btn.setFixedHeight(44)
            sidebar_layout.addWidget(btn)

        sidebar_layout.addStretch()

        # 하단 서버 상태 위젯
        server_status_box = QWidget()
        server_status_box.setStyleSheet("background-color: #181825; border-radius: 8px; margin: 10px; padding: 10px;")
        ss_layout = QVBoxLayout(server_status_box)
        ss_layout.setContentsMargins(5, 5, 5, 5)

        self.lbl_sidebar_server_status = QLabel("🔴 서버 연결 중...")
        self.lbl_sidebar_server_status.setStyleSheet("color: #f38ba8; font-size: 12px; font-weight: bold;")
        self.lbl_sidebar_online_count = QLabel("접속자: 0명")
        self.lbl_sidebar_online_count.setStyleSheet("color: #a6adc8; font-size: 11px;")

        ss_layout.addWidget(self.lbl_sidebar_server_status)
        ss_layout.addWidget(self.lbl_sidebar_online_count)
        sidebar_layout.addWidget(server_status_box)

        main_layout.addWidget(sidebar)

        # =========================================================
        # 2. 우측 메인 콘텐츠
        # =========================================================
        right_container = QWidget()
        right_container.setStyleSheet("background-color: #11111b;")
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(30, 25, 30, 25)

        self.stacked_widget = QStackedWidget()

        # ---------------------------------------------------------
        # [탭 1: 홈 / 로비]
        # ---------------------------------------------------------
        home_page = QWidget()
        home_layout = QVBoxLayout(home_page)
        home_layout.setSpacing(20)

        lbl_hero = QLabel("더 스파이크 크로스 (The Spike Cross)")
        lbl_hero.setStyleSheet("font-size: 26px; font-weight: bold; color: #cdd6f4;")
        
        lbl_desc = QLabel("공식 스팀 게임을 실행하거나, 멀티플레이 탭에서 친구와 온라인 공방을 즐기세요.")
        lbl_desc.setStyleSheet("font-size: 14px; color: #a6adc8;")

        self.btn_launch = QPushButton("▶  스팀으로 게임 시작")
        self.btn_launch.setFixedHeight(55)
        self.btn_launch.setFixedWidth(280)
        self.btn_launch.setStyleSheet("""
            QPushButton {
                font-size: 16px; 
                font-weight: bold; 
                background-color: #89b4fa; 
                color: #11111b; 
                border-radius: 10px;
            }
            QPushButton:hover {
                background-color: #b4befe;
            }
        """)
        self.btn_launch.clicked.connect(self.launch_game)

        self.lbl_game_status = QLabel("상태: 준비 완료")
        self.lbl_game_status.setStyleSheet("font-size: 13px; color: #a6e3a1;")

        home_layout.addWidget(lbl_hero)
        home_layout.addWidget(lbl_desc)
        home_layout.addWidget(self.btn_launch)
        home_layout.addWidget(self.lbl_game_status)
        home_layout.addStretch()

        # ---------------------------------------------------------
        # [탭 2: 멀티플레이 공방 컨테이너]
        # ---------------------------------------------------------
        multi_page = QWidget()
        multi_layout = QVBoxLayout(multi_page)
        multi_layout.setContentsMargins(0, 0, 0, 0)
        multi_layout.setSpacing(15)

        self.multi_stacked = QStackedWidget()

        # (A) 방 목록 및 개설 화면
        lobby_view = QWidget()
        lobby_layout = QVBoxLayout(lobby_view)
        lobby_layout.setContentsMargins(0, 0, 0, 0)
        lobby_layout.setSpacing(12)

        # 상단 닉네임 & 방 개설 바
        top_bar = QHBoxLayout()
        self.input_nickname = QLineEdit()
        self.input_nickname.setPlaceholderText("내 닉네임")
        self.input_nickname.setText(self.my_name)
        self.input_nickname.setFixedHeight(38)
        self.input_nickname.setFixedWidth(150)
        self.input_nickname.setStyleSheet("background-color: #1e1e2e; color: #cdd6f4; border: 1px solid #313244; border-radius: 6px; padding: 0 10px;")

        self.btn_update_name = QPushButton("닉네임 변경")
        self.btn_update_name.setFixedHeight(38)
        self.btn_update_name.setStyleSheet("background-color: #45475a; color: #cdd6f4; border-radius: 6px; font-weight: bold; padding: 0 15px;")
        self.btn_update_name.clicked.connect(self.update_nickname)

        self.input_room_name = QLineEdit()
        self.input_room_name.setPlaceholderText("개설할 방 제목 입력 (예: 초보 환영 1:1)")
        self.input_room_name.setFixedHeight(38)
        self.input_room_name.setStyleSheet("background-color: #1e1e2e; color: #cdd6f4; border: 1px solid #313244; border-radius: 6px; padding: 0 10px;")

        self.btn_create_room = QPushButton("➕ 방 만들기")
        self.btn_create_room.setFixedHeight(38)
        self.btn_create_room.setFixedWidth(130)
        self.btn_create_room.setStyleSheet("background-color: #a6e3a1; color: #11111b; font-weight: bold; border-radius: 6px;")
        self.btn_create_room.clicked.connect(self.create_room)

        top_bar.addWidget(QLabel("닉네임:"))
        top_bar.addWidget(self.input_nickname)
        top_bar.addWidget(self.btn_update_name)
        top_bar.addSpacing(15)
        top_bar.addWidget(self.input_room_name)
        top_bar.addWidget(self.btn_create_room)
        lobby_layout.addLayout(top_bar)

        # 방 목록 헤더
        list_header = QHBoxLayout()
        lbl_room_list = QLabel("📋 실시간 온라인 공개 방 목록 (중앙 서버 연동)")
        lbl_room_list.setStyleSheet("font-size: 15px; font-weight: bold; color: #cdd6f4;")
        
        self.btn_refresh = QPushButton("🔄 새로고침")
        self.btn_refresh.setFixedHeight(32)
        self.btn_refresh.setStyleSheet("background-color: #313244; color: #cdd6f4; border-radius: 6px; padding: 0 12px;")
        self.btn_refresh.clicked.connect(self.request_room_list)

        list_header.addWidget(lbl_room_list)
        list_header.addStretch()
        list_header.addWidget(self.btn_refresh)
        lobby_layout.addLayout(list_header)

        # 방 목록 리스트
        self.room_list_widget = QListWidget()
        self.room_list_widget.setStyleSheet("""
            QListWidget {
                background-color: #181825; 
                color: #cdd6f4; 
                border: 1px solid #313244; 
                border-radius: 8px; 
                padding: 8px;
                font-size: 14px;
            }
            QListWidget::item {
                padding: 12px;
                border-bottom: 1px solid #313244;
                border-radius: 6px;
            }
            QListWidget::item:selected {
                background-color: #313244;
                color: #89b4fa;
            }
        """)
        lobby_layout.addWidget(self.room_list_widget)

        self.btn_join_selected = QPushButton("입장하기")
        self.btn_join_selected.setFixedHeight(45)
        self.btn_join_selected.setStyleSheet("""
            QPushButton {
                background-color: #89b4fa; 
                color: #11111b; 
                font-weight: bold; 
                font-size: 15px; 
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #b4befe;
            }
        """)
        self.btn_join_selected.clicked.connect(self.join_selected_room)
        lobby_layout.addWidget(self.btn_join_selected)

        # (B) 대기실 및 실시간 채팅 화면
        room_view = QWidget()
        room_view_layout = QVBoxLayout(room_view)
        room_view_layout.setContentsMargins(0, 0, 0, 0)
        room_view_layout.setSpacing(12)

        self.lbl_current_room_title = QLabel("🏠 방 제목: [대기실]")
        self.lbl_current_room_title.setStyleSheet("font-size: 20px; font-weight: bold; color: #89b4fa;")
        
        self.lbl_connection_status = QLabel("상태: 참가자 대기 중...")
        self.lbl_connection_status.setStyleSheet("font-size: 13px; color: #f9e2af; font-weight: bold;")

        self.chat_display = QListWidget()
        self.chat_display.setStyleSheet("""
            QListWidget {
                background-color: #181825; 
                color: #cdd6f4; 
                border: 1px solid #313244; 
                border-radius: 8px; 
                padding: 10px;
                font-size: 13px;
            }
            QListWidget::item {
                margin: 3px 0;
            }
        """)

        chat_input_layout = QHBoxLayout()
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("채팅을 입력하세요... (Enter 전송)")
        self.chat_input.setFixedHeight(42)
        self.chat_input.setStyleSheet("background-color: #1e1e2e; color: #cdd6f4; border: 1px solid #313244; border-radius: 6px; padding: 0 12px;")
        self.chat_input.returnPressed.connect(self.send_chat_message)
        
        self.btn_send_chat = QPushButton("전송")
        self.btn_send_chat.setFixedHeight(42)
        self.btn_send_chat.setFixedWidth(80)
        self.btn_send_chat.setStyleSheet("background-color: #89b4fa; color: #11111b; font-weight: bold; border-radius: 6px;")
        self.btn_send_chat.clicked.connect(self.send_chat_message)

        chat_input_layout.addWidget(self.chat_input)
        chat_input_layout.addWidget(self.btn_send_chat)

        room_bottom_bar = QHBoxLayout()
        self.btn_launch_in_room = QPushButton("🎮 스팀 게임 켜기")
        self.btn_launch_in_room.setFixedHeight(42)
        self.btn_launch_in_room.setStyleSheet("background-color: #a6e3a1; color: #11111b; font-weight: bold; border-radius: 6px; padding: 0 20px;")
        self.btn_launch_in_room.clicked.connect(self.launch_game)

        self.btn_room_leave = QPushButton("🚪 방 나가기")
        self.btn_room_leave.setFixedHeight(42)
        self.btn_room_leave.setFixedWidth(120)
        self.btn_room_leave.setStyleSheet("background-color: #f38ba8; color: #11111b; font-weight: bold; border-radius: 6px;")
        self.btn_room_leave.clicked.connect(self.leave_room)

        room_bottom_bar.addWidget(self.btn_launch_in_room)
        room_bottom_bar.addStretch()
        room_bottom_bar.addWidget(self.btn_room_leave)

        room_view_layout.addWidget(self.lbl_current_room_title)
        room_view_layout.addWidget(self.lbl_connection_status)
        room_view_layout.addWidget(QLabel("💬 실시간 방 채팅"))
        room_view_layout.addWidget(self.chat_display)
        room_view_layout.addLayout(chat_input_layout)
        room_view_layout.addLayout(room_bottom_bar)

        self.multi_stacked.addWidget(lobby_view)
        self.multi_stacked.addWidget(room_view)
        multi_layout.addWidget(self.multi_stacked)

        # ---------------------------------------------------------
        # [탭 3: 설정]
        # ---------------------------------------------------------
        settings_page = QWidget()
        settings_layout = QVBoxLayout(settings_page)
        settings_layout.setSpacing(20)

        lbl_set_title = QLabel("⚙️ 런처 설정")
        lbl_set_title.setStyleSheet("font-size: 22px; font-weight: bold; color: #cdd6f4;")
        settings_layout.addWidget(lbl_set_title)

        form_box = QWidget()
        form_box.setStyleSheet("background-color: #181825; border-radius: 10px; padding: 20px;")
        fb_layout = QVBoxLayout(form_box)
        fb_layout.setSpacing(15)

        fb_layout.addWidget(QLabel("중앙 서버 IP 주소:"))
        self.input_server_host = QLineEdit(self.server_host)
        self.input_server_host.setFixedHeight(38)
        self.input_server_host.setStyleSheet("background-color: #1e1e2e; color: #cdd6f4; border: 1px solid #313244; border-radius: 6px; padding: 0 10px;")
        fb_layout.addWidget(self.input_server_host)

        fb_layout.addWidget(QLabel("서버 포트 번호:"))
        self.input_server_port = QLineEdit(str(self.server_port))
        self.input_server_port.setFixedHeight(38)
        self.input_server_port.setStyleSheet("background-color: #1e1e2e; color: #cdd6f4; border: 1px solid #313244; border-radius: 6px; padding: 0 10px;")
        fb_layout.addWidget(self.input_server_port)

        self.btn_reconnect = QPushButton("서버 재연결")
        self.btn_reconnect.setFixedHeight(40)
        self.btn_reconnect.setStyleSheet("background-color: #89b4fa; color: #11111b; font-weight: bold; border-radius: 6px;")
        self.btn_reconnect.clicked.connect(self.reconnect_with_new_settings)
        fb_layout.addWidget(self.btn_reconnect)

        settings_layout.addWidget(form_box)
        settings_layout.addStretch()

        # 페이지 스택 등록
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
            if i == idx:
                btn.setStyleSheet("background-color: #313244; color: #89b4fa; text-align: left; padding-left: 15px; border-radius: 8px; margin: 3px 10px; font-weight: bold;")
            else:
                btn.setStyleSheet("background-color: transparent; color: #cdd6f4; text-align: left; padding-left: 15px; border-radius: 8px; margin: 3px 10px; font-weight: bold;")

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
            # 닉네임 입력칸 동기화
            QTimer.singleShot(0, lambda: self.input_nickname.setText(self.my_name))

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
        self.lbl_sidebar_server_status.setStyleSheet("color: #a6e3a1; font-size: 12px; font-weight: bold;")
        self.request_room_list()

    def on_server_disconnected(self):
        self.lbl_sidebar_server_status.setText("🔴 서버 연결 끊김")
        self.lbl_sidebar_server_status.setStyleSheet("color: #f38ba8; font-size: 12px; font-weight: bold;")
        self.lbl_sidebar_online_count.setText("재연결 대기 중...")
        # 3초 후 자동 재시도
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
            status_badge = "🟢 대기 중 (1/2)" if r['user_count'] < r['max_users'] else "🔴 진행 중 (2/2)"
            display = f"🏠  [{r['room_name']}]   |   방장: {r['host_name']}   |   {status_badge}"
            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, r['room_id'])
            self.room_list_widget.addItem(item)

    def request_room_list(self):
        self.send_json({'action': 'get_rooms'})

    def update_nickname(self):
        new_name = self.input_nickname.text().strip()
        if not new_name:
            QMessageBox.warning(self, "안내", "닉네임을 입력해주세요.")
            return
        self.my_name = new_name
        self.send_json({'action': 'set_name', 'name': new_name})
        QMessageBox.information(self, "성공", f"닉네임이 '{new_name}'(으)로 변경되었습니다.")

    def create_room(self):
        if not self.is_connected:
            QMessageBox.warning(self, "연결 오류", "중앙 서버에 연결되어 있지 않습니다.")
            return

        room_name = self.input_room_name.text().strip()
        if not room_name:
            room_name = f"{self.my_name}의 방"

        self.send_json({'action': 'create_room', 'room_name': room_name})

    def on_room_created(self, data):
        self.current_room_id = data['room_id']
        self.my_role = 'host'
        room_name = data['room_name']

        self.lbl_current_room_title.setText(f"🏠 방 제목: [{room_name}] (방장)")
        self.lbl_connection_status.setText("상태: ⏳ 참가자의 입장을 기다리는 중입니다...")
        self.lbl_connection_status.setStyleSheet("color: #f9e2af; font-size: 13px; font-weight: bold;")
        self.chat_display.clear()
        self.chat_display.addItem(f"[안내] 방이 성공적으로 개설되었습니다! (방 코드: {self.current_room_id})")
        self.chat_display.addItem("[안내] 상대방이 입장하면 대화가 시작됩니다.")
        self.multi_stacked.setCurrentIndex(1)

    def join_selected_room(self):
        if not self.is_connected:
            QMessageBox.warning(self, "연결 오류", "중앙 서버에 연결되어 있지 않습니다.")
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

        self.lbl_current_room_title.setText(f"🏠 방 제목: [{room_name}] (참가자)")
        self.lbl_connection_status.setText(f"상태: 🟢 방장({host_name})님과 연결되었습니다!")
        self.lbl_connection_status.setStyleSheet("color: #a6e3a1; font-size: 13px; font-weight: bold;")
        self.chat_display.clear()
        self.chat_display.addItem(f"[시스템] '{room_name}' 방에 입장했습니다.")
        self.chat_display.addItem(f"[시스템] 방장({host_name})님과 실시간 채팅이 가능합니다.")
        self.multi_stacked.setCurrentIndex(1)

    def on_peer_joined(self, peer_name):
        self.lbl_connection_status.setText(f"상태: 🟢 {peer_name} 님이 입장했습니다!")
        self.lbl_connection_status.setStyleSheet("color: #a6e3a1; font-size: 13px; font-weight: bold;")
        self.chat_display.addItem(f"[시스템] 🎉 {peer_name}님이 방에 입장하셨습니다!")

    def on_peer_left(self, reason):
        self.lbl_connection_status.setText("상태: ⏳ 참가자가 퇴장했습니다. 새로운 대기 중...")
        self.lbl_connection_status.setStyleSheet("color: #f9e2af; font-size: 13px; font-weight: bold;")
        self.chat_display.addItem(f"[시스템] 🚪 {reason}")

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
        self.chat_display.addItem(f"나 ({self.my_name}): {msg}")
        self.chat_display.scrollToItem(self.chat_display.item(self.chat_display.count() - 1))
        self.chat_input.clear()

    def on_chat_received(self, sender, msg):
        self.chat_display.addItem(f"{sender}: {msg}")
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
            self.lbl_game_status.setText("상태: 🚀 스팀 실행 명령 전달됨")
            if self.current_room_id:
                self.chat_display.addItem("[안내] 내 PC에서 게임을 실행했습니다.")
        except Exception as e:
            self.lbl_game_status.setText(f"상태: ❌ 실행 오류 ({e})")

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
