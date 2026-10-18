package com.thespike.remoteplayer

import android.os.Bundle
import android.view.InputDevice
import android.view.KeyEvent
import android.view.MotionEvent
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.*
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import com.thespike.remoteplayer.network.InputSender
import com.thespike.remoteplayer.network.SignalingClient
import com.thespike.remoteplayer.network.SpikeButtons
import com.thespike.remoteplayer.ui.GameViewerScreen
import com.thespike.remoteplayer.ui.LobbyScreen
import com.thespike.remoteplayer.ui.RoomWaitingScreen

class MainActivity : ComponentActivity() {

    private lateinit var signalingClient: SignalingClient
    private var activeInputSender: InputSender? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // 화면 꺼짐 방지 및 몰입형 전체화면(Immersive Sticky) 적용
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        hideSystemBars()

        signalingClient = SignalingClient(
            serverIp = "146.56.101.107",
            serverPort = 5555
        )
        signalingClient.connect()

        setContent {
            MaterialTheme(colorScheme = darkColorScheme()) {
                val isConnected by signalingClient.isConnected.collectAsState()
                val rooms by signalingClient.rooms.collectAsState()
                val joinedRoom by signalingClient.joinedRoom.collectAsState()
                val gameStartedHostIp by signalingClient.gameStartedHostIp.collectAsState()
                val errorMsg by signalingClient.errorMsg.collectAsState()

                val currentHostIp = gameStartedHostIp
                val currentHostLocalIp by signalingClient.hostLocalIp.collectAsState()
                val currentRoomId by signalingClient.currentRoomId.collectAsState()

                when {
                    // 1. 스트리밍 및 원격 플레이 화면
                    currentHostIp != null -> {
                        val sender = remember(currentHostIp, currentHostLocalIp, currentRoomId) {
                            InputSender(
                                hostIp = currentHostIp,
                                port = 47990,
                                hostLocalIp = currentHostLocalIp,
                                roomId = currentRoomId
                            ).also {
                                activeInputSender = it
                            }
                        }
                        GameViewerScreen(
                            hostIp = currentHostIp,
                            inputSender = sender,
                            onExitGame = {
                                activeInputSender = null
                                signalingClient.leaveRoom()
                            }
                        )
                    }

                    // 2. 방 입장 후 대기 화면
                    joinedRoom != null -> {
                        RoomWaitingScreen(
                            room = joinedRoom!!,
                            onStartStreamingNow = { ip ->
                                signalingClient.forceStartWithHostIp(ip)
                            },
                            onLeaveRoom = {
                                signalingClient.leaveRoom()
                            }
                        )
                    }

                    // 3. 메인 로비 화면
                    else -> {
                        LobbyScreen(
                            isConnected = isConnected,
                            rooms = rooms,
                            errorMsg = errorMsg,
                            onRefresh = {
                                if (!isConnected) signalingClient.connect()
                                else signalingClient.requestRoomList()
                            },
                            onJoinByCode = { code ->
                                signalingClient.joinRoom(code)
                            },
                            onDirectConnectIp = { ip ->
                                signalingClient.forceStartWithHostIp(ip)
                            },
                            onDismissError = {
                                signalingClient.clearError()
                            }
                        )
                    }
                }
            }
        }
    }

    /**
     * 외장 블루투스/USB 게임패드 버튼 이벤트 처리
     */
    override fun dispatchKeyEvent(event: KeyEvent): Boolean {
        val sender = activeInputSender
        if (sender != null && isGamepadKeyEvent(event)) {
            val isDown = event.action == KeyEvent.ACTION_DOWN
            val buttonFlag = when (event.keyCode) {
                KeyEvent.KEYCODE_DPAD_LEFT -> SpikeButtons.LEFT
                KeyEvent.KEYCODE_DPAD_RIGHT -> SpikeButtons.RIGHT
                KeyEvent.KEYCODE_DPAD_UP -> SpikeButtons.UP
                KeyEvent.KEYCODE_DPAD_DOWN -> SpikeButtons.DOWN
                // A / R1 / R2 버튼 -> 스파이크
                KeyEvent.KEYCODE_BUTTON_A, KeyEvent.KEYCODE_BUTTON_R1, KeyEvent.KEYCODE_BUTTON_R2 -> SpikeButtons.SPIKE
                // X / L1 / L2 버튼 -> 리시브
                KeyEvent.KEYCODE_BUTTON_X, KeyEvent.KEYCODE_BUTTON_L1, KeyEvent.KEYCODE_BUTTON_L2 -> SpikeButtons.RECEIVE
                // B 버튼 -> 블로킹
                KeyEvent.KEYCODE_BUTTON_B -> SpikeButtons.BLOCK
                // Y 버튼 -> 슬라이딩
                KeyEvent.KEYCODE_BUTTON_Y -> SpikeButtons.SLIDE
                // Start / Select -> 일시정지 (PAUSE)
                KeyEvent.KEYCODE_BUTTON_START, KeyEvent.KEYCODE_BUTTON_SELECT -> SpikeButtons.PAUSE
                else -> 0
            }

            if (buttonFlag != 0) {
                sender.updateGamepadButton(buttonFlag, isDown)
                return true
            }
        }
        return super.dispatchKeyEvent(event)
    }

    /**
     * 외장 블루투스/USB 게임패드 아날로그 조이스틱 및 Hat Switch(D-Pad) 처리
     */
    override fun dispatchGenericMotionEvent(event: MotionEvent): Boolean {
        val sender = activeInputSender
        if (sender != null && isJoystickMotionEvent(event.source) && event.action == MotionEvent.ACTION_MOVE) {
            val axisX = event.getAxisValue(MotionEvent.AXIS_X)
            val hatX = event.getAxisValue(MotionEvent.AXIS_HAT_X)
            val axisY = event.getAxisValue(MotionEvent.AXIS_Y)
            val hatY = event.getAxisValue(MotionEvent.AXIS_HAT_Y)

            val deadZone = 0.25f
            val left = (axisX < -deadZone) || (hatX < -deadZone)
            val right = (axisX > deadZone) || (hatX > deadZone)
            val up = (axisY < -deadZone) || (hatY < -deadZone)
            val down = (axisY > deadZone) || (hatY > deadZone)

            sender.updateGamepadAxis(left, right, up, down)
            return true
        }
        return super.dispatchGenericMotionEvent(event)
    }

    private fun isGamepadKeyEvent(event: KeyEvent): Boolean {
        val src = event.source
        if ((src and InputDevice.SOURCE_GAMEPAD) != 0 ||
            (src and InputDevice.SOURCE_JOYSTICK) != 0 ||
            (src and InputDevice.SOURCE_DPAD) != 0) {
            return true
        }
        if (KeyEvent.isGamepadButton(event.keyCode)) return true
        return event.keyCode in intArrayOf(
            KeyEvent.KEYCODE_DPAD_LEFT, KeyEvent.KEYCODE_DPAD_RIGHT,
            KeyEvent.KEYCODE_DPAD_UP, KeyEvent.KEYCODE_DPAD_DOWN,
            KeyEvent.KEYCODE_BUTTON_A, KeyEvent.KEYCODE_BUTTON_B,
            KeyEvent.KEYCODE_BUTTON_X, KeyEvent.KEYCODE_BUTTON_Y,
            KeyEvent.KEYCODE_BUTTON_L1, KeyEvent.KEYCODE_BUTTON_R1,
            KeyEvent.KEYCODE_BUTTON_L2, KeyEvent.KEYCODE_BUTTON_R2,
            KeyEvent.KEYCODE_BUTTON_START, KeyEvent.KEYCODE_BUTTON_SELECT
        )
    }

    private fun isJoystickMotionEvent(source: Int): Boolean {
        return (source and InputDevice.SOURCE_CLASS_JOYSTICK) != 0 ||
               (source and InputDevice.SOURCE_JOYSTICK) != 0 ||
               (source and InputDevice.SOURCE_GAMEPAD) != 0
    }

    private fun hideSystemBars() {
        WindowCompat.setDecorFitsSystemWindows(window, false)
        WindowInsetsControllerCompat(window, window.decorView).let { controller ->
            controller.hide(WindowInsetsCompat.Type.systemBars())
            controller.systemBarsBehavior =
                WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        activeInputSender?.stop()
        signalingClient.disconnect()
    }
}
