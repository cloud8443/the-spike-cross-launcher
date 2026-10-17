package com.thespike.remoteplayer.network

import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.PrintWriter
import java.net.InetSocketAddress
import java.net.Socket

data class RoomInfo(
    val code: String,
    val title: String,
    val hostIp: String,
    val playerCount: Int
)

class SignalingClient(
    private val serverIp: String = "146.56.101.107",
    private val serverPort: Int = 5555
) {
    private var socket: Socket? = null
    private var writer: PrintWriter? = null
    private var reader: BufferedReader? = null
    private var listenerJob: Job? = null
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    private val _isConnected = MutableStateFlow(false)
    val isConnected: StateFlow<Boolean> = _isConnected

    private val _rooms = MutableStateFlow<List<RoomInfo>>(emptyList())
    val rooms: StateFlow<List<RoomInfo>> = _rooms

    private val _joinedRoom = MutableStateFlow<RoomInfo?>(null)
    val joinedRoom: StateFlow<RoomInfo?> = _joinedRoom

    private val _gameStartedHostIp = MutableStateFlow<String?>(null)
    val gameStartedHostIp: StateFlow<String?> = _gameStartedHostIp

    private val _errorMsg = MutableStateFlow<String?>(null)
    val errorMsg: StateFlow<String?> = _errorMsg

    fun connect() {
        scope.launch {
            try {
                disconnectInternal()
                val newSocket = Socket()
                newSocket.tcpNoDelay = true
                newSocket.connect(InetSocketAddress(serverIp, serverPort), 5000)
                
                socket = newSocket
                writer = PrintWriter(newSocket.getOutputStream(), true)
                reader = BufferedReader(InputStreamReader(newSocket.getInputStream()))
                _isConnected.value = true

                startReading()
                requestRoomList()
            } catch (e: Exception) {
                _isConnected.value = false
                _errorMsg.value = "매칭 서버 연결 실패: ${e.localizedMessage}"
            }
        }
    }

    private fun startReading() {
        listenerJob = scope.launch {
            try {
                val r = reader ?: return@launch
                while (isActive) {
                    val line = r.readLine() ?: break
                    handleServerMessage(line)
                }
            } catch (e: Exception) {
                if (isActive) {
                    _errorMsg.value = "서버와 연결이 끊어졌습니다."
                }
            } finally {
                _isConnected.value = false
            }
        }
    }

    private fun handleServerMessage(rawJson: String) {
        try {
            val json = JSONObject(rawJson)
            val action = json.optString("action", json.optString("type"))

            when (action) {
                "ROOM_LIST", "LIST_RES" -> {
                    val list = mutableListOf<RoomInfo>()
                    val arr = json.optJSONArray("rooms")
                    if (arr != null) {
                        for (i in 0 until arr.length()) {
                            val obj = arr.getJSONObject(i)
                            list.add(
                                RoomInfo(
                                    code = obj.optString("code", "0000"),
                                    title = obj.optString("title", "The Spike Room"),
                                    hostIp = obj.optString("host_ip", ""),
                                    playerCount = obj.optInt("players", 1)
                                )
                            )
                        }
                    }
                    _rooms.value = list
                }
                "JOIN_SUCCESS", "JOIN_OK" -> {
                    val hostIp = json.optString("host_ip", "")
                    val code = json.optString("code", "")
                    val title = json.optString("title", "대기실 ($code)")
                    _joinedRoom.value = RoomInfo(code, title, hostIp, 2)
                    
                    // 호스트가 즉시 스트리밍 대기 중일 경우 바로 시작할 수 있도록 지원
                    if (json.optBoolean("auto_start", false) && hostIp.isNotEmpty()) {
                        _gameStartedHostIp.value = hostIp
                    }
                }
                "GAME_START", "START_STREAM" -> {
                    val hostIp = json.optString("host_ip", _joinedRoom.value?.hostIp ?: "")
                    if (hostIp.isNotEmpty()) {
                        _gameStartedHostIp.value = hostIp
                    }
                }
                "ERROR" -> {
                    _errorMsg.value = json.optString("message", "알 수 없는 서버 오류")
                }
            }
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    fun requestRoomList() {
        sendJson(JSONObject().apply {
            put("action", "LIST_ROOMS")
        })
    }

    fun joinRoom(code: String) {
        sendJson(JSONObject().apply {
            put("action", "JOIN_ROOM")
            put("code", code.trim())
            put("role", "GUEST_2P")
        })
    }

    fun forceStartWithHostIp(hostIp: String) {
        _gameStartedHostIp.value = hostIp
    }

    fun leaveRoom() {
        sendJson(JSONObject().apply {
            put("action", "LEAVE_ROOM")
        })
        _joinedRoom.value = null
        _gameStartedHostIp.value = null
    }

    fun clearError() {
        _errorMsg.value = null
    }

    private fun sendJson(json: JSONObject) {
        scope.launch {
            try {
                writer?.println(json.toString())
            } catch (e: Exception) {
                _errorMsg.value = "메시지 전송 실패"
            }
        }
    }

    private fun disconnectInternal() {
        listenerJob?.cancel()
        try { reader?.close() } catch (_: Exception) {}
        try { writer?.close() } catch (_: Exception) {}
        try { socket?.close() } catch (_: Exception) {}
        socket = null
    }

    fun disconnect() {
        scope.launch {
            disconnectInternal()
            _isConnected.value = false
        }
    }
}
