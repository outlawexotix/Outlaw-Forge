import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        cad: {
          bg: "#090d16",
          panel: "#0f172a",
          "panel-header": "#131d35",
          border: "#1e293b",
          "border-active": "#38bdf8",
          grid: "rgba(56, 189, 248, 0.05)",
          accent: "#06b6d4",
          "accent-amber": "#f59e0b",
          "accent-cyan": "#00f2fe",
          "accent-emerald": "#10b981",
          muted: "#64748b",
          text: "#f1f5f9",
          "text-dim": "#94a3b8",
        },
      },
      fontFamily: {
        mono: ["JetBrains Mono", "Fira Code", "ui-monospace", "SFMono-Regular", "Menlo", "Monaco", "Consolas", "monospace"],
        sans: ["Inter", "system-ui", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Roboto", "sans-serif"],
      },
      backgroundImage: {
        "cad-grid": "linear-gradient(to right, rgba(56, 189, 248, 0.04) 1px, transparent 1px), linear-gradient(to bottom, rgba(56, 189, 248, 0.04) 1px, transparent 1px)",
        "cad-grid-dense": "linear-gradient(to right, rgba(56, 189, 248, 0.08) 1px, transparent 1px), linear-gradient(to bottom, rgba(56, 189, 248, 0.08) 1px, transparent 1px)",
        "radial-dark": "radial-gradient(circle at 50% 50%, #131c31 0%, #080c14 100%)",
      },
      backgroundSize: {
        "grid-sm": "20px 20px",
        "grid-lg": "100px 100px",
      },
      boxShadow: {
        "glow-cyan": "0 0 15px rgba(6, 182, 212, 0.35)",
        "glow-amber": "0 0 15px rgba(245, 158, 11, 0.35)",
        "cad-panel": "0 4px 20px -2px rgba(0, 0, 0, 0.5)",
      },
    },
  },
  plugins: [],
};

export default config;
