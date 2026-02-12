"use client";

import { useEffect, useState } from "react";
import { MoonIcon, SunIcon } from "@heroicons/react/24/outline";

export function Navbar() {
  const [isDark, setIsDark] = useState(true);

  useEffect(() => {
    const stored = typeof window !== "undefined"
      ? window.localStorage.getItem("theme")
      : null;
    const prefersDark =
      typeof window !== "undefined" &&
      window.matchMedia &&
      window.matchMedia("(prefers-color-scheme: dark)").matches;

    const initial = stored ?? (prefersDark ? "dark" : "dark");
    const nextIsDark = initial === "dark";
    setIsDark(nextIsDark);
    document.documentElement.classList.toggle("dark", nextIsDark);
  }, []);

  const toggleTheme = () => {
    setIsDark((prev) => {
      const next = !prev;
      const theme = next ? "dark" : "light";
      document.documentElement.classList.toggle("dark", next);
      window.localStorage.setItem("theme", theme);
      return next;
    });
  };

  return (
    <nav className="sticky top-0 z-20 border-b border-slate-800/70 bg-slate-950/80 backdrop-blur">
      <div className="mx-auto flex max-w-4xl items-center justify-between px-4 py-3">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-indigo-500/90 text-xs font-bold text-white shadow-md shadow-indigo-500/40">
            CP
          </div>
          <div>
            <p className="text-sm font-semibold tracking-tight text-slate-50">
              CodePilot
            </p>
            <p className="text-[11px] text-slate-400">
              Autonomous coding assistant
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={toggleTheme}
          className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-slate-700/70 bg-slate-900/80 text-slate-200 shadow-sm shadow-black/40 transition hover:border-slate-500/80 hover:bg-slate-800"
          aria-label="Toggle dark mode"
        >
          {isDark ? (
            <SunIcon className="h-4 w-4" />
          ) : (
            <MoonIcon className="h-4 w-4" />
          )}
        </button>
      </div>
    </nav>
  );
}

