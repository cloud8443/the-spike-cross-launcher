import asyncio
import json
import logging
import uuid

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("SpikeServer")

# 전역 상태 관리
connected_clients = {}  # client_id -> {'writer': StreamWriter, 'name': str, 'room_id': str or None}
rooms = {}  # room_id -> {'id': str, 'name': str, 'host_id': str, 'guest_id': str or None, 'status': str}

def get_room_list_payload():
    room_list = []
    for r_id, r in rooms.items():
        host_name = connected_clients.get(r['host_id'], {}).get('name', '알 수 없음')
        guest_name = connected_clients.get(r['guest_id'], {}).get('name', '') if r['guest_id'] else ''
        room_list.append({
            'room_id': r_id,
            'room_name': r['name'],
            'host_name': host_name,
            'guest_name': guest_name,
            'user_count': 2 if r['guest_id'] else 1,
            'max_users': 2,
            'status': r['status']
        })
    return {'type': 'room_list', 'rooms': room_list, 'online_count': len(connected_clients)}

async def send_json(writer, data):
    try:
        payload = json.dumps(data, ensure_ascii=False) + '\n'
        writer.write(payload.encode('utf-8'))
        await writer.drain()
    except Exception as e:
        logger.debug(f"전송 실패: {e}")

async def broadcast_lobby(data):
    # 로비(방에 들어가 있지 않거나 방 목록을 수신해야 하는 모든 클라이언트)에 브로드캐스트
    dead_clients = []
    for c_id, client in list(connected_clients.items()):
        try:
            await send_json(client['writer'], data)
        except Exception:
            dead_clients.append(c_id)

async def handle_client(reader, writer):
    client_id = str(uuid.uuid4())[:8]
    client_name = f"플레이어_{client_id}"
    connected_clients[client_id] = {
        'writer': writer,
        'name': client_name,
        'room_id': None
    }
    
    addr = writer.get_extra_info('peername')
    logger.info(f"[+] 클라이언트 접속: {client_name} ({addr})")

    # 접속 환영 및 초기 방 목록 전송
    await send_json(writer, {
        'type': 'welcome',
        'client_id': client_id,
        'name': client_name
    })
    await send_json(writer, get_room_list_payload())

    try:
        while True:
            line = await reader.readline()
            if not line:
                break

            line_str = line.decode('utf-8').strip()
            if not line_str:
                continue

            try:
                msg = json.loads(line_str)
            except json.JSONDecodeError:
                continue

            action = msg.get('action')

            # 1. 닉네임 설정
            if action == 'set_name':
                new_name = msg.get('name', '').strip()
                if new_name:
                    connected_clients[client_id]['name'] = new_name
                    client_name = new_name
                    await send_json(writer, {'type': 'name_updated', 'name': client_name})

            # 2. 방 목록 새로고침 요청
            elif action == 'get_rooms':
                await send_json(writer, get_room_list_payload())

            # 3. 방 생성
            elif action == 'create_room':
                # 이미 방에 참여 중인 경우 기존 방 정리
                curr_room_id = connected_clients[client_id]['room_id']
                if curr_room_id and curr_room_id in rooms:
                    await leave_current_room(client_id)

                room_name = msg.get('room_name', f"{client_name}의 방").strip()
                if not room_name:
                    room_name = f"{client_name}의 방"

                new_room_id = str(uuid.uuid4())[:6]
                rooms[new_room_id] = {
                    'id': new_room_id,
                    'name': room_name,
                    'host_id': client_id,
                    'guest_id': None,
                    'status': 'waiting'
                }
                connected_clients[client_id]['room_id'] = new_room_id

                logger.info(f"[방 생성] '{room_name}' (ID: {new_room_id}) by {client_name}")

                await send_json(writer, {
                    'type': 'room_created',
                    'room_id': new_room_id,
                    'room_name': room_name,
                    'role': 'host'
                })
                # 모든 유저에게 방 목록 업데이트
                await broadcast_lobby(get_room_list_payload())

            # 4. 방 입장
            elif action == 'join_room':
                target_room_id = msg.get('room_id')
                if target_room_id not in rooms:
                    await send_json(writer, {'type': 'error', 'message': '존재하지 않는 방입니다.'})
                    continue

                target_room = rooms[target_room_id]
                if target_room['guest_id'] is not None:
                    await send_json(writer, {'type': 'error', 'message': '이미 방이 가득 찼습니다.'})
                    continue

                if target_room['host_id'] == client_id:
                    await send_json(writer, {'type': 'error', 'message': '자신이 만든 방입니다.'})
                    continue

                # 입장 처리
                target_room['guest_id'] = client_id
                target_room['status'] = 'ready'
                connected_clients[client_id]['room_id'] = target_room_id

                host_info = connected_clients.get(target_room['host_id'])

                logger.info(f"[방 입장] '{target_room['name']}'에 {client_name} 입장 완료 (호스트: {host_info['name']})")

                # 참가자에게 알림
                await send_json(writer, {
                    'type': 'room_joined',
                    'room_id': target_room_id,
                    'room_name': target_room['name'],
                    'role': 'guest',
                    'host_name': host_info['name'] if host_info else '방장'
                })

                # 방장에게 알림
                if host_info:
                    await send_json(host_info['writer'], {
                        'type': 'peer_joined',
                        'peer_name': client_name
                    })

                # 로비 유저들에게 방 목록 갱신 알림
                await broadcast_lobby(get_room_list_payload())

            # 5. 대기실 채팅
            elif action == 'chat':
                room_id = connected_clients[client_id]['room_id']
                if not room_id or room_id not in rooms:
                    await send_json(writer, {'type': 'error', 'message': '입장한 방이 없습니다.'})
                    continue

                room = rooms[room_id]
                chat_text = msg.get('message', '').strip()
                if not chat_text:
                    continue

                # 상대방 찾기
                peer_id = room['guest_id'] if room['host_id'] == client_id else room['host_id']
                if peer_id and peer_id in connected_clients:
                    await send_json(connected_clients[peer_id]['writer'], {
                        'type': 'chat_message',
                        'sender': client_name,
                        'message': chat_text
                    })

            # 6. 방 나가기
            elif action == 'leave_room':
                await leave_current_room(client_id)

    except Exception as e:
        logger.warning(f"통신 중 예외 발생 ({client_name}): {e}")
    finally:
        logger.info(f"[-] 클라이언트 퇴장: {client_name}")
        await leave_current_room(client_id)
        if client_id in connected_clients:
            del connected_clients[client_id]
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass
        await broadcast_lobby(get_room_list_payload())

async def leave_current_room(client_id):
    if client_id not in connected_clients:
        return

    room_id = connected_clients[client_id]['room_id']
    if not room_id or room_id not in rooms:
        connected_clients[client_id]['room_id'] = None
        return

    room = rooms[room_id]
    client_name = connected_clients[client_id]['name']

    # 1. 방장이 나간 경우 -> 방 폭파 및 참가자 퇴장
    if room['host_id'] == client_id:
        logger.info(f"[방 폭파] 방장 {client_name} 퇴장으로 '{room['name']}' 삭제")
        guest_id = room['guest_id']
        if guest_id and guest_id in connected_clients:
            connected_clients[guest_id]['room_id'] = None
            await send_json(connected_clients[guest_id]['writer'], {
                'type': 'room_closed',
                'reason': '방장이 방을 나갔습니다.'
            })
        del rooms[room_id]

    # 2. 참가자가 나간 경우 -> 방장에게 알림 후 방 대기 상태로 변경
    elif room['guest_id'] == client_id:
        logger.info(f"[참가자 퇴장] '{room['name']}'에서 {client_name} 퇴장")
        room['guest_id'] = None
        room['status'] = 'waiting'
        host_id = room['host_id']
        if host_id and host_id in connected_clients:
            await send_json(connected_clients[host_id]['writer'], {
                'type': 'peer_left',
                'reason': f'{client_name}님이 퇴장하셨습니다.'
            })

    connected_clients[client_id]['room_id'] = None
    await broadcast_lobby(get_room_list_payload())

async def main():
    HOST = '0.0.0.0'
    PORT = 5555
    server = await asyncio.start_server(handle_client, HOST, PORT)
    logger.info(f"==================================================")
    logger.info(f" [The Spike Cross] 매칭 및 중계 서버 가동 시작")
    logger.info(f" 포트: {PORT} (TCP)")
    logger.info(f"==================================================")

    async with server:
        await server.serve_forever()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("서버를 종료합니다.")
