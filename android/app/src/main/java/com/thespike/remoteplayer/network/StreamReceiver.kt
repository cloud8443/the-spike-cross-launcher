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

    private var packetBuffer = ByteArray(1024 * 512) // 초기 512KB
    private val tempStorage = ByteArray(64 * 1024)   // 64KB 디코딩 임시 버퍼

    fun start() {
        if (job?.isActive == true) return
        job = scope.launch {
            var attempt = 0

            // 자동 재연결 루프: 호스트가 준비될 때까지 또는 일시적 끊김 발생 시 자동 복구
            while (isActive) {
                attempt++
                var socket: Socket? = null
                try {
                    _statusMessage.value = "호스트($hostIp:$port) 스트림 연결 시도 중... (#$attempt)"

                    socket = Socket()
                    socket.tcpNoDelay = true
                    socket.soTimeout = 4000 // 4초간 프레임 미수신 시 즉시 감지 후 재연결
                    socket.receiveBufferSize = 1024 * 1024 * 2 // 2MB 수신 윈도우
                    socket.connect(InetSocketAddress(hostIp, port), 3500)

                    val input = DataInputStream(socket.getInputStream())
                    _statusMessage.value = "연결 성공! 첫 비디오 프레임 수신 대기 중..."

                    var frameCount = 0
                    var lastFpsTimestamp = System.currentTimeMillis()

                    val decodeOptions = BitmapFactory.Options().apply {
                        inPreferredConfig = Bitmap.Config.RGB_565
                        inTempStorage = tempStorage
                    }

                    while (isActive) {
                        // 1. 4바이트 Big-Endian 프레임 크기 헤더 수신
                        val frameSize = input.readInt()
                        if (frameSize <= 0 || frameSize > 10 * 1024 * 1024) {
                            break
                        }

                        if (packetBuffer.size < frameSize) {
                            packetBuffer = ByteArray((frameSize * 1.5).toInt())
                        }

                        // 2. 페이로드 정밀 수신
                        input.readFully(packetBuffer, 0, frameSize)

                        // 3. 고속 JPEG 디코딩
                        val decodedBitmap = BitmapFactory.decodeByteArray(
                            packetBuffer, 0, frameSize, decodeOptions
                        )

                        if (decodedBitmap != null) {
                            if (!_isStreaming.value) {
                                _isStreaming.value = true
                                _statusMessage.value = "실시간 스트리밍 중"
                            }
                            onFrameDecoded(decodedBitmap)
                            frameCount++
                        }

                        // 4. 실시간 FPS 계측
                        val now = System.currentTimeMillis()
                        if (now - lastFpsTimestamp >= 1000L) {
                            _fps.value = frameCount
                            frameCount = 0
                            lastFpsTimestamp = now
                        }
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
                    delay(1000L) // 1초 후 자동 재연결
                }
            }
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
    }
}
