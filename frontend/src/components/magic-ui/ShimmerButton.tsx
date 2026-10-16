import React from 'react';
import { cn } from '@/lib/utils';

interface ShimmerButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  shimmerColor?: string;
  shimmerSize?: string;
  borderRadius?: string;
  shimmerDuration?: string;
  background?: string;
  className?: string;
  children?: React.ReactNode;
}

export const ShimmerButton = React.forwardRef<HTMLButtonElement, ShimmerButtonProps>(
  (
    {
      shimmerColor = '#ffffff',
      shimmerSize = '0.05em',
      shimmerDuration = '3s',
      borderRadius = '100px',
      background = 'linear-gradient(135deg, #ff4d4d 0%, #e11d48 100%)',
      className,
      children,
      ...props
    },
    ref
  ) => {
    return (
      <button
        ref={ref}
        style={
          {
            '--spread': '90deg',
            '--shimmer-color': shimmerColor,
            '--radius': borderRadius,
            '--speed': shimmerDuration,
            '--cut': shimmerSize,
            '--bg': background,
          } as React.CSSProperties
        }
        className={cn(
          'group relative z-0 flex cursor-pointer items-center justify-center overflow-hidden whitespace-nowrap border border-white/10 px-6 py-3 text-white [background:var(--bg)] [border-radius:var(--radius)] hover:scale-[1.02] active:scale-[0.98] transition-all duration-300 shadow-lg shadow-rose-950/40',
          className
        )}
        {...props}
      >
        {/* Spark container */}
        <div className="absolute inset-0 -z-30 overflow-visible [container-type:size]">
          <div className="absolute inset-0 h-[100cqh] animate-shimmer [aspect-ratio:1] [border-radius:0] [mask:none]">
            <div className="animate-spin-around absolute inset-[-100%] w-auto rotate-0 [background:conic-gradient(from_calc(270deg-(var(--spread)*0.5)),transparent_0,var(--shimmer-color)_var(--spread),transparent_var(--spread))] [translate:0_0]" />
          </div>
        </div>

        {/* Backdrop overlay */}
        <div className="absolute [inset:var(--cut)] -z-20 rounded-[inherit] bg-gradient-to-r from-red-600 to-rose-700 transition-colors duration-300 group-hover:from-red-500 group-hover:to-rose-600" />

        {/* Content */}
        <span className="relative z-10 flex items-center gap-2 font-bold tracking-wide">
          {children}
        </span>
      </button>
    );
  }
);

ShimmerButton.displayName = 'ShimmerButton';
