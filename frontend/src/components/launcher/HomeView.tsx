import React, { useRef } from 'react';
import gsap from 'gsap';
import { useGSAP } from '@gsap/react';
import confetti from 'canvas-confetti';
import {
  Play,
  Zap,
  Globe,
  MessageSquare,
  Trophy,
  Server,
  Cpu,
  ArrowRight,
  Sparkles,
} from 'lucide-react';
import { ShinyText } from '@/components/react-bits/ShinyText';
import { DecryptedText } from '@/components/react-bits/DecryptedText';
import { BorderBeam } from '@/components/magic-ui/BorderBeam';
import { Marquee } from '@/components/magic-ui/Marquee';
import { BentoGrid, BentoCard } from '@/components/magic-ui/BentoGrid';
import { ShimmerButton } from '@/components/magic-ui/ShimmerButton';
import { Badge } from '@/components/ui/badge';

interface HomeViewProps {
  onGoToMultiplayer: () => void;
  onlineCount: number;
  serverOnline: boolean;
  ping: number;
}

export const HomeView: React.FC<HomeViewProps> = ({
  onGoToMultiplayer,
  onlineCount,
  serverOnline,
  ping,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const heroRef = useRef<HTMLDivElement>(null);

  // GSAP 쾌속 인트로 애니메이션
  useGSAP(
    () => {
      const tl = gsap.timeline();
      tl.from('.gsap-hero-badge', {
        opacity: 0,
        y: -20,
        duration: 0.6,
        ease: 'power3.out',
      })
        .from(
          '.gsap-hero-title',
          {
            opacity: 0,
            scale: 0.95,
            y: 20,
            duration: 0.8,
            ease: 'back.out(1.7)',
          },
          '-=0.3'
        )
        .from(
          '.gsap-hero-desc',
          {
            opacity: 0,
            y: 20,
            duration: 0.6,
            ease: 'power3.out',
          },
          '-=0.4'
        )
        .from(
          '.gsap-hero-buttons',
          {
            opacity: 0,
            y: 20,
            duration: 0.6,
            ease: 'power3.out',
          },
          '-=0.3'
        )
        .from(
          '.gsap-server-card',
          {
            opacity: 0,
            y: 30,
            duration: 0.8,
            ease: 'power3.out',
          },
          '-=0.2'
        )
        .from(
          '.gsap-bento',
          {
            opacity: 0,
            y: 40,
            duration: 0.8,
            stagger: 0.15,
            ease: 'power3.out',
          },
          '-=0.4'
        );
    },
    { scope: containerRef }
  );

  const handleLaunchSteamGame = () => {
    // 폭죽 연출
    confetti({
      particleCount: 80,
      spread: 70,
      origin: { y: 0.7 },
      colors: ['#ff4d4d', '#ff7849', '#38bdf8', '#fbbf24'],
    });

    // 스팀 프로토콜 URI 실행
    window.location.href = 'steam://rungameid/3983810';
  };

  const marqueeAnnouncements = [
    '🏐 더 스파이크 크로스 v1.0 멀티플레이어 정식 릴리즈 오픈!',
    '⚡ 오라클 클라우드 춘천 리전 전용 고속 매칭 릴레이 서버 가동 중 (평균 핑 20ms)',
    '⚔️ 1:1 친선전 공방 실시간 대기실에서 상대를 찾아 스파이크를 날리세요!',
    '🏆 실시간 패킷 프레이밍 및 연결 끊김 자동 복구 엔진 적용 완료',
    '💬 대기실 인게임 소통을 위한 고속 암호화 채팅 시스템 탑재',
  ];

  return (
    <div ref={containerRef} className="space-y-12 pb-24">
      {/* Marquee Banner */}
      <div className="relative -mx-8 -mt-8 mb-6 border-b border-white/10 bg-[#0e101c]/80 backdrop-blur-md">
        <Marquee pauseOnHover className="py-2.5">
          {marqueeAnnouncements.map((item, idx) => (
            <div key={idx} className="flex items-center gap-3 text-xs font-semibold text-neutral-300">
              <span className="flex h-2 w-2 rounded-full bg-primary animate-ping" />
              <span>{item}</span>
              <span className="text-white/20">|</span>
            </div>
          ))}
        </Marquee>
      </div>

      {/* Hero Section */}
      <div
        ref={heroRef}
        className="relative overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-b from-[#16192e]/90 via-[#0f1120]/90 to-[#0a0c16]/90 p-8 md:p-14 shadow-2xl backdrop-blur-2xl"
      >
        <BorderBeam size={320} duration={12} colorFrom="#ff4d4d" colorTo="#38bdf8" />

        {/* Hero Background Glows */}
        <div className="pointer-events-none absolute -right-20 -top-20 h-96 w-96 rounded-full bg-primary/20 blur-[100px]" />
        <div className="pointer-events-none absolute -left-20 -bottom-20 h-96 w-96 rounded-full bg-secondary/15 blur-[100px]" />

        <div className="relative z-10 max-w-3xl space-y-6">
          <div className="gsap-hero-badge flex flex-wrap items-center gap-2.5">
            <Badge variant="live" className="px-3.5 py-1 text-xs">
              <Sparkles className="w-3.5 h-3.5 mr-1 text-emerald-400" /> ONLINE MULTIPLAYER READY
            </Badge>
            <Badge variant="outline" className="px-3 py-1 text-xs font-mono">
              OCI Cloud 146.56.101.107:5555
            </Badge>
          </div>

          <div className="gsap-hero-title space-y-2">
            <h2 className="text-sm md:text-base font-extrabold uppercase tracking-widest text-primary">
              <DecryptedText text="NEXT-GEN VOLLEYBALL ACTION" speed={30} />
            </h2>
            <h1 className="font-teko text-5xl md:text-7xl lg:text-8xl tracking-tight leading-none text-white font-bold drop-shadow-md">
              <ShinyText text="THE SPIKE CROSS" speed={4} />
            </h1>
          </div>

          <p className="gsap-hero-desc text-base md:text-lg text-neutral-300 max-w-2xl leading-relaxed font-normal">
            더 강력해진 오라클 클라우드 중앙 중계 서버를 통해, 전 세계 친구 및 라이벌과
            지연 없는 1:1 배구 매치를 즐기세요. 스팀 자동 실행과 실시간 공방 매칭을 지원합니다.
          </p>

          <div className="gsap-hero-buttons flex flex-wrap items-center gap-4 pt-2">
            <ShimmerButton
              onClick={handleLaunchSteamGame}
              shimmerColor="#ffffff"
              shimmerDuration="2.5s"
              className="px-8 py-4 text-base font-bold shadow-xl shadow-red-950/60"
            >
              <Play className="w-5 h-5 fill-current" />
              <span>스팀으로 게임 실행</span>
            </ShimmerButton>

            <button
              onClick={onGoToMultiplayer}
              className="flex items-center gap-2.5 px-7 py-3.5 rounded-full text-base font-bold text-white bg-white/5 hover:bg-white/10 border border-white/15 transition-all duration-300 hover:scale-105 hover:border-white/30 backdrop-blur-lg"
            >
              <Zap className="w-5 h-5 text-amber-400" />
              <span>온라인 공방 입장하기</span>
              <ArrowRight className="w-4 h-4 ml-1" />
            </button>
          </div>
        </div>
      </div>

      {/* Real-time Server Infrastructure Card */}
      <div className="gsap-server-card relative overflow-hidden rounded-2xl border border-white/10 bg-[#121422]/80 p-6 backdrop-blur-xl">
        <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-6">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Server className="w-5 h-5 text-primary" />
              <h3 className="text-lg font-bold text-white tracking-wide">
                오라클 클라우드 고성능 중계 인프라
              </h3>
              <Badge variant="success">24/7 데몬 가동 중</Badge>
            </div>
            <p className="text-sm text-neutral-400">
              춘천 리전 (ap-chuncheon-1) 4 OCPU / 24GB RAM 인프라에서 구동되는 고속 TCP 매칭 엔진
            </p>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 w-full lg:w-auto">
            <div className="p-3 rounded-xl bg-white/5 border border-white/5 text-center min-w-[100px]">
              <span className="text-[11px] text-neutral-400 uppercase font-semibold">서버 상태</span>
              <p className="text-sm font-bold text-emerald-400 mt-0.5">정상 (Online)</p>
            </div>
            <div className="p-3 rounded-xl bg-white/5 border border-white/5 text-center min-w-[100px]">
              <span className="text-[11px] text-neutral-400 uppercase font-semibold">네트워크 핑</span>
              <p className="text-sm font-bold text-emerald-400 mt-0.5 font-mono">{ping} ms</p>
            </div>
            <div className="p-3 rounded-xl bg-white/5 border border-white/5 text-center min-w-[100px]">
              <span className="text-[11px] text-neutral-400 uppercase font-semibold">접속자 수</span>
              <p className="text-sm font-bold text-sky-400 mt-0.5 font-mono">{onlineCount} 명</p>
            </div>
            <div className="p-3 rounded-xl bg-white/5 border border-white/5 text-center min-w-[100px]">
              <span className="text-[11px] text-neutral-400 uppercase font-semibold">포트 보안</span>
              <p className="text-sm font-bold text-amber-400 mt-0.5">5555 TCP 개방</p>
            </div>
          </div>
        </div>
      </div>

      {/* Feature Bento Grid (Magic UI) */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">
              <Zap className="w-6 h-6 text-primary" />
              멀티플레이어 핵심 기능
            </h2>
            <p className="text-sm text-neutral-400 mt-1">
              더 스파이크 크로스를 위한 최적화된 넷플레이 시스템
            </p>
          </div>
        </div>

        <BentoGrid className="gsap-bento">
          <BentoCard
            name="실시간 1:1 친선전 공방"
            className="md:col-span-2"
            description="공개 방을 개설하거나 검색하여 친구 및 전 세계 유저와 즉시 매칭하고 대기실에서 게임을 준비하세요."
            Icon={Trophy}
            cta="방 목록 둘러보기"
            background={
              <div className="absolute -right-10 -bottom-10 h-64 w-64 rounded-full bg-red-600/10 blur-3xl" />
            }
          />
          <BentoCard
            name="초저지연 P2P TCP 엔진"
            className="md:col-span-1"
            description="오라클 클라우드 백본망을 통한 초고속 데이터 릴레이로 조작 인풋 렉을 최소화합니다."
            Icon={Globe}
            cta="서버 사양 확인"
            background={
              <div className="absolute -right-10 -bottom-10 h-64 w-64 rounded-full bg-sky-500/10 blur-3xl" />
            }
          />
          <BentoCard
            name="실시간 대기실 인게임 채팅"
            className="md:col-span-1"
            description="상대방과의 원활한 경기 진행을 위해 실시간 메시지 송수신과 참가/퇴장 알림을 완벽 지원합니다."
            Icon={MessageSquare}
            cta="채팅 테스트"
            background={
              <div className="absolute -right-10 -bottom-10 h-64 w-64 rounded-full bg-amber-500/10 blur-3xl" />
            }
          />
          <BentoCard
            name="스팀 클라이언트 원클릭 연동"
            className="md:col-span-2"
            description="스팀(Steam)의 App ID(3983810) 프로토콜을 다이렉트로 호출하여 번거로운 게임 검색 없이 즉시 기동합니다."
            Icon={Play}
            cta="스팀 런처 바로가기"
            background={
              <div className="absolute -right-10 -bottom-10 h-64 w-64 rounded-full bg-rose-600/10 blur-3xl" />
            }
          />
        </BentoGrid>
      </div>
    </div>
  );
};
