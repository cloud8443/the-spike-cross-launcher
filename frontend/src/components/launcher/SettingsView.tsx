import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

interface SettingsViewProps {
  serverHost: string;
  serverPort: number;
  onUpdateServer: (host: string, port: number) => void;
}

export const SettingsView: React.FC<SettingsViewProps> = ({
  serverHost,
  serverPort,
  onUpdateServer,
}) => {
  const [hostInput, setHostInput] = useState(serverHost);
  const [portInput, setPortInput] = useState(String(serverPort));

  const handleReconnect = (e: React.FormEvent) => {
    e.preventDefault();
    const portNum = parseInt(portInput, 10);
    if (isNaN(portNum)) {
      alert('포트 번호는 숫자여야 합니다.');
      return;
    }
    onUpdateServer(hostInput, portNum);
    alert(`서버 주소가 ${hostInput}:${portNum}로 변경되었습니다.`);
  };

  return (
    <div className="space-y-6 max-w-xl mx-auto py-8">
      <h2 className="text-xl font-bold text-white">⚙️ 런처 설정</h2>

      <form
        onSubmit={handleReconnect}
        className="rounded-2xl border border-white/10 bg-[#121420]/90 p-6 backdrop-blur-xl space-y-5"
      >
        <div className="space-y-2">
          <label className="text-sm font-semibold text-neutral-300">
            중앙 서버 IP 주소:
          </label>
          <Input
            type="text"
            value={hostInput}
            onChange={(e) => setHostInput(e.target.value)}
            className="h-11"
          />
        </div>

        <div className="space-y-2">
          <label className="text-sm font-semibold text-neutral-300">
            서버 포트 번호:
          </label>
          <Input
            type="text"
            value={portInput}
            onChange={(e) => setPortInput(e.target.value)}
            className="h-11"
          />
        </div>

        <Button
          type="submit"
          className="w-full py-3 bg-sky-600 hover:bg-sky-500 text-white font-bold rounded-xl"
        >
          서버 재연결
        </Button>
      </form>
    </div>
  );
};
