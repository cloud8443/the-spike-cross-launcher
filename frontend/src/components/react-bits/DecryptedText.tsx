import React, { useState, useEffect } from 'react';

interface DecryptedTextProps {
  text: string;
  speed?: number;
  maxIterations?: number;
  characters?: string;
  className?: string;
  parentClassName?: string;
  animateOn?: 'view' | 'hover';
}

export const DecryptedText: React.FC<DecryptedTextProps> = ({
  text,
  speed = 40,
  maxIterations = 10,
  characters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890!@#$%^&*()_+-=<>?/',
  className = '',
  parentClassName = '',
}) => {
  const [displayText, setDisplayText] = useState<string>(text);
  const [isHovered, setIsHovered] = useState<boolean>(false);

  useEffect(() => {
    let iteration = 0;
    const interval = setInterval(() => {
      setDisplayText(
        text
          .split('')
          .map((letter, index) => {
            if (letter === ' ') return ' ';
            if (index < iteration) {
              return text[index];
            }
            return characters[Math.floor(Math.random() * characters.length)];
          })
          .join('')
      );

      if (iteration >= text.length) {
        clearInterval(interval);
      }

      iteration += 1 / (maxIterations / text.length);
    }, speed);

    return () => clearInterval(interval);
  }, [text, speed, maxIterations, characters, isHovered]);

  return (
    <span
      className={`inline-block ${parentClassName}`}
      onMouseEnter={() => setIsHovered((prev) => !prev)}
    >
      <span className={className}>{displayText}</span>
    </span>
  );
};
