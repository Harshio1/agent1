"use client";

import { useEffect } from "react";

export default function GlobalError({
  error,
  reset
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // In a real app you might send this to observability tooling.
    // console.error(error);
  }, [error]);

  return (
    <html>
      <body className="min-h-screen bg-[#0f172a] text-slate-100 antialiased flex items-center justify-center px-4">
        <div className="w-full max-w-md space-y-4 rounded-2xl border border-rose-500/40 bg-rose-950/70 p-5 text-sm text-rose-100 shadow-xl shadow-black/40">
          <h1 className="text-base font-semibold tracking-tight text-rose-50">
            Something went wrong in the CodePilot UI
          </h1>
          <p className="text-xs text-rose-100/90">
            {error.message || "An unexpected error occurred."}
          </p>
          {error.digest && (
            <p className="text-[11px] text-rose-200/80">
              Error reference: <span className="font-mono">{error.digest}</span>
            </p>
          )}
          <button
            type="button"
            onClick={reset}
            className="mt-1 inline-flex items-center justify-center rounded-full bg-rose-500 px-4 py-1.5 text-xs font-semibold text-white shadow-md shadow-rose-500/40 hover:bg-rose-400"
          >
            Reload CodePilot
          </button>
        </div>
      </body>
    </html>
  );
}

