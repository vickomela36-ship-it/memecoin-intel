import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: {
          primary: "#0A0A0F",
          surface: "#12121A",
          elevated: "#1A1A25",
        },
        text: {
          primary: "#E8E6E1",
          secondary: "#8A8A95",
          tertiary: "#4A4A55",
        },
        signal: {
          long: "#00E5A0",
          short: "#FF3B5C",
          neutral: "#FFB800",
          edge: "#7B61FF",
        },
      },
      fontFamily: {
        display: ["var(--font-jetbrains)", "monospace"],
        body: ["var(--font-inter)", "-apple-system", "sans-serif"],
      },
      fontSize: {
        xs: "0.6875rem",
        sm: "0.8125rem",
        base: "0.9375rem",
        lg: "1.125rem",
        xl: "1.5rem",
        "2xl": "2rem",
      },
      borderRadius: {
        card: "4px",
        input: "2px",
        btn: "6px",
      },
    },
  },
  plugins: [],
};
export default config;
