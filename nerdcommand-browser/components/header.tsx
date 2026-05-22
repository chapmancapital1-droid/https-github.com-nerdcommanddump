"use client";
import { Monitor, Clapperboard, Wrench, ChevronDown, Terminal } from "lucide-react";
import { useAppStore } from "@/store/app-store";
import { THEME_LIST, Theme } from "@/lib/theme-config";
import { useState, useEffect } from "react";

export default function Header() {
  const { activeMode, setActiveMode, toolsOpen, setToolsOpen, currentTheme, setTheme } =
    useAppStore();
  const [pickerOpen, setPickerOpen] = useState(false);

  // Apply theme CSS variables whenever theme changes
  useEffect(() => {
    const root = document.documentElement;
    root.style.setProperty("--bg-from", currentTheme.bgFrom);
    root.style.setProperty("--bg-to", currentTheme.bgTo);
    root.style.setProperty("--accent", currentTheme.accent);
    root.style.setProperty("--accent-fg", currentTheme.accentFg);
    root.style.setProperty("--card-bg", currentTheme.cardBg);
    root.style.setProperty("--border-color", currentTheme.borderColor);
  }, [currentTheme]);

  const handleThemeSelect = (theme: Theme) => {
    setTheme(theme);
    setPickerOpen(false);
  };

  const modeBtn = (
    mode: typeof activeMode,
    label: string,
    Icon: React.ElementType
  ) => (
    <button
      onClick={() => setActiveMode(mode)}
      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
        activeMode === mode
          ? "accent-bg shadow-lg"
          : "bg-white/5 hover:bg-white/10 text-slate-300"
      }`}
    >
      <Icon size={14} />
      <span className="hidden sm:inline">{label}</span>
    </button>
  );

  return (
    <header
      className="sticky top-0 z-50 flex items-center justify-between px-4 py-3 glass-card rounded-none"
      style={{ borderRadius: 0, borderLeft: "none", borderRight: "none", borderTop: "none" }}
    >
      {/* Logo */}
      <div className="flex items-center gap-2">
        <div className="w-8 h-8 rounded-lg accent-bg flex items-center justify-center">
          <Terminal size={16} />
        </div>
        <span className="font-bold text-lg tracking-tight">
          NerdCommand
        </span>
      </div>

      {/* Mode buttons */}
      <nav className="flex items-center gap-2">
        {modeBtn("search", "Search Hub", Monitor)}
        {modeBtn("os", "OS Mode", Monitor)}
        {modeBtn("studio", "Studio", Clapperboard)}
      </nav>

      {/* Right side: theme + tools */}
      <div className="flex items-center gap-2">
        {/* Theme display + picker */}
        <div className="relative">
          <button
            onClick={() => setPickerOpen((p) => !p)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-sm transition-all"
          >
            <span>{currentTheme.emoji}</span>
            <span className="hidden sm:inline text-slate-300 text-xs">
              {currentTheme.name}
            </span>
            <ChevronDown size={12} className="text-slate-400" />
          </button>

          {pickerOpen && (
            <div
              className="absolute right-0 top-full mt-2 w-48 glass-card overflow-hidden z-50"
              style={{ maxHeight: "320px", overflowY: "auto" }}
            >
              {THEME_LIST.map((t) => (
                <button
                  key={t.id}
                  onClick={() => handleThemeSelect(t)}
                  className={`w-full flex items-center gap-2 px-3 py-2 text-sm text-left hover:bg-white/10 transition-colors ${
                    t.id === currentTheme.id ? "bg-white/10 accent-text" : "text-slate-300"
                  }`}
                >
                  <span>{t.emoji}</span>
                  <span>{t.name}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Tools toggle */}
        <button
          onClick={() => setToolsOpen(!toolsOpen)}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
            toolsOpen ? "accent-bg" : "bg-white/5 hover:bg-white/10 text-slate-300"
          }`}
        >
          <Wrench size={14} />
          <span className="hidden sm:inline">Tools</span>
        </button>
      </div>
    </header>
  );
}
