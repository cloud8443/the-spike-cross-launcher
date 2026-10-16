import socket
import json
import time
import sys

DEFAULT_HOST = "146.56.101.107"
DEFAULT_PORT = 5555

def main():
    host = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].isalnum() else DEFAULT_HOST
    port = DEFAULT_PORT

    print(f"[*] 서버 연결 시도: {host}:{port}...", flush=True)
    s = socket.socket()
    s.connect((host, port))
    s.settimeout(60.0)

    buffer = ""
    def send(action, **kwargs):
        payload = {'action': action, **kwargs}
        s.sendall((json.dumps(payload, ensure_ascii=False) + '\n').encode('utf-8'))

    # 닉네임 설정
    send('set_name', name='테스트_봇(2P)')
    time.sleep(0.3)

    joined = False
    start_time = time.time()
    last_poll = 0

    print("[*] 봇 대기 중: 개설된 방을 감지하면 자동으로 입장합니다...", flush=True)

    while time.time() - start_time < 900:  # 15분 동안 유지
        # 방에 안 들어갔으면 2초마다 방 목록 폴링
        if not joined and time.time() - last_poll > 2.0:
            send('get_rooms')
            last_poll = time.time()

        try:
            data = s.recv(2048)
            if not data:
                break
        except socket.timeout:
            continue
        except Exception:
            break

        buffer += data.decode('utf-8', errors='ignore')
        while '\n' in buffer:
            line, buffer = buffer.split('\n', 1)
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except Exception:
                continue

            mtype = msg.get('type')

            if mtype == 'room_list' and not joined:
                rooms = msg.get('rooms', [])
                room_to_join = None
                for r in rooms:
                    if r.get('status') == 'waiting' and r.get('user_count') < 2:
                        room_to_join = r.get('room_id')
                        break
                if room_to_join:
                    print(f"[BOT] 대기 중인 방 발견! ID={room_to_join} 입장 시도...", flush=True)
                    send('join_room', room_id=room_to_join)
                    joined = True

            elif mtype == 'room_joined':
                room_name = msg.get('room_name')
                print(f"[BOT] 방 입장 성공: {room_name}", flush=True)
                time.sleep(0.5)
                send('chat', message="안녕하세요! 테스트 봇(2P)이 입장했습니다! 🏐")
                time.sleep(0.8)
                send('chat', message="2명이 모였으므로 상단에 [🚀 내가 호스트로 시작하기] 버튼이 나타났습니다!")

            elif mtype == 'room_ready_for_host':
                print(f"[BOT] 2인 충원 완료! 호스트 시작 가능 상태 감지.", flush=True)

            elif mtype == 'session_started':
                role = msg.get('role')
                host_name = msg.get('host')
                print(f"[BOT] 세션 시작 수신: 역할={role}, 호스트={host_name}", flush=True)
                time.sleep(0.5)
                send('chat', message=f"[봇] {host_name}님이 호스트로 시작하셨습니다! 게스트 모드로 대기 중입니다.")

            elif mtype == 'signal_exchange':
                payload = msg.get('payload', {})
                print(f"[BOT] P2P 시그널링 수신: {payload}", flush=True)
                time.sleep(0.5)
                send('chat', message=f"[봇] P2P 시그널링 정보 수신 완료 ({payload.get('host_ip')}:{payload.get('input_port')})!")

            elif mtype == 'chat_message':
                sender = msg.get('sender')
                text = msg.get('message')
                print(f"[BOT] 채팅 수신 from {sender}: {text}", flush=True)
                time.sleep(0.6)
                send('chat', message=f"'{text}' 메시지 잘 받았습니다! 👍")

            elif mtype in ('peer_left', 'room_closed'):
                print(f"[BOT] 상대방 퇴장 또는 방 종료: {mtype}", flush=True)
                joined = False
                # 다시 로비에서 대기
                send('get_rooms')

    s.close()
    print("[BOT] 봇 종료.", flush=True)

if __name__ == '__main__':
    main()
