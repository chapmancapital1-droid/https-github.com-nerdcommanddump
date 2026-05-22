"use client";
import { useAppStore } from "@/store/app-store";
import Header from "@/components/header";
import SearchHub from "@/components/search-hub";
import OsMode from "@/components/os-mode";
import StudioMode from "@/components/studio-mode";
import ToolsDrawer from "@/components/tools-drawer";
import { Wrench } from "lucide-react";

export default function Home() {
  const { activeMode, toolsOpen, setToolsOpen } = useAppStore();
  const isFullscreen = activeMode === "os" || activeMode === "studio";

  return (
    <>
      {/* Fullscreen mode overlays */}
      {activeMode === "os" && <OsMode />}
      {activeMode === "studio" && <StudioMode />}

      {/* Normal search hub layout */}
      {!isFullscreen && (
        <div className="flex flex-col min-h-screen">
          <Header />
          <main className="flex flex-col flex-1">
            <SearchHub />
          </main>
        </div>
      )}

      {/* Floating tools button visible in fullscreen modes */}
      {isFullscreen && (
        <button
          onClick={() => setToolsOpen(!toolsOpen)}
          className="fixed bottom-16 right-4 z-50 w-10 h-10 rounded-full flex items-center justify-center shadow-lg transition-all hover:scale-110"
          style={{ background: "var(--accent)", color: "var(--accent-fg)" }}
          title="Tools"
        >
          <Wrench size={16} />
        </button>
      )}

      {/* Tools drawer — always available */}
      <ToolsDrawer />
    </>
  );
}
