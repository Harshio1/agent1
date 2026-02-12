import type { ExecutionLogEntry } from "../types";
import {
  BeakerIcon,
  BugAntIcon,
  ClockIcon,
  CodeBracketIcon,
  LightBulbIcon,
  XCircleIcon,
  CheckCircleIcon
} from "@heroicons/react/24/outline";

type ExecutionTimelineProps = {
  executionLog?: ExecutionLogEntry[] | null;
};

function stageIcon(stage: string) {
  const key = stage.toLowerCase();
  if (key.includes("intent") || key.includes("plan")) return LightBulbIcon;
  if (key.includes("code") || key.includes("implement")) return CodeBracketIcon;
  if (key.includes("test")) return BeakerIcon;
  if (key.includes("debug")) return BugAntIcon;
  return ClockIcon;
}

function statusClasses(status?: string) {
  if (!status) return "border-slate-500 bg-slate-900 text-slate-200";
  const s = status.toLowerCase();
  if (s === "success" || s === "ok")
    return "border-emerald-500/60 bg-emerald-500/10 text-emerald-200";
  if (s === "error" || s === "failed")
    return "border-rose-500/60 bg-rose-500/10 text-rose-200";
  return "border-amber-500/60 bg-amber-500/10 text-amber-200";
}

export function ExecutionTimeline({ executionLog }: ExecutionTimelineProps) {
  if (!executionLog || executionLog.length === 0) {
    return (
      <p className="text-sm text-slate-400">
        No execution timeline available.
      </p>
    );
  }

  return (
    <ol className="relative space-y-4 border-l border-slate-700 pl-4">
      {executionLog.map((entry, idx) => {
        const stageLabel = entry.stage || `Step ${idx + 1}`;
        const duration =
          typeof entry.duration_ms === "number"
            ? `${entry.duration_ms.toFixed(0)} ms`
            : null;
        const status = entry.status;
        const Icon = stageIcon(stageLabel);
        const StatusIcon =
          status && status.toLowerCase() === "success"
            ? CheckCircleIcon
            : status && status.toLowerCase() === "error"
            ? XCircleIcon
            : null;

        return (
          <li key={idx} className="relative space-y-1">
            <div className="absolute -left-[10px] mt-1 flex h-5 w-5 items-center justify-center rounded-full border border-slate-600 bg-slate-900">
              <Icon className="h-3 w-3 text-slate-200" />
            </div>
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-300">
                  {stageLabel}
                </p>
                {status && (
                  <span
                    className={[
                      "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                      statusClasses(status)
                    ].join(" ")}
                  >
                    {StatusIcon && (
                      <StatusIcon className="h-3 w-3" />
                    )}
                    {status}
                  </span>
                )}
              </div>
              <div className="flex flex-col items-end gap-0.5">
                {duration && (
                  <span className="text-[11px] text-slate-400">
                    {duration}
                  </span>
                )}
                {entry.timestamp && (
                  <span className="text-[11px] text-slate-500">
                    {entry.timestamp}
                  </span>
                )}
              </div>
            </div>
            {entry.message && (
              <p className="text-sm text-slate-200">{entry.message}</p>
            )}
          </li>
        );
      })}
    </ol>
  );
}

