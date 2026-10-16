import socket
import json
import time
import sys

def main():
    s1 = socket.socket()
    s1.connect(('146.56.101.107', 5555))
    s2 = socket.socket()
    s2.connect(('146.56.101.107', 5555))

    class BufferedSocket:
        def __init__(self, s):
            self.s = s
            self.buf = ""
            self.s.settimeout(5.0)

        def send(self, data):
            payload = json.dumps(data, ensure_ascii=False) + '\n'
            self.s.sendall(payload.encode('utf-8'))

        def recv_json(self):
            while '\n' not in self.buf:
                data = self.s.recv(4096)
                if not data:
                    raise ConnectionError("Disconnected")
                self.buf += data.decode('utf-8')
            line, self.buf = self.buf.split('\n', 1)
            return json.loads(line)

    c1 = BufferedSocket(s1)
    c2 = BufferedSocket(s2)

    # 1. Welcome & Initial room list
    w1 = c1.recv_json()
    r1 = c1.recv_json()
    w2 = c2.recv_json()
    r2 = c2.recv_json()
    print(f"[OK] C1 Welcome: {w1['name']}, C2 Welcome: {w2['name']}", flush=True)

    # 2. Set Names
    c1.send({'action': 'set_name', 'name': '호스트_유저'})
    c2.send({'action': 'set_name', 'name': '게스트_유저'})
    time.sleep(0.2)

    # 3. C1 creates room
    c1.send({'action': 'create_room', 'room_name': '2인_원격_매칭방'})
    msg = c1.recv_json()
    while msg.get('type') != 'room_created':
        msg = c1.recv_json()
    room_id = msg['room_id']
    print(f"[OK] C1 방 개설 성공: {room_id}", flush=True)

    # 4. C2 joins room
    time.sleep(0.2)
    c2.send({'action': 'join_room', 'room_id': room_id})
    print(f"[OK] C2 방 입장 요청: {room_id}", flush=True)

    # Both should get room_ready_for_host
    c1_ready = False
    c2_ready = False

    for _ in range(5):
        m = c1.recv_json()
        if m.get('type') == 'room_ready_for_host':
            c1_ready = True
            print(f"[OK] C1 호스트 버튼 활성화 신호 수신: {m['type']} (유저: {m.get('users')})", flush=True)
            break

    for _ in range(5):
        m = c2.recv_json()
        if m.get('type') == 'room_ready_for_host':
            c2_ready = True
            print(f"[OK] C2 호스트 버튼 활성화 신호 수신: {m['type']} (유저: {m.get('users')})", flush=True)
            break

    assert c1_ready and c2_ready, "room_ready_for_host not received by both clients!"

    # 5. C1 claims host
    print("[+] C1이 [내가 호스트로 시작하기] 버튼 클릭 (claim_host)", flush=True)
    c1.send({'action': 'claim_host', 'room_id': room_id})

    # Both should receive session_started
    c1_session = None
    c2_session = None

    for _ in range(5):
        m = c1.recv_json()
        if m.get('type') == 'session_started':
            c1_session = m
            print(f"[OK] C1 세션 시작 수신: 역할={m['role']}, 호스트={m['host']}, 게스트={m['guest']}", flush=True)
            break

    for _ in range(5):
        m = c2.recv_json()
        if m.get('type') == 'session_started':
            c2_session = m
            print(f"[OK] C2 세션 시작 수신: 역할={m['role']}, 호스트={m['host']}, 게스트={m['guest']}", flush=True)
            break

    assert c1_session['role'] == 'streaming_host'
    assert c2_session['role'] == 'streaming_guest'

    # 6. C1 sends P2P signaling (host_info) to C2
    c1.send({
        'action': 'signal_exchange',
        'room_id': room_id,
        'payload': {
            'type': 'host_info',
            'host_ip': '146.56.101.107',
            'input_port': 47990
        }
    })

    # C2 receives signal_exchange
    c2_signal = None
    for _ in range(5):
        m = c2.recv_json()
        if m.get('type') == 'signal_exchange':
            c2_signal = m
            print(f"[OK] C2 P2P 시그널링 수신: {m['payload']}", flush=True)
            break

    assert c2_signal is not None

    s1.close()
    s2.close()
    print("\n🎉 [성공] 2인 매칭 -> 호스트 버튼 활성화 -> 세션 시작 -> P2P 시그널링 전 과정 통과!", flush=True)

if __name__ == '__main__':
    main()
