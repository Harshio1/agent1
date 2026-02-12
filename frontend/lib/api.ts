import type { CodePilotResponse, ExecutionLogEntry } from "../types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

type RunCodePilotOptions = {
  problem: string;
  userId?: string;
  timeoutMs?: number;
  signal?: AbortSignal;
};

export class CodePilotError extends Error {
  status?: number;
  constructor(message: string, status?: number) {
    super(message);
    this.name = "CodePilotError";
    this.status = status;
  }
}

function mergeAbortSignals(parent?: AbortSignal): AbortController {
  const controller = new AbortController();
  if (!parent) return controller;
  if (parent.aborted) {
    controller.abort(parent.reason);
  } else {
    const listener = () => controller.abort(parent.reason);
    parent.addEventListener("abort", listener, { once: true });
  }
  return controller;
}

function normaliseResponse(raw: any): CodePilotResponse {
  const executionLog =
    (raw?.execution_log as ExecutionLogEntry[] | undefined | null) ?? null;

  return {
    request_id: raw?.request_id ?? null,
    intent_result:
      (raw?.intent_result ?? raw?.intent_classification) ?? null,
    planning_result:
      (raw?.planning_result ?? raw?.engineering_plan) ?? null,
    test_result: (raw?.test_result ?? raw?.test_results) ?? null,
    debug_result: (raw?.debug_result ?? raw?.debug_analysis) ?? null,
    generated_code: raw?.generated_code ?? null,
    execution_log: executionLog
  };
}

export async function runCodePilot({
  problem,
  userId,
  timeoutMs = 60_000,
  signal
}: RunCodePilotOptions): Promise<CodePilotResponse> {
  const controller = mergeAbortSignals(signal);
  const timeout = setTimeout(
    () => controller.abort("Request timed out"),
    timeoutMs
  );

  try {
    const res = await fetch(`${API_BASE}/solve`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        problem,
        user_id: userId
      }),
      signal: controller.signal
    });

    if (!res.ok) {
      throw new CodePilotError(
        `Backend error: ${res.status} ${res.statusText}`,
        res.status
      );
    }

    const raw = await res.json();
    return normaliseResponse(raw);
  } catch (error: any) {
    if (error?.name === "AbortError") {
      throw new CodePilotError(
        typeof error?.message === "string"
          ? error.message
          : "Request aborted or timed out"
      );
    }
    if (error instanceof CodePilotError) {
      throw error;
    }
    throw new CodePilotError(
      "Network error while calling CodePilot. Please try again."
    );
  } finally {
    clearTimeout(timeout);
  }
}

// Placeholder shape for future streaming support.
// This can be wired to a streaming backend (e.g. Server-Sent Events or chunked JSON)
// without changing the UI surface.
export type CodePilotStreamHandlers = {
  onPartialUpdate?: (partial: Partial<CodePilotResponse>) => void;
  onComplete?: (full: CodePilotResponse) => void;
};

export async function runCodePilotStream(
  _options: RunCodePilotOptions,
  _handlers: CodePilotStreamHandlers
): Promise<void> {
  // Not implemented yet: structured so that a streaming backend can be
  // connected later without changing callers.
  throw new CodePilotError("Streaming API is not enabled yet.");
}

