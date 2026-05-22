"use client";
import { useAppStore } from "@/store/app-store";
import {
  Calculator, Clock, StickyNote, KeyRound, CheckSquare,
  X, Copy, Check, Plus, Trash2, RotateCcw, Play, Pause
} from "lucide-react";
import { useState, useEffect, useCallback, useRef } from "react";

// ─── Calculator ────────────────────────────────────────────────
function CalculatorTool() {
  const [display, setDisplay] = useState("0");
  const [prev, setPrev] = useState<string | null>(null);
  const [op, setOp] = useState<string | null>(null);
  const [fresh, setFresh] = useState(false);

  const press = (val: string) => {
    if (val === "C") { setDisplay("0"); setPrev(null); setOp(null); setFresh(false); return; }
    if (val === "±") { setDisplay((d) => String(-parseFloat(d))); return; }
    if (val === "%") { setDisplay((d) => String(parseFloat(d) / 100)); return; }
    if (["+", "−", "×", "÷"].includes(val)) {
      setPrev(display); setOp(val); setFresh(true); return;
    }
    if (val === "=") {
      if (op && prev !== null) {
        const a = parseFloat(prev), b = parseFloat(display);
        const res = op === "+" ? a + b : op === "−" ? a - b : op === "×" ? a * b : a / b;
        setDisplay(String(parseFloat(res.toFixed(10))));
        setPrev(null); setOp(null); setFresh(false);
      }
      return;
    }
    if (val === ".") {
      const base = fresh ? "0" : display;
      if (!base.includes(".")) setDisplay(base + ".");
      setFresh(false); return;
    }
    if (fresh) { setDisplay(val); setFresh(false); }
    else setDisplay((d) => d === "0" ? val : d.length < 12 ? d + val : d);
  };

  const BTNS = [
    ["C", "±", "%", "÷"],
    ["7", "8", "9", "×"],
    ["4", "5", "6", "−"],
    ["1", "2", "3", "+"],
    ["0", ".", "="],
  ];
  const isOp = (v: string) => ["÷", "×", "−", "+", "="].includes(v);

  return (
    <div className="select-none">
      <div className="bg-black/40 rounded-xl px-4 py-3 mb-3 text-right">
        <p className="text-slate-500 text-xs h-4">{op ? `${prev} ${op}` : ""}</p>
        <p className="text-white text-3xl font-light truncate">{display}</p>
      </div>
      {BTNS.map((row, ri) => (
        <div key={ri} className="flex gap-2 mb-2">
          {row.map((btn) => (
            <button
              key={btn}
              onClick={() => press(btn)}
              className={`flex-1 py-3 rounded-xl text-sm font-medium transition-all active:scale-95 ${
                isOp(btn)
                  ? "text-[var(--accent-fg)] hover:opacity-80"
                  : btn === "C" || btn === "±" || btn === "%"
                  ? "bg-white/15 text-white hover:bg-white/25"
                  : "bg-white/8 text-white hover:bg-white/15"
              }`}
              style={isOp(btn) ? { background: "var(--accent)" } : {}}
            >
              {btn}
            </button>
          ))}
        </div>
      ))}
    </div>
  );
}

// ─── Clock & Stopwatch ─────────────────────────────────────────
function ClockTool() {
  const [time, setTime] = useState(() => new Date().toLocaleTimeString());
  const [elapsed, setElapsed] = useState(0);
  const [running, setRunning] = useState(false);
  const startRef = useRef<number>(0);
  const baseRef = useRef<number>(0);

  useEffect(() => {
    const id = setInterval(() => setTime(new Date().toLocaleTimeString()), 1000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (!running) return;
    startRef.current = Date.now();
    const id = setInterval(() => {
      setElapsed(baseRef.current + Date.now() - startRef.current);
    }, 100);
    return () => clearInterval(id);
  }, [running]);

  const toggle = () => {
    if (running) { baseRef.current = elapsed; }
    setRunning((r) => !r);
  };
  const reset = () => { setRunning(false); setElapsed(0); baseRef.current = 0; };

  const fmt = (ms: number) => {
    const s = Math.floor(ms / 1000);
    const m = Math.floor(s / 60);
    const h = Math.floor(m / 60);
    return `${String(h).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}.${String(Math.floor((ms % 1000) / 100))}`;
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="glass-card p-4 text-center rounded-xl">
        <p className="text-slate-500 text-xs mb-1">Current Time</p>
        <p className="text-3xl font-mono text-white">{time}</p>
      </div>
      <div className="glass-card p-4 text-center rounded-xl">
        <p className="text-slate-500 text-xs mb-2">Stopwatch</p>
        <p className="text-2xl font-mono text-white mb-3">{fmt(elapsed)}</p>
        <div className="flex justify-center gap-2">
          <button
            onClick={toggle}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-all"
            style={{ background: "var(--accent)", color: "var(--accent-fg)" }}
          >
            {running ? <Pause size={14} /> : <Play size={14} />}
            {running ? "Pause" : "Start"}
          </button>
          <button
            onClick={reset}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-white/10 hover:bg-white/20 text-sm transition-all"
          >
            <RotateCcw size={14} />
            Reset
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Notes ─────────────────────────────────────────────────────
function NotesTool() {
  const { notes, setNotes } = useAppStore();
  return (
    <div>
      <p className="text-slate-500 text-xs mb-2">Saved automatically to localStorage</p>
      <textarea
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        placeholder="Start typing your notes..."
        rows={12}
        className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2.5 text-sm text-slate-200 placeholder-slate-600 resize-none focus:outline-none focus:border-[var(--accent)] transition-colors"
      />
      <p className="text-right text-slate-600 text-xs mt-1">{notes.length} chars</p>
    </div>
  );
}

// ─── Password Generator ────────────────────────────────────────
function buildPassword(length: number, symbols: boolean, numbers: boolean): string {
  const lower = "abcdefghijklmnopqrstuvwxyz";
  const upper = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
  const nums = "0123456789";
  const syms = "!@#$%^&*()_+-=[]{}|;:,.<>?";
  let charset = lower + upper;
  if (numbers) charset += nums;
  if (symbols) charset += syms;
  const arr = new Uint32Array(length);
  crypto.getRandomValues(arr);
  return Array.from(arr).map((n) => charset[n % charset.length]).join("");
}

function PasswordTool() {
  const [length, setLength] = useState(16);
  const [symbols, setSymbols] = useState(true);
  const [numbers, setNumbers] = useState(true);
  const [password, setPassword] = useState(() => buildPassword(16, true, true));
  const [copied, setCopied] = useState(false);

  const generate = useCallback(() => {
    setPassword(buildPassword(length, symbols, numbers));
    setCopied(false);
  }, [length, symbols, numbers]);

  const copy = () => {
    navigator.clipboard.writeText(password).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="glass-card px-3 py-2.5 rounded-xl flex items-center gap-2">
        <p className="flex-1 font-mono text-sm text-white break-all">{password}</p>
        <button onClick={copy} className="shrink-0 p-1.5 rounded-lg hover:bg-white/10 transition-colors" title="Copy">
          {copied ? <Check size={16} className="text-green-400" /> : <Copy size={16} className="text-slate-400" />}
        </button>
      </div>
      <div>
        <div className="flex justify-between text-sm mb-1">
          <span className="text-slate-400">Length</span>
          <span className="text-white font-medium">{length}</span>
        </div>
        <input type="range" min={8} max={64} value={length} onChange={(e) => setLength(Number(e.target.value))} className="w-full" />
      </div>
      <div className="flex gap-4">
        {[["Numbers", numbers, setNumbers], ["Symbols", symbols, setSymbols]].map(([label, val, setter]) => (
          <label key={label as string} className="flex items-center gap-2 cursor-pointer text-sm text-slate-300">
            <input type="checkbox" checked={val as boolean} onChange={(e) => (setter as (v: boolean) => void)(e.target.checked)} className="accent-[var(--accent)]" />
            {label as string}
          </label>
        ))}
      </div>
      <button
        onClick={generate}
        className="w-full py-2.5 rounded-xl text-sm font-semibold transition-all hover:opacity-90"
        style={{ background: "var(--accent)", color: "var(--accent-fg)" }}
      >
        Regenerate
      </button>
    </div>
  );
}

// ─── Todo List ─────────────────────────────────────────────────
function TodoTool() {
  const { todos, addTodo, toggleTodo, deleteTodo } = useAppStore();
  const [input, setInput] = useState("");

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;
    addTodo(input.trim());
    setInput("");
  };

  return (
    <div className="flex flex-col gap-3">
      <form onSubmit={submit} className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Add a task..."
          className="flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-[var(--accent)] transition-colors"
        />
        <button type="submit" className="p-2 rounded-lg transition-all hover:opacity-80" style={{ background: "var(--accent)", color: "var(--accent-fg)" }}>
          <Plus size={16} />
        </button>
      </form>
      <div className="flex flex-col gap-1.5 max-h-64 overflow-y-auto">
        {todos.length === 0 && <p className="text-slate-600 text-sm text-center py-4">No tasks yet</p>}
        {todos.map((todo) => (
          <div key={todo.id} className="flex items-center gap-2 glass-card px-3 py-2 rounded-lg">
            <input
              type="checkbox"
              checked={todo.done}
              onChange={() => toggleTodo(todo.id)}
              className="accent-[var(--accent)] shrink-0"
            />
            <span className={`flex-1 text-sm ${todo.done ? "line-through text-slate-600" : "text-slate-200"}`}>
              {todo.text}
            </span>
            <button onClick={() => deleteTodo(todo.id)} className="text-slate-600 hover:text-red-400 transition-colors p-1">
              <Trash2 size={13} />
            </button>
          </div>
        ))}
      </div>
      {todos.length > 0 && (
        <p className="text-slate-600 text-xs text-right">{todos.filter((t) => t.done).length}/{todos.length} done</p>
      )}
    </div>
  );
}

// ─── Drawer ────────────────────────────────────────────────────
const TOOLS = [
  { id: "calculator", label: "Calculator", icon: Calculator, Component: CalculatorTool },
  { id: "clock", label: "Clock", icon: Clock, Component: ClockTool },
  { id: "notes", label: "Notes", icon: StickyNote, Component: NotesTool },
  { id: "password", label: "Passwords", icon: KeyRound, Component: PasswordTool },
  { id: "todos", label: "Todos", icon: CheckSquare, Component: TodoTool },
];

export default function ToolsDrawer() {
  const { toolsOpen, setToolsOpen, activeTool, setActiveTool } = useAppStore();
  const active = TOOLS.find((t) => t.id === activeTool) ?? TOOLS[0];

  return (
    <>
      {/* Backdrop */}
      {toolsOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/40"
          onClick={() => setToolsOpen(false)}
        />
      )}

      {/* Drawer */}
      <aside
        className={`fixed top-0 right-0 h-full w-80 z-50 flex flex-col transition-transform duration-300 ${
          toolsOpen ? "translate-x-0" : "translate-x-full"
        }`}
        style={{ background: "rgba(10,10,20,0.97)", borderLeft: "1px solid rgba(255,255,255,0.08)" }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b" style={{ borderColor: "rgba(255,255,255,0.08)" }}>
          <span className="font-semibold text-sm text-white">Built-in Tools</span>
          <button onClick={() => setToolsOpen(false)} className="text-slate-500 hover:text-white transition-colors p-1 rounded-lg hover:bg-white/10">
            <X size={16} />
          </button>
        </div>

        {/* Tool tabs */}
        <div className="flex border-b overflow-x-auto" style={{ borderColor: "rgba(255,255,255,0.08)" }}>
          {TOOLS.map((t) => {
            const Icon = t.icon;
            return (
              <button
                key={t.id}
                onClick={() => setActiveTool(t.id)}
                className={`flex flex-col items-center gap-1 px-3 py-2.5 text-xs shrink-0 transition-all border-b-2 ${
                  t.id === activeTool
                    ? "text-white border-[var(--accent)]"
                    : "text-slate-500 border-transparent hover:text-slate-300"
                }`}
              >
                <Icon size={16} />
                <span>{t.label}</span>
              </button>
            );
          })}
        </div>

        {/* Tool content */}
        <div className="flex-1 overflow-y-auto p-4">
          <active.Component />
        </div>
      </aside>
    </>
  );
}
