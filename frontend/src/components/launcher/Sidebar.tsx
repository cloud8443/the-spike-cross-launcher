import React from 'react';
import { Home, Swords, Settings, Flame, Activity, Wifi, ShieldCheck } from 'lucide-react';
import { cn } from '@/lib/utils';

interface SidebarProps {
  currentTab: 'home' | 'multiplayer' | 'settings';
  onSelectTab: (tab: 'home' | 'multiplayer' | 'settings') => void;
  onlineCount: number;
  serverOnline: boolean;
  ping: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  onSelectTab,
  onlineCount,
  serverOnline,
  ping,
}) => {
  interface NavItem {
    id: 'home' | 'multiplayer' | 'settings';
    label: string;
    icon: React.ElementType;
    badge?: string;
  }

  const navItems: NavItem[] = [
    { id: 'home', label: '홈 / 대시보드', icon: Home, badge: 'READY' },
    { id: 'multiplayer', label: '멀티플레이 (공방)', icon: Swords, badge: 'HOT' },
    { id: 'settings', label: '런처 설정', icon: Settings },
  ];

  return (
    <aside className="w-64 h-screen sticky top-0 flex flex-col justify-between p-4 bg-[#0d0f1a]/95 border-r border-white/10 backdrop-blur-2xl z-30 select-none">
      <div>
        {/* Logo */}
        <div className="flex items-center gap-3 px-3 py-4 mb-6 group cursor-pointer" onClick={() => onSelectTab('home')}>
          <div className="relative flex items-center justify-center w-11 h-11 rounded-2xl bg-gradient-to-tr from-red-600 via-rose-500 to-amber-500 p-[1.5px] shadow-lg shadow-rose-950/60 group-hover:scale-105 transition-transform duration-300">
            <div className="w-full h-full bg-[#121422] rounded-[14px] flex items-center justify-center">
              <Flame className="w-6 h-6 text-primary animate-pulse" />
            </div>
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="font-teko text-2xl tracking-wider text-white font-bold leading-none">
                SPIKE CROSS
              </span>
              <span className="text-[10px] px-1.5 py-0.5 rounded font-black tracking-widest bg-primary text-white uppercase">
                PRO
              </span>
            </div>
            <p className="text-[11px] text-neutral-400 tracking-tight font-medium">
              Multiplayer Edition
            </p>
          </div>
        </div>

        {/* Navigation Items */}
        <nav className="space-y-1.5">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onSelectTab(item.id)}
                className={cn(
                  'w-full flex items-center justify-between px-3.5 py-3 rounded-xl text-sm font-semibold transition-all duration-200 group text-left relative overflow-hidden',
                  isActive
                    ? 'bg-gradient-to-r from-red-600/20 via-rose-500/10 to-transparent text-white border border-red-500/30 shadow-md shadow-red-950/20'
                    : 'text-neutral-400 hover:text-white hover:bg-white/5 border border-transparent'
                )}
              >
                {isActive && (
                  <span className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-5 bg-primary rounded-r-full" />
                )}
                <div className="flex items-center gap-3">
                  <Icon
                    className={cn(
                      'w-5 h-5 transition-transform duration-200 group-hover:scale-110',
                      isActive ? 'text-primary' : 'text-neutral-400 group-hover:text-neutral-200'
                    )}
                  />
                  <span>{item.label}</span>
                </div>
                {item.badge && (
                  <span
                    className={cn(
                      'text-[10px] px-2 py-0.5 rounded-full font-bold uppercase tracking-wider',
                      item.badge === 'HOT'
                        ? 'bg-primary/20 text-primary border border-primary/30 animate-pulse'
                        : 'bg-white/10 text-neutral-300'
                    )}
                  >
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Server Status Panel */}
      <div className="rounded-2xl p-4 bg-[#141727]/80 border border-white/10 backdrop-blur-xl space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-neutral-300 flex items-center gap-1.5">
            <Activity className="w-3.5 h-3.5 text-primary" /> 오라클 클라우드
          </span>
          <div className="flex items-center gap-1.5">
            <span
              className={cn(
                'w-2 h-2 rounded-full',
                serverOnline ? 'bg-emerald-400 animate-ping' : 'bg-rose-500'
              )}
            />
            <span
              className={cn(
                'text-[11px] font-bold',
                serverOnline ? 'text-emerald-400' : 'text-rose-400'
              )}
            >
              {serverOnline ? '온라인' : '점검중'}
            </span>
          </div>
        </div>

        <div className="space-y-1.5 text-xs text-neutral-400">
          <div className="flex justify-between items-center">
            <span className="flex items-center gap-1">
              <Wifi className="w-3 h-3 text-secondary" /> 지연 시간 (Ping)
            </span>
            <span className="font-mono text-emerald-400 font-bold">{ping}ms</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="flex items-center gap-1">
              <ShieldCheck className="w-3 h-3 text-amber-400" /> 접속 중인 유저
            </span>
            <span className="font-mono text-white font-bold">{onlineCount}명</span>
          </div>
        </div>

        <div className="pt-2 border-t border-white/5 flex items-center justify-between text-[10px] text-neutral-400">
          <span>포트: 5555 (TCP)</span>
          <span className="text-neutral-400">v1.0.0</span>
        </div>
      </div>
    </aside>
  );
};
