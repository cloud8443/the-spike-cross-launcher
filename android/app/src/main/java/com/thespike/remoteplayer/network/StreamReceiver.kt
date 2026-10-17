package com.thespike.remoteplayer.network

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import java.io.DataInputStream
import java.net.InetSocketAddress
import java.net.Socket

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

    // Zero-Allocation을 위한 재사용 버퍼 풀
    private var packetBuffer = ByteArray(1024 * 512) // 초기 512KB
    private val bitmapPool = arrayOfNulls<Bitmap>(2)
    private var poolIndex = 0
    private val tempStorage = ByteArray(64 * 1024) // 64KB 디코딩 임시 버퍼

    fun start() {
        if (job?.isActive == true) return
        job = scope.launch {
            var socket: Socket? = null
            try {
                socket = Socket()
                socket.tcpNoDelay = true
                socket.receiveBufferSize = 1024 * 1024 * 2 // 2MB 수신 윈도우
                socket.connect(InetSocketAddress(hostIp, port), 5000)

                val input = DataInputStream(socket.getInputStream())
                _isStreaming.value = true

                var frameCount = 0
                var lastFpsTimestamp = System.currentTimeMillis()

                val decodeOptions = BitmapFactory.Options().apply {
                    inMutable = true
                    inPreferredConfig = Bitmap.Config.RGB_565 // 알파 채널 제거로 디코딩 속도 2배 향상
                    inTempStorage = tempStorage
                }

                while (isActive) {
                    // 1. 4바이트 Big-Endian 프레임 크기 헤더 수신
                    val frameSize = input.readInt()
                    if (frameSize <= 0 || frameSize > 10 * 1024 * 1024) {
                        // 비정상 패킷 방어 (최대 10MB 제한)
                        break
                    }

                    // 버퍼 크기 동적 확장 (할당 최소화)
                    if (packetBuffer.size < frameSize) {
                        packetBuffer = ByteArray((frameSize * 1.5).toInt())
                    }

                    // 2. 페이로드 정밀 수신
                    input.readFully(packetBuffer, 0, frameSize)

                    // 3. 더블 버퍼링 inBitmap 재사용으로 GC Pause 원천 차단
                    decodeOptions.inBitmap = bitmapPool[poolIndex]
                    val decodedBitmap = try {
                        BitmapFactory.decodeByteArray(packetBuffer, 0, frameSize, decodeOptions)
                    } catch (e: IllegalArgumentException) {
                        // 해상도 변경 등으로 inBitmap 재사용 실패 시 새로 할당
                        decodeOptions.inBitmap = null
                        BitmapFactory.decodeByteArray(packetBuffer, 0, frameSize, decodeOptions)
                    }

                    if (decodedBitmap != null) {
                        bitmapPool[poolIndex] = decodedBitmap
                        poolIndex = (poolIndex + 1) % 2
                        
                        // SurfaceView 하드웨어 캔버스로 즉시 전달
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
            } catch (e: Exception) {
                e.printStackTrace()
            } finally {
                _isStreaming.value = false
                try { socket?.close() } catch (_: Exception) {}
            }
        }
    }

    fun stop() {
        job?.cancel()
        _isStreaming.value = false
    }
}
