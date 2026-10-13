import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        rafiq: {
          navy: "#1F4E79",
          teal: "#0E7C86",
          bg: "#F7FAFB",
          text: "#1A2B3C",
          muted: "#5B6B7A",
          border: "#DDE5EA",
          surface: "#FFFFFF",
        },
        clinsight: {
          navy: "#1F4E79",
          teal: "#0E7C86",
          bg: "#F7FAFB",
          text: "#1A2B3C",
          muted: "#5B6B7A",
          border: "#DDE5EA",
          surface: "#FFFFFF",
        },
        severity: {
          info: {
            DEFAULT: "#DBEAFE",
            text: "#1E40AF",
          },
          review: {
            DEFAULT: "#FEF3C7",
            text: "#92400E",
          },
          urgent: {
            DEFAULT: "#FEE2E2",
            text: "#991B1B",
          },
          done: {
            DEFAULT: "#DCFCE7",
            text: "#166534",
          },
        },
        border: "var(--border)",
        input: "var(--input)",
        ring: "var(--ring)",
        background: "var(--background)",
        foreground: "var(--foreground)",
        primary: {
          DEFAULT: "var(--primary)",
          foreground: "var(--primary-foreground)",
        },
        secondary: {
          DEFAULT: "var(--secondary)",
          foreground: "var(--secondary-foreground)",
        },
        muted: {
          DEFAULT: "var(--muted)",
          foreground: "var(--muted-foreground)",
        },
        card: {
          DEFAULT: "var(--card)",
          foreground: "var(--card-foreground)",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      fontFamily: {
        sans: ["var(--font-inter)", "Inter", "system-ui", "sans-serif"],
        arabic: ["var(--font-arabic)", "IBM Plex Sans Arabic", "system-ui", "sans-serif"],
      },
      spacing: {
        "grid-1": "8px",
        "grid-2": "16px",
        "grid-3": "24px",
        "grid-4": "32px",
      },
    },
  },
  plugins: [],
};

export default config;
