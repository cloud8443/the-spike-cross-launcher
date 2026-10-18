package com.thespike.remoteplayer.network

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import kotlinx.coroutines.*
import kotlinx.coroutines.channels.Channel
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

    // 무충돌 트리플 버퍼:
    // 1) writePacket: 소켓 스레드가 현재 네트워크에서 데이터를 채우는 전용 버퍼
    // 2) latestFrameHolder: 가장 최신의 완성된 프레임이 대기하는 원자적 슬롯
    // 3) freePacketHolder: 디코딩이 끝난 빈 버퍼를 소켓 스레드에 돌려주는 원자적 슬롯
    private val latestFrameHolder = AtomicReference<FramePacket?>(null)
    private val freePacketHolder = AtomicReference<FramePacket>(FramePacket(ByteArray(256 * 1024)))

    // 새 프레임 도착 시 디코더를 0ms 만에 즉시 깨우는 경량 신호 채널 (CONFLATED)
    private val frameSignal = Channel<Unit>(Channel.CONFLATED)

    // 0-GC 더블 비트맵 버퍼
    private var bitmapBufferA: Bitmap? = null
    private var bitmapBufferB: Bitmap? = null
    private var useBufferA = true
    private val tempStorage = ByteArray(32 * 1024)

    fun start() {
        if (job?.isActive == true) return
        job = scope.launch {
            var attempt = 0

            // 1. 디코딩/렌더링 전용 고속 코루틴 (소켓 수신과 버퍼 메모리 완전 분리)
            val renderJob = launch(Dispatchers.Default) {
                var frameCount = 0
                var lastFpsTimestamp = System.currentTimeMillis()
                var renderPacket = FramePacket(ByteArray(256 * 1024))

                val decodeOptions = BitmapFactory.Options().apply {
                    inMutable = true
                    inPreferredConfig = Bitmap.Config.RGB_565
                    inSampleSize = 1
                    inTempStorage = tempStorage
                }

                while (isActive) {
                    // 새 프레임 신호 대기 (폴링 지연 0ms)
                    frameSignal.receiveCatching()

                    val incoming = latestFrameHolder.getAndSet(null) ?: continue

                    val targetBuffer = if (useBufferA) bitmapBufferA else bitmapBufferB
                    decodeOptions.inBitmap = targetBuffer

                    var decoded: Bitmap? = null
                    try {
                        decoded = BitmapFactory.decodeByteArray(
                            incoming.data,
                            0,
                            incoming.size,
                            decodeOptions
                        )
                    } catch (e: IllegalArgumentException) {
                        // 해상도 변경(예: 720p -> 480p) 시 비트맵 풀 즉시 재할당
                        decodeOptions.inBitmap = null
                        decoded = BitmapFactory.decodeByteArray(
                            incoming.data,
                            0,
                            incoming.size,
                            decodeOptions
                        )
                        if (decoded != null) {
                            bitmapBufferA = Bitmap.createBitmap(
                                decoded.width,
                                decoded.height,
                                Bitmap.Config.RGB_565
                            )
                            bitmapBufferB = Bitmap.createBitmap(
                                decoded.width,
                                decoded.height,
                                Bitmap.Config.RGB_565
                            )
                        }
                    } catch (_: Exception) {
                        decoded = null
                    }

                    // 사용이 끝난 incoming 패킷을 재사용 풀에 반납하고, 이전 renderPacket을 교체
                    val oldFree = freePacketHolder.getAndSet(incoming)
                    if (oldFree != null) {
                        renderPacket = oldFree
                    }

                    if (decoded != null) {
                        if (bitmapBufferA == null) {
                            bitmapBufferA = decoded
                            bitmapBufferB = Bitmap.createBitmap(
                                decoded.width,
                                decoded.height,
                                Bitmap.Config.RGB_565
                            )
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

            // 2. 고속 네트워크 소켓 수신 루프
            var writePacket = FramePacket(ByteArray(256 * 1024))

            while (isActive) {
                attempt++
                var socket: Socket? = null
                try {
                    val targetConnectIp = if (attempt % 2 == 1 && hostIp.isNotBlank() && hostIp != "127.0.0.1" && hostIp != "146.56.101.107") {
                        hostIp
                    } else {
                        "146.56.101.107"
                    }
                    val isRelay = targetConnectIp == "146.56.101.107"
                    _statusMessage.value = if (isRelay) {
                        "OCI 고속 릴레이($targetConnectIp:$port) 스트림 연결 중..."
                    } else {
                        "호스트($targetConnectIp:$port) 직결 스트림 연결 시도 중... (#$attempt)"
                    }

                    socket = Socket()
                    socket.tcpNoDelay = true
                    socket.soTimeout = 4000
                    socket.receiveBufferSize = 64 * 1024 // 480p 초경량 프레임에 맞춘 저지연 수신 버퍼
                    socket.connect(InetSocketAddress(targetConnectIp, port), if (isRelay) 4000 else 2000)

                    val input = DataInputStream(socket.getInputStream())
                    _statusMessage.value = "연결 성공! (${if (isRelay) "OCI 릴레이" else "P2P 직결"}) 비디오 수신 중..."

                    while (isActive) {
                        val frameSize = input.readInt()
                        if (frameSize <= 0 || frameSize > 5 * 1024 * 1024) {
                            break
                        }

                        if (writePacket.data.size < frameSize) {
                            writePacket.data = ByteArray((frameSize * 1.3).toInt())
                        }
                        writePacket.size = frameSize

                        // 소켓에서 페이로드를 끝까지 읽음 (렌더 스레드와 절대 겹치지 않는 독립 버퍼)
                        input.readFully(writePacket.data, 0, frameSize)

                        // 최신 프레임을 홀더에 등록하고, 만약 아직 소비되지 않은 이전 프레임이 있었다면 즉시 회수하여 재사용!
                        val unconsumed = latestFrameHolder.getAndSet(writePacket)
                        writePacket = unconsumed
                            ?: freePacketHolder.getAndSet(null)
                            ?: FramePacket(ByteArray(256 * 1024))

                        // 디코더 코루틴 즉시 깨우기
                        frameSignal.trySend(Unit)
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
