import React from 'react';
import { cn } from '@/lib/utils';

export const BentoGrid = ({
  className,
  children,
}: {
  className?: string;
  children: React.ReactNode;
}) => {
  return (
    <div
      className={cn(
        'grid w-full auto-rows-[18rem] grid-cols-1 md:grid-cols-3 gap-5 max-w-7xl mx-auto',
        className
      )}
    >
      {children}
    </div>
  );
};

export const BentoCard = ({
  className,
  name,
  classNameContent,
  background,
  Icon,
  description,
  href,
  cta,
}: {
  className?: string;
  name: string;
  classNameContent?: string;
  background?: React.ReactNode;
  Icon?: React.ElementType;
  description: string;
  href?: string;
  cta?: string;
}) => {
  return (
    <div
      className={cn(
        'group relative col-span-1 flex flex-col justify-between overflow-hidden rounded-2xl',
        'bg-[#121420]/80 border border-white/10 [box-shadow:0_0_0_1px_rgba(255,255,255,.05)] backdrop-blur-xl',
        'hover:border-white/20 hover:shadow-2xl hover:shadow-black/60 transition-all duration-300',
        className
      )}
    >
      <div className="absolute inset-0 z-0">{background}</div>
      <div className="pointer-events-none z-10 flex flex-col gap-1 p-6 transition-all duration-300 group-hover:-translate-y-2">
        {Icon && (
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-white/5 border border-white/10 text-white shadow-inner mb-2 group-hover:scale-110 group-hover:text-primary transition-all duration-300">
            <Icon className="h-6 w-6" />
          </div>
        )}
        <h3 className="text-xl font-bold text-white tracking-wide">{name}</h3>
        <p className="max-w-lg text-sm text-neutral-400 leading-relaxed">{description}</p>
      </div>

      <div
        className={cn(
          'pointer-events-none absolute bottom-0 flex w-full translate-y-10 transform-gpu flex-row items-center p-4 opacity-0 transition-all duration-300 group-hover:translate-y-0 group-hover:opacity-100',
          classNameContent
        )}
      >
        {cta && (
          <div className="pointer-events-auto flex items-center text-xs font-semibold text-primary gap-1 tracking-wider uppercase">
            {cta} →
          </div>
        )}
      </div>
      <div className="pointer-events-none absolute inset-0 transform-gpu transition-all duration-300 group-hover:bg-gradient-to-t group-hover:from-red-500/10 group-hover:via-transparent" />
    </div>
  );
};
