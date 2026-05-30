const BASE = process.env.NEXT_PUBLIC_AGENT_API_URL ?? process.env.AGENT_API_URL ?? "http://localhost:8000";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { ...init, cache: "no-store" });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${path} → ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export interface Run {
  id: string;
  started_at: string;
  finished_at: string | null;
  status: "pending" | "running" | "completed" | "failed";
  csv_filename: string;
  total_rows: number | null;
  matched: number | null;
  escalated: number | null;
  total_cost_usd: number | null;
}

export interface StepTrace {
  id: string;
  run_id: string;
  step_name: string;
  attempt: number;
  input_json: Record<string, unknown>;
  output_json: Record<string, unknown> | null;
  latency_ms: number | null;
  tokens_in: number | null;
  tokens_out: number | null;
  cost_usd: number | null;
  status: "success" | "retry" | "failure" | "escalated";
  invariant_results: Array<{ name: string; passed: boolean; detail: string | null }> | null;
  llm_provider: string | null;
  llm_model: string | null;
  created_at: string;
}

export interface EvalResult {
  id: string;
  ran_at: string;
  total_cases: number;
  passed: number;
  accuracy: number | null;
  precision_score: number | null;
  recall_score: number | null;
  f1_score: number | null;
  avg_cost_usd: number | null;
  p95_latency_ms: number | null;
  regressions: string[] | null;
}

export const api = {
  getRuns: () => apiFetch<Run[]>("/runs"),
  getRun: (id: string) => apiFetch<Run>(`/runs/${id}`),
  getTraces: (id: string) => apiFetch<StepTrace[]>(`/runs/${id}/traces`),
  replayStep: (runId: string, step: string) =>
    apiFetch<{ status: string; output: Record<string, unknown> }>(
      `/runs/${runId}/steps/${step}/replay`,
      { method: "POST" }
    ),
  getEvalResults: () => apiFetch<EvalResult[]>("/evals/results"),
  triggerEvals: () => apiFetch<Record<string, unknown>>("/evals/run", { method: "POST" }),
};
