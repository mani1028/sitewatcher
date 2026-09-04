import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: {
          DEFAULT: "#13212B",
          soft: "#3A4A55",
          mute: "#6B7C87",
        },
        mist: {
          DEFAULT: "#EEF3F1",
          deep: "#D8E4DF",
        },
        teal: {
          DEFAULT: "#0B5F4A",
          bright: "#11805F",
          soft: "#D7EFE6",
        },
        alert: {
          down: "#C23B2E",
          slow: "#C47A12",
          up: "#0B5F4A",
        },
      },
      fontFamily: {
        display: ["var(--font-display)", "sans-serif"],
        sans: ["var(--font-sans)", "sans-serif"],
        mono: ["var(--font-mono)", "monospace"],
      },
      boxShadow: {
        soft: "0 18px 50px rgba(19, 33, 43, 0.08)",
      },
      keyframes: {
        rise: {
          "0%": { opacity: "0", transform: "translateY(10px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        pulseDot: {
          "0%, 100%": { transform: "scale(1)", opacity: "1" },
          "50%": { transform: "scale(1.25)", opacity: "0.7" },
        },
      },
      animation: {
        rise: "rise 0.45s ease-out both",
        "pulse-dot": "pulseDot 1.8s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
