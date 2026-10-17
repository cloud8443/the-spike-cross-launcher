package com.thespike.remoteplayer.ui

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Rect
import android.view.SurfaceHolder
import android.view.SurfaceView

class VideoSurfaceView(context: Context) : SurfaceView(context), SurfaceHolder.Callback {

    @Volatile
    private var isSurfaceReady = false
    private val dstRect = Rect()
    // 고속 렌더링을 위해 Anti-Aliasing과 Filter를 비활성화한 순수 블리팅 페인트
    private val fastPaint = Paint().apply {
        isFilterBitmap = false
        isAntiAlias = false
        isDither = false
    }

    init {
        holder.addCallback(this)
    }

    override fun surfaceCreated(holder: SurfaceHolder) {
        isSurfaceReady = true
    }

    override fun surfaceChanged(holder: SurfaceHolder, format: Int, width: Int, height: Int) {
        dstRect.set(0, 0, width, height)
    }

    override fun surfaceDestroyed(holder: SurfaceHolder) {
        isSurfaceReady = false
    }

    /**
     * 네트워크 수신 스레드에서 디코딩 직후 직접 호출되어
     * UI 스레드 개입 없이 하드웨어 가속 캔버스에 즉시 렌더링합니다.
     */
    fun renderFrame(bitmap: Bitmap) {
        if (!isSurfaceReady) return
        val surfaceHolder = holder
        val canvas = try {
            surfaceHolder.lockHardwareCanvas()
        } catch (e: Exception) {
            null
        } ?: return

        try {
            // 16:9 비율 유지 레터박스 계산 또는 전체화면 스케일링
            if (dstRect.width() == 0 || dstRect.height() == 0) {
                dstRect.set(0, 0, canvas.width, canvas.height)
            }
            canvas.drawBitmap(bitmap, null, dstRect, fastPaint)
        } finally {
            try {
                surfaceHolder.unlockCanvasAndPost(canvas)
            } catch (_: Exception) {}
        }
    }
}
