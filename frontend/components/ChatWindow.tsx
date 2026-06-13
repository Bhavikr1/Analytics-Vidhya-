'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError, type ChatMessage, type Session, type Source, createSession, getSession, streamAsk } from '@/lib/api';
import MessageBubble from './MessageBubble';

const SUGGESTIONS = [
  'How do I merge two dictionaries in Python?',
  "What's the difference between a list and a tuple?",
  'How does pandas groupby aggregation work?',
  "Why am I getting 'NoneType' object is not subscriptable?",
];

type ThinkingStatus = 'idle' | 'retrieving' | 'generating' | 'streaming';

interface StreamingState {
  content: string;
  sources: Source[];
  grounded?: boolean;
  latency_ms?: number;
  model?: string;
}

interface Props {
  sessionId: string | null;
  onSessionFirstMessage?: () => void;
  onNewSession?: (session: Session) => void;
}

export default function ChatWindow({ sessionId, onSessionFirstMessage, onNewSession }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [thinkingStatus, setThinkingStatus] = useState<ThinkingStatus>('idle');
  const [streaming, setStreaming] = useState<StreamingState | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Load messages when session changes
  useEffect(() => {
    if (!sessionId) {
      setMessages([]);
      return;
    }
    getSession(sessionId)
      .then((s) => setMessages(s.messages))
      .catch(() => setMessages([]));
  }, [sessionId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streaming, thinkingStatus]);

  // Auto-resize textarea
  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = `${Math.min(ta.scrollHeight, 200)}px`;
  }, [input]);

  const send = useCallback(
    async (question: string) => {
      const q = question.trim();
      if (!q || thinkingStatus !== 'idle') return;

      // Auto-create a session if none exists yet
      let activeId = sessionId;
      if (!activeId) {
        try {
          const newSession = await createSession();
          onNewSession?.(newSession);
          activeId = newSession.id;
        } catch {
          return;
        }
      }

      setInput('');
      const userMsg: ChatMessage = {
        id: `tmp-user-${Date.now()}`,
        role: 'user',
        content: q,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userMsg]);
      setThinkingStatus('retrieving');
      setStreaming({ content: '', sources: [] });

      abortRef.current = new AbortController();

      // Local accumulators — avoids reading back from React state inside updaters,
      // which causes Strict Mode to run them twice and produce duplicate keys.
      let accContent = '';
      let accMeta: { sources: Source[]; grounded?: boolean; latency_ms?: number; model?: string } =
        { sources: [] };

      try {
        for await (const event of streamAsk(activeId, q, abortRef.current.signal)) {
          if (event.type === 'thinking') {
            setThinkingStatus(event.status === 'retrieving' ? 'retrieving' : 'generating');
          } else if (event.type === 'token') {
            accContent += event.content;
            setThinkingStatus('streaming');
            setStreaming({ content: accContent, ...accMeta });
          } else if (event.type === 'metadata') {
            accMeta = {
              sources: event.sources,
              grounded: event.grounded,
              latency_ms: event.latency_ms,
              model: event.model,
            };
            setStreaming((prev) => (prev ? { ...prev, ...accMeta } : null));
          } else if (event.type === 'done') {
            const finalMsg: ChatMessage = {
              id: `msg-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
              role: 'assistant',
              content: accContent,
              sources: accMeta.sources,
              grounded: accMeta.grounded,
              latency_ms: accMeta.latency_ms,
              model: accMeta.model,
              created_at: new Date().toISOString(),
            };
            setStreaming(null);
            setThinkingStatus('idle');
            setMessages((m) => [...m, finalMsg]);
            onSessionFirstMessage?.();
          } else if (event.type === 'error') {
            throw new Error(event.detail);
          }
        }
      } catch (err) {
        if (err instanceof Error && err.name === 'AbortError') return;
        const detail =
          err instanceof ApiError ? err.message : 'Something went wrong. Please try again.';
        const errMsg: ChatMessage = {
          id: `tmp-err-${Date.now()}`,
          role: 'assistant',
          content: detail,
          isError: true,
          created_at: new Date().toISOString(),
        };
        setMessages((m) => [...m, errMsg]);
        setStreaming(null);
        setThinkingStatus('idle');
      }
    },
    [sessionId, thinkingStatus, onSessionFirstMessage],
  );

  const isIdle = thinkingStatus === 'idle';

  return (
    <div className="flex h-full flex-col bg-[#212121]">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-3xl px-4 py-8 space-y-2">
          {messages.length === 0 && isIdle && (
            <div className="flex flex-col items-center justify-center pt-16 text-center">
              <div className="text-5xl mb-4">🐍</div>
              <h2 className="text-2xl font-semibold text-[#ececec] mb-2">
                Ask me anything about Python
              </h2>
              <p className="text-sm text-[#ececec]/50 max-w-md mb-8">
                Answers are grounded in real Stack Overflow questions and answers — with sources
                you can verify.
              </p>
              <div className="grid gap-2 sm:grid-cols-2 w-full max-w-xl">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    onClick={() => send(s)}
                    className="rounded-xl border border-white/10 bg-[#2f2f2f] px-4 py-3 text-left text-sm text-[#ececec]/70 transition hover:border-white/20 hover:bg-[#3a3a3a] hover:text-white"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m) => (
            <MessageBubble key={m.id} message={m} />
          ))}

          {/* Thinking / streaming bubble */}
          {thinkingStatus !== 'idle' && (
            <div className="flex justify-start py-1">
              <div className="flex gap-4 max-w-3xl w-full">
                {/* Avatar */}
                <div className="mt-1 h-7 w-7 shrink-0 rounded-full bg-[#19c37d]/20 flex items-center justify-center text-sm">
                  🐍
                </div>
                <div className="flex-1 min-w-0">
                  {thinkingStatus === 'retrieving' && (
                    <ThinkingIndicator label="Searching Stack Overflow knowledge base…" />
                  )}
                  {thinkingStatus === 'generating' && (
                    <ThinkingIndicator label="Generating answer…" />
                  )}
                  {thinkingStatus === 'streaming' && streaming && (
                    <StreamingBubble state={streaming} />
                  )}
                </div>
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      </div>

      {/* Input */}
      <div className="border-t border-white/10 bg-[#212121] px-4 py-4">
        <form
          onSubmit={(e) => { e.preventDefault(); send(input); }}
          className="mx-auto max-w-3xl"
        >
          <div className="flex items-end gap-3 rounded-2xl border border-white/10 bg-[#2f2f2f] px-4 py-3 focus-within:border-white/20">
            <textarea
              ref={textareaRef}
              rows={1}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  send(input);
                }
              }}
              placeholder="Ask a Python question…"
              maxLength={2000}
              disabled={!isIdle}
              className="flex-1 resize-none bg-transparent text-sm text-[#ececec] placeholder-[#ececec]/30 outline-none disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={!isIdle || input.trim().length < 3}
              className="shrink-0 rounded-lg bg-white p-1.5 text-black transition hover:bg-white/90 disabled:cursor-not-allowed disabled:opacity-30"
              title="Send"
            >
              <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
                <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
              </svg>
            </button>
          </div>
          <p className="mt-1.5 text-center text-[11px] text-[#ececec]/25">
            Answers grounded in Stack Overflow · Press Enter to send, Shift+Enter for new line
          </p>
        </form>
      </div>
    </div>
  );
}

function ThinkingIndicator({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-3 py-2">
      <span className="flex gap-1">
        <span className="h-2 w-2 rounded-full bg-[#19c37d] animate-bounce [animation-delay:0ms]" />
        <span className="h-2 w-2 rounded-full bg-[#19c37d] animate-bounce [animation-delay:150ms]" />
        <span className="h-2 w-2 rounded-full bg-[#19c37d] animate-bounce [animation-delay:300ms]" />
      </span>
      <span className="text-sm text-[#ececec]/50 italic">{label}</span>
    </div>
  );
}

function StreamingBubble({ state }: { state: StreamingState }) {
  return (
    <div className="rounded-2xl rounded-tl-sm bg-[#2f2f2f] px-4 py-3 text-sm text-[#ececec] shadow">
      <div className="prose prose-sm prose-invert max-w-none whitespace-pre-wrap wrap-break-word">
        {state.content}
        <span className="ml-0.5 inline-block h-4 w-0.5 animate-pulse bg-[#ececec]/60 align-middle" />
      </div>
    </div>
  );
}
