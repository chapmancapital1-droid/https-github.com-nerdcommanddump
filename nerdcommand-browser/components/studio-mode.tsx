"use client";
import { useAppStore } from "@/store/app-store";
import {
  FileText, Image, Music, Video, Clock, Download,
  Sparkles, X, ChevronRight
} from "lucide-react";
import { useState } from "react";

interface StudioTab {
  id: string;
  label: string;
  icon: React.ElementType;
  placeholder: string;
  btnLabel: string;
}

const TABS: StudioTab[] = [
  {
    id: "script",
    label: "Script",
    icon: FileText,
    placeholder: "Describe your script idea, scene, or dialogue...",
    btnLabel: "Generate Script",
  },
  {
    id: "images",
    label: "Images",
    icon: Image,
    placeholder: "Describe the image you want to generate...",
    btnLabel: "Generate Image",
  },
  {
    id: "audio",
    label: "Audio",
    icon: Music,
    placeholder: "Describe the audio, music style, or sound effect...",
    btnLabel: "Generate Audio",
  },
  {
    id: "video",
    label: "Video",
    icon: Video,
    placeholder: "Describe the video scene, style, or animation...",
    btnLabel: "Generate Video",
  },
  {
    id: "timeline",
    label: "Timeline",
    icon: Clock,
    placeholder: "Describe your project timeline or sequence of events...",
    btnLabel: "Build Timeline",
  },
  {
    id: "export",
    label: "Export",
    icon: Download,
    placeholder: "Describe export settings, format preferences, or notes...",
    btnLabel: "Export Project",
  },
];

function TabPanel({ tab, projectName }: { tab: StudioTab; projectName: string }) {
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState("");

  const handleGenerate = () => {
    if (!prompt.trim()) return;
    setLoading(true);
    setResult("");
    // Simulate async generation — API can be wired later
    console.log(`[NerdCommand Studio] ${tab.label} generate:`, { project: projectName, prompt });
    setTimeout(() => {
      setLoading(false);
      setResult(`[${tab.label} output for "${projectName}" — API not yet wired. Prompt: "${prompt}"]`);
    }, 800);
  };

  return (
    <div className="flex flex-col gap-4 h-full">
      <div className="flex items-center gap-2 text-slate-400 text-sm">
        <tab.icon size={16} />
        <span>{tab.label}</span>
        <ChevronRight size={12} />
        <span className="text-white">{projectName}</span>
      </div>

      <textarea
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        placeholder={tab.placeholder}
        rows={6}
        className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-slate-200 placeholder-slate-600 resize-none focus:outline-none focus:border-[var(--accent)] transition-colors"
      />

      <button
        onClick={handleGenerate}
        disabled={loading || !prompt.trim()}
        className="flex items-center justify-center gap-2 px-5 py-3 rounded-xl font-semibold text-sm transition-all disabled:opacity-40"
        style={{ background: "var(--accent)", color: "var(--accent-fg)" }}
      >
        <Sparkles size={16} className={loading ? "animate-spin" : ""} />
        {loading ? "Generating…" : tab.btnLabel}
      </button>

      {result && (
        <div className="glass-card p-4 text-sm text-slate-300 rounded-xl whitespace-pre-wrap">
          {result}
        </div>
      )}
    </div>
  );
}

export default function StudioMode() {
  const { studioTab, setStudioTab, projectName, setProjectName, setActiveMode } =
    useAppStore();

  const activeTab = TABS.find((t) => t.id === studioTab) ?? TABS[0];

  return (
    <div
      className="fixed inset-0 z-40 flex"
      style={{ background: "linear-gradient(135deg, #0a0010 0%, #00001a 100%)" }}
    >
      {/* Sidebar */}
      <aside
        className="w-16 sm:w-48 flex flex-col border-r shrink-0"
        style={{ borderColor: "rgba(255,255,255,0.08)", background: "rgba(0,0,0,0.4)" }}
      >
        {/* Logo row */}
        <div className="flex items-center gap-2 px-3 py-4 border-b" style={{ borderColor: "rgba(255,255,255,0.08)" }}>
          <div
            className="w-7 h-7 rounded-md flex items-center justify-center text-xs font-bold shrink-0"
            style={{ background: "var(--accent)", color: "var(--accent-fg)" }}
          >
            S
          </div>
          <span className="hidden sm:inline text-sm font-semibold text-slate-200">Studio</span>
        </div>

        {/* Tabs */}
        <nav className="flex-1 py-2">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            const active = tab.id === studioTab;
            return (
              <button
                key={tab.id}
                onClick={() => setStudioTab(tab.id)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 text-sm transition-all ${
                  active
                    ? "text-white bg-white/10"
                    : "text-slate-500 hover:text-slate-300 hover:bg-white/5"
                }`}
              >
                <Icon size={16} className="shrink-0" />
                <span className="hidden sm:inline">{tab.label}</span>
              </button>
            );
          })}
        </nav>

        {/* Exit */}
        <button
          onClick={() => setActiveMode("search")}
          className="flex items-center gap-2 px-3 py-3 text-slate-600 hover:text-slate-300 hover:bg-white/5 transition-all text-sm border-t"
          style={{ borderColor: "rgba(255,255,255,0.08)" }}
        >
          <X size={16} className="shrink-0" />
          <span className="hidden sm:inline">Exit</span>
        </button>
      </aside>

      {/* Main content */}
      <main className="flex-1 flex flex-col min-w-0">
        {/* Top bar with project name */}
        <div
          className="flex items-center gap-3 px-6 py-3 border-b shrink-0"
          style={{ borderColor: "rgba(255,255,255,0.08)", background: "rgba(0,0,0,0.2)" }}
        >
          <span className="text-slate-500 text-sm shrink-0">Project:</span>
          <input
            type="text"
            value={projectName}
            onChange={(e) => setProjectName(e.target.value)}
            className="bg-transparent text-white text-sm font-medium focus:outline-none border-b border-transparent focus:border-[var(--accent)] transition-colors min-w-0 flex-1 max-w-xs"
            placeholder="Untitled Project"
          />
        </div>

        {/* Tab content */}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="max-w-2xl">
            <TabPanel tab={activeTab} projectName={projectName} />
          </div>
        </div>
      </main>
    </div>
  );
}
