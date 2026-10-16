"""
signaling.py
OCI 중앙 서버를 통한 P2P 시그널링 핸드셰이크 관리.
호스트/게스트 연결 정보(IP, 포트)를 교환합니다.
"""

import json
import logging
import socket

logger = logging.getLogger("Signaling")


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

    def send_host_info(self, room_id, host_ip, input_port):
        """호스트 연결 정보를 서버를 통해 게스트에게 전달."""
        self.send_json({
            "action": "signal_exchange",
            "room_id": room_id,
            "payload": {
                "type": "host_info",
                "host_ip": host_ip,
                "input_port": input_port,
            }
        })

    def send_guest_ready(self, room_id, guest_ip):
        """게스트가 준비 완료 상태를 서버를 통해 호스트에게 전달."""
        self.send_json({
            "action": "signal_exchange",
            "room_id": room_id,
            "payload": {
                "type": "guest_ready",
                "guest_ip": guest_ip,
            }
        })

    @staticmethod
    def get_public_ip():
        """공인 IP 주소 확인 (STUN 대용 간이 방식)."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"
