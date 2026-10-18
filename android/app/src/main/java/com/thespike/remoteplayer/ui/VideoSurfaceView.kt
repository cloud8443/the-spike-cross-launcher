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
    // 하드웨어 가속 양선형 필터링 페인트 (모바일 고해상도 화면에서 깨끗하고 부드러운 720p 렌더링)
    private val highQualityPaint = Paint().apply {
        isFilterBitmap = true
        isAntiAlias = true
        isDither = true
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
            val canvasW = canvas.width
            val canvasH = canvas.height
            val bitmapW = bitmap.width
            val bitmapH = bitmap.height

            if (bitmapW > 0 && bitmapH > 0 && canvasW > 0 && canvasH > 0) {
                // 원본 16:9 화면비 유지 및 중앙 정렬 (화면 찌그러짐 원천 차단)
                val scale = minOf(canvasW.toFloat() / bitmapW, canvasH.toFloat() / bitmapH)
                val targetW = (bitmapW * scale).toInt()
                val targetH = (bitmapH * scale).toInt()
                val left = (canvasW - targetW) / 2
                val top = (canvasH - targetH) / 2

                dstRect.set(left, top, left + targetW, top + targetH)
                canvas.drawColor(Color.BLACK)
                canvas.drawBitmap(bitmap, null, dstRect, highQualityPaint)
            }
        } finally {
            try {
                surfaceHolder.unlockCanvasAndPost(canvas)
            } catch (_: Exception) {}
        }
    }
}
