/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#0b0c13",
        surface: "#121420",
        "surface-card": "#181b2c",
        "surface-hover": "#22263d",
        border: "#262b45",
        primary: {
          DEFAULT: "#ff4d4d", // The Spike의 강렬한 스파이크 레드/오렌지
          foreground: "#ffffff",
          glow: "#ff3366",
        },
        secondary: {
          DEFAULT: "#38bdf8", // 사이버 블루
          foreground: "#0b0c13",
        },
        accent: {
          DEFAULT: "#fbbf24", // 배구공 골드 옐로우
          foreground: "#0b0c13",
        },
        muted: {
          DEFAULT: "#8e98b0",
          foreground: "#cbd5e1",
        },
      },
      fontFamily: {
        sans: ["Pretendard", "Inter", "sans-serif"],
        display: ["Teko", "Impact", "sans-serif"],
      },
      animation: {
        "border-beam": "border-beam calc(var(--duration)*1s) infinite linear",
        marquee: "marquee var(--duration) linear infinite",
        "marquee-vertical": "marquee-vertical var(--duration) linear infinite",
        shimmer: "shimmer 2s linear infinite",
        pulseGlow: "pulseGlow 2.5s ease-in-out infinite",
        float: "float 4s ease-in-out infinite",
      },
      keyframes: {
        "border-beam": {
          "100%": {
            "offset-distance": "100%",
          },
        },
        marquee: {
          from: { transform: "translateX(0)" },
          to: { transform: "translateX(calc(-100% - var(--gap)))" },
        },
        "marquee-vertical": {
          from: { transform: "translateY(0)" },
          to: { transform: "translateY(calc(-100% - var(--gap)))" },
        },
        shimmer: {
          from: { backgroundPosition: "0 0" },
          to: { backgroundPosition: "-200% 0" },
        },
        pulseGlow: {
          "0%, 100%": { opacity: 0.6, transform: "scale(1)" },
          "50%": { opacity: 1, transform: "scale(1.05)" },
        },
        float: {
          "0%, 100%": { transform: "translateY(0px)" },
          "50%": { transform: "translateY(-10px)" },
        },
      },
    },
  },
  plugins: [],
}
