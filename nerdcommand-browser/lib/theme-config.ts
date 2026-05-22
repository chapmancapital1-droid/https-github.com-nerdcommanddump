export interface Theme {
  id: string;
  name: string;
  emoji: string;
  bgFrom: string;
  bgTo: string;
  accent: string;
  accentFg: string;
  cardBg: string;
  borderColor: string;
}

export const THEMES: Record<string, Theme> = {
  christmas: {
    id: "christmas",
    name: "Christmas",
    emoji: "❄",
    bgFrom: "#0d1f0d",
    bgTo: "#1a0000",
    accent: "#e63946",
    accentFg: "#ffffff",
    cardBg: "rgba(255,255,255,0.05)",
    borderColor: "rgba(230,57,70,0.3)",
  },
  halloween: {
    id: "halloween",
    name: "Halloween",
    emoji: "🎃",
    bgFrom: "#1a0a00",
    bgTo: "#2d0066",
    accent: "#ff6b00",
    accentFg: "#ffffff",
    cardBg: "rgba(255,255,255,0.05)",
    borderColor: "rgba(255,107,0,0.3)",
  },
  thanksgiving: {
    id: "thanksgiving",
    name: "Thanksgiving",
    emoji: "🍂",
    bgFrom: "#1a0f00",
    bgTo: "#2d1a00",
    accent: "#d97706",
    accentFg: "#ffffff",
    cardBg: "rgba(255,255,255,0.05)",
    borderColor: "rgba(217,119,6,0.3)",
  },
  valentines: {
    id: "valentines",
    name: "Valentine's",
    emoji: "💕",
    bgFrom: "#1a0010",
    bgTo: "#2d0020",
    accent: "#ec4899",
    accentFg: "#ffffff",
    cardBg: "rgba(255,255,255,0.05)",
    borderColor: "rgba(236,72,153,0.3)",
  },
  stpatricks: {
    id: "stpatricks",
    name: "St. Patrick's",
    emoji: "☘️",
    bgFrom: "#001a00",
    bgTo: "#002d00",
    accent: "#16a34a",
    accentFg: "#ffffff",
    cardBg: "rgba(255,255,255,0.05)",
    borderColor: "rgba(22,163,74,0.3)",
  },
  independence: {
    id: "independence",
    name: "Independence Day",
    emoji: "🎆",
    bgFrom: "#000d1a",
    bgTo: "#1a0000",
    accent: "#3b82f6",
    accentFg: "#ffffff",
    cardBg: "rgba(255,255,255,0.05)",
    borderColor: "rgba(59,130,246,0.3)",
  },
  easter: {
    id: "easter",
    name: "Spring / Easter",
    emoji: "🌸",
    bgFrom: "#0f001a",
    bgTo: "#1a1a00",
    accent: "#a855f7",
    accentFg: "#ffffff",
    cardBg: "rgba(255,255,255,0.05)",
    borderColor: "rgba(168,85,247,0.3)",
  },
  winter: {
    id: "winter",
    name: "Winter",
    emoji: "❄",
    bgFrom: "#020617",
    bgTo: "#0f172a",
    accent: "#60a5fa",
    accentFg: "#ffffff",
    cardBg: "rgba(255,255,255,0.05)",
    borderColor: "rgba(96,165,250,0.3)",
  },
  spring: {
    id: "spring",
    name: "Spring",
    emoji: "🌿",
    bgFrom: "#001a00",
    bgTo: "#1a1a00",
    accent: "#84cc16",
    accentFg: "#000000",
    cardBg: "rgba(255,255,255,0.05)",
    borderColor: "rgba(132,204,22,0.3)",
  },
  summer: {
    id: "summer",
    name: "Summer",
    emoji: "☀️",
    bgFrom: "#1a1000",
    bgTo: "#0d0d00",
    accent: "#f59e0b",
    accentFg: "#000000",
    cardBg: "rgba(255,255,255,0.05)",
    borderColor: "rgba(245,158,11,0.3)",
  },
  autumn: {
    id: "autumn",
    name: "Autumn",
    emoji: "🍁",
    bgFrom: "#1a0a00",
    bgTo: "#1a0000",
    accent: "#ea580c",
    accentFg: "#ffffff",
    cardBg: "rgba(255,255,255,0.05)",
    borderColor: "rgba(234,88,12,0.3)",
  },
};

export function detectTheme(date: Date = new Date()): Theme {
  const month = date.getMonth() + 1; // 1-12
  const day = date.getDate();
  const mmdd = month * 100 + day;

  if (mmdd >= 1218 && mmdd <= 1225) return THEMES.christmas;
  if (mmdd >= 1024 && mmdd <= 1031) return THEMES.halloween;
  if (mmdd >= 1120 && mmdd <= 1128) return THEMES.thanksgiving;
  if (mmdd >= 207 && mmdd <= 214) return THEMES.valentines;
  if (mmdd >= 310 && mmdd <= 317) return THEMES.stpatricks;
  if (mmdd >= 701 && mmdd <= 704) return THEMES.independence;
  if (mmdd >= 401 && mmdd <= 407) return THEMES.easter;

  // Seasons
  if (mmdd >= 1221 || mmdd <= 319) return THEMES.winter;
  if (mmdd >= 320 && mmdd <= 620) return THEMES.spring;
  if (mmdd >= 621 && mmdd <= 921) return THEMES.summer;
  return THEMES.autumn;
}

export const THEME_LIST = Object.values(THEMES);
