const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface Source {
  title: string;
  link: string;
  question_score: number;
  answer_score: number;
  snippet: string;
}

export interface AskResponse {
  answer: string;
  sources: Source[];
  grounded: boolean;
  latency_ms: number;
  model: string;
}

export interface HealthResponse {
  status: "ok" | "degraded";
  vector_db: { connected: boolean; document_count: number };
  model: string;
  timestamp: string;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public status?: number,
  ) {
    super(message);
  }
}

export async function ask(question: string): Promise<AskResponse> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
  } catch {
    throw new ApiError("Cannot reach the API server. Is the backend running?");
  }
  if (!res.ok) {
    const detail = await res
      .json()
      .then((b) => (typeof b.detail === "string" ? b.detail : JSON.stringify(b.detail)))
      .catch(() => res.statusText);
    throw new ApiError(detail, res.status);
  }
  return res.json();
}

export async function getHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_URL}/health`, { cache: "no-store" });
  if (!res.ok) throw new ApiError("Health check failed", res.status);
  return res.json();
}
