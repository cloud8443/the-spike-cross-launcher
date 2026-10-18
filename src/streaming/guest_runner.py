"""
guest_runner.py
게스트(Guest) 세션 오케스트레이터 (UDP 홀 펀칭 + OCI 무지연 릴레이 자동 전환 지원).
1. 세션 시작 즉시 OCI 릴레이로 입력 전송 (연결 대기 0초)
2. 백그라운드에서 호스트 사설/공인 IP로 홀 펀칭 시도
3. 홀 펀칭 성공 시 P2P 직결 타겟으로 핫스왑 (더 낮은 레이턴시)
4. TCP 비디오 스트림은 LAN 우선 -> OCI 릴레이 폴백 자동 선택
"""

import json
import logging
import os
import socket
import subprocess
import sys
import threading
import time

logger = logging.getLogger("GuestRunner")

OCI_SERVER_IP = "146.56.101.107"
OCI_UDP_PORT = 47990
OCI_STREAM_PORT = 47998


def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


class GuestRunner:
    """게스트 세션 전체를 관리하는 컨트롤러."""

    def __init__(self, host_ip, input_port, status_callback=None, host_local_ip=None, room_id="default"):
        self.host_ip = host_ip            # 호스트 공인 IP (STUN 실패 시 OCI_SERVER_IP)
        self.host_local_ip = host_local_ip or host_ip  # 같은 와이파이 직결용 LAN IP
        self.input_port = int(input_port)
        self.room_id = str(room_id)
        self.status_callback = status_callback or (lambda msg: None)

        self._udp_sock = None
        self._local_udp_port = 0
        self._running = False
        self._moonlight_proc = None
        self._pressed_keys = set()
        self._keys_lock = threading.Lock()
        self._sync_thread = None
        self._p2p_thread = None

        # 초기 타겟: 같은 서브넷이면 LAN 직결, 아니면 OCI 무지연 릴레이로 즉시 시작 (0초 연결)
        self.local_ip = self._get_local_ip()
        if self._is_same_lan(self.local_ip, self.host_local_ip):
            self._active_target = (self.host_local_ip, self.input_port)
            self._p2p_connected = True
            logger.info(f"🏠 같은 LAN 감지: 직결 모드로 시작 ({self.host_local_ip}:{self.input_port})")
        else:
            self._active_target = (OCI_SERVER_IP, OCI_UDP_PORT)
            self._p2p_connected = False
            logger.info(f"🌐 다른 네트워크 감지: OCI 릴레이 모드로 즉시 시작 ({OCI_SERVER_IP}:{OCI_UDP_PORT})")

        # 홀 펀칭 후보 주소 목록 (공인 IP + 사설 IP 동시 타격)
        self._candidate_targets = set()
        if self.host_local_ip and self.host_local_ip not in ("127.0.0.1", ""):
            self._candidate_targets.add((self.host_local_ip, self.input_port))
        if self.host_ip and self.host_ip != OCI_SERVER_IP:
            self._candidate_targets.add((self.host_ip, self.input_port))

    @staticmethod
    def _get_local_ip():
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception:
            return "127.0.0.1"

    @staticmethod
    def _is_same_lan(ip1: str, ip2: str) -> bool:
        try:
            return (ip1.split(".")[:3] == ip2.split(".")[:3]
                    and ip1 not in ("127.0.0.1", "")
                    and ip2 not in ("127.0.0.1", ""))
        except Exception:
            return False

    def get_best_stream_endpoint(self, stream_port=47998):
        """
        내장 스트리밍 뷰어(TCP)가 접속할 최적의 (IP, Port)를 반환.
        1순위: 호스트 LAN IP (0.25초 내 응답 시)
        2순위: OCI 무지연 비디오 스플라이서 (146.56.101.107:47998)
        """
        for candidate_ip in (self.host_local_ip, self.host_ip):
            if not candidate_ip or candidate_ip in ("", "127.0.0.1", OCI_SERVER_IP):
                continue
            try:
                with socket.create_connection((candidate_ip, stream_port), timeout=0.25):
                    logger.info(f"⚡ 비디오 스트림 LAN/직결 경로 확인됨: {candidate_ip}:{stream_port}")
                    return candidate_ip, stream_port
            except Exception:
                pass

        logger.info(f"🌐 비디오 스트림 OCI 고속 릴레이 경로 사용: {OCI_SERVER_IP}:{OCI_STREAM_PORT}")
        return OCI_SERVER_IP, OCI_STREAM_PORT

    def start_session(self):
        """게스트 세션을 시작."""
        self._running = True

        # 1. UDP 송신/수신 겸용 소켓 준비 (홀 펀칭 응답 수신 포함)
        self.status_callback("📡 호스트 P2P/릴레이 하이브리드 소켓을 준비하는 중...")
        try:
            self._udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._udp_sock.bind(("0.0.0.0", 0))  # OS로부터 로컬 포트 할당
            self._udp_sock.settimeout(0.3)
            self._udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 256 * 1024)
            self._local_udp_port = self._udp_sock.getsockname()[1]
            self.status_callback(
                f"✅ 입력 송신 준비 완료 → "
                f"{'직결' if self._p2p_connected else 'OCI 릴레이'}: "
                f"{self._active_target[0]}:{self._active_target[1]}"
            )
        except Exception as e:
            self.status_callback(f"❌ 소켓 오류: {e}")
            return False, str(e)

        # 2. 백그라운드 STUN & UDP 홀 펀칭 스레드 시작 (다른 와이파이인 경우에만)
        if not self._p2p_connected:
            self._p2p_thread = threading.Thread(target=self._p2p_hole_punch_loop, daemon=True)
            self._p2p_thread.start()

        # 3. UDP 패킷 유실 보정용 주기적 키 상태 동기화 스레드 시작
        self._sync_thread = threading.Thread(target=self._state_sync_loop, daemon=True)
        self._sync_thread.start()

        # 4. Moonlight 자동 실행 시도
        self._try_start_moonlight()

        return True, "게스트 세션 준비 완료"

    def _p2p_hole_punch_loop(self):
        """OCI STUN 서버와 협력하여 UDP 홀 펀칭을 수행하고, 성공 시 직결 P2P로 즉시 전환."""
        last_stun_time = 0.0

        while self._running and self._udp_sock:
            now = time.perf_counter()
            if now - last_stun_time >= 1.0:
                last_stun_time = now
                # OCI 서버에 게스트 등록 (릴레이 바인딩 + 호스트 좌표 요청)
                stun_pkt = json.dumps({
                    "type": "stun_guest",
                    "room_id": self.room_id,
                    "local_ip": self.local_ip,
                    "local_port": self._local_udp_port
                }).encode("utf-8")
                try:
                    self._udp_sock.sendto(stun_pkt, (OCI_SERVER_IP, OCI_UDP_PORT))
                except Exception:
                    pass

                # 아직 직결되지 않았다면 호스트 후보 주소들로 홀 펀칭 패킷 발사
                if not self._p2p_connected:
                    punch_pkt = json.dumps({"type": "punch", "room_id": self.room_id}).encode("utf-8")
                    for target in list(self._candidate_targets):
                        try:
                            self._udp_sock.sendto(punch_pkt, target)
                        except Exception:
                            pass

            # 홀 펀칭 응답(punch / punch_ack / peer_info) 수신 대기
            try:
                data, addr = self._udp_sock.recvfrom(512)
                pkt = json.loads(data.decode("utf-8"))
                pkt_type = pkt.get("type")

                if pkt_type == "peer_info":
                    # OCI 서버가 호스트 좌표를 알려줌 -> 즉시 홀 펀칭 패킷 발사
                    h_pub = (pkt.get("public_ip"), int(pkt.get("public_port", 0)))
                    h_loc = (pkt.get("local_ip"), int(pkt.get("local_port", 0)))
                    punch_pkt = json.dumps({"type": "punch", "room_id": self.room_id}).encode("utf-8")
                    for t in (h_loc, h_pub):
                        if t[0] and t[1] > 0:
                            self._candidate_targets.add(t)
                            try:
                                self._udp_sock.sendto(punch_pkt, t)
                            except Exception:
                                pass

                elif pkt_type in ("punch", "punch_ack") and addr[0] != OCI_SERVER_IP:
                    if not self._p2p_connected:
                        self._p2p_connected = True
                        self._active_target = addr
                        self.status_callback(f"⚡ P2P 홀 펀칭 직결 성공! ({addr[0]}:{addr[1]})")
                        logger.info(f"⚡ P2P 직결 전환: OCI 릴레이 → {addr}")
                    if pkt_type == "punch":
                        try:
                            self._udp_sock.sendto(
                                json.dumps({"type": "punch_ack", "room_id": self.room_id}).encode("utf-8"),
                                addr
                            )
                        except Exception:
                            pass

            except socket.timeout:
                continue
            except Exception:
                pass

    def _send_packet(self, payload: dict):
        if not self._udp_sock or not self._running:
            return
        try:
            data = json.dumps(payload).encode('utf-8')
            self._udp_sock.sendto(data, self._active_target)
        except Exception as e:
            logger.debug(f"패킷 전송 오류: {e}")

    def send_key_input(self, key_name, is_pressed):
        """
        키 입력을 호스트에 UDP로 즉시 전송.
        중복 방지 및 UDP 패킷 유실 대비 이중 전송(Release 시) 적용.
        """
        if not self._udp_sock or not self._running:
            return

        key_upper = key_name.upper()
        with self._keys_lock:
            if is_pressed:
                if key_upper in self._pressed_keys:
                    return
                self._pressed_keys.add(key_upper)
            else:
                if key_upper not in self._pressed_keys:
                    return
                self._pressed_keys.discard(key_upper)

        pkt = {
            "type": "input",
            "key": key_name,
            "pressed": is_pressed
        }
        self._send_packet(pkt)

    def release_all_keys(self):
        """창 포커스 이탈 또는 종료 시 모든 키 입력을 즉시 해제."""
        with self._keys_lock:
            if not self._pressed_keys:
                return
            self._pressed_keys.clear()

        # UDP 유실 방지를 위해 release_all 패킷 전송
        self._send_packet({"type": "release_all"})

    def send_gamepad_state(self, left=False, right=False, up=False, down=False,
                           spike=False, receive=False, block=False, slide=False,
                           pause=False, lb=False, rb=False):
        """PC 게스트에 연결된 물리 게임패드(Xbox, PS, USB 패드) 상태를 호스트에 실시간 무지연 전송."""
        if not self._udp_sock or not self._running:
            return
        mask = 0
        if left: mask |= 1
        if right: mask |= 2
        if up: mask |= 4
        if down: mask |= 8
        if spike: mask |= 16
        if receive: mask |= 32
        if block: mask |= 64
        if slide: mask |= 128
        pkt = {
            "player": 2,
            "mask": mask,
            "left": bool(left),
            "right": bool(right),
            "up": bool(up),
            "down": bool(down),
            "spike": bool(spike),
            "receive": bool(receive),
            "block": bool(block),
            "slide": bool(slide),
            "sliding": bool(slide),
            "pause": bool(pause),
            "lb": bool(lb),
            "rb": bool(rb),
        }
        self._send_packet(pkt)

    def _state_sync_loop(self):
        """
        UDP 패킷 유실로 인해 특정 키의 Release 이벤트가 누락되는 현상을 방지하기 위해
        현재 눌려있는 전체 키 목록을 주기적으로 호스트와 동기화.
        """
        while self._running:
            with self._keys_lock:
                active_keys = list(self._pressed_keys)

            self._send_packet({
                "type": "sync_keys",
                "keys": active_keys
            })
            # 키가 눌려 있을 때는 150ms 주기로 빠르게 보정, 유휴 시에는 500ms 주기
            time.sleep(0.15 if active_keys else 0.5)

    def send_set_fps(self, fps: int):
        """호스트 스트리머에게 목표 FPS 변경 요청 전송 (예: 60 또는 120)."""
        self._send_packet({
            "type": "set_fps",
            "fps": int(fps)
        })
        logger.info(f"호스트에게 FPS 변경 패킷 전송: {fps} FPS")

    def _try_start_moonlight(self):
        """Moonlight 포터블 바이너리가 있으면 호스트에 자동 연결."""
        moonlight_path = resource_path(os.path.join("tools", "moonlight", "Moonlight.exe"))
        if os.path.exists(moonlight_path):
            try:
                self.status_callback("🌙 Moonlight 스트리밍 클라이언트를 시작하는 중...")
                cmd = [
                    moonlight_path,
                    "stream", self.host_ip,
                    "--fps", "60",
                    "--bitrate", "20000",
                    "--packetsize", "1024",
                ]
                self._moonlight_proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                )
                self.status_callback("✅ Moonlight 스트리밍 클라이언트 활성화")
            except Exception as e:
                self.status_callback(f"⚠️ Moonlight 시작 실패: {e}")
        else:
            self.status_callback(
                f"ℹ️ 내장 초저지연 스트리밍 뷰어 사용 중 "
                f"({'직결' if self._p2p_connected else 'OCI 릴레이'})\n"
                f"호스트 IP: {self._active_target[0]}"
            )

    def stop_session(self):
        """게스트 세션을 종료하고 모든 리소스를 정리."""
        self.release_all_keys()
        self._running = False

        if self._udp_sock:
            try:
                self._udp_sock.close()
            except Exception:
                pass
            self._udp_sock = None

        if self._moonlight_proc:
            try:
                self._moonlight_proc.terminate()
                self._moonlight_proc.wait(timeout=5)
            except Exception:
                try:
                    self._moonlight_proc.kill()
                except Exception:
                    pass
            self._moonlight_proc = None

        logger.info("게스트 세션 종료 완료")
