import React from 'react';
import { cn } from '@/lib/utils';

interface ShinyTextProps {
  text: string;
  disabled?: boolean;
  speed?: number;
  className?: string;
}

export const ShinyText: React.FC<ShinyTextProps> = ({
  text,
  disabled = false,
  speed = 5,
  className,
}) => {
  const animationDuration = `${speed}s`;

  return (
    <span
      className={cn(
        'inline-block bg-clip-text text-transparent bg-gradient-to-r from-neutral-200 via-white to-neutral-400 font-extrabold',
        !disabled && 'animate-shimmer bg-[length:200%_100%]',
        className
      )}
      style={{
        animationDuration,
      }}
    >
      {text}
    </span>
  );
};
