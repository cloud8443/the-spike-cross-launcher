package com.thespike.remoteplayer.network

import kotlinx.coroutines.*
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.util.concurrent.atomic.AtomicInteger

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
}

class InputSender(
    private val hostIp: String,
    private val port: Int = 47990
) {
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private var syncJob: Job? = null
    private var udpSocket: DatagramSocket? = null
    private var targetAddress: InetAddress? = null

    // 터치패드와 블루투스 게임패드의 입력을 독립적으로 관리 후 OR 병합
    private val touchMask = AtomicInteger(0)
    private val gamepadMask = AtomicInteger(0)
    private val sequenceNumber = AtomicInteger(0)

    fun start() {
        if (syncJob?.isActive == true) return
        syncJob = scope.launch {
            try {
                udpSocket = DatagramSocket()
                udpSocket?.trafficClass = 0x10 // IPTOS_LOWDELAY (초저지연 라우팅 우선순위)
                targetAddress = InetAddress.getByName(hostIp)

                // 120Hz (약 8ms) 주기로 지속적인 상태 하트비트 전송 (패킷 유실 완벽 방어)
                while (isActive) {
                    sendCurrentStateSnapshot()
                    delay(8)
                }
            } catch (e: Exception) {
                e.printStackTrace()
            }
        }
    }

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
        scope.launch {
            sendCurrentStateSnapshot()
        }
    }

    private fun sendCurrentStateSnapshot() {
        val socket = udpSocket ?: return
        val address = targetAddress ?: return

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
            append("}")
        }

        try {
            val bytes = payload.toByteArray(Charsets.UTF_8)
            val packet = DatagramPacket(bytes, bytes.size, address, port)
            socket.send(packet)
        } catch (_: Exception) {}
    }

    fun stop() {
        syncJob?.cancel()
        try { udpSocket?.close() } catch (_: Exception) {}
        udpSocket = null
    }
}
