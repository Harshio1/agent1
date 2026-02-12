"use client";

import { ClipboardIcon, ClipboardDocumentCheckIcon } from "@heroicons/react/24/outline";
import { useState } from "react";

type Props = {
  requestId?: string | null;
};

export function RequestMeta({ requestId }: Props) {
  const [copied, setCopied] = useState(false);

  if (!requestId) return null;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(requestId);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };

  const Icon = copied ? ClipboardDocumentCheckIcon : ClipboardIcon;

  return (
    <div className="flex items-center justify-between gap-2 text-[11px] text-slate-400">
      <span className="truncate">
        Request ID: <span className="font-mono text-slate-300">{requestId}</span>
      </span>
      <button
        type="button"
        onClick={handleCopy}
        className="inline-flex items-center gap-1 rounded-full border border-slate-700/70 bg-slate-900/80 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-slate-200 hover:border-slate-500/70"
      >
        <Icon className="h-3.5 w-3.5" />
        <span>{copied ? "Copied" : "Copy"}</span>
      </button>
    </div>
  );
}

