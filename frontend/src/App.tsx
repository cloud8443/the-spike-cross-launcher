import React, { useState, useEffect } from 'react';
import { SmoothScrollProvider } from '@/components/providers/SmoothScrollProvider';
import { ParticlesBackground } from '@/components/react-bits/ParticlesBackground';
import { Sidebar } from '@/components/launcher/Sidebar';
import { HomeView } from '@/components/launcher/HomeView';
import { MultiplayerView } from '@/components/launcher/MultiplayerView';
import { SettingsView } from '@/components/launcher/SettingsView';

export function App() {
  const [currentTab, setCurrentTab] = useState<'home' | 'multiplayer' | 'settings'>('home');
  const [nickname, setNickname] = useState('구름');
  const [serverHost, setServerHost] = useState('146.56.101.107');
  const [serverPort, setServerPort] = useState(5555);
  const [particlesEnabled, setParticlesEnabled] = useState(true);

  // 시뮬레이션 상태 (오라클 클라우드 연동)
  const [onlineCount, setOnlineCount] = useState(4);
  const [ping, setPing] = useState(19);
  const serverOnline = true;

  useEffect(() => {
    // 핑 & 접속자 수 미세 변동 시뮬레이션
    const interval = setInterval(() => {
      setPing(Math.floor(17 + Math.random() * 5));
    }, 4000);
    return () => clearInterval(interval);
  }, []);

  return (
    <SmoothScrollProvider>
      <div className="relative min-h-screen bg-[#08090e] text-slate-100 flex overflow-x-hidden">
        {/* Background Particles Canvas */}
        {particlesEnabled && <ParticlesBackground />}

        {/* Global Ambient Glow Overlays */}
        <div className="pointer-events-none fixed -top-40 -left-40 w-[550px] h-[550px] bg-red-600/10 rounded-full blur-[140px] z-0" />
        <div className="pointer-events-none fixed top-1/2 -right-40 w-[600px] h-[600px] bg-sky-500/10 rounded-full blur-[150px] z-0" />

        {/* Left Sticky Sidebar */}
        <Sidebar
          currentTab={currentTab}
          onSelectTab={setCurrentTab}
          onlineCount={onlineCount}
          serverOnline={serverOnline}
          ping={ping}
        />

        {/* Right Main Content Area */}
        <main className="flex-1 relative z-10 px-8 py-8 min-w-0">
          <div className="max-w-7xl mx-auto">
            {currentTab === 'home' && (
              <HomeView
                onGoToMultiplayer={() => setCurrentTab('multiplayer')}
                onlineCount={onlineCount}
                serverOnline={serverOnline}
                ping={ping}
              />
            )}

            {currentTab === 'multiplayer' && (
              <MultiplayerView
                nickname={nickname}
                onUpdateNickname={setNickname}
              />
            )}

            {currentTab === 'settings' && (
              <SettingsView
                serverHost={serverHost}
                serverPort={serverPort}
                onUpdateServer={(h, p) => {
                  setServerHost(h);
                  setServerPort(p);
                }}
                particlesEnabled={particlesEnabled}
                onToggleParticles={setParticlesEnabled}
              />
            )}
          </div>
        </main>
      </div>
    </SmoothScrollProvider>
  );
}

export default App;
