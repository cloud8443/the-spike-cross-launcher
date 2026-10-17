package com.thespike.remoteplayer.network

import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.io.PrintWriter
import java.net.InetSocketAddress
import java.net.Socket
import java.nio.charset.StandardCharsets

data class RoomInfo(
    val code: String,
    val title: String,
    val hostIp: String,
    val playerCount: Int,
    val hostName: String = "방장"
)

class SignalingClient(
    private val serverIp: String = "146.56.101.107",
    private val serverPort: Int = 5555
) {
    private var socket: Socket? = null
    private var writer: PrintWriter? = null
    private var reader: BufferedReader? = null
    private var listenerJob: Job? = null
    private var pollingJob: Job? = null
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
                newSocket.keepAlive = true
                newSocket.connect(InetSocketAddress(serverIp, serverPort), 5000)

                socket = newSocket
                writer = PrintWriter(
                    OutputStreamWriter(newSocket.getOutputStream(), StandardCharsets.UTF_8),
                    true
                )
                reader = BufferedReader(
                    InputStreamReader(newSocket.getInputStream(), StandardCharsets.UTF_8)
                )
                _isConnected.value = true

                // 모바일 게스트 닉네임 등록
                sendJson(JSONObject().apply {
                    put("action", "set_name")
                    put("name", "모바일_2P")
                })

                startReading()
                startAutoPolling()
                requestRoomList()
            } catch (e: Exception) {
                _isConnected.value = false
                _errorMsg.value = "매칭 서버 연결 실패: ${e.localizedMessage}"
            }
        }
    }

    private fun startAutoPolling() {
        pollingJob?.cancel()
        pollingJob = scope.launch {
            while (isActive && _isConnected.value) {
                if (_joinedRoom.value == null) {
                    requestRoomList()
                }
                delay(2500L)
            }
        }
    }

    private fun startReading() {
        listenerJob?.cancel()
        listenerJob = scope.launch {
            try {
                val r = reader ?: return@launch
                while (isActive) {
                    val line = r.readLine() ?: break
                    if (line.isNotBlank()) {
                        handleServerMessage(line.trim())
                    }
                }
            } catch (e: Exception) {
                if (isActive) {
                    _errorMsg.value = "서버와 연결이 끊어졌습니다."
                }
            } finally {
                _isConnected.value = false
                pollingJob?.cancel()
            }
        }
    }

    private fun handleServerMessage(rawJson: String) {
        try {
            val json = JSONObject(rawJson)
            val rawType = json.optString("type").ifEmpty { json.optString("action") }
            val type = rawType.lowercase()

            when (type) {
                "room_list", "list_res" -> {
                    val list = mutableListOf<RoomInfo>()
                    val arr = json.optJSONArray("rooms")
                    if (arr != null) {
                        for (i in 0 until arr.length()) {
                            val obj = arr.getJSONObject(i)
                            val roomId = obj.optString("room_id").ifEmpty { obj.optString("code", "0000") }
                            val roomName = obj.optString("room_name").ifEmpty { obj.optString("title", "The Spike Room") }
                            val hostName = obj.optString("host_name", "방장")
                            val hostIp = obj.optString("host_ip", "")
                            val userCount = if (obj.has("user_count")) obj.optInt("user_count", 1) else obj.optInt("players", 1)

                            list.add(
                                RoomInfo(
                                    code = roomId,
                                    title = roomName,
                                    hostIp = hostIp,
                                    playerCount = userCount,
                                    hostName = hostName
                                )
                            )
                        }
                    }
                    _rooms.value = list
                }

                "room_joined", "join_success", "join_ok" -> {
                    val code = json.optString("room_id").ifEmpty { json.optString("code", "") }
                    val title = json.optString("room_name").ifEmpty { json.optString("title", "대기실 ($code)") }
                    val hostName = json.optString("host_name", "방장")
                    // 서버가 준 host_ip가 없으면 현재 방 목록에서 해당 방의 hostIp 조회
                    val fallbackIp = _rooms.value.find { it.code.equals(code, ignoreCase = true) }?.hostIp ?: ""
                    val hostIp = json.optString("host_ip").ifEmpty { fallbackIp }

                    _joinedRoom.value = RoomInfo(
                        code = code,
                        title = title,
                        hostIp = hostIp,
                        playerCount = 2,
                        hostName = hostName
                    )

                    if (json.optBoolean("auto_start", false) && hostIp.isNotEmpty()) {
                        _gameStartedHostIp.value = hostIp
                    }
                }

                "session_started", "game_start", "start_stream" -> {
                    val currentRoom = _joinedRoom.value
                    val hostIp = json.optString("host_ip").ifEmpty { currentRoom?.hostIp ?: "" }
                    if (currentRoom != null && hostIp.isNotEmpty()) {
                        _joinedRoom.value = currentRoom.copy(hostIp = hostIp)
                    }
                    if (hostIp.isNotEmpty() && hostIp != "127.0.0.1") {
                        _gameStartedHostIp.value = hostIp
                    }
                }

                "signal_exchange" -> {
                    val payload = json.optJSONObject("payload")
                    if (payload != null && payload.optString("type") == "host_info") {
                        val sigHostIp = payload.optString("host_ip").ifEmpty {
                            json.optString("host_ip").ifEmpty { _joinedRoom.value?.hostIp ?: "" }
                        }
                        if (sigHostIp.isNotEmpty()) {
                            val currentRoom = _joinedRoom.value
                            if (currentRoom != null) {
                                _joinedRoom.value = currentRoom.copy(hostIp = sigHostIp)
                            }
                            _gameStartedHostIp.value = sigHostIp
                        }
                    }
                }

                "room_closed" -> {
                    val reason = json.optString("reason", "방장이 방을 나갔습니다.")
                    _joinedRoom.value = null
                    _gameStartedHostIp.value = null
                    _errorMsg.value = reason
                    requestRoomList()
                }

                "error" -> {
                    _errorMsg.value = json.optString("message", "알 수 없는 서버 오류")
                }
            }
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    fun requestRoomList() {
        sendJson(JSONObject().apply {
            put("action", "get_rooms")
        })
    }

    fun joinRoom(code: String) {
        val cleanCode = code.trim()
        if (cleanCode.isEmpty()) return
        sendJson(JSONObject().apply {
            put("action", "join_room")
            put("room_id", cleanCode)
            put("code", cleanCode)
            put("role", "guest")
        })
    }

    fun forceStartWithHostIp(hostIp: String) {
        _gameStartedHostIp.value = hostIp.trim()
    }

    fun leaveRoom() {
        sendJson(JSONObject().apply {
            put("action", "leave_room")
        })
        _joinedRoom.value = null
        _gameStartedHostIp.value = null
        requestRoomList()
    }

    fun clearError() {
        _errorMsg.value = null
    }

    private fun sendJson(json: JSONObject) {
        scope.launch {
            try {
                val w = writer
                if (w != null && _isConnected.value) {
                    synchronized(this@SignalingClient) {
                        w.println(json.toString())
                    }
                }
            } catch (e: Exception) {
                _errorMsg.value = "메시지 전송 실패"
            }
        }
    }

    private fun disconnectInternal() {
        pollingJob?.cancel()
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
