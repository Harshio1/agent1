import type { TestResult, TestCaseResult } from "../types";
import {
  CheckCircleIcon,
  ExclamationCircleIcon
} from "@heroicons/react/24/outline";

type Props = {
  test?: TestResult | null;
};

const statusColor = (status?: string) => {
  if (!status) return "text-slate-300";
  const lower = status.toLowerCase();
  if (lower === "passed" || lower === "success") return "text-emerald-400";
  if (lower === "failed" || lower === "error") return "text-rose-400";
  return "text-amber-300";
};

const statusChipClasses = (status?: string) => {
  if (!status) return "bg-slate-800/80 text-slate-200";
  const lower = status.toLowerCase();
  if (lower === "passed" || lower === "success")
    return "bg-emerald-500/15 text-emerald-300 border-emerald-400/40";
  if (lower === "failed" || lower === "error")
    return "bg-rose-500/10 text-rose-300 border-rose-400/40";
  return "bg-amber-500/10 text-amber-300 border-amber-400/40";
};

function CaseRow({ testCase }: { testCase: TestCaseResult }) {
  const status = testCase.status ?? "unknown";
  const isPass = status.toLowerCase() === "passed" || status === "success";
  const Icon = isPass ? CheckCircleIcon : ExclamationCircleIcon;

  return (
    <div className="flex items-start justify-between gap-3 rounded-lg border border-slate-700/60 bg-slate-900/70 px-3 py-2 text-xs transition hover:border-slate-500/70">
      <div className="flex flex-1 items-start gap-2">
        <Icon className={`mt-[2px] h-4 w-4 flex-shrink-0 ${statusColor(status)}`} />
        <div>
          <p className="font-medium text-slate-100">
            {testCase.name ?? "Unnamed test case"}
          </p>
          {testCase.message && (
            <p className="mt-0.5 text-[11px] text-slate-300">
              {testCase.message}
            </p>
          )}
          {testCase.error && (
            <p className="mt-0.5 text-[11px] text-rose-300">
              {testCase.error}
            </p>
          )}
        </div>
      </div>
      <span
        className={[
          "inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
          statusChipClasses(status)
        ].join(" ")}
      >
        {status}
      </span>
    </div>
  );
}

export function TestResults({ test }: Props) {
  if (!test) {
    return (
      <p className="text-sm text-slate-400">
        No tests were run for this problem.
      </p>
    );
  }

  const cases = test.cases ?? [];
  const total = cases.length;
  const passed = cases.filter(
    (c) =>
      (c.status ?? "").toLowerCase() === "passed" ||
      c.status === "success"
  ).length;

  return (
    <div className="space-y-3 text-sm text-slate-200">
      <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-slate-300">
        <div>
          <p className="font-semibold uppercase tracking-wide text-slate-400">
            Summary
          </p>
          <p className="mt-1 text-sm text-slate-200">
            {test.summary ?? "Test execution summary not provided."}
          </p>
        </div>
        {total > 0 && (
          <div className="flex gap-3 text-[11px]">
            <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-emerald-300">
              Passed: {passed}
            </span>
            <span className="rounded-full bg-rose-500/10 px-2 py-0.5 text-rose-300">
              Failed: {total - passed}
            </span>
          </div>
        )}
      </div>

      {total > 0 && (
        <div className="space-y-2">
          {cases.map((testCase, idx) => (
            <CaseRow key={idx} testCase={testCase} />
          ))}
        </div>
      )}
    </div>
  );
}

