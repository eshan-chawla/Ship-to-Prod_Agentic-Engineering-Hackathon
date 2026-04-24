import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#172019",
        paper: "#f4efe2",
        clay: "#bc5f3a",
        moss: "#526c45",
        brass: "#c7943e",
        line: "#d7cab2"
      },
      boxShadow: {
        hard: "8px 8px 0 #172019"
      }
    }
  },
  plugins: []
};

export default config;

