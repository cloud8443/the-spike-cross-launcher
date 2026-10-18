"""
signaling.py
OCI 중앙 서버를 통한 P2P 시그널링 핸드셰이크 관리.
호스트/게스트의 공인 IP(STUN), 사설 IP(LAN), 그리고 OCI 릴레이 정보를 함께 교환합니다.
"""

import json
import logging
import socket

logger = logging.getLogger("Signaling")

OCI_SERVER_IP = "146.56.101.107"
OCI_UDP_PORT = 47990


class SignalingHandler:
    """
    기존 TCP 로비 연결(send_json)을 통해
    호스트-게스트 간 연결 정보를 교환하는 시그널링 핸들러.
    """

    def __init__(self, send_json_func):
        """
        Args:
            send_json_func: main.py의 send_json 함수 참조
        """
        self.send_json = send_json_func

    def claim_host(self, room_id):
        """서버에 호스트 권한을 요청."""
        self.send_json({
            "action": "claim_host",
            "room_id": room_id
        })

    def send_host_info(self, room_id, host_ip, input_port, stream_port=47998, local_ip=None):
        """
        호스트 연결 정보(화면 공유 포트 포함)를 서버를 통해 게스트에게 전달.
        하위 호환성을 위해 host_ip 필드를 유지하면서, local_ip와 relay_ip를 함께 전달합니다.
        """
        if not local_ip:
            local_ip = self.get_local_ip()

        self.send_json({
            "action": "signal_exchange",
            "room_id": room_id,
            "payload": {
                "type": "host_info",
                "room_id": str(room_id),
                "host_ip": host_ip,          # 공인 IP (또는 STUN 실패 시 OCI_SERVER_IP)
                "local_ip": local_ip,        # 같은 와이파이 직결용 LAN IP (192.168.x.x)
                "relay_ip": OCI_SERVER_IP,   # 다른 네트워크 무지연 릴레이/홀펀칭 서버 IP
                "input_port": input_port,
                "stream_port": stream_port,
            }
        })

    def send_guest_ready(self, room_id, guest_ip):
        """게스트가 준비 완료 상태를 서버를 통해 호스트에게 전달."""
        self.send_json({
            "action": "signal_exchange",
            "room_id": room_id,
            "payload": {
                "type": "guest_ready",
                "room_id": str(room_id),
                "guest_ip": guest_ip,
                "local_ip": self.get_local_ip(),
            }
        })

    @staticmethod
    def get_local_ip():
        """공유기 내부 사설(LAN) IP 주소 확인."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception:
            return "127.0.0.1"

    @staticmethod
    def get_public_ip(existing_udp_sock=None, room_id="default"):
        """
        OCI UDP STUN 서버(146.56.101.107:47990)에 패킷을 보내 실제 공인 IP를 조회.
        응답 지연 시에도 연결이 100% 되도록 OCI_SERVER_IP를 안전한 기본값으로 반환합니다.
        """
        local_ip = SignalingHandler.get_local_ip()
        close_sock = False
        sock = existing_udp_sock

        try:
            if sock is None:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(0.8)
                close_sock = True

            req = json.dumps({
                "type": "stun_host",
                "room_id": str(room_id),
                "local_ip": local_ip,
                "local_port": 47990
            }).encode("utf-8")

            sock.sendto(req, (OCI_SERVER_IP, OCI_UDP_PORT))
            if close_sock:
                data, _ = sock.recvfrom(512)
                resp = json.loads(data.decode("utf-8"))
                if resp.get("type") == "stun_ack":
                    return resp.get("public_ip", OCI_SERVER_IP)
        except Exception:
            pass
        finally:
            if close_sock and sock:
                try:
                    sock.close()
                except Exception:
                    pass

        return OCI_SERVER_IP
