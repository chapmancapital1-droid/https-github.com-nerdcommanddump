"use client";
import { useState } from "react";
import { Search, ExternalLink } from "lucide-react";

const QUICK_LINKS = [
  { label: "GitHub", url: "https://github.com", emoji: "🐙" },
  { label: "Reddit", url: "https://reddit.com", emoji: "🤖" },
  { label: "YouTube", url: "https://youtube.com", emoji: "▶️" },
  { label: "Twitter / X", url: "https://x.com", emoji: "✖️" },
  { label: "HN", url: "https://news.ycombinator.com", emoji: "🔶" },
  { label: "MDN", url: "https://developer.mozilla.org", emoji: "📖" },
  { label: "Wikipedia", url: "https://wikipedia.org", emoji: "📚" },
  { label: "Discord", url: "https://discord.com/app", emoji: "💬" },
  { label: "Twitch", url: "https://twitch.tv", emoji: "🎮" },
  { label: "LinkedIn", url: "https://linkedin.com", emoji: "💼" },
];

export default function SearchHub() {
  const [query, setQuery] = useState("");

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    window.open(`https://z.ai/search?q=${encodeURIComponent(query.trim())}`, "_blank");
    setQuery("");
  };

  return (
    <div className="flex flex-col items-center justify-center flex-1 px-4 py-16">
      {/* Hero text */}
      <div className="text-center mb-10">
        <h1 className="text-5xl font-bold mb-3 tracking-tight">
          <span className="accent-text">Nerd</span>Command
        </h1>
        <p className="text-slate-400 text-lg">Your intelligent browser dashboard</p>
      </div>

      {/* Search bar */}
      <form onSubmit={handleSearch} className="w-full max-w-2xl mb-10">
        <div
          className="flex items-center gap-3 px-5 py-4 glass-card"
          style={{ borderRadius: "999px" }}
        >
          <Search size={20} className="text-slate-400 shrink-0" />
          <input
            type="text"
            placeholder="Search with z.ai..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="flex-1 bg-transparent text-white placeholder-slate-500 text-lg focus:outline-none"
            autoFocus
          />
          <button
            type="submit"
            className="accent-bg px-5 py-2 rounded-full text-sm font-semibold transition-opacity hover:opacity-90 shrink-0"
          >
            Search
          </button>
        </div>
      </form>

      {/* Quick links */}
      <div className="w-full max-w-2xl">
        <p className="text-slate-500 text-xs uppercase tracking-widest mb-3 text-center">
          Quick Access
        </p>
        <div className="flex flex-wrap justify-center gap-2">
          {QUICK_LINKS.map((link) => (
            <button
              key={link.url}
              onClick={() => window.open(link.url, "_blank")}
              className="flex items-center gap-2 px-4 py-2 glass-card text-sm text-slate-300 hover:text-white hover:bg-white/10 transition-all rounded-full"
            >
              <span>{link.emoji}</span>
              <span>{link.label}</span>
              <ExternalLink size={10} className="text-slate-500" />
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
