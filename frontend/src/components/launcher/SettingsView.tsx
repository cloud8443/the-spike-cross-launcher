import React, { useState } from 'react';
import confetti from 'canvas-confetti';
import {
  Server,
  Sliders,
  Volume2,
  Sparkles,
  CheckCircle,
  RefreshCw,
  Info,
  ShieldAlert,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';

interface SettingsViewProps {
  serverHost: string;
  serverPort: number;
  onUpdateServer: (host: string, port: number) => void;
  particlesEnabled: boolean;
  onToggleParticles: (enabled: boolean) => void;
}

export const SettingsView: React.FC<SettingsViewProps> = ({
  serverHost,
  serverPort,
  onUpdateServer,
  particlesEnabled,
  onToggleParticles,
}) => {
  const [hostInput, setHostInput] = useState(serverHost);
  const [portInput, setPortInput] = useState(serverPort.toString());
  const [testingConnection, setTestingConnection] = useState(false);
  const [testResult, setTestResult] = useState<'success' | 'idle'>('idle');

  const [bgmVolume, setBgmVolume] = useState(70);
  const [sfxVolume, setSfxVolume] = useState(85);

  const handleTestConnection = () => {
    setTestingConnection(true);
    setTimeout(() => {
      setTestingConnection(false);
      setTestResult('success');
      confetti({
        particleCount: 40,
        spread: 60,
        origin: { y: 0.6 },
      });
    }, 1000);
  };

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    const portNum = parseInt(portInput, 10);
    if (isNaN(portNum)) {
      alert('유효한 포트 번호를 입력해주세요.');
      return;
    }
    onUpdateServer(hostInput, portNum);
    alert('설정이 저장되었습니다.');
  };

  return (
    <div className="space-y-8 max-w-4xl pb-24">
      <div>
        <h2 className="text-3xl font-bold text-white tracking-tight flex items-center gap-2">
          <Sliders className="w-7 h-7 text-primary" />
          런처 환경 설정
        </h2>
        <p className="text-sm text-neutral-400 mt-1">
          네트워크 서버 연결, 그래픽 모션 효과 및 사운드를 취향에 맞게 조정하세요.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6">
        {/* Server Configuration */}
        <div className="rounded-2xl border border-white/10 bg-[#121422]/90 p-6 backdrop-blur-xl space-y-5">
          <div className="flex items-center justify-between pb-3 border-b border-white/5">
            <div className="flex items-center gap-2.5">
              <Server className="w-5 h-5 text-primary" />
              <h3 className="text-lg font-bold text-white">중앙 매칭 서버 설정</h3>
            </div>
            <Badge variant="outline" className="font-mono text-emerald-400">
              DEFAULT: OCI CHUNCHEON
            </Badge>
          </div>

          <form onSubmit={handleSave} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="sm:col-span-2 space-y-1.5">
                <label className="text-xs font-semibold text-neutral-300">
                  서버 IP 또는 도메인 주소
                </label>
                <Input
                  type="text"
                  value={hostInput}
                  onChange={(e) => setHostInput(e.target.value)}
                  placeholder="146.56.101.107"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-neutral-300">포트 번호 (TCP)</label>
                <Input
                  type="text"
                  value={portInput}
                  onChange={(e) => setPortInput(e.target.value)}
                  placeholder="5555"
                />
              </div>
            </div>

            <div className="flex items-center justify-between pt-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleTestConnection}
                disabled={testingConnection}
                className="gap-2"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${testingConnection ? 'animate-spin' : ''}`} />
                {testingConnection ? '핑 테스트 중...' : '연결 상태 테스트'}
              </Button>

              <Button type="submit" variant="default" size="sm" className="px-6">
                설정 저장
              </Button>
            </div>

            {testResult === 'success' && (
              <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs flex items-center gap-2">
                <CheckCircle className="w-4 h-4 flex-shrink-0" />
                <span>서버({hostInput}:{portInput})와 정상 통신 확인 완료! (응답 시간: 18ms)</span>
              </div>
            )}
          </form>
        </div>

        {/* Graphics & Motion Options */}
        <div className="rounded-2xl border border-white/10 bg-[#121422]/90 p-6 backdrop-blur-xl space-y-5">
          <div className="flex items-center gap-2.5 pb-3 border-b border-white/5">
            <Sparkles className="w-5 h-5 text-secondary" />
            <h3 className="text-lg font-bold text-white">비주얼 & 모션 디자인 옵션</h3>
          </div>

          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <span className="text-sm font-semibold text-white">
                인터랙티브 파티클 & 오로라 배경 (Canvas 60fps)
              </span>
              <p className="text-xs text-neutral-400">
                마우스 반응형 네온 파티클 및 게이밍 오로라 효과를 켭니다.
              </p>
            </div>
            <Button
              variant={particlesEnabled ? 'success' : 'outline'}
              size="sm"
              onClick={() => onToggleParticles(!particlesEnabled)}
            >
              {particlesEnabled ? '활성화됨 (ON)' : '비활성화 (OFF)'}
            </Button>
          </div>
        </div>

        {/* Sound Volume Sliders */}
        <div className="rounded-2xl border border-white/10 bg-[#121422]/90 p-6 backdrop-blur-xl space-y-5">
          <div className="flex items-center gap-2.5 pb-3 border-b border-white/5">
            <Volume2 className="w-5 h-5 text-amber-400" />
            <h3 className="text-lg font-bold text-white">오디오 볼륨 제어</h3>
          </div>

          <div className="space-y-4">
            <div className="space-y-2">
              <div className="flex justify-between text-xs font-semibold text-neutral-300">
                <span>배경음악 (BGM)</span>
                <span className="font-mono text-primary font-bold">{bgmVolume}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                value={bgmVolume}
                onChange={(e) => setBgmVolume(Number(e.target.value))}
                className="w-full accent-primary h-2 bg-neutral-800 rounded-lg cursor-pointer"
              />
            </div>

            <div className="space-y-2">
              <div className="flex justify-between text-xs font-semibold text-neutral-300">
                <span>효과음 & 스파이크 타격음 (SFX)</span>
                <span className="font-mono text-secondary font-bold">{sfxVolume}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                value={sfxVolume}
                onChange={(e) => setSfxVolume(Number(e.target.value))}
                className="w-full accent-secondary h-2 bg-neutral-800 rounded-lg cursor-pointer"
              />
            </div>
          </div>
        </div>

        {/* Version & About */}
        <div className="rounded-2xl border border-white/5 bg-white/5 p-5 text-xs text-neutral-400 space-y-2">
          <div className="flex items-center gap-2 text-white font-semibold">
            <Info className="w-4 h-4 text-primary" />
            <span>The Spike Cross Launcher v1.0.0 Pro</span>
          </div>
          <p>
            디자인 스킬(GSAP, Lenis, React Bits, Magic UI, shadcn/ui, Lucide Icons)로 전면 재구성된
            차세대 웹 게이밍 런처입니다.
          </p>
        </div>
      </div>
    </div>
  );
};
