"""
host_runner.py
호스트(Host) 역할이 확정되었을 때 실행되는 세션 오케스트레이터.
1. 가상 Xbox 360 2P 패드 생성 (ViGEmBus) - 미설치 시 자동 설치 유도 또는 키보드 폴백으로 무중단 진행
2. 스팀 게임 자동 실행
3. 게스트 입력 수신용 UDP 서버 가동 (UDP 홀 펀칭 + OCI STUN 하이브리드 포함)
4. 실시간 화면 공유 서버 및 OCI 역방향 비디오 터널 관리
"""

import json
import logging
import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser

from src.streaming.virtual_controller import VirtualGamepadManager, KeymapManager
from src.streaming.screen_streamer import ScreenStreamer

logger = logging.getLogger("HostRunner")

STEAM_APP_ID = "3983810"
INPUT_UDP_PORT = 47990  # 게스트로부터 입력을 받을 UDP 포트
STREAM_PORT = 47998     # 게스트에게 비디오 화면을 송출할 TCP 포트

# OCI 하이브리드 릴레이 서버 정보
OCI_SERVER_IP = "146.56.101.107"
OCI_UDP_PORT = 47990
OCI_TUNNEL_PORT = 47999


def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


class HostRunner:
    """호스트 세션 전체를 관리하는 컨트롤러 (인터넷 P2P 홀펀칭 + OCI 역방향 스트림 터널 내장)."""

    def __init__(self, status_callback=None, driver_prompt_callback=None, room_id="default"):
        """
        :param status_callback: 상태 로그 출력 콜백 (str -> None)
        :param driver_prompt_callback: ViGEmBus 미설치 시 사용자에게 자동 설치 여부를 묻는 콜백 (() -> bool)
        :param room_id: 방 ID (홀 펀칭 STUN 등록에 사용)
        """
        self.gamepad_manager = VirtualGamepadManager()
        self.keymap_manager = KeymapManager()
        self.status_callback = status_callback or (lambda msg: None)
        self.driver_prompt_callback = driver_prompt_callback
        self.room_id = str(room_id)

        self._input_thread = None
        self._stun_thread = None
        self._tunnel_thread = None
        self._running = False
        self._udp_sock = None
        self._sunshine_proc = None

        self.local_ip = self._get_local_ip()
        self.public_ip = OCI_SERVER_IP  # STUN 조회 전 안전한 기본값
        self.input_port = INPUT_UDP_PORT
        self.stream_port = STREAM_PORT
        self._peer_candidates = set()  # 게스트 홀 펀칭 대상 (공인/사설 IP, Port)

        self.screen_streamer = ScreenStreamer(
            port=self.stream_port,
            status_callback=self.status_callback,
            target_fps=60
        )

    def _get_local_ip(self):
        """로컬 IP 주소를 가져옴 (소켓 자동 정리 보장)."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception:
            return "127.0.0.1"

    def start_session(self):
        """호스트 세션을 시작합니다. ViGEmBus 미설치 시에도 중단되지 않고 폴백으로 진행합니다."""
        self._running = True

        # 1. 가상 패드 초기화 (우선 순수 ViGEmBus 모드 시도)
        self.status_callback("🎮 가상 2P 패드를 준비하는 중...")
        ok, msg = self.gamepad_manager.initialize(allow_fallback=False)

        if not ok:
            # ViGEmBus 드라이버가 없을 때 사용자에게 원클릭 자동 설치 의사 확인
            should_install = False
            if callable(self.driver_prompt_callback):
                try:
                    should_install = bool(self.driver_prompt_callback())
                except Exception:
                    should_install = False

            if should_install:
                installed_ok = self.gamepad_manager.try_auto_install_and_reinit(
                    status_callback=self.status_callback
                )
                if installed_ok:
                    self.status_callback("✅ 가상 Xbox 360 패드 (2P) 준비 완료")
                else:
                    self.gamepad_manager.initialize(allow_fallback=True)
                    self.status_callback(
                        "⚠️ 가상 패드 드라이버 미적용 → 키보드 시뮬레이션(2P 폴백) 모드로 계속 진행합니다."
                    )
            else:
                # 설치를 건너뛰더라도 세션을 중단하지 않고 키보드 폴백 활성화
                self.gamepad_manager.initialize(allow_fallback=True)
                self.status_callback(
                    "ℹ️ ViGEmBus 미설치 → 키보드 시뮬레이션(2P 폴백) 모드로 전환하여 세션을 계속 시작합니다."
                )
        else:
            self.status_callback("✅ 가상 Xbox 360 패드 (2P) 준비 완료")

        # 2. UDP 입력 수신 서버 + STUN + 홀 펀칭 시작
        self.status_callback("📡 입력 수신 서버를 시작하는 중...")
        try:
            self._start_input_receiver()
            self.status_callback(f"✅ 입력 수신 대기 중 (UDP 포트 {self.input_port})")
        except Exception as e:
            self.status_callback(f"❌ 입력 수신 서버 오류: {e}")
            return False, str(e)

        # 3. 실시간 화면 공유(비디오 스트리밍) 서버 시작
        self.status_callback("📺 실시간 화면 공유 서버를 시작하는 중...")
        stream_ok = self.screen_streamer.start_streaming()
        if stream_ok:
            self.status_callback(f"✅ 화면 공유 서버 준비 완료 (포트 {self.stream_port})")
        else:
            self.status_callback("⚠️ 화면 공유 서버 시작 실패")

        # 4. Sunshine 스트리밍 데몬 시도 (설치되어 있을 경우)
        self._try_start_sunshine()

        # 5. 스팀 게임 실행
        self.status_callback("🎮 더 스파이크 크로스를 실행하는 중...")
        try:
            webbrowser.open(f"steam://rungameid/{STEAM_APP_ID}")
            self.status_callback("✅ 게임 실행 명령 전달 완료")
        except Exception as e:
            self.status_callback(f"⚠️ 게임 실행 오류: {e}")

        return True, "호스트 세션 준비 완료"

    def _start_input_receiver(self):
        """게스트 입력 패킷 수신 + OCI STUN 등록 및 UDP 홀 펀칭 가동."""
        self._udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 1024)
        self._udp_sock.settimeout(0.5)
        self._udp_sock.bind(("0.0.0.0", self.input_port))

        def receiver_loop():
            logger.info(f"입력 수신 UDP 서버 시작 (포트 {self.input_port})")
            last_packet_time = time.perf_counter()
            watchdog_released = True

            while self._running:
                try:
                    data, addr = self._udp_sock.recvfrom(512)
                    # P2P 제어 패킷인지 먼저 확인
                    if self._handle_p2p_control_packet(data, addr):
                        continue

                    last_packet_time = time.perf_counter()
                    watchdog_released = False
                    self._process_input_packet(data)
                except socket.timeout:
                    # 2초 이상 게스트로부터 아무런 패킷이 없으면 모든 버튼 강제 해제 (무한 눌림 방어)
                    if not watchdog_released and (time.perf_counter() - last_packet_time > 2.0):
                        self.gamepad_manager.release_all()
                        watchdog_released = True
                    continue
                except Exception as e:
                    if self._running:
                        logger.warning(f"입력 수신 오류: {e}")

        self._input_thread = threading.Thread(target=receiver_loop, daemon=True)
        self._input_thread.start()

        # STUN 하트비트 및 홀 펀칭 유지 스레드 시작
        self._stun_thread = threading.Thread(target=self._stun_and_punch_loop, daemon=True)
        self._stun_thread.start()

        # 인터넷 게스트를 위한 비디오 역방향 터널 스레드 시작
        self._tunnel_thread = threading.Thread(target=self._video_reverse_tunnel_loop, daemon=True)
        self._tunnel_thread.start()

    def _handle_p2p_control_packet(self, raw_data: bytes, addr: tuple) -> bool:
        """STUN 및 UDP 홀 펀칭 제어 패킷을 처리. 제어 패킷이면 True 반환."""
        if (b'"stun_' not in raw_data and b'"peer_info"' not in raw_data
                and b'"punch"' not in raw_data and b'"punch_ack"' not in raw_data):
            return False
        try:
            pkt = json.loads(raw_data.decode("utf-8"))
            pkt_type = pkt.get("type")

            if pkt_type == "stun_ack":
                new_pub_ip = pkt.get("public_ip", self.public_ip)
                if new_pub_ip != self.public_ip:
                    self.public_ip = new_pub_ip
                    logger.info(f"🌐 공인 IP 확인됨: {self.public_ip}")
                return True

            elif pkt_type == "peer_info":
                # OCI 서버로부터 게스트의 공인/사설 좌표를 수신 -> 즉시 홀 펀칭 패킷 발사!
                g_pub = (pkt.get("public_ip"), int(pkt.get("public_port", 0)))
                g_loc = (pkt.get("local_ip"), int(pkt.get("local_port", 0)))
                for target in (g_pub, g_loc):
                    if target[0] and target[1] > 0:
                        self._peer_candidates.add(target)
                        self._send_udp_json({"type": "punch", "room_id": self.room_id}, target)
                logger.info(f"🚀 게스트 홀 펀칭 시작: 공인={g_pub}, 사설={g_loc}")
                return True

            elif pkt_type == "punch":
                # 게스트의 홀 펀칭 패킷이 직접 도달함 -> 즉시 punch_ack 응답하여 P2P 직결 완성!
                self._peer_candidates.add(addr)
                self._send_udp_json({"type": "punch_ack", "room_id": self.room_id}, addr)
                logger.info(f"⚡ 홀 펀칭 수신! 게스트 직결 주소: {addr}")
                return True

            elif pkt_type == "punch_ack":
                return True

        except Exception:
            pass
        return False

    def _send_udp_json(self, payload: dict, target_addr: tuple):
        if not self._udp_sock or not self._running:
            return
        try:
            self._udp_sock.sendto(json.dumps(payload).encode("utf-8"), target_addr)
        except Exception:
            pass

    def _stun_and_punch_loop(self):
        """주기적으로 OCI 서버와 게스트 후보 주소에 UDP NAT 매핑 유지 패킷 전송."""
        while self._running:
            # 1. OCI STUN & 릴레이 서버에 호스트 생존 신고 (NAT 포트 유지)
            self._send_udp_json({
                "type": "stun_host",
                "room_id": self.room_id,
                "local_ip": self.local_ip,
                "local_port": self.input_port
            }, (OCI_SERVER_IP, OCI_UDP_PORT))

            # 2. 게스트 후보 주소들로 홀 펀칭 패킷 전송 (방화벽 홀 유지)
            for peer_addr in list(self._peer_candidates):
                self._send_udp_json({"type": "punch", "room_id": self.room_id}, peer_addr)

            time.sleep(2.0)

    def _video_reverse_tunnel_loop(self):
        """
        외부 네트워크의 게스트가 공유기 포트포워딩 없이도 화면을 수신할 수 있도록
        OCI 서버(47999)에 대기 터널을 유지하고, 게스트 접속("START") 시 로컬 47998 스트리머와 연결.
        """
        while self._running:
            tunnel_sock = None
            try:
                tunnel_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                tunnel_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                tunnel_sock.settimeout(10.0)
                tunnel_sock.connect((OCI_SERVER_IP, OCI_TUNNEL_PORT))

                # 호스트 터널 등록
                tunnel_sock.sendall(f"HOST:{self.room_id}\n".encode("utf-8"))
                self.status_callback("🌐 인터넷 게스트용 비디오 터널 대기 중 (OCI 서버 연결됨)...")

                # 게스트가 접속할 때까지 대기 (블로킹)
                tunnel_sock.settimeout(None)
                cmd = b""
                while self._running and b"\n" not in cmd:
                    chunk = tunnel_sock.recv(64)
                    if not chunk:
                        break
                    cmd += chunk

                if not self._running or not cmd.startswith(b"START"):
                    try:
                        tunnel_sock.close()
                    except Exception:
                        pass
                    time.sleep(1.0)
                    continue

                # 게스트가 OCI 47998에 접속함! -> 즉시 로컬 ScreenStreamer(127.0.0.1:47998)와 브릿징
                self.status_callback("🟢 인터넷 게스트 비디오 연결됨! OCI 터널 통해 화면 중계 중...")
                local_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                local_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                local_sock.connect(("127.0.0.1", self.stream_port))

                threading.Thread(
                    target=self._bridge_sockets,
                    args=(local_sock, tunnel_sock),
                    daemon=True
                ).start()

            except Exception as e:
                if tunnel_sock:
                    try:
                        tunnel_sock.close()
                    except Exception:
                        pass
                if self._running:
                    logger.debug(f"비디오 역방향 터널 재연결 중: {e}")
                    time.sleep(3.0)

    def _bridge_sockets(self, local_sock: socket.socket, tunnel_sock: socket.socket):
        """로컬 스트리머(127.0.0.1:47998)의 비디오 프레임을 OCI 역방향 터널로 무지연 전송."""
        try:
            while self._running:
                data = local_sock.recv(65536)
                if not data:
                    break
                tunnel_sock.sendall(data)
        except Exception:
            pass
        finally:
            for s in (local_sock, tunnel_sock):
                try:
                    s.close()
                except Exception:
                    pass

    def _process_input_packet(self, raw_data):
        """게스트 입력 UDP 패킷을 파싱하여 가상 패드(또는 키보드 폴백)에 주입."""
        try:
            pkt = json.loads(raw_data.decode('utf-8'))
            pkt_type = pkt.get("type")

            if pkt_type == "input":
                key_name = pkt.get("key", "")
                is_pressed = bool(pkt.get("pressed", False))
                xbox_btn = self.keymap_manager.key_to_xbox_button(key_name)
                if xbox_btn:
                    self.gamepad_manager.update_input(xbox_btn, is_pressed)

            elif pkt_type == "release_all":
                self.gamepad_manager.release_all()

            elif pkt_type == "sync_keys":
                active_keys = pkt.get("keys", [])
                active_xbox_btns = {
                    self.keymap_manager.key_to_xbox_button(k)
                    for k in active_keys
                }
                active_xbox_btns.discard(None)
                self.gamepad_manager.sync_pressed_buttons(active_xbox_btns)

            elif pkt_type == "set_fps":
                fps = int(pkt.get("fps", 120))
                self.screen_streamer.set_fps(fps)

            # 비트마스크 패킷 (Android 터치패드/모바일 패드 및 PC 게스트 물리 컨트롤러) 완벽 호환
            elif "mask" in pkt:
                active_xbox_btns = set()
                if pkt.get("left"): active_xbox_btns.add("DPAD_LEFT")
                if pkt.get("right"): active_xbox_btns.add("DPAD_RIGHT")
                if pkt.get("up"): active_xbox_btns.add("DPAD_UP")
                if pkt.get("down"): active_xbox_btns.add("DPAD_DOWN")
                # The Spike Cross 2P 실제 게임 컨트롤 매핑
                if pkt.get("spike"): active_xbox_btns.add("A")    # 스파이크
                if pkt.get("receive"): active_xbox_btns.add("X")  # 리시브
                if pkt.get("block"): active_xbox_btns.add("B")    # 블로킹
                if pkt.get("slide") or pkt.get("sliding") or pkt.get("toss"): active_xbox_btns.add("Y")  # 슬라이딩
                if pkt.get("pause") or pkt.get("start"): active_xbox_btns.add("START")
                if pkt.get("back") or pkt.get("select"): active_xbox_btns.add("BACK")
                if pkt.get("lb"): active_xbox_btns.add("LB")
                if pkt.get("rb"): active_xbox_btns.add("RB")
                self.gamepad_manager.sync_pressed_buttons(active_xbox_btns)

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.debug(f"입력 패킷 파싱 오류: {e}")

    def _try_start_sunshine(self):
        """Sunshine 포터블 바이너리가 있으면 헤드리스 모드로 구동."""
        sunshine_path = resource_path(os.path.join("tools", "sunshine", "sunshine.exe"))
        if os.path.exists(sunshine_path):
            try:
                self.status_callback("☀️ Sunshine 스트리밍 데몬을 시작하는 중...")
                self._sunshine_proc = subprocess.Popen(
                    [sunshine_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                )
                self.status_callback("✅ Sunshine 스트리밍 데몬 활성화")
            except Exception as e:
                self.status_callback(f"⚠️ Sunshine 시작 실패 (내장 스트리머 동작 중): {e}")
        else:
            self.status_callback("ℹ️ 내장 초저지연(60 FPS) 화면 공유 서버로 동작합니다.")

    def set_room_id(self, room_id: str):
        """방 ID를 업데이트합니다 (STUN/홀 펀칭 그룹 식별자)."""
        self.room_id = str(room_id)

    def set_target_window(self, hwnd=None):
        """스트리밍 화면 공유 대상을 지정 (None: 자동 감지, 0: 전체 화면, >0: 특정 창)."""
        self.screen_streamer.set_target_window(hwnd)

    def get_game_detection_status(self):
        """현재 화면 스트리머가 The Spike 게임 창을 감지했는지 확인 (bool, dict)."""
        return self.screen_streamer.get_detection_status()

    def get_connection_info(self):
        """게스트에게 전달할 연결 정보를 반환."""
        return {
            "host_ip": self.public_ip,
            "local_ip": self.local_ip,
            "relay_ip": OCI_SERVER_IP,
            "input_port": self.input_port,
            "stream_port": self.stream_port,
            "sunshine_available": self._sunshine_proc is not None,
            "fallback_mode": self.gamepad_manager.fallback_mode,
        }

    def stop_session(self):
        """호스트 세션을 종료하고 모든 리소스를 정리."""
        self._running = False

        # 화면 공유 서버 종료
        try:
            self.screen_streamer.stop_streaming()
        except Exception:
            pass

        # UDP 소켓 종료
        if self._udp_sock:
            try:
                self._udp_sock.close()
            except Exception:
                pass
            self._udp_sock = None

        # Sunshine 프로세스 종료
        if self._sunshine_proc:
            try:
                self._sunshine_proc.terminate()
                self._sunshine_proc.wait(timeout=5)
            except Exception:
                try:
                    self._sunshine_proc.kill()
                except Exception:
                    pass
            self._sunshine_proc = None

        # 가상 패드 정리
        self.gamepad_manager.cleanup()
        logger.info("호스트 세션 종료 완료")
