"use client";
import { create } from "zustand";
import { persist } from "zustand/middleware";
import { Theme, detectTheme } from "@/lib/theme-config";

export type AppMode = "search" | "os" | "studio";

export interface TodoItem {
  id: string;
  text: string;
  done: boolean;
}

interface AppState {
  // Mode
  activeMode: AppMode;
  setActiveMode: (mode: AppMode) => void;

  // Tools drawer
  toolsOpen: boolean;
  setToolsOpen: (open: boolean) => void;
  activeTool: string;
  setActiveTool: (tool: string) => void;

  // Theme
  currentTheme: Theme;
  setTheme: (theme: Theme) => void;

  // Notes
  notes: string;
  setNotes: (notes: string) => void;

  // Todos
  todos: TodoItem[];
  addTodo: (text: string) => void;
  toggleTodo: (id: string) => void;
  deleteTodo: (id: string) => void;

  // Studio
  studioTab: string;
  setStudioTab: (tab: string) => void;
  projectName: string;
  setProjectName: (name: string) => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      activeMode: "search",
      setActiveMode: (mode) => set({ activeMode: mode }),

      toolsOpen: false,
      setToolsOpen: (open) => set({ toolsOpen: open }),
      activeTool: "calculator",
      setActiveTool: (tool) => set({ activeTool: tool }),

      currentTheme: detectTheme(),
      setTheme: (theme) => set({ currentTheme: theme }),

      notes: "",
      setNotes: (notes) => set({ notes }),

      todos: [],
      addTodo: (text) =>
        set((state) => ({
          todos: [
            ...state.todos,
            { id: Date.now().toString(), text, done: false },
          ],
        })),
      toggleTodo: (id) =>
        set((state) => ({
          todos: state.todos.map((t) =>
            t.id === id ? { ...t, done: !t.done } : t
          ),
        })),
      deleteTodo: (id) =>
        set((state) => ({
          todos: state.todos.filter((t) => t.id !== id),
        })),

      studioTab: "script",
      setStudioTab: (tab) => set({ studioTab: tab }),
      projectName: "Untitled Project",
      setProjectName: (name) => set({ projectName: name }),
    }),
    {
      name: "nerdcommand-store",
      partialize: (state) => ({
        notes: state.notes,
        todos: state.todos,
        projectName: state.projectName,
        currentTheme: state.currentTheme,
      }),
    }
  )
);
