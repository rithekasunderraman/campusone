/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#12233D",
        navy: "#0F2A4A",
        brass: "#B98B3E",
        brassLight: "#D9AE6B",
        paper: "#F6F4EF",
        slate: "#5B6B7C",
        leaf: "#3D7A5C",
        clay: "#B5573C",
      },
      fontFamily: {
        display: ["'Fraunces'", "serif"],
        body: ["'Inter'", "sans-serif"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(18,35,61,0.06), 0 8px 24px rgba(18,35,61,0.06)",
      },
    },
  },
  plugins: [],
};
