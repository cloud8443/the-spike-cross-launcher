import React from 'react';
import { Home, Swords, Settings, Circle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface SidebarProps {
  currentTab: 'home' | 'multiplayer' | 'settings';
  onSelectTab: (tab: 'home' | 'multiplayer' | 'settings') => void;
  onlineCount: number;
  serverOnline: boolean;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  onSelectTab,
  onlineCount,
  serverOnline,
}) => {
  const navItems = [
    { id: 'home', label: '🏠 홈 / 로비', icon: Home },
    { id: 'multiplayer', label: '⚔️ 멀티플레이 (공방)', icon: Swords },
    { id: 'settings', label: '⚙️ 설정', icon: Settings },
  ] as const;

  return (
    <aside className="w-56 h-screen sticky top-0 flex flex-col justify-between p-4 bg-[#121420]/95 border-r border-white/10 backdrop-blur-xl z-30 select-none">
      <div>
        {/* Title */}
        <div
          className="px-3 py-4 mb-4 cursor-pointer"
          onClick={() => onSelectTab('home')}
        >
          <h1 className="font-teko text-3xl font-bold tracking-wider text-white">
            SPIKE CROSS
          </h1>
        </div>

        {/* Navigation Items */}
        <nav className="space-y-1">
          {navItems.map((item) => {
            const isActive = currentTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onSelectTab(item.id)}
                className={cn(
                  'w-full flex items-center px-4 py-3 rounded-xl text-sm font-semibold transition-all duration-200 text-left',
                  isActive
                    ? 'bg-gradient-to-r from-red-600/25 to-rose-500/10 text-white border border-red-500/30'
                    : 'text-neutral-400 hover:text-white hover:bg-white/5 border border-transparent'
                )}
              >
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
      </div>

      {/* Server Status Panel */}
      <div className="rounded-xl p-3 bg-[#181b2c] border border-white/10 space-y-1.5 text-xs">
        <div className="flex items-center gap-2">
          <Circle
            className={cn(
              'w-2.5 h-2.5 fill-current',
              serverOnline ? 'text-emerald-400' : 'text-rose-500'
            )}
          />
          <span className="font-bold text-white">
            {serverOnline ? '서버 정상 연결' : '서버 연결 끊김'}
          </span>
        </div>
        <div className="text-neutral-400 pl-4.5">
          접속자: <span className="text-white font-mono font-bold">{onlineCount}</span>명
        </div>
      </div>
    </aside>
  );
};
