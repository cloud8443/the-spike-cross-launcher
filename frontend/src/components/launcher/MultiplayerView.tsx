import React, { useState } from 'react';
import { Send, LogOut } from 'lucide-react';
import { SpotlightCard } from '@/components/react-bits/SpotlightCard';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

interface Room {
  id: string;
  name: string;
}

interface ChatMessage {
  id: string;
  sender: string;
  text: string;
  isSystem?: boolean;
}

export const MultiplayerView: React.FC = () => {
  const [rooms, setRooms] = useState<Room[]>([
    { id: '1', name: '고수만 오세요' },
    { id: '2', name: '초보 환영 친선전' },
    { id: '3', name: '1:1 스파이크 대결' },
  ]);

  const [selectedRoomId, setSelectedRoomId] = useState<string | null>(null);
  const [inputRoomName, setInputRoomName] = useState('');

  // 대기실 상태
  const [activeRoom, setActiveRoom] = useState<Room | null>(null);
  const [isHost, setIsHost] = useState(false);
  const [statusMessage, setStatusMessage] = useState('');
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState('');

  // 방 만들기
  const handleCreateRoom = (e: React.FormEvent) => {
    e.preventDefault();
    const name = inputRoomName.trim() || '나의 친선 방';
    const newRoom: Room = {
      id: String(Date.now()),
      name,
    };
    setRooms([newRoom, ...rooms]);
    setActiveRoom(newRoom);
    setIsHost(true);
    setStatusMessage('상태: 상대방의 입장을 기다리는 중...');
    setChatMessages([
      {
        id: '1',
        sender: '안내',
        text: '[안내] 방이 개설되었습니다. 상대를 기다리는 중입니다.',
        isSystem: true,
      },
    ]);
    setInputRoomName('');

    // 가상 상대 접속 시뮬레이션
    setTimeout(() => {
      setStatusMessage('상태: 🟢 상대방 (참가자) 접속 완료! 대화가 가능합니다.');
      setChatMessages((prev) => [
        ...prev,
        {
          id: String(Date.now()),
          sender: '시스템',
          text: '[시스템] 상대방 (참가자)님이 입장하셨습니다.',
          isSystem: true,
        },
      ]);
    }, 2000);
  };

  // 선택한 방 입장하기
  const handleJoinSelected = () => {
    const target = rooms.find((r) => r.id === selectedRoomId);
    if (!target) {
      alert('입장할 방을 목록에서 선택해주세요.');
      return;
    }
    setActiveRoom(target);
    setIsHost(false);
    setStatusMessage('상태: 🟢 방장과 연결되었습니다! 대화가 가능합니다.');
    setChatMessages([
      {
        id: '1',
        sender: '시스템',
        text: `[시스템] 🏠 ${target.name} 방에 성공적으로 입장했습니다!`,
        isSystem: true,
      },
    ]);
  };

  // 방 나가기
  const handleLeaveRoom = () => {
    setActiveRoom(null);
    setIsHost(false);
    setChatMessages([]);
  };

  // 채팅 전송
  const handleSendChat = (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim()) return;

    const userText = chatInput.trim();
    setChatMessages((prev) => [
      ...prev,
      { id: String(Date.now()), sender: '나', text: userText },
    ]);
    setChatInput('');

    // 상대방 응답 시뮬레이션
    setTimeout(() => {
      setChatMessages((prev) => [
        ...prev,
        {
          id: String(Date.now() + 1),
          sender: '상대방',
          text: `네, 반갑습니다! 준비되시면 말씀해주세요.`,
        },
      ]);
    }, 1000);
  };

  // ========================================================
  // [대기실 화면]
  // ========================================================
  if (activeRoom) {
    return (
      <div className="space-y-5 max-w-4xl mx-auto py-4">
        {/* 방 제목 및 연결 상태 */}
        <div className="p-6 rounded-2xl bg-[#121420]/90 border border-white/10 backdrop-blur-xl space-y-2">
          <h2 className="text-xl font-bold text-sky-400">
            🏠 방 제목: [{activeRoom.name}] {isHost ? '(방장)' : ''}
          </h2>
          <p className="text-sm font-bold text-emerald-400">
            {statusMessage}
          </p>
        </div>

        {/* 실시간 대화창 */}
        <div className="rounded-2xl border border-white/10 bg-[#121420]/90 backdrop-blur-xl overflow-hidden flex flex-col h-[400px]">
          <div className="p-4 border-b border-white/10 bg-white/5 font-bold text-sm text-neutral-200">
            💬 실시간 대화창
          </div>

          <div className="flex-1 p-4 overflow-y-auto space-y-2.5">
            {chatMessages.map((msg) => {
              if (msg.isSystem) {
                return (
                  <div key={msg.id} className="text-xs text-neutral-400 py-1">
                    {msg.text}
                  </div>
                );
              }
              const isMe = msg.sender === '나';
              return (
                <div key={msg.id} className="text-sm leading-relaxed">
                  <span className={isMe ? 'font-bold text-sky-400 mr-2' : 'font-bold text-rose-400 mr-2'}>
                    {msg.sender}:
                  </span>
                  <span className="text-neutral-100">{msg.text}</span>
                </div>
              );
            })}
          </div>

          <form onSubmit={handleSendChat} className="p-3 border-t border-white/10 bg-[#0d0f1a] flex gap-2">
            <Input
              type="text"
              placeholder="채팅을 입력하세요... (Enter 전송)"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              className="flex-1"
            />
            <Button type="submit" variant="secondary" className="px-5 bg-sky-600 hover:bg-sky-500 text-white font-bold">
              전송
            </Button>
          </form>
        </div>

        <Button
          onClick={handleLeaveRoom}
          variant="danger"
          className="w-full py-3 bg-red-600 hover:bg-red-500 text-white font-bold rounded-xl"
        >
          방 나가기
        </Button>
      </div>
    );
  }

  // ========================================================
  // [공방 목록 화면]
  // ========================================================
  return (
    <div className="space-y-6 max-w-4xl mx-auto py-4">
      {/* 방 만들기 인풋 바 */}
      <form onSubmit={handleCreateRoom} className="flex gap-3">
        <Input
          type="text"
          placeholder="개설할 방 제목 입력 (예: 고수만 오세요)"
          value={inputRoomName}
          onChange={(e) => setInputRoomName(e.target.value)}
          className="flex-1 h-11"
        />
        <Button
          type="submit"
          className="h-11 px-6 bg-emerald-600 hover:bg-emerald-500 text-white font-bold whitespace-nowrap rounded-xl"
        >
          방 만들기
        </Button>
      </form>

      {/* 실시간 공개 방 목록 헤더 */}
      <div className="space-y-3">
        <h2 className="text-base font-bold text-white">
          📋 실시간 공개 방 목록 (자동 검색)
        </h2>

        {/* 방 목록 (SpotlightCard 적용) */}
        <div className="space-y-2.5 min-h-[260px]">
          {rooms.map((room) => {
            const isSelected = selectedRoomId === room.id;
            return (
              <SpotlightCard
                key={room.id}
                spotlightColor="rgba(56, 189, 248, 0.15)"
                onClick={() => setSelectedRoomId(room.id)}
                className={`p-4 cursor-pointer transition-all duration-200 ${
                  isSelected
                    ? 'border-sky-500 bg-sky-950/20 shadow-md'
                    : 'border-white/10 hover:border-white/20'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-bold text-white text-base">
                    🏠 {room.name}
                  </span>
                  {isSelected && (
                    <span className="text-xs text-sky-400 font-bold">선택됨</span>
                  )}
                </div>
              </SpotlightCard>
            );
          })}
        </div>
      </div>

      {/* 선택한 방 입장하기 버튼 */}
      <Button
        onClick={handleJoinSelected}
        className="w-full py-3.5 bg-sky-600 hover:bg-sky-500 text-white font-bold text-base rounded-xl shadow-lg shadow-sky-950/40"
      >
        선택한 방 입장하기
      </Button>
    </div>
  );
};
