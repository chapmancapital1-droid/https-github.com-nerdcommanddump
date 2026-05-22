"use client";
import { useAppStore } from "@/store/app-store";
import { Clock, X } from "lucide-react";
import { useEffect, useState } from "react";

interface AppIcon {
  name: string;
  url: string;
  emoji: string;
  color: string;
}

const SOCIAL_APPS: AppIcon[] = [
  { name: "Facebook",   url: "https://facebook.com",         emoji: "📘", color: "#1877F2" },
  { name: "Instagram",  url: "https://instagram.com",        emoji: "📸", color: "#E1306C" },
  { name: "X / Twitter",url: "https://x.com",               emoji: "✖️", color: "#1DA1F2" },
  { name: "LinkedIn",   url: "https://linkedin.com",         emoji: "💼", color: "#0A66C2" },
  { name: "YouTube",    url: "https://youtube.com",          emoji: "▶️", color: "#FF0000" },
  { name: "TikTok",     url: "https://tiktok.com",           emoji: "🎵", color: "#010101" },
  { name: "Reddit",     url: "https://reddit.com",           emoji: "🤖", color: "#FF4500" },
  { name: "Pinterest",  url: "https://pinterest.com",        emoji: "📌", color: "#E60023" },
  { name: "Discord",    url: "https://discord.com/app",      emoji: "🎮", color: "#5865F2" },
  { name: "Twitch",     url: "https://twitch.tv",            emoji: "🟣", color: "#9146FF" },
  { name: "WhatsApp",   url: "https://web.whatsapp.com",     emoji: "💬", color: "#25D366" },
  { name: "Snapchat",   url: "https://snapchat.com",         emoji: "👻", color: "#FFFC00" },
  { name: "GitHub",     url: "https://github.com",           emoji: "🐙", color: "#f1f5f9" },
  { name: "Telegram",   url: "https://web.telegram.org",     emoji: "✈️", color: "#2AABEE" },
];

function DesktopClock() {
  const [time, setTime] = useState("");
  const [date, setDate] = useState("");

  useEffect(() => {
    const tick = () => {
      const now = new Date();
      setTime(now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }));
      setDate(
        now.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" })
      );
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="flex items-center gap-2 text-sm text-slate-300">
      <Clock size={14} />
      <span>{time}</span>
      <span className="text-slate-500 hidden sm:inline">{date}</span>
    </div>
  );
}

export default function OsMode() {
  const { setActiveMode } = useAppStore();

  return (
    <div className="fixed inset-0 z-40 flex flex-col" style={{ background: "#000000" }}>
      {/* Desktop grid */}
      <div className="flex-1 p-6 overflow-y-auto">
        <div className="max-w-5xl mx-auto">
          <p className="text-slate-700 text-xs uppercase tracking-widest mb-6 text-center">
            Social Media
          </p>
          <div className="grid grid-cols-4 sm:grid-cols-5 md:grid-cols-7 gap-4">
            {SOCIAL_APPS.map((app) => (
              <button
                key={app.name}
                onClick={() => window.open(app.url, "_blank")}
                className="flex flex-col items-center gap-2 p-3 rounded-xl hover:bg-white/10 transition-all group"
              >
                <div
                  className="w-14 h-14 rounded-2xl flex items-center justify-center text-3xl shadow-lg group-hover:scale-110 transition-transform"
                  style={{
                    background: app.color + "22",
                    border: `1px solid ${app.color}55`,
                  }}
                >
                  {app.emoji}
                </div>
                <span className="text-xs text-slate-500 group-hover:text-slate-200 transition-colors text-center leading-tight">
                  {app.name}
                </span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Taskbar */}
      <div
        className="flex items-center justify-between px-6 py-3 border-t"
        style={{
          background: "rgba(255,255,255,0.04)",
          borderColor: "rgba(255,255,255,0.08)",
        }}
      >
        <div className="flex items-center gap-2">
          <div
            className="w-7 h-7 rounded-md flex items-center justify-center text-xs font-bold"
            style={{ background: "var(--accent)", color: "var(--accent-fg)" }}
          >
            N
          </div>
          <span className="text-slate-500 text-xs hidden sm:inline">NerdCommand OS</span>
        </div>

        <DesktopClock />

        <button
          onClick={() => setActiveMode("search")}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/15 text-slate-300 text-sm transition-all"
        >
          <X size={14} />
          <span className="hidden sm:inline">Exit</span>
        </button>
      </div>
    </div>
  );
}
