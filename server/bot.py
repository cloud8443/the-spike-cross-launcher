import socket
import json
import time
import sys

def main():
    s = socket.socket()
    s.connect(('127.0.0.1', 5555))
    s.settimeout(60.0)
    
    buffer = ""
    def send(action, **kwargs):
        payload = {'action': action, **kwargs}
        s.sendall((json.dumps(payload, ensure_ascii=False) + '\n').encode('utf-8'))

    # 닉네임 설정
    send('set_name', name='AI_테스트봇')
    time.sleep(0.3)

    target_id = sys.argv[1] if len(sys.argv) > 1 else None
    send('get_rooms')
    
    joined = False
    start_time = time.time()

    while time.time() - start_time < 300:  # 5분 동안 유지
        try:
            data = s.recv(2048)
            if not data:
                break
        except socket.timeout:
            continue

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
                    if r.get('status') == 'waiting' and (not target_id or r.get('room_id') == target_id):
                        room_to_join = r.get('room_id')
                        break
                if room_to_join:
                    print(f"[BOT] 방 '{room_to_join}' 입장 시도...")
                    send('join_room', room_id=room_to_join)
                    joined = True

            elif mtype == 'room_joined':
                print(f"[BOT] 방 입장 성공: {msg.get('room_name')}")
                time.sleep(0.5)
                send('chat', message="안녕하세요! 원격 클라우드 서버에서 접속한 AI 가상 유저입니다! 🎉")
                time.sleep(1.0)
                send('chat', message="실시간 온라인 연동과 대기실 채팅이 완벽하게 정상 작동 중입니다! 👍")
                time.sleep(1.0)
                send('chat', message="채팅창에 아무 말이나 입력해 보세요! 바로 답장해 드릴게요. 😊")

            elif mtype == 'chat_message':
                sender = msg.get('sender')
                text = msg.get('message')
                print(f"[BOT] 수신: {sender}: {text}")
                time.sleep(0.8)
                reply = f"[봇] '{text}' 말씀 잘 전달받았습니다! 🚀"
                send('chat', message=reply)

            elif mtype in ('peer_left', 'room_closed'):
                print(f"[BOT] 방 종료 이벤트: {mtype}")
                s.close()
                return

    s.close()

if __name__ == '__main__':
    main()
