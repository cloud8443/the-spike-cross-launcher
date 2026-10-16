import React, { useState } from 'react';
import confetti from 'canvas-confetti';
import {
  Plus,
  RefreshCw,
  Users,
  Send,
  LogOut,
  Swords,
  Play,
  CheckCircle2,
  Clock,
  Sparkles,
  Shield,
  User,
} from 'lucide-react';
import { SpotlightCard } from '@/components/react-bits/SpotlightCard';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';

interface Room {
  id: string;
  name: string;
  hostName: string;
  guestName?: string;
  userCount: number;
  maxUsers: number;
  status: 'waiting' | 'in_game';
  ping: number;
}

interface ChatMessage {
  id: string;
  sender: string;
  text: string;
  time: string;
  isSystem?: boolean;
}

interface MultiplayerViewProps {
  nickname: string;
  onUpdateNickname: (name: string) => void;
}

export const MultiplayerView: React.FC<MultiplayerViewProps> = ({
  nickname,
  onUpdateNickname,
}) => {
  // 방 목록 상태
  const [rooms, setRooms] = useState<Room[]>([
    {
      id: 'spk-991',
      name: '🔥 고수만 오세요 1:1 진검승부',
      hostName: '스파이크마스터',
      guestName: undefined,
      userCount: 1,
      maxUsers: 2,
      status: 'waiting',
      ping: 18,
    },
    {
      id: 'spk-402',
      name: '초보자 환영 연습경기 (핑 양호)',
      hostName: '배구소년',
      guestName: '하이큐팬',
      userCount: 2,
      maxUsers: 2,
      status: 'in_game',
      ping: 24,
    },
    {
      id: 'spk-105',
      name: '⚡ [공식] 오라클 서버 테스트룸',
      hostName: '클라우드봇',
      guestName: undefined,
      userCount: 1,
      maxUsers: 2,
      status: 'waiting',
      ping: 15,
    },
  ]);

  // 대기실 상태
  const [activeRoom, setActiveRoom] = useState<Room | null>(null);
  const [isHost, setIsHost] = useState(false);
  const [isReady, setIsReady] = useState(false);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState('');

  // 방 생성 입력
  const [newRoomTitle, setNewRoomTitle] = useState('');
  const [nicknameInput, setNicknameInput] = useState(nickname);

  // 방 생성 처리
  const handleCreateRoom = (e: React.FormEvent) => {
    e.preventDefault();
    const title = newRoomTitle.trim() || `${nickname}의 친선방`;
    const newRoom: Room = {
      id: `spk-${Math.floor(100 + Math.random() * 900)}`,
      name: title,
      hostName: nickname,
      userCount: 1,
      maxUsers: 2,
      status: 'waiting',
      ping: 20,
    };

    setRooms([newRoom, ...rooms]);
    setActiveRoom(newRoom);
    setIsHost(true);
    setIsReady(true);
    setNewRoomTitle('');

    setChatMessages([
      {
        id: 'sys-1',
        sender: '시스템',
        text: `🏠 '${title}' 방이 생성되었습니다! 상대방의 입장을 기다리는 중입니다.`,
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        isSystem: true,
      },
    ]);

    confetti({
      particleCount: 50,
      spread: 60,
      origin: { y: 0.6 },
    });
  };

  // 방 입장 처리
  const handleJoinRoom = (room: Room) => {
    if (room.userCount >= room.maxUsers) {
      alert('이미 인원이 가득 찬 방입니다.');
      return;
    }

    const updatedRoom: Room = {
      ...room,
      guestName: nickname,
      userCount: 2,
    };

    setActiveRoom(updatedRoom);
    setIsHost(false);
    setIsReady(false);

    setChatMessages([
      {
        id: 'sys-1',
        sender: '시스템',
        text: `🎮 '${room.name}' 방에 입장했습니다! 방장 [${room.hostName}]님과 연결되었습니다.`,
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        isSystem: true,
      },
    ]);
  };

  // 방 퇴장
  const handleLeaveRoom = () => {
    setActiveRoom(null);
    setIsHost(false);
    setIsReady(false);
    setChatMessages([]);
  };

  // 채팅 전송
  const handleSendMessage = (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim() || !activeRoom) return;

    const userMsg: ChatMessage = {
      id: `msg-${Date.now()}`,
      sender: nickname,
      text: chatInput.trim(),
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setChatMessages((prev) => [...prev, userMsg]);
    setChatInput('');

    // 가상 상대방 자동 센스 응답 시뮬레이션
    setTimeout(() => {
      const peerName = isHost ? activeRoom.guestName || '상대방' : activeRoom.hostName;
      const responses = [
        `안녕하세요 ${nickname}님! 나이스 스파이크 한 판 가시죠! 🔥`,
        `오케이 준비 완료되었습니다! 경기 시작 눌러주세요 🏐`,
        `핑 상태 아주 좋네요! 렉 없이 진행 가능할 것 같습니다 👍`,
        `이번 판은 절대 안 집니다 ㅎㅎ 드루오세요!`,
      ];
      const botMsg: ChatMessage = {
        id: `bot-${Date.now()}`,
        sender: peerName,
        text: responses[Math.floor(Math.random() * responses.length)],
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setChatMessages((prev) => [...prev, botMsg]);
    }, 1200);
  };

  // 스팀 게임 실행
  const handleLaunchGame = () => {
    confetti({
      particleCount: 100,
      spread: 80,
      origin: { y: 0.6 },
    });
    window.location.href = 'steam://rungameid/3983810';
  };

  // ========================================================
  // [대기실 화면 (Waiting Room UI)]
  // ========================================================
  if (activeRoom) {
    return (
      <div className="space-y-6 max-w-5xl mx-auto pb-16">
        {/* Room Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-6 rounded-2xl bg-[#121422]/90 border border-white/10 backdrop-blur-xl">
          <div className="space-y-1">
            <div className="flex items-center gap-2.5">
              <span className="flex h-3 w-3 rounded-full bg-emerald-400 animate-ping" />
              <h2 className="text-2xl font-bold text-white tracking-tight">{activeRoom.name}</h2>
              <Badge variant="live">실시간 연결됨</Badge>
            </div>
            <p className="text-sm text-neutral-400">
              방 코드: <span className="font-mono text-white">{activeRoom.id}</span> | 레이턴시: 
              <span className="font-mono text-emerald-400 ml-1 font-bold">{activeRoom.ping}ms</span>
            </p>
          </div>

          <div className="flex items-center gap-3">
            <Button
              onClick={handleLaunchGame}
              variant="default"
              className="gap-2 px-6 shadow-lg shadow-red-950/60"
            >
              <Play className="w-4 h-4 fill-current" /> 게임 시작 (스팀)
            </Button>
            <Button
              onClick={handleLeaveRoom}
              variant="danger"
              className="gap-2"
            >
              <LogOut className="w-4 h-4" /> 방 나가기
            </Button>
          </div>
        </div>

        {/* 1:1 Matchup Arena Card */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {/* Player 1 (Host) */}
          <div className="relative overflow-hidden rounded-2xl border border-primary/30 bg-gradient-to-br from-red-950/40 via-[#121422] to-[#0c0d16] p-6 backdrop-blur-xl">
            <div className="flex items-center justify-between mb-4">
              <Badge variant="default" className="text-xs">
                👑 HOST (방장)
              </Badge>
              <span className="text-xs font-mono text-emerald-400">READY</span>
            </div>
            <div className="flex items-center gap-4">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-red-600 to-rose-400 flex items-center justify-center text-2xl font-black text-white shadow-xl shadow-red-950/50">
                {activeRoom.hostName.slice(0, 1).toUpperCase()}
              </div>
              <div>
                <h3 className="text-xl font-bold text-white">{activeRoom.hostName}</h3>
                <p className="text-xs text-neutral-400 mt-0.5">배구공 스파이크 준비 완료</p>
              </div>
            </div>
          </div>

          {/* Player 2 (Guest / Challenger) */}
          <div className="relative overflow-hidden rounded-2xl border border-sky-500/30 bg-gradient-to-br from-sky-950/30 via-[#121422] to-[#0c0d16] p-6 backdrop-blur-xl">
            <div className="flex items-center justify-between mb-4">
              <Badge variant="secondary" className="text-xs">
                ⚔️ CHALLENGER (도전자)
              </Badge>
              <span className="text-xs font-mono text-sky-400">CONNECTED</span>
            </div>
            <div className="flex items-center gap-4">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-sky-500 to-indigo-500 flex items-center justify-center text-2xl font-black text-white shadow-xl shadow-sky-950/50">
                {(activeRoom.guestName || 'AI').slice(0, 1).toUpperCase()}
              </div>
              <div>
                <h3 className="text-xl font-bold text-white">
                  {activeRoom.guestName || 'AI_연습용_상대봇'}
                </h3>
                <p className="text-xs text-neutral-400 mt-0.5">상대 접속 및 준비 완료</p>
              </div>
            </div>
          </div>
        </div>

        {/* Real-time Room Chat Section */}
        <div className="rounded-2xl border border-white/10 bg-[#121422]/90 backdrop-blur-xl overflow-hidden flex flex-col h-[380px]">
          <div className="p-4 border-b border-white/10 flex items-center justify-between bg-white/5">
            <span className="text-sm font-bold text-white flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-primary" /> 대기실 실시간 암호화 대화창
            </span>
            <span className="text-xs text-neutral-400">P2P 암호화 활성화</span>
          </div>

          {/* Messages Area */}
          <div className="flex-1 p-4 overflow-y-auto space-y-3">
            {chatMessages.map((msg) => {
              if (msg.isSystem) {
                return (
                  <div key={msg.id} className="text-center my-2">
                    <span className="inline-block px-3 py-1 rounded-full text-xs font-medium bg-white/5 text-neutral-400 border border-white/5">
                      {msg.text}
                    </span>
                  </div>
                );
              }

              const isMe = msg.sender === nickname;
              return (
                <div
                  key={msg.id}
                  className={`flex flex-col ${isMe ? 'items-end' : 'items-start'}`}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-bold text-neutral-300">{msg.sender}</span>
                    <span className="text-[10px] text-neutral-400">{msg.time}</span>
                  </div>
                  <div
                    className={`px-4 py-2.5 rounded-2xl max-w-md text-sm leading-relaxed ${
                      isMe
                        ? 'bg-gradient-to-r from-red-600 to-rose-600 text-white rounded-tr-none shadow-md shadow-red-950/40'
                        : 'bg-[#1e2238] text-slate-200 border border-white/10 rounded-tl-none'
                    }`}
                  >
                    {msg.text}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Input Area */}
          <form onSubmit={handleSendMessage} className="p-3 border-t border-white/10 bg-[#0d0f1a] flex gap-2">
            <Input
              type="text"
              placeholder="상대방에게 보낼 메시지를 입력하세요... (Enter)"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              className="flex-1"
            />
            <Button type="submit" variant="default" className="px-5">
              <Send className="w-4 h-4" />
            </Button>
          </form>
        </div>
      </div>
    );
  }

  // ========================================================
  // [공방 목록 화면 (Lobby & Rooms List UI)]
  // ========================================================
  return (
    <div className="space-y-8 pb-20">
      {/* Top Banner & Nickname Setup Bar */}
      <div className="p-6 rounded-3xl border border-white/10 bg-[#121422]/90 backdrop-blur-xl flex flex-col md:flex-row items-center justify-between gap-6">
        <div className="flex items-center gap-4 w-full md:w-auto">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-primary to-amber-500 flex items-center justify-center text-white shadow-lg shadow-red-950/40">
            <User className="w-6 h-6" />
          </div>
          <div>
            <span className="text-xs text-neutral-400 font-semibold uppercase tracking-wider">
              플레이어 닉네임 설정
            </span>
            <div className="flex items-center gap-2 mt-1">
              <Input
                type="text"
                value={nicknameInput}
                onChange={(e) => setNicknameInput(e.target.value)}
                onBlur={() => onUpdateNickname(nicknameInput)}
                className="w-44 h-9 text-sm font-bold text-white bg-white/5"
              />
              <Button
                variant="secondary"
                size="sm"
                onClick={() => onUpdateNickname(nicknameInput)}
              >
                저장
              </Button>
            </div>
          </div>
        </div>

        {/* Quick Room Create Form */}
        <form onSubmit={handleCreateRoom} className="flex items-center gap-3 w-full md:w-auto">
          <Input
            type="text"
            placeholder="개설할 방 제목 (예: 초보만 1:1 대결)"
            value={newRoomTitle}
            onChange={(e) => setNewRoomTitle(e.target.value)}
            className="w-full md:w-72 h-11"
          />
          <Button type="submit" variant="default" className="h-11 px-6 whitespace-nowrap gap-2 font-bold shadow-lg shadow-rose-950/50">
            <Plus className="w-4 h-4" /> 방 만들기
          </Button>
        </form>
      </div>

      {/* Room List Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">
            <Swords className="w-6 h-6 text-primary" /> 실시간 오픈 공방 목록
          </h2>
          <p className="text-sm text-neutral-400 mt-1">
            원하는 방을 클릭하여 즉시 입장하고 스파이크 대결을 펼치세요.
          </p>
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            confetti({ particleCount: 20, spread: 40 });
          }}
          className="gap-2"
        >
          <RefreshCw className="w-3.5 h-3.5" /> 새로고침
        </Button>
      </div>

      {/* Rooms Grid (SpotlightCard 적용) */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {rooms.map((room) => {
          const isFull = room.userCount >= room.maxUsers;
          return (
            <SpotlightCard
              key={room.id}
              spotlightColor="rgba(255, 77, 77, 0.18)"
              className="group cursor-pointer flex flex-col justify-between h-56 hover:border-primary/40 transition-all duration-300"
              onClick={() => handleJoinRoom(room)}
            >
              <div>
                <div className="flex items-center justify-between mb-3">
                  <Badge
                    variant={isFull ? 'outline' : 'success'}
                    className="text-xs"
                  >
                    {isFull ? '🔴 경기 진행 중' : '🟢 입장 가능 (대기)'}
                  </Badge>
                  <span className="text-xs font-mono text-emerald-400 font-bold">
                    {room.ping}ms
                  </span>
                </div>

                <h3 className="text-lg font-bold text-white group-hover:text-primary transition-colors duration-200 line-clamp-1">
                  {room.name}
                </h3>

                <p className="text-xs text-neutral-400 mt-2 flex items-center gap-1.5">
                  <Shield className="w-3.5 h-3.5 text-neutral-400" /> 방장: 
                  <span className="font-semibold text-neutral-200">{room.hostName}</span>
                </p>
              </div>

              <div className="pt-4 border-t border-white/5 flex items-center justify-between">
                <div className="flex items-center gap-1.5 text-xs text-neutral-400">
                  <Users className="w-4 h-4 text-secondary" />
                  <span className="font-mono font-bold text-white">
                    {room.userCount} / {room.maxUsers}
                  </span>
                </div>

                <Button
                  variant={isFull ? 'outline' : 'default'}
                  size="sm"
                  disabled={isFull}
                  className="px-4"
                >
                  {isFull ? '입장 불가' : '입장하기 →'}
                </Button>
              </div>
            </SpotlightCard>
          );
        })}
      </div>
    </div>
  );
};
