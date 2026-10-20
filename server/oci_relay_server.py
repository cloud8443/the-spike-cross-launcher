"""
oci_relay_server.py
OCI 서버(146.56.101.107)에서 실행되는 초저지연 P2P 하이브리드 중계 서버.
- UDP 47990: STUN(공인 IP:Port 매핑) + UDP 홀 펀칭 중재 + 무파싱(Zero-parse) UDP 고속 릴레이
- TCP 47999(Host) <-> TCP 47998(Guest): Reverse-TCP 무지연 비디오 스트림 스플라이서

실행 방법 (OCI 서버에서):
  nohup python3 oci_relay_server.py > /tmp/relay.log 2>&1 &
"""

import asyncio
import json
import logging
import socket
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("OCIRelay")

UDP_PORT = 47990
TCP_GUEST_STREAM_PORT = 47998
TCP_HOST_TUNNEL_PORT = 47999


class HybridUDPProtocol(asyncio.DatagramProtocol):
    """
    단일 UDP 포트(47990)에서 STUN, 홀 펀칭 시그널링, 폴백 릴레이를 동시에 처리.
    일반 게임 입력 패킷은 JSON 파싱 없이 O(1) 해시테이블 조회로 즉시 포워딩합니다.
    """

    def __init__(self):
        self.transport = None
        # room_id -> {"host_pub": (ip, port), "host_loc": (ip, port),
        #             "guest_pub": (ip, port), "guest_loc": (ip, port), "ts": float}
        self.rooms = {}
        # (ip, port) -> target (ip, port): JSON 파싱 없는 초고속 포워딩 테이블
        self.forward_map = {}
        self.latest_room_id = "default"
        self.latest_host_pub = None

    def connection_made(self, transport):
        self.transport = transport
        sock = transport.get_extra_info("socket")
        if sock:
            # UDP 수신/송신 커널 버퍼 확장 (패킷 드롭 방지)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4 * 1024 * 1024)
        logger.info(f"✅ UDP STUN & 초저지연 릴레이 서버 가동 (포트 {UDP_PORT})")

    def datagram_received(self, data: bytes, addr: tuple):
        # [초고속 경로] STUN 제어 패킷이 아니면 JSON 파싱 없이 즉시 포워딩 (0.05ms 미만)
        if b'"stun_' not in data and b'"peer_info"' not in data:
            target = self.forward_map.get(addr)
            if target:
                self.transport.sendto(data, target)
                return
            # 아직 stun 등록 안 한 클라이언트 자동 매핑 시도
            if self.latest_room_id in self.rooms:
                host_pub = self.rooms[self.latest_room_id].get("host_pub")
                if host_pub and host_pub != addr:
                    self.forward_map[addr] = host_pub
                    self.forward_map[host_pub] = addr
                    self.transport.sendto(data, host_pub)
                    return
            # 최신 활성 호스트로 글로벌 폴백 포워딩
            if self.latest_host_pub and self.latest_host_pub != addr:
                self.forward_map[addr] = self.latest_host_pub
                self.transport.sendto(data, self.latest_host_pub)
            return

        # [제어 경로] STUN 등록 및 홀 펀칭 좌표 교환
        try:
            pkt = json.loads(data.decode("utf-8"))
            pkt_type = pkt.get("type")
            room_id = str(pkt.get("room_id") or "default")
            self.latest_room_id = room_id

            room = self.rooms.setdefault(room_id, {})
            room["ts"] = time.time()

            if pkt_type == "stun_host":
                old_pub = room.get("host_pub")
                if old_pub and old_pub != addr:
                    self.forward_map.pop(old_pub, None)

                room["host_pub"] = addr
                room["host_loc"] = (pkt.get("local_ip", "127.0.0.1"), int(pkt.get("local_port", UDP_PORT)))
                self.latest_host_pub = addr

                # 호스트에게 자신의 공인 IP/Port 응답
                ack = json.dumps({
                    "type": "stun_ack",
                    "public_ip": addr[0],
                    "public_port": addr[1]
                }).encode("utf-8")
                self.transport.sendto(ack, addr)

                # 이미 게스트가 대기 중이면 양측에 홀 펀칭 좌표 전송
                if "guest_pub" in room:
                    self._bind_and_notify_peers(room_id, room)

            elif pkt_type == "stun_guest":
                old_pub = room.get("guest_pub")
                if old_pub and old_pub != addr:
                    self.forward_map.pop(old_pub, None)

                room["guest_pub"] = addr
                room["guest_loc"] = (pkt.get("local_ip", "127.0.0.1"), int(pkt.get("local_port", 0)))

                ack = json.dumps({
                    "type": "stun_ack",
                    "public_ip": addr[0],
                    "public_port": addr[1]
                }).encode("utf-8")
                self.transport.sendto(ack, addr)

                if "host_pub" in room:
                    self._bind_and_notify_peers(room_id, room)

        except Exception as e:
            logger.debug(f"STUN 패킷 처리 오류: {e}")

    def _bind_and_notify_peers(self, room_id: str, room: dict):
        host_pub = room["host_pub"]
        guest_pub = room["guest_pub"]
        host_loc = room.get("host_loc", ("127.0.0.1", UDP_PORT))
        guest_loc = room.get("guest_loc", ("127.0.0.1", 0))

        # 즉시 릴레이 테이블 연결 (홀 펀칭 성공 전에도 0ms 대기로 입력 전달)
        self.forward_map[guest_pub] = host_pub
        self.forward_map[host_pub] = guest_pub

        # 호스트에게 게스트의 공인/사설 좌표 전달 (홀 펀칭 트리거)
        to_host = json.dumps({
            "type": "peer_info",
            "room_id": room_id,
            "public_ip": guest_pub[0],
            "public_port": guest_pub[1],
            "local_ip": guest_loc[0],
            "local_port": guest_loc[1],
        }).encode("utf-8")

        # 게스트에게 호스트의 공인/사설 좌표 전달 (홀 펀칭 트리거)
        to_guest = json.dumps({
            "type": "peer_info",
            "room_id": room_id,
            "public_ip": host_pub[0],
            "public_port": host_pub[1],
            "local_ip": host_loc[0],
            "local_port": host_loc[1],
        }).encode("utf-8")

        self.transport.sendto(to_host, host_pub)
        self.transport.sendto(to_guest, guest_pub)
        logger.info(f"🔗 [Room {room_id}] 홀 펀칭 & 릴레이 매칭 완료: Host({host_pub}) <-> Guest({guest_pub})")


class VideoStreamSplicer:
    """
    호스트의 아웃바운드 터널(47999)과 게스트의 스트림 접속(47998)을
    TCP_NODELAY 상태로 즉시 스플라이싱(직결)하는 무지연 비디오 중계기.
    """

    def __init__(self):
        # 대기 중인 호스트 역방향 소켓 스택 (LIFO: 가장 최신의 살아있는 호스트 터널 최우선 매칭)
        self.host_waiters = []
        self.new_host_event = asyncio.Event()

    @staticmethod
    def _tune_low_latency_socket(writer: asyncio.StreamWriter):
        sock = writer.get_extra_info("socket")
        if sock:
            try:
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                # 버퍼블로트(Bufferbloat) 원천 차단을 위해 릴레이 커널 버퍼를 32KB(약 1.5 프레임)로 제한
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 32768)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 32768)
            except Exception:
                pass

    def _pop_healthy_host_tunnel(self):
        """가장 최근에 연결된 살아있는 호스트 터널을 LIFO로 꺼내고, 죽은 구형 터널은 정리."""
        while self.host_waiters:
            r, w = self.host_waiters.pop()
            if not w.is_closing() and not r.at_eof():
                # 남은 대기 터널은 최대 2개까지만 유지하고 오래된 것은 닫음
                while len(self.host_waiters) > 2:
                    _, old_w = self.host_waiters.pop(0)
                    try:
                        old_w.close()
                    except Exception:
                        pass
                return r, w
            else:
                try:
                    w.close()
                except Exception:
                    pass
        return None, None

    async def handle_host_tunnel(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """호스트가 47999 포트로 연결하여 대기."""
        self._tune_low_latency_socket(writer)
        addr = writer.get_extra_info("peername")
        try:
            # 호스트 등록 헤더 수신 ("HOST:room_id\n")
            line = await asyncio.wait_for(reader.readline(), timeout=10.0)
            if not line.startswith(b"HOST"):
                writer.close()
                return
            logger.info(f"📺 호스트 비디오 터널 대기 등록: {addr}")
            self.host_waiters.append((reader, writer))
            self.new_host_event.set()
        except Exception:
            try:
                writer.close()
            except Exception:
                pass

    async def handle_guest_stream(self, guest_reader: asyncio.StreamReader, guest_writer: asyncio.StreamWriter):
        """게스트가 47998 포트로 접속하면 대기 중인 최신 호스트 터널과 즉시 직결 (최대 5초 대기)."""
        self._tune_low_latency_socket(guest_writer)
        guest_addr = guest_writer.get_extra_info("peername")
        logger.info(f"📱 게스트 비디오 스트림 접속: {guest_addr}")

        host_reader, host_writer = self._pop_healthy_host_tunnel()

        # 게스트가 호스트보다 0.5~2초 먼저 접속한 경우 호스트 터널이 도착할 때까지 최대 5초 대기
        if not host_writer:
            deadline = time.monotonic() + 5.0
            while not host_writer and time.monotonic() < deadline:
                self.new_host_event.clear()
                remaining = max(0.1, deadline - time.monotonic())
                try:
                    await asyncio.wait_for(self.new_host_event.wait(), timeout=remaining)
                except asyncio.TimeoutError:
                    break
                host_reader, host_writer = self._pop_healthy_host_tunnel()

        if not host_writer:
            logger.warning("⚠️ 대기 중인 호스트 비디오 터널이 없습니다 (5초 타임아웃).")
            try:
                guest_writer.close()
            except Exception:
                pass
            return

        try:
            # 호스트 터널에 송출 시작 신호("START\n") 전송 -> 호스트가 즉시 ScreenStreamer에 소켓 직접 연결
            host_writer.write(b"START\n")
            await host_writer.drain()

            # 양방향 제로딜레이 파이프 가동
            await asyncio.gather(
                self._pipe(host_reader, guest_writer),
                self._pipe(guest_reader, host_writer),
                return_exceptions=True
            )
        finally:
            for w in (host_writer, guest_writer):
                try:
                    w.close()
                except Exception:
                    pass
            logger.info(f"🔌 비디오 스트림 세션 종료: {guest_addr}")

    @staticmethod
    async def _pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            while not reader.at_eof():
                chunk = await reader.read(65536)
                if not chunk:
                    break
                writer.write(chunk)
                await writer.drain()
        except Exception:
            pass


async def cleanup_stale_rooms(udp_proto: HybridUDPProtocol):
    """오래된 방 정보(30분 이상) 주기적 정리."""
    while True:
        await asyncio.sleep(300)
        now = time.time()
        stale = [rid for rid, r in udp_proto.rooms.items() if now - r.get("ts", 0) > 1800]
        for rid in stale:
            room = udp_proto.rooms.pop(rid, {})
            for key in ("host_pub", "guest_pub"):
                addr = room.get(key)
                if addr:
                    udp_proto.forward_map.pop(addr, None)
        if stale:
            logger.info(f"🧹 오래된 방 {len(stale)}개 정리 완료")


async def main():
    loop = asyncio.get_running_loop()

    # 1. UDP 47990 서버 시작
    udp_transport, udp_protocol = await loop.create_datagram_endpoint(
        lambda: HybridUDPProtocol(),
        local_addr=("0.0.0.0", UDP_PORT)
    )

    # 2. TCP 47999 (호스트 역방향 터널) & TCP 47998 (게스트 스트림 수신) 시작
    splicer = VideoStreamSplicer()
    host_srv = await asyncio.start_server(splicer.handle_host_tunnel, "0.0.0.0", TCP_HOST_TUNNEL_PORT)
    guest_srv = await asyncio.start_server(splicer.handle_guest_stream, "0.0.0.0", TCP_GUEST_STREAM_PORT)

    logger.info(f"✅ TCP 비디오 스플라이서 가동 (Host터널: {TCP_HOST_TUNNEL_PORT}, Guest수신: {TCP_GUEST_STREAM_PORT})")

    # 3. 오래된 방 정리 태스크
    asyncio.ensure_future(cleanup_stale_rooms(udp_protocol))

    async with host_srv, guest_srv:
        await asyncio.gather(host_srv.serve_forever(), guest_srv.serve_forever())


if __name__ == "__main__":
    asyncio.run(main())
