"""
guest_runner.py
게스트(Guest) 역할이 확정되었을 때 실행되는 세션 오케스트레이터.
1. 호스트 IP 및 입력 포트로 UDP 입력 송신 소켓 준비
2. 로컬 키보드/게임패드 입력을 캡처하여 실시간 전송
3. Moonlight 클라이언트 자동 실행 (포터블 바이너리가 있을 경우)
"""

import json
import logging
import os
import socket
import subprocess
import sys
import threading

logger = logging.getLogger("GuestRunner")


def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


class GuestRunner:
    """게스트 세션 전체를 관리하는 컨트롤러."""

    def __init__(self, host_ip, input_port, status_callback=None):
        """
        Args:
            host_ip: 호스트의 IP 주소
            input_port: 호스트의 UDP 입력 수신 포트
            status_callback: 상태 메시지를 UI에 전달하는 콜백 함수
        """
        self.host_ip = host_ip
        self.input_port = input_port
        self.status_callback = status_callback or (lambda msg: None)
        self._udp_sock = None
        self._running = False
        self._moonlight_proc = None
        self._pressed_keys = set()  # 현재 눌린 키 추적

    def start_session(self):
        """게스트 세션을 시작."""
        self._running = True

        # 1. UDP 송신 소켓 준비
        self.status_callback("📡 호스트 입력 전송 소켓을 준비하는 중...")
        try:
            self._udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.status_callback(f"✅ 입력 송신 준비 완료 → {self.host_ip}:{self.input_port}")
        except Exception as e:
            self.status_callback(f"❌ 소켓 오류: {e}")
            return False, str(e)

        # 2. Moonlight 자동 실행 시도
        self._try_start_moonlight()

        return True, "게스트 세션 준비 완료"

    def send_key_input(self, key_name, is_pressed):
        """
        키 입력을 호스트에 UDP로 전송.
        Args:
            key_name: 키 이름 (예: "W", "K", "Escape" 등)
            is_pressed: True=눌림, False=릴리즈
        """
        if not self._udp_sock or not self._running:
            return

        # 중복 방지: 이미 눌린 키의 press 또는 이미 뗀 키의 release 무시
        key_upper = key_name.upper()
        if is_pressed:
            if key_upper in self._pressed_keys:
                return
            self._pressed_keys.add(key_upper)
        else:
            if key_upper not in self._pressed_keys:
                return
            self._pressed_keys.discard(key_upper)

        packet = json.dumps({
            "type": "input",
            "key": key_name,
            "pressed": is_pressed
        }).encode('utf-8')

        try:
            self._udp_sock.sendto(packet, (self.host_ip, self.input_port))
        except Exception as e:
            logger.debug(f"입력 전송 오류: {e}")

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
                "ℹ️ Moonlight 미설치 - 수동으로 호스트 화면을 연결하거나 "
                "tools/moonlight/ 폴더에 Moonlight를 배치하세요.\n"
                f"호스트 IP: {self.host_ip}"
            )

    def stop_session(self):
        """게스트 세션을 종료하고 모든 리소스를 정리."""
        self._running = False
        self._pressed_keys.clear()

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
