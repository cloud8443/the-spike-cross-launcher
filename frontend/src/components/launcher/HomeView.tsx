import React, { useRef, useState } from 'react';
import gsap from 'gsap';
import { useGSAP } from '@gsap/react';
import { Play } from 'lucide-react';
import { ShinyText } from '@/components/react-bits/ShinyText';
import { BorderBeam } from '@/components/magic-ui/BorderBeam';
import { ShimmerButton } from '@/components/magic-ui/ShimmerButton';

export const HomeView: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [statusText, setStatusText] = useState('상태: 준비 완료');

  useGSAP(
    () => {
      gsap.from('.gsap-home-content', {
        opacity: 0,
        y: 20,
        duration: 0.7,
        ease: 'power3.out',
      });
    },
    { scope: containerRef }
  );

  const handleLaunchGame = () => {
    try {
      window.location.href = 'steam://rungameid/3983810';
      setStatusText('상태: 스팀 실행 명령 전달됨');
    } catch (e) {
      setStatusText('상태: 실행 오류');
    }
  };

  return (
    <div ref={containerRef} className="h-full flex items-center justify-center py-16">
      <div className="gsap-home-content relative w-full max-w-2xl rounded-3xl border border-white/10 bg-[#121420]/90 p-10 md:p-14 backdrop-blur-2xl text-center space-y-8 shadow-2xl overflow-hidden">
        <BorderBeam size={280} duration={10} colorFrom="#ff4d4d" colorTo="#38bdf8" />

        <div className="space-y-3">
          <h1 className="text-3xl md:text-5xl font-extrabold text-white tracking-tight">
            <ShinyText text="더 스파이크 크로스 (The Spike Cross)" speed={4} />
          </h1>
        </div>

        <div className="pt-2 flex flex-col items-center gap-4">
          <ShimmerButton
            onClick={handleLaunchGame}
            className="w-full max-w-sm py-4 text-lg font-bold shadow-xl shadow-red-950/50"
          >
            <Play className="w-5 h-5 fill-current" />
            <span>게임 시작 (Steam)</span>
          </ShimmerButton>

          <p className="text-sm font-semibold text-emerald-400">
            {statusText}
          </p>
        </div>
      </div>
    </div>
  );
};
