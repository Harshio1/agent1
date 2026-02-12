"use client";

import { useState, ReactNode } from "react";
import { ChevronDownIcon, ChevronRightIcon } from "@heroicons/react/24/solid";

type ResultSectionProps = {
  title: string;
  children: ReactNode;
  defaultOpen?: boolean;
};

export function ResultSection({
  title,
  children,
  defaultOpen = true
}: ResultSectionProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <section className="rounded-2xl border border-slate-700/70 bg-slate-900/70 p-4 shadow-md shadow-black/40">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-3 text-left"
      >
        <div className="flex items-center gap-2">
          {open ? (
            <ChevronDownIcon className="h-4 w-4 text-slate-300" />
          ) : (
            <ChevronRightIcon className="h-4 w-4 text-slate-300" />
          )}
          <h2 className="text-sm font-semibold tracking-wide text-slate-100">
            {title}
          </h2>
        </div>
      </button>
      {open && (
        <div className="mt-3 border-t border-slate-700/60 pt-3 text-sm text-slate-200">
          {children}
        </div>
      )}
    </section>
  );
}

