package com.thespike.remoteplayer.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.SportsVolleyball
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.thespike.remoteplayer.network.RoomInfo

@Composable
fun LobbyScreen(
    isConnected: Boolean,
    rooms: List<RoomInfo>,
    errorMsg: String?,
    onRefresh: () -> Unit,
    onJoinByCode: (String) -> Unit,
    onDirectConnectIp: (String) -> Unit,
    onDismissError: () -> Unit
) {
    var roomCodeInput by remember { mutableStateOf("") }
    var directIpInput by remember { mutableStateOf("") }

    Row(
        modifier = Modifier
            .fillMaxSize()
            .background(Color(0xFF121214))
            .padding(24.dp),
        horizontalArrangement = Arrangement.spacedBy(24.dp)
    ) {
        // 좌측 패널: 타이틀 및 코드/IP 직접 입장
        Column(
            modifier = Modifier
                .weight(1f)
                .fillMaxHeight(),
            verticalArrangement = Arrangement.SpaceBetween
        ) {
            Column {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        imageVector = Icons.Default.SportsVolleyball,
                        contentDescription = null,
                        tint = Color(0xFFFFB300),
                        modifier = Modifier.size(36.dp)
                    )
                    Spacer(modifier = Modifier.width(12.dp))
                    Text(
                        text = "THE SPIKE REMOTE 2P",
                        color = Color.White,
                        fontSize = 22.sp,
                        fontWeight = FontWeight.ExtraBold
                    )
                    Spacer(modifier = Modifier.width(10.dp))
                    Surface(
                        color = Color(0xFF2E7D32),
                        shape = RoundedCornerShape(6.dp)
                    ) {
                        Text(
                            text = "v1.4.0 WAN",
                            color = Color.White,
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Bold,
                            modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp)
                        )
                    }
                }
                Spacer(modifier = Modifier.height(6.dp))
                Text(
                    text = if (isConnected) "● OCI 매칭 서버 (146.56.101.107:5555) 실시간 연동됨" else "○ 매칭 서버 연결 중...",
                    color = if (isConnected) Color(0xFF4CAF50) else Color(0xFFFF5252),
                    fontSize = 13.sp
                )
            }

            // 방 코드 입력 카드
            Card(
                colors = CardDefaults.cardColors(containerColor = Color(0xFF1E1E24)),
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text("방 코드로 입장", color = Color.White, fontWeight = FontWeight.Bold)
                    Spacer(modifier = Modifier.height(8.dp))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        OutlinedTextField(
                            value = roomCodeInput,
                            onValueChange = { roomCodeInput = it.trim() },
                            placeholder = { Text("6자리 방 코드 입력", color = Color.Gray) },
                            singleLine = true,
                            modifier = Modifier.weight(1f),
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedTextColor = Color.White,
                                unfocusedTextColor = Color.White,
                                focusedBorderColor = Color(0xFFFFB300)
                            )
                        )
                        Spacer(modifier = Modifier.width(12.dp))
                        Button(
                            onClick = { if (roomCodeInput.isNotBlank()) onJoinByCode(roomCodeInput.trim()) },
                            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFFB300)),
                            modifier = Modifier.height(54.dp)
                        ) {
                            Text("입장", color = Color.Black, fontWeight = FontWeight.Bold)
                        }
                    }
                }
            }

            // 호스트 PC IP 직접 연결 카드 (LAN/Tailscale/수동 연결 지원)
            Card(
                colors = CardDefaults.cardColors(containerColor = Color(0xFF1E1E24)),
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text("호스트 PC IP 직접 연결 (즉시 시작)", color = Color.LightGray, fontSize = 14.sp)
                    Spacer(modifier = Modifier.height(8.dp))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        OutlinedTextField(
                            value = directIpInput,
                            onValueChange = { directIpInput = it.trim() },
                            placeholder = { Text("예: 192.168.0.10", color = Color.Gray) },
                            singleLine = true,
                            modifier = Modifier.weight(1f),
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedTextColor = Color.White,
                                unfocusedTextColor = Color.White,
                                focusedBorderColor = Color(0xFF29B6F6)
                            )
                        )
                        Spacer(modifier = Modifier.width(12.dp))
                        Button(
                            onClick = { if (directIpInput.isNotBlank()) onDirectConnectIp(directIpInput) },
                            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF29B6F6)),
                            modifier = Modifier.height(54.dp)
                        ) {
                            Text("직접 연결", color = Color.Black, fontWeight = FontWeight.Bold)
                        }
                    }
                }
            }
        }

        // 우측 패널: 실시간 공개 방 목록
        Card(
            colors = CardDefaults.cardColors(containerColor = Color(0xFF1A1A1F)),
            shape = RoundedCornerShape(12.dp),
            modifier = Modifier
                .weight(1f)
                .fillMaxHeight()
        ) {
            Column(modifier = Modifier.padding(16.dp).fillMaxSize()) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text("실시간 대기 방 목록 (${rooms.size})", color = Color.White, fontSize = 18.sp, fontWeight = FontWeight.Bold)
                    IconButton(onClick = onRefresh) {
                        Icon(Icons.Default.Refresh, contentDescription = "새로고침", tint = Color.White)
                    }
                }
                HorizontalDivider(color = Color(0xFF2C2C35), modifier = Modifier.padding(vertical = 8.dp))

                if (rooms.isEmpty()) {
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Text("현재 생성된 대기 방이 없습니다. (자동 검색 중...)", color = Color.Gray)
                    }
                } else {
                    LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        items(rooms, key = { it.code }) { room ->
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .background(Color(0xFF25252D), RoundedCornerShape(8.dp))
                                    .clickable { onJoinByCode(room.code) }
                                    .padding(16.dp),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Column {
                                    Text(room.title, color = Color.White, fontWeight = FontWeight.Bold)
                                    val ipDisplay = if (room.hostIp.isNotBlank()) " | IP: ${room.hostIp}" else ""
                                    Text(
                                        text = "방장: ${room.hostName} | 코드: ${room.code}$ipDisplay",
                                        color = Color.Gray,
                                        fontSize = 12.sp
                                    )
                                }
                                Badge(
                                    containerColor = if (room.playerCount < 2) Color(0xFFFFB300) else Color(0xFFEF5350)
                                ) {
                                    Text(
                                        text = "${room.playerCount}/2",
                                        color = Color.Black,
                                        fontWeight = FontWeight.Bold,
                                        modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    if (errorMsg != null) {
        AlertDialog(
            onDismissRequest = onDismissError,
            confirmButton = {
                TextButton(onClick = onDismissError) { Text("확인") }
            },
            title = { Text("알림") },
            text = { Text(errorMsg) }
        )
    }
}
