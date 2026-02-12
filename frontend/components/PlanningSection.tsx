import { useState } from "react";
import type { PlanningResult, PlanApproach, PlanStep } from "../types";
import { ChevronDownIcon, ChevronRightIcon } from "@heroicons/react/24/outline";

type Props = {
  planning?: PlanningResult | null;
};

function renderSteps(steps?: PlanStep[] | string[]) {
  if (!steps || steps.length === 0) return null;

  return (
    <ol className="mt-2 space-y-1 text-sm text-slate-200">
      {steps.map((step, idx) => {
        const content =
          typeof step === "string"
            ? step
            : step.description ?? step.title ?? "";
        if (!content) return null;
        return (
          <li key={idx} className="flex gap-2">
            <span className="mt-[3px] h-1.5 w-1.5 flex-shrink-0 rounded-full bg-indigo-400" />
            <span>{content}</span>
          </li>
        );
      })}
    </ol>
  );
}

function ApproachCard({
  approach,
  label,
  highlighted
}: {
  approach: PlanApproach;
  label?: string;
  highlighted?: boolean;
}) {
  const name =
    approach.name ?? approach.title ?? approach.id ?? "Unnamed approach";

  return (
    <div
      className={[
        "rounded-xl border px-3 py-2.5 text-sm transition",
        highlighted
          ? "border-indigo-400/70 bg-indigo-500/10 shadow-md shadow-indigo-500/30"
          : "border-slate-700/70 bg-slate-900/60 hover:border-slate-500/70"
      ].join(" ")}
    >
      <div className="flex items-center justify-between gap-2">
        <p className="font-semibold text-slate-100">{name}</p>
        {label && (
          <span className="rounded-full bg-indigo-500/20 px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide text-indigo-300">
            {label}
          </span>
        )}
      </div>
      {approach.summary && (
        <p className="mt-1 text-sm text-slate-200">{approach.summary}</p>
      )}
      {approach.rationale && !approach.summary && (
        <p className="mt-1 text-sm text-slate-200">{approach.rationale}</p>
      )}
      {renderSteps(approach.steps)}
    </div>
  );
}

export function PlanningSection({ planning }: Props) {
  const [showAlternatives, setShowAlternatives] = useState(false);

  if (!planning) {
    return (
      <p className="text-sm text-slate-400">
        No planning information returned.
      </p>
    );
  }

  const alternatives = planning.alternative_approaches ?? [];

  return (
    <div className="space-y-3 text-sm text-slate-200">
      {planning.selected_approach && (
        <ApproachCard
          approach={planning.selected_approach}
          label="Selected approach"
          highlighted
        />
      )}

      {alternatives.length > 0 && (
        <div className="rounded-xl border border-slate-700/70 bg-slate-900/60">
          <button
            type="button"
            onClick={() => setShowAlternatives((v) => !v)}
            className="flex w-full items-center justify-between px-3 py-2 text-left text-xs font-medium uppercase tracking-wide text-slate-400"
          >
            <span>Alternative approaches</span>
            {showAlternatives ? (
              <ChevronDownIcon className="h-3.5 w-3.5" />
            ) : (
              <ChevronRightIcon className="h-3.5 w-3.5" />
            )}
          </button>
          {showAlternatives && (
            <div className="space-y-2 border-t border-slate-700/70 px-3 py-2.5">
              {alternatives.map((alt, idx) => (
                <ApproachCard
                  key={idx}
                  approach={alt}
                  label={`Option ${idx + 1}`}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {planning.notes && (
        <p className="text-sm text-slate-300">{planning.notes}</p>
      )}
    </div>
  );
}

