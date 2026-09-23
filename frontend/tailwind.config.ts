import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        panel: "#111827",
        panelborder: "#1f2937",
        status: {
          up: "#22c55e",
          warning: "#eab308",
          critical: "#ef4444",
          down: "#ef4444",
          unknown: "#6b7280",
        },
      },
    },
  },
  plugins: [],
};

export default config;
