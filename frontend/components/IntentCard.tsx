import type { IntentResult } from "../types";

type Props = {
  intent?: IntentResult | null;
};

export function IntentCard({ intent }: Props) {
  if (!intent) {
    return (
      <p className="text-sm text-slate-400">
        No intent information returned.
      </p>
    );
  }

  const confidence =
    typeof intent.confidence === "number"
      ? Math.round(intent.confidence * 100)
      : null;

  return (
    <div className="space-y-3 text-sm text-slate-200">
      {intent.intent && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            Predicted intent
          </p>
          <p className="mt-1 text-base font-semibold text-slate-50">
            {intent.intent}
          </p>
        </div>
      )}

      {confidence !== null && (
        <div>
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Confidence</span>
            <span>{confidence}%</span>
          </div>
          <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-slate-800">
            <div
              className="h-2 rounded-full bg-emerald-500 transition-all"
              style={{ width: `${Math.min(Math.max(confidence, 0), 100)}%` }}
            />
          </div>
        </div>
      )}

      {intent.summary && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            Summary
          </p>
          <p className="mt-1 text-sm text-slate-200">{intent.summary}</p>
        </div>
      )}

      {intent.details && !intent.summary && (
        <p className="text-sm text-slate-200">{intent.details}</p>
      )}
    </div>
  );
}

