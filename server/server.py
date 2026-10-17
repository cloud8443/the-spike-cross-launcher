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
# client_id -> {'writer': StreamWriter, 'name': str, 'room_id': str or None, 'ip': str, 'local_ip': str}
connected_clients = {}
# room_id -> {'id': str, 'name': str, 'host_id': str, 'host_ip': str, 'guest_id': str or None, 'status': str, 'streaming_host': str or None}
rooms = {}

def get_room_list_payload():
    room_list = []
    for r_id, r in list(rooms.items()):
        host_client = connected_clients.get(r['host_id'], {})
        host_name = host_client.get('name', '알 수 없음')
        host_ip = r.get('host_ip') or host_client.get('local_ip') or host_client.get('ip', '')
        guest_name = connected_clients.get(r['guest_id'], {}).get('name', '') if r['guest_id'] else ''
        user_count = 2 if r['guest_id'] else 1

        room_list.append({
            # PC 런처 규격 필드
            'room_id': r_id,
            'room_name': r['name'],
            'host_name': host_name,
            'guest_name': guest_name,
            'user_count': user_count,
            'max_users': 2,
            'status': r['status'],
            # 안드로이드 & 공통 호환 필드
            'code': r_id,
            'title': r['name'],
            'host_ip': host_ip,
            'players': user_count
        })
    return {
        'type': 'room_list',
        'action': 'ROOM_LIST',
        'rooms': room_list,
        'online_count': len(connected_clients)
    }

async def send_json(writer, data):
    try:
        payload = json.dumps(data, ensure_ascii=False) + '\n'
        writer.write(payload.encode('utf-8'))
        await writer.drain()
    except Exception as e:
        logger.debug(f"전송 실패: {e}")

async def broadcast_lobby(data):
    dead_clients = []
    for c_id, client in list(connected_clients.items()):
        try:
            await send_json(client['writer'], data)
        except Exception:
            dead_clients.append(c_id)

def find_room_by_id_or_code(target_id: str):
    if not target_id:
        return None
    target_id_clean = target_id.strip().lower()
    for r_id, r in rooms.items():
        if r_id.lower() == target_id_clean:
            return r_id
    return None

async def handle_client(reader, writer):
    client_id = str(uuid.uuid4())[:8]
    client_name = f"플레이어_{client_id[:4]}"
    addr = writer.get_extra_info('peername')
    peer_ip = addr[0] if addr else "127.0.0.1"

    connected_clients[client_id] = {
        'writer': writer,
        'name': client_name,
        'room_id': None,
        'ip': peer_ip,
        'local_ip': ''
    }

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

            line_str = line.decode('utf-8', errors='ignore').strip()
            if not line_str:
                continue

            try:
                msg = json.loads(line_str)
            except json.JSONDecodeError:
                continue

            raw_action = msg.get('action') or msg.get('type') or ''
            action = raw_action.strip().lower()

            # 0. Ping / Heartbeat 응답
            if action == 'ping':
                await send_json(writer, {'type': 'pong', 'online_count': len(connected_clients)})

            # 1. 닉네임 설정
            elif action == 'set_name':
                new_name = msg.get('name', '').strip()
                if new_name:
                    connected_clients[client_id]['name'] = new_name
                    client_name = new_name
                    await send_json(writer, {'type': 'name_updated', 'name': client_name})

            # 2. 방 목록 새로고침 요청 (PC: get_rooms / Android: list_rooms 호환)
            elif action in ('get_rooms', 'list_rooms'):
                await send_json(writer, get_room_list_payload())

            # 3. 방 생성
            elif action == 'create_room':
                curr_room_id = connected_clients[client_id]['room_id']
                if curr_room_id and curr_room_id in rooms:
                    await leave_current_room(client_id)

                room_name = msg.get('room_name') or msg.get('title') or f"{client_name}의 방"
                room_name = room_name.strip() or f"{client_name}의 방"

                local_ip = msg.get('local_ip', '').strip()
                if local_ip:
                    connected_clients[client_id]['local_ip'] = local_ip

                host_ip_to_use = local_ip if local_ip else peer_ip

                new_room_id = str(uuid.uuid4())[:6]
                rooms[new_room_id] = {
                    'id': new_room_id,
                    'name': room_name,
                    'host_id': client_id,
                    'host_ip': host_ip_to_use,
                    'guest_id': None,
                    'status': 'waiting',
                    'streaming_host': None
                }
                connected_clients[client_id]['room_id'] = new_room_id

                logger.info(f"[방 생성] '{room_name}' (ID: {new_room_id}, IP: {host_ip_to_use}) by {client_name}")

                await send_json(writer, {
                    'type': 'room_created',
                    'room_id': new_room_id,
                    'code': new_room_id,
                    'room_name': room_name,
                    'title': room_name,
                    'host_ip': host_ip_to_use,
                    'role': 'host'
                })
                await broadcast_lobby(get_room_list_payload())

            # 4. 방 입장 (PC: join_room / Android: JOIN_ROOM 호환)
            elif action == 'join_room':
                raw_target_id = msg.get('room_id') or msg.get('code') or ''
                target_room_id = find_room_by_id_or_code(raw_target_id)

                if not target_room_id or target_room_id not in rooms:
                    await send_json(writer, {'type': 'error', 'action': 'ERROR', 'message': '존재하지 않는 방입니다.'})
                    continue

                target_room = rooms[target_room_id]
                if target_room['guest_id'] is not None and target_room['guest_id'] != client_id:
                    await send_json(writer, {'type': 'error', 'action': 'ERROR', 'message': '이미 방이 가득 찼습니다.'})
                    continue

                if target_room['host_id'] == client_id:
                    await send_json(writer, {'type': 'error', 'action': 'ERROR', 'message': '자신이 만든 방입니다.'})
                    continue

                # 기존에 다른 방에 있었다면 정리
                curr_room_id = connected_clients[client_id]['room_id']
                if curr_room_id and curr_room_id != target_room_id:
                    await leave_current_room(client_id)

                target_room['guest_id'] = client_id
                target_room['status'] = 'ready'
                connected_clients[client_id]['room_id'] = target_room_id

                host_info = connected_clients.get(target_room['host_id'])
                host_name = host_info['name'] if host_info else '방장'
                host_ip = target_room.get('host_ip') or (host_info.get('local_ip') or host_info.get('ip', '') if host_info else '')

                logger.info(f"[방 입장] '{target_room['name']}'({target_room_id})에 {client_name} 입장 완료 (호스트: {host_name})")

                # 참가자(PC 또는 안드로이드)에게 알림
                await send_json(writer, {
                    'type': 'room_joined',
                    'action': 'JOIN_SUCCESS',
                    'room_id': target_room_id,
                    'code': target_room_id,
                    'room_name': target_room['name'],
                    'title': target_room['name'],
                    'role': 'guest',
                    'host_name': host_name,
                    'host_ip': host_ip,
                    'auto_start': target_room.get('status') == 'streaming'
                })

                # 방장에게 알림
                if host_info:
                    await send_json(host_info['writer'], {
                        'type': 'peer_joined',
                        'peer_name': client_name
                    })

                await broadcast_lobby(get_room_list_payload())

                # 2인 충원 완료 시 양쪽 클라이언트에 호스트 시작 버튼 활성화 알림
                room_users = [target_room['host_id'], target_room['guest_id']]
                for uid in room_users:
                    if uid in connected_clients:
                        await send_json(connected_clients[uid]['writer'], {
                            'type': 'room_ready_for_host',
                            'room_id': target_room_id,
                            'host_ip': host_ip,
                            'users': [connected_clients[u]['name'] for u in room_users if u in connected_clients]
                        })

            # 5. 스트리밍 호스트 권한 요청 (첫 번째로 누른 유저 또는 방장이 호스트)
            elif action in ('claim_host', 'start_stream', 'game_start'):
                room_id = find_room_by_id_or_code(msg.get('room_id')) or connected_clients[client_id].get('room_id')
                if not room_id or room_id not in rooms:
                    await send_json(writer, {'type': 'error', 'action': 'ERROR', 'message': '방을 찾을 수 없습니다.'})
                    continue

                room = rooms[room_id]
                if room.get('streaming_host') is not None:
                    await send_json(writer, {'type': 'error', 'action': 'ERROR', 'message': '이미 호스트가 결정되었습니다.'})
                    continue

                if room['guest_id'] is None:
                    await send_json(writer, {'type': 'error', 'action': 'ERROR', 'message': '아직 상대방이 입장하지 않았습니다.'})
                    continue

                room['streaming_host'] = client_id
                room['status'] = 'streaming'
                streaming_host_name = connected_clients[client_id]['name']
                host_ip = msg.get('host_ip') or room.get('host_ip') or connected_clients[client_id].get('local_ip') or connected_clients[client_id].get('ip', '')
                room['host_ip'] = host_ip

                if room['host_id'] == client_id:
                    streaming_guest_id = room['guest_id']
                else:
                    streaming_guest_id = room['host_id']
                streaming_guest_name = connected_clients.get(streaming_guest_id, {}).get('name', '상대방')

                logger.info(f"[스트리밍 시작] 방 '{room['name']}' - 호스트: {streaming_host_name}({host_ip}), 게스트: {streaming_guest_name}")

                await send_json(connected_clients[client_id]['writer'], {
                    'type': 'session_started',
                    'action': 'GAME_START',
                    'room_id': room_id,
                    'role': 'streaming_host',
                    'host': streaming_host_name,
                    'host_ip': host_ip,
                    'guest': streaming_guest_name,
                    'relay_server': '146.56.101.107:7777'
                })

                if streaming_guest_id in connected_clients:
                    await send_json(connected_clients[streaming_guest_id]['writer'], {
                        'type': 'session_started',
                        'action': 'GAME_START',
                        'room_id': room_id,
                        'role': 'streaming_guest',
                        'host': streaming_host_name,
                        'host_ip': host_ip,
                        'guest': streaming_guest_name,
                        'relay_server': '146.56.101.107:7777'
                    })

                await broadcast_lobby(get_room_list_payload())

            # 6. P2P 시그널링 정보 교환 중계 (호스트 IP / 포트 전달)
            elif action == 'signal_exchange':
                room_id = find_room_by_id_or_code(msg.get('room_id')) or connected_clients[client_id].get('room_id')
                if not room_id or room_id not in rooms:
                    continue

                room = rooms[room_id]
                payload = msg.get('payload', {})

                # 호스트가 보낸 host_info에 IP가 있으면 방 정보에도 최신화
                if isinstance(payload, dict) and payload.get('type') == 'host_info':
                    sig_ip = payload.get('host_ip')
                    if sig_ip and sig_ip != '127.0.0.1':
                        room['host_ip'] = sig_ip

                target_id = room['guest_id'] if room['host_id'] == client_id else room['host_id']
                if target_id and target_id in connected_clients:
                    await send_json(connected_clients[target_id]['writer'], {
                        'type': 'signal_exchange',
                        'action': 'SIGNAL_EXCHANGE',
                        'from': client_name,
                        'host_ip': room.get('host_ip', ''),
                        'payload': payload
                    })

            # 7. 채팅
            elif action == 'chat':
                room_id = connected_clients[client_id]['room_id']
                if not room_id or room_id not in rooms:
                    await send_json(writer, {'type': 'error', 'action': 'ERROR', 'message': '입장한 방이 없습니다.'})
                    continue

                room = rooms[room_id]
                chat_text = msg.get('message', '').strip()
                if not chat_text:
                    continue

                peer_id = room['guest_id'] if room['host_id'] == client_id else room['host_id']
                if peer_id and peer_id in connected_clients:
                    await send_json(connected_clients[peer_id]['writer'], {
                        'type': 'chat_message',
                        'sender': client_name,
                        'message': chat_text
                    })

            # 8. 방 나가기
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
                'action': 'ROOM_CLOSED',
                'reason': '방장이 방을 나갔습니다.'
            })
        del rooms[room_id]

    # 2. 참가자가 나간 경우 -> 방장에게 알림 후 방 대기 상태로 변경
    elif room['guest_id'] == client_id:
        logger.info(f"[참가자 퇴장] '{room['name']}'에서 {client_name} 퇴장")
        room['guest_id'] = None
        room['status'] = 'waiting'
        room['streaming_host'] = None
        host_id = room['host_id']
        if host_id and host_id in connected_clients:
            await send_json(connected_clients[host_id]['writer'], {
                'type': 'peer_left',
                'action': 'PEER_LEFT',
                'reason': f'{client_name}님이 퇴장하셨습니다.'
            })

    connected_clients[client_id]['room_id'] = None
    await broadcast_lobby(get_room_list_payload())

async def main():
    HOST = '0.0.0.0'
    PORT = 5555
    server = await asyncio.start_server(handle_client, HOST, PORT)
    logger.info("==================================================")
    logger.info(" [The Spike Cross] 매칭 및 중계 서버 가동 시작")
    logger.info(f" 포트: {PORT} (TCP) - PC & Android 통합 프로토콜 지원")
    logger.info("==================================================")

    async with server:
        await server.serve_forever()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("서버를 종료합니다.")
