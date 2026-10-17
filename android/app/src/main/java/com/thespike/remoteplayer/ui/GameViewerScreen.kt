package com.thespike.remoteplayer.ui

import android.content.Context
import android.os.Build
import android.os.VibrationEffect
import android.os.Vibrator
import android.view.MotionEvent
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.ExperimentalComposeUiApi
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInteropFilter
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import com.thespike.remoteplayer.network.InputSender
import com.thespike.remoteplayer.network.SpikeButtons
import com.thespike.remoteplayer.network.StreamReceiver

@Composable
fun GameViewerScreen(
    hostIp: String,
    inputSender: InputSender,
    onExitGame: () -> Unit
) {
    val context = LocalContext.current
    val surfaceView = remember { VideoSurfaceView(context) }
    val streamReceiver = remember(hostIp) {
        StreamReceiver(
            hostIp = hostIp,
            port = 47998,
            onFrameDecoded = { bitmap -> surfaceView.renderFrame(bitmap) }
        )
    }

    val fps by streamReceiver.fps.collectAsState()
    val isStreaming by streamReceiver.isStreaming.collectAsState()
    var showTouchControls by remember { mutableStateOf(true) }

    DisposableEffect(hostIp) {
        streamReceiver.start()
        inputSender.start()
        onDispose {
            streamReceiver.stop()
            inputSender.stop()
        }
    }

    Box(modifier = Modifier.fillMaxSize().background(Color.Black)) {
        // 1. 백그라운드 초저지연 SurfaceView 비디오 렌더러
        AndroidView(
            factory = { surfaceView },
            modifier = Modifier.fillMaxSize()
        )

        // 2. 상단 HUD 상태 표시줄 (FPS, 호스트 IP, 터치패드 토글, 나가기)
        Row(
            modifier = Modifier
                .align(Alignment.TopCenter)
                .padding(top = 8.dp)
                .background(Color(0x99000000), RoundedCornerShape(20.dp))
                .padding(horizontal = 16.dp, vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            Text(
                text = if (isStreaming) "● $fps FPS" else "○ 스트림 연결 중...",
                color = if (fps >= 60) Color(0xFF4CAF50) else Color(0xFFFFB300),
                fontSize = 13.sp,
                fontWeight = FontWeight.Bold
            )
            Text(text = "HOST: $hostIp", color = Color.LightGray, fontSize = 12.sp)
            
            TextButton(
                onClick = { showTouchControls = !showTouchControls },
                contentPadding = PaddingValues(horizontal = 8.dp, vertical = 0.dp),
                modifier = Modifier.height(28.dp)
            ) {
                Text(
                    text = if (showTouchControls) "터치패드 숨기기" else "터치패드 표시",
                    color = Color(0xFF29B6F6),
                    fontSize = 12.sp
                )
            }

            TextButton(
                onClick = onExitGame,
                contentPadding = PaddingValues(horizontal = 8.dp, vertical = 0.dp),
                modifier = Modifier.height(28.dp)
            ) {
                Text("나가기", color = Color(0xFFFF5252), fontSize = 12.sp, fontWeight = FontWeight.Bold)
            }
        }

        // 3. 멀티터치 가상 컨트롤러 오버레이 (좌측 조이스틱 + 우측 배구 액션 버튼 4개)
        if (showTouchControls) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(horizontal = 32.dp, vertical = 24.dp)
            ) {
                // 좌측 하단: 좌/우 이동 슬라이드 조이스틱
                VirtualHorizontalJoystick(
                    modifier = Modifier.align(Alignment.BottomStart),
                    onDirectionChanged = { left, right ->
                        inputSender.updateTouchDirection(left, right)
                    }
                )

                // 우측 하단: 더 스파이크 크로스 전용 다이아몬드 액션 버튼 배치
                Box(
                    modifier = Modifier
                        .align(Alignment.BottomEnd)
                        .size(230.dp)
                ) {
                    // 상단: 블로킹 (BLOCK)
                    MultiTouchActionButton(
                        label = "블로킹",
                        color = Color(0xFF42A5F5),
                        size = 72.dp,
                        modifier = Modifier.align(Alignment.TopCenter),
                        onStateChanged = { pressed ->
                            inputSender.updateTouchButton(SpikeButtons.BLOCK, pressed)
                        }
                    )
                    // 좌측: 리시브 / 다이빙 (RECEIVE)
                    MultiTouchActionButton(
                        label = "리시브",
                        color = Color(0xFF66BB6A),
                        size = 72.dp,
                        modifier = Modifier.align(Alignment.CenterStart),
                        onStateChanged = { pressed ->
                            inputSender.updateTouchButton(SpikeButtons.RECEIVE, pressed)
                        }
                    )
                    // 하단: 토스 (TOSS)
                    MultiTouchActionButton(
                        label = "토스",
                        color = Color(0xFFFFCA28),
                        size = 72.dp,
                        modifier = Modifier.align(Alignment.BottomCenter),
                        onStateChanged = { pressed ->
                            inputSender.updateTouchButton(SpikeButtons.TOSS, pressed)
                        }
                    )
                    // 우측(메인 대형 버튼): 점프 / 스파이크 (SPIKE)
                    MultiTouchActionButton(
                        label = "스파이크",
                        color = Color(0xFFEF5350),
                        size = 86.dp,
                        modifier = Modifier.align(Alignment.CenterEnd),
                        onStateChanged = { pressed ->
                            inputSender.updateTouchButton(SpikeButtons.SPIKE, pressed)
                        }
                    )
                }
            }
        }
    }
}

@OptIn(ExperimentalComposeUiApi::class)
@Composable
fun VirtualHorizontalJoystick(
    modifier: Modifier = Modifier,
    onDirectionChanged: (left: Boolean, right: Boolean) -> Unit
) {
    val context = LocalContext.current
    var knobOffsetX by remember { mutableStateOf(0f) }
    var currentDir by remember { mutableStateOf(0) } // -1: Left, 0: Neutral, 1: Right

    Box(
        modifier = modifier
            .width(200.dp)
            .height(90.dp)
            .background(Color(0x44FFFFFF), RoundedCornerShape(45.dp))
            .border(2.dp, Color(0x66FFFFFF), RoundedCornerShape(45.dp))
            .pointerInteropFilter { event ->
                val centerX = 200.dp.value * context.resources.displayMetrics.density / 2f
                val deadZone = centerX * 0.2f

                when (event.actionMasked) {
                    MotionEvent.ACTION_DOWN, MotionEvent.ACTION_MOVE -> {
                        val dx = (event.x - centerX).coerceIn(-centerX * 0.7f, centerX * 0.7f)
                        knobOffsetX = dx
                        val newDir = when {
                            dx < -deadZone -> -1
                            dx > deadZone -> 1
                            else -> 0
                        }
                        if (newDir != currentDir) {
                            currentDir = newDir
                            triggerShortVibrate(context)
                            onDirectionChanged(newDir == -1, newDir == 1)
                        }
                        true
                    }
                    MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                        knobOffsetX = 0f
                        currentDir = 0
                        onDirectionChanged(false, false)
                        true
                    }
                    else -> false
                }
            },
        contentAlignment = Alignment.Center
    ) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 24.dp),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Text("◀", color = Color(0x99FFFFFF), fontSize = 22.sp)
            Text("▶", color = Color(0x99FFFFFF), fontSize = 22.sp)
        }

        Canvas(modifier = Modifier.fillMaxSize()) {
            drawCircle(
                color = if (currentDir != 0) Color(0xCCFFB300) else Color(0xAAFFFFFF),
                radius = size.height * 0.38f,
                center = Offset(size.width / 2f + knobOffsetX, size.height / 2f)
            )
        }
    }
}

@OptIn(ExperimentalComposeUiApi::class)
@Composable
fun MultiTouchActionButton(
    label: String,
    color: Color,
    size: Dp,
    modifier: Modifier = Modifier,
    onStateChanged: (Boolean) -> Unit
) {
    val context = LocalContext.current
    var isPressed by remember { mutableStateOf(false) }

    Box(
        modifier = modifier
            .size(size)
            .background(
                color = if (isPressed) color.copy(alpha = 0.85f) else color.copy(alpha = 0.35f),
                shape = CircleShape
            )
            .border(
                width = if (isPressed) 3.dp else 1.5.dp,
                color = if (isPressed) Color.White else color.copy(alpha = 0.8f),
                shape = CircleShape
            )
            .pointerInteropFilter { event ->
                when (event.actionMasked) {
                    MotionEvent.ACTION_DOWN, MotionEvent.ACTION_POINTER_DOWN -> {
                        if (!isPressed) {
                            isPressed = true
                            triggerShortVibrate(context)
                            onStateChanged(true)
                        }
                        true
                    }
                    MotionEvent.ACTION_UP, MotionEvent.ACTION_POINTER_UP, MotionEvent.ACTION_CANCEL -> {
                        if (isPressed) {
                            isPressed = false
                            onStateChanged(false)
                        }
                        true
                    }
                    else -> true
                }
            },
        contentAlignment = Alignment.Center
    ) {
        Text(
            text = label,
            color = Color.White,
            fontSize = 13.sp,
            fontWeight = FontWeight.ExtraBold
        )
    }
}

private fun triggerShortVibrate(context: Context) {
    try {
        val vibrator = context.getSystemService(Context.VIBRATOR_SERVICE) as? Vibrator ?: return
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            vibrator.vibrate(VibrationEffect.createOneShot(12, VibrationEffect.DEFAULT_AMPLITUDE))
        } else {
            @Suppress("DEPRECATION")
            vibrator.vibrate(12)
        }
    } catch (_: Exception) {}
}
