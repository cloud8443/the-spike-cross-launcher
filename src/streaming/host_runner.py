"""
host_runner.py
호스트(Host) 역할이 확정되었을 때 실행되는 세션 오케스트레이터.
1. 가상 Xbox 360 2P 패드 생성 (ViGEmBus)
2. 스팀 게임 자동 실행
3. 게스트 입력 수신용 UDP 서버 가동 (패킷 유실 복구 및 Watchdog 포함)
4. 실시간 화면 공유 서버 및 Sunshine 스트리밍 데몬 관리
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


def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


class HostRunner:
    """호스트 세션 전체를 관리하는 컨트롤러."""

    def __init__(self, status_callback=None):
        self.gamepad_manager = VirtualGamepadManager()
        self.keymap_manager = KeymapManager()
        self.status_callback = status_callback or (lambda msg: None)
        self._input_thread = None
        self._running = False
        self._udp_sock = None
        self._sunshine_proc = None
        self.local_ip = self._get_local_ip()
        self.input_port = INPUT_UDP_PORT
        self.stream_port = STREAM_PORT
        self.screen_streamer = ScreenStreamer(
            port=self.stream_port,
            status_callback=self.status_callback,
            target_fps=120
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
        """호스트 세션을 시작합니다. 순서대로 초기화."""
        self._running = True

        # 1. 가상 패드 초기화
        self.status_callback("🎮 가상 2P 패드를 준비하는 중...")
        ok, msg = self.gamepad_manager.initialize()
        if not ok:
            self.status_callback(f"❌ 패드 오류: {msg}")
            return False, msg
        self.status_callback("✅ 가상 Xbox 360 패드 (2P) 준비 완료")

        # 2. UDP 입력 수신 서버 시작
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
        """게스트 입력 패킷을 수신하는 UDP 서버를 백그라운드 스레드로 가동."""
        self._udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._udp_sock.settimeout(0.5)
        self._udp_sock.bind(("0.0.0.0", self.input_port))

        def receiver_loop():
            logger.info(f"입력 수신 UDP 서버 시작 (포트 {self.input_port})")
            last_packet_time = time.perf_counter()
            watchdog_released = True

            while self._running:
                try:
                    data, _ = self._udp_sock.recvfrom(512)
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

    def _process_input_packet(self, raw_data):
        """게스트 입력 UDP 패킷을 파싱하여 가상 패드에 주입."""
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
            self.status_callback("ℹ️ 내장 초저지연(120 FPS) 화면 공유 서버로 동작합니다.")

    def get_connection_info(self):
        """게스트에게 전달할 연결 정보를 반환."""
        return {
            "host_ip": self.local_ip,
            "input_port": self.input_port,
            "stream_port": self.stream_port,
            "sunshine_available": self._sunshine_proc is not None,
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
