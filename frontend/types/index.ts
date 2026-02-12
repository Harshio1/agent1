export type IntentResult = {
  intent?: string;
  confidence?: number;
  summary?: string;
  details?: string;
  [key: string]: unknown;
};

export type PlanStep = {
  title?: string;
  description?: string;
};

export type PlanApproach = {
  id?: string;
  name?: string;
  title?: string;
  summary?: string;
  rationale?: string;
  steps?: PlanStep[] | string[];
};

export type PlanningResult = {
  selected_approach?: PlanApproach | null;
  alternative_approaches?: PlanApproach[];
  notes?: string;
};

export type TestCaseResult = {
  name?: string;
  status?: "passed" | "failed" | "error" | string;
  message?: string;
  error?: string;
};

export type TestResult = {
  summary?: string;
  cases?: TestCaseResult[];
};

export type DebugResult = {
  summary?: string;
  issues?: string[];
  suggestions?: string[];
  [key: string]: unknown;
};

export type ExecutionStatus = "success" | "error" | "running" | string;

export type ExecutionLogEntry = {
  stage: string;
  duration_ms?: number;
  status?: ExecutionStatus;
  message?: string;
  timestamp?: string;
};

export type CodePilotResponse = {
  request_id?: string | null;
  intent_result?: IntentResult | null;
  planning_result?: PlanningResult | null;
  test_result?: TestResult | null;
  debug_result?: DebugResult | null;
  generated_code?: string | null;
  execution_log?: ExecutionLogEntry[] | null;
};

