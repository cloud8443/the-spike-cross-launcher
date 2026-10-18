package com.thespike.remoteplayer.network

import kotlinx.coroutines.*
import org.json.JSONObject
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.Inet4Address
import java.net.InetAddress
import java.net.NetworkInterface
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicReference

/**
 * 더 스파이크 크로스 2P 입력 비트마스크 상수
 */
object SpikeButtons {
    const val LEFT    = 1 shl 0  // 1   : 좌측 이동
    const val RIGHT   = 1 shl 1  // 2   : 우측 이동
    const val UP      = 1 shl 2  // 4   : 상단 이동
    const val DOWN    = 1 shl 3  // 8   : 하단 이동
    const val SPIKE   = 1 shl 4  // 16  : 스파이크
    const val RECEIVE = 1 shl 5  // 32  : 리시브
    const val BLOCK   = 1 shl 6  // 64  : 블로킹
    const val SLIDE   = 1 shl 7  // 128 : 슬라이딩
    const val TOSS    = 1 shl 8  // 256 : 호환용
    const val PAUSE   = 1 shl 9  // 512 : 일시정지 (Start)
}

/**
 * UDP 입력 전송기 (WAN 지원 하이브리드 P2P)
 *
 * 연결 전략:
 * 1. 세션 시작 즉시 OCI 릴레이(146.56.101.107:47990)로 입력 전송 → 연결 대기 0초
 * 2. 백그라운드에서 호스트 LAN IP & 공인 IP로 UDP 홀 펀칭 동시 시도
 * 3. 호스트로부터 punch/punch_ack 수신 시 직결 P2P 타겟으로 자동 핫스왑
 */
class InputSender(
    val hostIp: String,
    val port: Int = 47990,
    val hostLocalIp: String? = null,
    val roomId: String = "default"
) {
    val hostPublicIp: String get() = hostIp
    val hostPort: Int get() = port

    companion object {
        const val OCI_RELAY_IP = "146.56.101.107"
        const val OCI_UDP_PORT = 47990
    }

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private var udpSocket: DatagramSocket? = null
    private var isRunning = false

    // 터치패드와 블루투스 게임패드의 입력을 독립적으로 관리 후 OR 병합
    private val touchMask = AtomicInteger(0)
    private val gamepadMask = AtomicInteger(0)
    private val sequenceNumber = AtomicInteger(0)

    // 현재 활성화된 전송 타겟 (초기값: OCI 무지연 릴레이 → 홀 펀칭 성공 시 호스트 직결로 자동 교체)
    private val activeTarget = AtomicReference<Pair<InetAddress, Int>>()
    @Volatile private var p2pConnected = false

    fun start() {
        if (isRunning) return
        isRunning = true

        scope.launch {
            try {
                val socket = DatagramSocket()
                socket.trafficClass = 0x10 // IPTOS_LOWDELAY (최저 지연 QoS 플래그)
                udpSocket = socket

                // 초기 타겟: 같은 서브넷이면 LAN 직결, 아니면 OCI 릴레이로 즉시 시작
                val myLocalIp = getDeviceLocalIp()
                if (!hostLocalIp.isNullOrBlank() && isSameLan(myLocalIp, hostLocalIp)) {
                    activeTarget.set(Pair(InetAddress.getByName(hostLocalIp), port))
                    p2pConnected = true
                } else if (!hostIp.isNullOrBlank() && isSameLan(myLocalIp, hostIp)) {
                    activeTarget.set(Pair(InetAddress.getByName(hostIp), port))
                    p2pConnected = true
                } else {
                    activeTarget.set(Pair(InetAddress.getByName(OCI_RELAY_IP), OCI_UDP_PORT))
                    p2pConnected = false

                    // 1. 수신 루프 (STUN peer_info 및 홀 펀칭 punch/punch_ack 감지)
                    launch { receivePunchLoop(socket) }

                    // 2. 송신 루프 (OCI STUN 등록 및 호스트 공인/사설 IP로 홀 펀칭 시도)
                    launch { stunAndPunchLoop(socket) }
                }

                // 3. 120Hz 주기 상태 하트비트 (패킷 유실 방어)
                launch { heartbeatLoop() }

            } catch (e: Exception) {
                e.printStackTrace()
            }
        }
    }

    private fun isSameLan(ip1: String, ip2: String): Boolean {
        return try {
            val p1 = ip1.split(".")
            val p2 = ip2.split(".")
            p1.size >= 3 && p2.size >= 3 &&
                p1[0] == p2[0] && p1[1] == p2[1] && p1[2] == p2[2] &&
                ip1 != "127.0.0.1" && ip2 != "127.0.0.1"
        } catch (_: Exception) { false }
    }

    /**
     * 터치 방향키 업데이트 (조이스틱)
     */
    fun updateTouchDirection(left: Boolean, right: Boolean) {
        while (true) {
            val current = touchMask.get()
            var next = current and (SpikeButtons.LEFT or SpikeButtons.RIGHT).inv()
            if (left) next = next or SpikeButtons.LEFT
            if (right) next = next or SpikeButtons.RIGHT
            if (touchMask.compareAndSet(current, next)) {
                if (current != next) triggerImmediateSend()
                break
            }
        }
    }

    /**
     * 터치 액션 버튼 업데이트 (스파이크/리시브/블로킹/슬라이딩)
     */
    fun updateTouchButton(buttonFlag: Int, isPressed: Boolean) {
        while (true) {
            val current = touchMask.get()
            val next = if (isPressed) (current or buttonFlag) else (current and buttonFlag.inv())
            if (touchMask.compareAndSet(current, next)) {
                if (current != next) triggerImmediateSend()
                break
            }
        }
    }

    fun updateGamepadButton(buttonFlag: Int, isPressed: Boolean) {
        while (true) {
            val current = gamepadMask.get()
            val next = if (isPressed) (current or buttonFlag) else (current and buttonFlag.inv())
            if (gamepadMask.compareAndSet(current, next)) {
                if (current != next) triggerImmediateSend()
                break
            }
        }
    }

    fun updateGamepadAxis(left: Boolean, right: Boolean, up: Boolean, down: Boolean) {
        while (true) {
            val current = gamepadMask.get()
            var next = current and (SpikeButtons.LEFT or SpikeButtons.RIGHT or SpikeButtons.UP or SpikeButtons.DOWN).inv()
            if (left) next = next or SpikeButtons.LEFT
            if (right) next = next or SpikeButtons.RIGHT
            if (up) next = next or SpikeButtons.UP
            if (down) next = next or SpikeButtons.DOWN
            if (gamepadMask.compareAndSet(current, next)) {
                if (current != next) triggerImmediateSend()
                break
            }
        }
    }

    /**
     * 버튼이 눌리거나 떼어지는 순간 딜레이 없이 즉시 UDP 패킷을 발사합니다.
     */
    private fun triggerImmediateSend() {
        scope.launch { sendCurrentStateSnapshot() }
    }

    private suspend fun heartbeatLoop() {
        while (isRunning) {
            sendCurrentStateSnapshot()
            delay(8) // 120Hz (약 8ms) 주기 하트비트
        }
    }

    private fun sendCurrentStateSnapshot() {
        val socket = udpSocket ?: return
        val target = activeTarget.get() ?: return

        val combinedMask = touchMask.get() or gamepadMask.get()
        val seq = sequenceNumber.incrementAndGet()

        // 호스트 파서 호환용 초경량 JSON 페이로드
        val payload = buildString(160) {
            append("{\"seq\":").append(seq)
            append(",\"player\":2")
            append(",\"mask\":").append(combinedMask)
            append(",\"left\":").append((combinedMask and SpikeButtons.LEFT) != 0)
            append(",\"right\":").append((combinedMask and SpikeButtons.RIGHT) != 0)
            append(",\"up\":").append((combinedMask and SpikeButtons.UP) != 0)
            append(",\"down\":").append((combinedMask and SpikeButtons.DOWN) != 0)
            append(",\"spike\":").append((combinedMask and SpikeButtons.SPIKE) != 0)
            append(",\"receive\":").append((combinedMask and SpikeButtons.RECEIVE) != 0)
            append(",\"block\":").append((combinedMask and SpikeButtons.BLOCK) != 0)
            append(",\"slide\":").append((combinedMask and SpikeButtons.SLIDE) != 0)
            append(",\"sliding\":").append((combinedMask and SpikeButtons.SLIDE) != 0)
            append(",\"toss\":").append((combinedMask and SpikeButtons.TOSS) != 0)
            append(",\"pause\":").append((combinedMask and SpikeButtons.PAUSE) != 0)
            append("}")
        }

        try {
            val bytes = payload.toByteArray(Charsets.UTF_8)
            val packet = DatagramPacket(bytes, bytes.size, target.first, target.second)
            socket.send(packet)
        } catch (_: Exception) {}
    }

    private suspend fun stunAndPunchLoop(socket: DatagramSocket) {
        val myLocalIp = getDeviceLocalIp()
        val myLocalPort = socket.localPort

        while (isRunning) {
            try {
                // 1. OCI 서버에 게스트 STUN 등록 (릴레이 경로 유지 + 호스트 좌표 요청)
                val stunJson = JSONObject().apply {
                    put("type", "stun_guest")
                    put("room_id", roomId)
                    put("local_ip", myLocalIp)
                    put("local_port", myLocalPort)
                }.toString().toByteArray(Charsets.UTF_8)

                socket.send(
                    DatagramPacket(stunJson, stunJson.size, InetAddress.getByName(OCI_RELAY_IP), OCI_UDP_PORT)
                )

                // 2. 아직 직결 전이면 호스트 LAN IP와 공인 IP 양쪽에 홀 펀칭 패킷 전송
                if (!p2pConnected) {
                    val punchBytes = JSONObject().apply {
                        put("type", "punch")
                        put("room_id", roomId)
                    }.toString().toByteArray(Charsets.UTF_8)

                    if (!hostLocalIp.isNullOrBlank()) {
                        socket.send(DatagramPacket(punchBytes, punchBytes.size, InetAddress.getByName(hostLocalIp), port))
                    }
                    if (hostIp.isNotBlank() && hostIp != OCI_RELAY_IP) {
                        socket.send(DatagramPacket(punchBytes, punchBytes.size, InetAddress.getByName(hostIp), port))
                    }
                }
            } catch (_: Exception) {}

            delay(1000L)
        }
    }

    private suspend fun receivePunchLoop(socket: DatagramSocket) {
        val buf = ByteArray(512)
        while (isRunning) {
            try {
                val packet = DatagramPacket(buf, buf.size)
                withContext(Dispatchers.IO) { socket.receive(packet) }
                val msg = String(packet.data, 0, packet.length, Charsets.UTF_8)
                val json = JSONObject(msg)

                when (json.optString("type")) {
                    "peer_info" -> {
                        val pubIp = json.optString("public_ip")
                        val pubPort = json.optInt("public_port", port)
                        val locIp = json.optString("local_ip")
                        val locPort = json.optInt("local_port", port)

                        val punchBytes = JSONObject().apply {
                            put("type", "punch")
                            put("room_id", roomId)
                        }.toString().toByteArray(Charsets.UTF_8)

                        if (locIp.isNotEmpty()) {
                            socket.send(DatagramPacket(punchBytes, punchBytes.size, InetAddress.getByName(locIp), locPort))
                        }
                        if (pubIp.isNotEmpty()) {
                            socket.send(DatagramPacket(punchBytes, punchBytes.size, InetAddress.getByName(pubIp), pubPort))
                        }
                    }
                    "punch", "punch_ack" -> {
                        val senderIp = packet.address.hostAddress ?: ""
                        if (senderIp != OCI_RELAY_IP) {
                            if (!p2pConnected) {
                                p2pConnected = true
                                activeTarget.set(Pair(packet.address, packet.port))
                            }

                            if (json.optString("type") == "punch") {
                                val ackBytes = JSONObject().apply {
                                    put("type", "punch_ack")
                                    put("room_id", roomId)
                                }.toString().toByteArray(Charsets.UTF_8)
                                socket.send(DatagramPacket(ackBytes, ackBytes.size, packet.address, packet.port))
                            }
                        }
                    }
                }
            } catch (_: Exception) {}
        }
    }

    private fun getDeviceLocalIp(): String {
        try {
            val interfaces = NetworkInterface.getNetworkInterfaces()
            while (interfaces.hasMoreElements()) {
                val intf = interfaces.nextElement()
                val addrs = intf.inetAddresses
                while (addrs.hasMoreElements()) {
                    val addr = addrs.nextElement()
                    if (!addr.isLoopbackAddress && addr is Inet4Address) {
                        return addr.hostAddress ?: "127.0.0.1"
                    }
                }
            }
        } catch (_: Exception) {}
        return "127.0.0.1"
    }

    fun stop() {
        isRunning = false
        scope.cancel()
        try { udpSocket?.close() } catch (_: Exception) {}
        udpSocket = null
    }
}
