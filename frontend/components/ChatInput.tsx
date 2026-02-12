"use client";

import { useState, FormEvent } from "react";

type ChatInputProps = {
  onSubmit: (problem: string) => Promise<void> | void;
  isLoading: boolean;
};

export function ChatInput({ onSubmit, isLoading }: ChatInputProps) {
  const [problem, setProblem] = useState("");

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!problem.trim() || isLoading) return;
    await onSubmit(problem.trim());
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="w-full space-y-3 rounded-2xl border border-slate-700/70 bg-slate-900/60 p-4 shadow-lg shadow-black/40 backdrop-blur"
    >
      <label className="block text-sm font-medium text-slate-200">
        Describe your programming problem
      </label>
      <textarea
        value={problem}
        onChange={(e) => setProblem(e.target.value)}
        placeholder="Explain what you want CodePilot to solve, generate, or debug..."
        className="mt-1 min-h-[120px] w-full resize-y rounded-xl border border-slate-700/60 bg-slate-900/80 px-3 py-2 text-sm text-slate-100 outline-none ring-0 transition focus:border-indigo-400 focus:ring-2 focus:ring-indigo-500/60 placeholder:text-slate-500"
      />
      <div className="flex items-center justify-end gap-3">
        <p className="text-xs text-slate-400">
          CodePilot will generate a full plan, code, tests, and analysis.
        </p>
        <button
          type="submit"
          disabled={isLoading || !problem.trim()}
          className="inline-flex items-center gap-2 rounded-full bg-indigo-500 px-4 py-2 text-sm font-semibold text-white shadow-md shadow-indigo-500/30 transition hover:bg-indigo-400 disabled:cursor-not-allowed disabled:bg-slate-600"
        >
          <span>{isLoading ? "Running CodePilot..." : "Run CodePilot"}</span>
        </button>
      </div>
    </form>
  );
}

