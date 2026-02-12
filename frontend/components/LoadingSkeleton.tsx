export function LoadingSkeleton() {
  return (
    <div className="space-y-4">
      <div className="h-4 w-40 animate-pulse rounded-full bg-slate-700/70" />
      <div className="space-y-3 rounded-2xl border border-slate-800/70 bg-slate-900/70 p-4">
        <div className="h-3 w-32 animate-pulse rounded-full bg-slate-700/70" />
        <div className="mt-3 space-y-2">
          <div className="h-3 w-full animate-pulse rounded bg-slate-800/80" />
          <div className="h-3 w-11/12 animate-pulse rounded bg-slate-800/80" />
          <div className="h-3 w-9/12 animate-pulse rounded bg-slate-800/80" />
        </div>
      </div>
      <div className="space-y-3 rounded-2xl border border-slate-800/70 bg-slate-900/70 p-4">
        <div className="h-3 w-40 animate-pulse rounded-full bg-slate-700/70" />
        <div className="mt-3 space-y-2">
          <div className="h-3 w-full animate-pulse rounded bg-slate-800/80" />
          <div className="h-3 w-10/12 animate-pulse rounded bg-slate-800/80" />
          <div className="h-3 w-8/12 animate-pulse rounded bg-slate-800/80" />
        </div>
      </div>
    </div>
  );
}

