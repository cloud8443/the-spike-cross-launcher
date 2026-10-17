package com.thespike.remoteplayer.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.thespike.remoteplayer.network.RoomInfo

@Composable
fun RoomWaitingScreen(
    room: RoomInfo,
    onStartStreamingNow: (String) -> Unit,
    onLeaveRoom: () -> Unit
) {
    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Color(0xFF121214)),
        contentAlignment = Alignment.Center
    ) {
        Card(
            colors = CardDefaults.cardColors(containerColor = Color(0xFF1E1E24)),
            shape = RoundedCornerShape(16.dp),
            modifier = Modifier.width(480.dp).padding(16.dp)
        ) {
            Column(
                modifier = Modifier.padding(24.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Text("방 입장 완료 (2P 게스트)", color = Color(0xFFFFB300), fontSize = 20.sp, fontWeight = FontWeight.Bold)
                Spacer(modifier = Modifier.height(12.dp))
                Text("방 제목: ${room.title}", color = Color.White, fontSize = 16.sp)
                Text("방 코드: ${room.code}", color = Color.LightGray, fontSize = 14.sp)
                Text("호스트 IP: ${room.hostIp}", color = Color(0xFF4CAF50), fontSize = 14.sp)

                Spacer(modifier = Modifier.height(24.dp))
                CircularProgressIndicator(color = Color(0xFFFFB300))
                Spacer(modifier = Modifier.height(12.dp))
                Text("PC 호스트의 게임 시작 신호를 기다리는 중...", color = Color.Gray, fontSize = 13.sp)

                Spacer(modifier = Modifier.height(24.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    OutlinedButton(
                        onClick = onLeaveRoom,
                        modifier = Modifier.weight(1f)
                    ) {
                        Text("나가기", color = Color.White)
                    }
                    if (room.hostIp.isNotEmpty()) {
                        Button(
                            onClick = { onStartStreamingNow(room.hostIp) },
                            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFFB300)),
                            modifier = Modifier.weight(1f)
                        ) {
                            Text("스트림 즉시 연결", color = Color.Black, fontWeight = FontWeight.Bold)
                        }
                    }
                }
            }
        }
    }
}
