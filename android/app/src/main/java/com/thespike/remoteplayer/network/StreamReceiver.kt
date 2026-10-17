package com.thespike.remoteplayer.network

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import java.io.DataInputStream
import java.net.ConnectException
import java.net.InetSocketAddress
import java.net.Socket
import java.net.SocketTimeoutException
import java.util.concurrent.atomic.AtomicReference

class FramePacket(
    var data: ByteArray,
    var size: Int = 0
)

class StreamReceiver(
    private val hostIp: String,
    private val port: Int = 47998,
    private val onFrameDecoded: (Bitmap) -> Unit
) {
    private var job: Job? = null
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    private val _fps = MutableStateFlow(0)
    val fps: StateFlow<Int> = _fps

    private val _isStreaming = MutableStateFlow(false)
    val isStreaming: StateFlow<Boolean> = _isStreaming

    private val _statusMessage = MutableStateFlow("호스트($hostIp:$port)에 연결 준비 중...")
    val statusMessage: StateFlow<String> = _statusMessage

    // 최신 프레임 홀더: 이전 미처리 프레임을 즉시 덮어써서 0ms 지연 유지
    private val latestFrameHolder = AtomicReference<FramePacket?>()

    // 0-Allocation 패킷 트리플 버퍼 (네트워크 수신 시 메모리 할당 0바이트)
    private val packetPool = arrayOf(
        FramePacket(ByteArray(512 * 1024)),
        FramePacket(ByteArray(512 * 1024)),
        FramePacket(ByteArray(512 * 1024))
    )
    private var currentPacketIndex = 0

    // 0-Garbage Collection 더블 비트맵 버퍼
    private var bitmapBufferA: Bitmap? = null
    private var bitmapBufferB: Bitmap? = null
    private var useBufferA = true
    private val tempStorage = ByteArray(64 * 1024)

    fun start() {
        if (job?.isActive == true) return
        job = scope.launch {
            var attempt = 0

            // 1. 디코딩/렌더링 전용 고속 백그라운드 코루틴 (소켓 I/O와 완전 분리)
            val renderJob = launch(Dispatchers.Default) {
                var frameCount = 0
                var lastFpsTimestamp = System.currentTimeMillis()

                val decodeOptions = BitmapFactory.Options().apply {
                    inMutable = true
                    inPreferredConfig = Bitmap.Config.RGB_565
                    inSampleSize = 1
                    inTempStorage = tempStorage
                }

                while (isActive) {
                    val packet = latestFrameHolder.getAndSet(null)
                    if (packet == null) {
                        // 대기 중인 새 프레임이 없으면 아주 짧게 양보 (1ms)
                        delay(1)
                        continue
                    }

                    val targetBuffer = if (useBufferA) bitmapBufferA else bitmapBufferB
                    decodeOptions.inBitmap = targetBuffer

                    var decoded: Bitmap? = null
                    try {
                        decoded = BitmapFactory.decodeByteArray(packet.data, 0, packet.size, decodeOptions)
                    } catch (e: IllegalArgumentException) {
                        decodeOptions.inBitmap = null
                        decoded = BitmapFactory.decodeByteArray(packet.data, 0, packet.size, decodeOptions)
                        if (decoded != null) {
                            bitmapBufferA = Bitmap.createBitmap(decoded.width, decoded.height, Bitmap.Config.RGB_565)
                            bitmapBufferB = Bitmap.createBitmap(decoded.width, decoded.height, Bitmap.Config.RGB_565)
                        }
                    } catch (_: Exception) {
                        decoded = null
                    }

                    if (decoded != null) {
                        if (bitmapBufferA == null) {
                            bitmapBufferA = decoded
                            bitmapBufferB = Bitmap.createBitmap(decoded.width, decoded.height, Bitmap.Config.RGB_565)
                        }

                        if (!_isStreaming.value) {
                            _isStreaming.value = true
                            _statusMessage.value = "실시간 스트리밍 중"
                        }
                        onFrameDecoded(decoded)
                        useBufferA = !useBufferA
                        frameCount++
                    }

                    val now = System.currentTimeMillis()
                    if (now - lastFpsTimestamp >= 1000L) {
                        _fps.value = frameCount
                        frameCount = 0
                        lastFpsTimestamp = now
                    }
                }
            }

            // 2. 고속 네트워크 소켓 수신 루프 (디코딩을 기다리지 않고 소켓을 즉각 비워 TCP 백프레셔 제거)
            while (isActive) {
                attempt++
                var socket: Socket? = null
                try {
                    _statusMessage.value = "호스트($hostIp:$port) 스트림 연결 시도 중... (#$attempt)"

                    socket = Socket()
                    socket.tcpNoDelay = true
                    socket.soTimeout = 4000
                    socket.receiveBufferSize = 128 * 1024 // 초저지연 버퍼
                    socket.connect(InetSocketAddress(hostIp, port), 3500)

                    val input = DataInputStream(socket.getInputStream())
                    _statusMessage.value = "연결 성공! 첫 비디오 프레임 수신 대기 중..."

                    while (isActive) {
                        val frameSize = input.readInt()
                        if (frameSize <= 0 || frameSize > 10 * 1024 * 1024) {
                            break
                        }

                        val packet = packetPool[currentPacketIndex % packetPool.size]
                        currentPacketIndex++

                        if (packet.data.size < frameSize) {
                            packet.data = ByteArray((frameSize * 1.5).toInt())
                        }
                        packet.size = frameSize

                        // 소켓에서 페이로드를 즉시 끝까지 수신
                        input.readFully(packet.data, 0, frameSize)

                        // 원자적 교체: 렌더러가 이전 프레임을 아직 그리고 있더라도 항상 가장 최신 프레임으로 덮어씀 (지연 시간 0)
                        latestFrameHolder.set(packet)
                    }
                } catch (e: ConnectException) {
                    _statusMessage.value = "호스트 화면 공유 대기 중... (재시도 #$attempt)\n호스트가 시작 버튼을 눌렀는지 확인해주세요."
                } catch (e: SocketTimeoutException) {
                    _statusMessage.value = "호스트($hostIp) 응답 시간 초과 (재시도 #$attempt)\nPC와 모바일이 같은 Wi-Fi에 연결되어 있는지 확인해주세요."
                } catch (e: Exception) {
                    _statusMessage.value = "스트림 연결 재시도 중... (#$attempt: ${e.javaClass.simpleName})"
                } finally {
                    _isStreaming.value = false
                    _fps.value = 0
                    try {
                        socket?.close()
                    } catch (_: Exception) {}
                }

                if (isActive) {
                    delay(1000L)
                }
            }

            renderJob.cancel()
        }
    }

    fun reconnectNow() {
        stop()
        start()
    }

    fun stop() {
        job?.cancel()
        job = null
        _isStreaming.value = false
        _fps.value = 0
        latestFrameHolder.set(null)
    }
}
