"use client";

import { useState } from "react";
import { ChatInput } from "../components/ChatInput";
import { ResultSection } from "../components/ResultSection";
import { ExecutionTimeline } from "../components/ExecutionTimeline";
import { IntentCard } from "../components/IntentCard";
import { PlanningSection } from "../components/PlanningSection";
import { TestResults } from "../components/TestResults";
import { DebugResult } from "../components/DebugResult";
import { LoadingSkeleton } from "../components/LoadingSkeleton";
import { RequestMeta } from "../components/RequestMeta";
import { runCodePilot, CodePilotError } from "../lib/api";
import type { CodePilotResponse } from "../types";
import { useToast } from "../components/ToastProvider";

export default function HomePage() {
  const [result, setResult] = useState<CodePilotResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const toast = useToast();

  const handleRun = async (problem: string) => {
    try {
      setIsLoading(true);
      setError(null);
      setResult(null);

      const data = await runCodePilot({ problem });
      setResult(data);
    } catch (e) {
      const message =
        e instanceof CodePilotError
          ? e.message
          : "Unexpected error while running CodePilot.";
      setError(message);
      toast.showToast(message, "error");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight text-slate-50">
          CodePilot – Engineering-grade AI
        </h1>
        <p className="text-sm text-slate-300">
          Describe a programming task and CodePilot will plan, implement, test, and
          debug the solution for you.
        </p>
      </header>

      <ChatInput onSubmit={handleRun} isLoading={isLoading} />

      {isLoading && !result && <LoadingSkeleton />}

      {error && (
        <div className="rounded-2xl border border-red-500/40 bg-red-950/40 p-3 text-xs text-red-200">
          {error}
        </div>
      )}

      {result && (
        <div className="space-y-4">
          <RequestMeta requestId={result.request_id ?? null} />
          <ResultSection title="Intent Classification">
            <IntentCard intent={result.intent_result ?? null} />
          </ResultSection>

          <ResultSection title="Engineering Plan">
            <PlanningSection planning={result.planning_result ?? null} />
          </ResultSection>

          <ResultSection title="Generated Code">
            <pre className="max-h-[360px] overflow-auto whitespace-pre text-xs text-slate-100">
              {result.generated_code || "No code generated."}
            </pre>
          </ResultSection>

          <ResultSection title="Test Results">
            <TestResults test={result.test_result ?? null} />
          </ResultSection>

          <ResultSection title="Debug Analysis">
            <DebugResult debug={result.debug_result ?? null} />
          </ResultSection>

          <ResultSection title="Execution Timeline">
            <ExecutionTimeline executionLog={result.execution_log ?? []} />
          </ResultSection>
        </div>
      )}
    </main>
  );
}

