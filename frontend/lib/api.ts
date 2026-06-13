import { AuthService } from './auth';

const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000').replace(/\/$/, '');

// ─── Core types ────────────────────────────────────────────────────────────

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
  status: 'ok' | 'degraded';
  vector_db: { connected: boolean; document_count: number };
  model: string;
  timestamp: string;
}

export interface Session {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
  grounded?: boolean;
  latency_ms?: number;
  model?: string;
  created_at: string;
  isError?: boolean;
}

export interface SessionWithMessages extends Session {
  messages: ChatMessage[];
}

// SSE event types streamed from /sessions/{id}/ask
export type StreamEvent =
  | { type: 'thinking'; status: 'retrieving' | 'generating' }
  | { type: 'token'; content: string }
  | { type: 'metadata'; sources: Source[]; grounded: boolean; latency_ms: number; model: string }
  | { type: 'done' }
  | { type: 'error'; detail: string };

export class ApiError extends Error {
  constructor(message: string, public status?: number) {
    super(message);
  }
}

// ─── Helpers ───────────────────────────────────────────────────────────────

function authHeaders(): Record<string, string> {
  const header = AuthService.getAuthHeader();
  if (!header) throw new ApiError('Authentication required. Please log in.', 401);
  return { 'Content-Type': 'application/json', Authorization: header };
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (res.status === 401) {
    AuthService.logout();
    throw new ApiError('Session expired. Please log in again.', 401);
  }
  if (!res.ok) {
    const detail = await res
      .json()
      .then((b) => (typeof b.detail === 'string' ? b.detail : JSON.stringify(b.detail)))
      .catch(() => res.statusText);
    throw new ApiError(detail, res.status);
  }
  return res.json() as Promise<T>;
}

// ─── Health ────────────────────────────────────────────────────────────────

export async function getHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_URL}/health`, { cache: 'no-store' });
  if (!res.ok) throw new ApiError('Health check failed', res.status);
  return res.json();
}

// ─── Sessions ──────────────────────────────────────────────────────────────

export async function listSessions(): Promise<Session[]> {
  const res = await fetch(`${API_URL}/sessions`, { headers: authHeaders() });
  return handleResponse<Session[]>(res);
}

export async function createSession(title = 'New Chat'): Promise<Session> {
  const res = await fetch(`${API_URL}/sessions`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ title }),
  });
  return handleResponse<Session>(res);
}

export async function getSession(id: string): Promise<SessionWithMessages> {
  const res = await fetch(`${API_URL}/sessions/${id}`, { headers: authHeaders() });
  return handleResponse<SessionWithMessages>(res);
}

export async function renameSession(id: string, title: string): Promise<Session> {
  const res = await fetch(`${API_URL}/sessions/${id}`, {
    method: 'PATCH',
    headers: authHeaders(),
    body: JSON.stringify({ title }),
  });
  return handleResponse<Session>(res);
}

export async function deleteSession(id: string): Promise<void> {
  const res = await fetch(`${API_URL}/sessions/${id}`, {
    method: 'DELETE',
    headers: authHeaders(),
  });
  if (res.status === 401) { AuthService.logout(); throw new ApiError('Session expired.', 401); }
  if (res.status !== 204 && !res.ok) throw new ApiError('Delete failed', res.status);
}

// ─── Streaming ask ─────────────────────────────────────────────────────────

export async function* streamAsk(
  sessionId: string,
  question: string,
  signal?: AbortSignal,
): AsyncGenerator<StreamEvent> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/sessions/${sessionId}/ask`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ question }),
      signal,
    });
  } catch (err: unknown) {
    if (err instanceof Error && err.name === 'AbortError') return;
    throw new ApiError('Cannot reach the API server.');
  }

  if (res.status === 401) { AuthService.logout(); throw new ApiError('Session expired.', 401); }
  if (!res.ok) {
    const detail = await res.json().then((b) => b.detail ?? res.statusText).catch(() => res.statusText);
    throw new ApiError(detail, res.status);
  }

  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split('\n\n');
      buffer = parts.pop() ?? '';
      for (const part of parts) {
        const line = part.trim();
        if (line.startsWith('data: ')) {
          try {
            yield JSON.parse(line.slice(6)) as StreamEvent;
          } catch { /* skip malformed chunk */ }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

// ─── Legacy non-streaming ask (kept for /ask endpoint) ─────────────────────

export async function ask(question: string): Promise<AskResponse> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/ask`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ question }),
    });
  } catch {
    throw new ApiError('Cannot reach the API server. Is the backend running?');
  }
  return handleResponse<AskResponse>(res);
}
