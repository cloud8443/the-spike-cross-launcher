import React, { useState } from 'react';
import { SmoothScrollProvider } from '@/components/providers/SmoothScrollProvider';
import { ParticlesBackground } from '@/components/react-bits/ParticlesBackground';
import { Sidebar } from '@/components/launcher/Sidebar';
import { HomeView } from '@/components/launcher/HomeView';
import { MultiplayerView } from '@/components/launcher/MultiplayerView';
import { SettingsView } from '@/components/launcher/SettingsView';

export function App() {
  const [currentTab, setCurrentTab] = useState<'home' | 'multiplayer' | 'settings'>('home');
  const [serverHost, setServerHost] = useState('146.56.101.107');
  const [serverPort, setServerPort] = useState(5555);

  const onlineCount = 1;
  const serverOnline = true;

  return (
    <SmoothScrollProvider>
      <div className="relative min-h-screen bg-[#08090e] text-slate-100 flex overflow-x-hidden">
        {/* Subtle Background Particles */}
        <ParticlesBackground />

        {/* Global Ambient Glow Overlays */}
        <div className="pointer-events-none fixed -top-40 -left-40 w-[500px] h-[500px] bg-red-600/10 rounded-full blur-[140px] z-0" />
        <div className="pointer-events-none fixed top-1/2 -right-40 w-[500px] h-[500px] bg-sky-500/10 rounded-full blur-[150px] z-0" />

        {/* Left Sidebar */}
        <Sidebar
          currentTab={currentTab}
          onSelectTab={setCurrentTab}
          onlineCount={onlineCount}
          serverOnline={serverOnline}
        />

        {/* Right Main Content */}
        <main className="flex-1 relative z-10 px-8 py-8 min-w-0">
          <div className="max-w-5xl mx-auto">
            {currentTab === 'home' && <HomeView />}
            {currentTab === 'multiplayer' && <MultiplayerView />}
            {currentTab === 'settings' && (
              <SettingsView
                serverHost={serverHost}
                serverPort={serverPort}
                onUpdateServer={(h, p) => {
                  setServerHost(h);
                  setServerPort(p);
                }}
              />
            )}
          </div>
        </main>
      </div>
    </SmoothScrollProvider>
  );
}

export default App;
