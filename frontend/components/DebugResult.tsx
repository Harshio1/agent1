import type { DebugResult as DebugResultType } from "../types";

type Props = {
  debug?: DebugResultType | null;
};

export function DebugResult({ debug }: Props) {
  if (!debug) {
    return (
      <p className="text-sm text-slate-400">
        No debug information was necessary.
      </p>
    );
  }

  const issues = debug.issues ?? [];
  const suggestions = debug.suggestions ?? [];

  return (
    <div className="space-y-3 text-sm text-slate-200">
      {debug.summary && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            Summary
          </p>
          <p className="mt-1 text-sm text-slate-200">{debug.summary}</p>
        </div>
      )}

      {issues.length > 0 && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-rose-300">
            Detected issues
          </p>
          <ul className="mt-1 space-y-1 text-sm text-slate-200">
            {issues.map((issue, idx) => (
              <li key={idx} className="flex gap-2">
                <span className="mt-[6px] h-1.5 w-1.5 flex-shrink-0 rounded-full bg-rose-400" />
                <span>{issue}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {suggestions.length > 0 && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-emerald-300">
            Suggestions
          </p>
          <ul className="mt-1 space-y-1 text-sm text-slate-200">
            {suggestions.map((s, idx) => (
              <li key={idx} className="flex gap-2">
                <span className="mt-[6px] h-1.5 w-1.5 flex-shrink-0 rounded-full bg-emerald-400" />
                <span>{s}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

