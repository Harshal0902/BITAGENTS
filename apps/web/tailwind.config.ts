import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/app/**/*.{ts,tsx}",
    "./src/components/**/*.{ts,tsx}",
    "./src/lib/**/*.{ts,tsx}"
  ],
  theme: {
    extend: {
      colors: {
        ember: "#ff6b4a",
        coral: "#ff8f70",
        ink: "#07090f",
        panel: "#111827",
        line: "#243044",
        mint: "#50e3b4",
        skybit: "#67d4ff"
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(255, 107, 74, 0.22), 0 20px 70px rgba(0, 0, 0, 0.35)"
      },
      fontFamily: {
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Monaco", "Consolas", "monospace"]
      }
    }
  },
  plugins: []
};

export default config;
