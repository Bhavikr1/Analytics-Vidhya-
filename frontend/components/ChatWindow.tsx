"use client";

import { useEffect, useRef, useState } from "react";
import { ApiError, ask } from "@/lib/api";
import MessageBubble, { type ChatMessage } from "./MessageBubble";

const SUGGESTIONS = [
  "How do I merge two dictionaries in Python?",
  "What's the difference between a list and a tuple?",
  "How does pandas groupby aggregation work?",
  "Why am I getting 'NoneType' object is not subscriptable?",
];

export default function ChatWindow() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function send(question: string) {
    const q = question.trim();
    if (!q || loading) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", content: q }]);
    setLoading(true);
    try {
      const res = await ask(q);
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: res.answer,
          sources: res.sources,
          grounded: res.grounded,
          latencyMs: res.latency_ms,
        },
      ]);
    } catch (err) {
      const detail =
        err instanceof ApiError ? err.message : "Something went wrong. Please try again.";
      setMessages((m) => [
        ...m,
        { role: "assistant", content: `⚠️ ${detail}`, isError: true },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 space-y-4 overflow-y-auto px-4 py-6">
        {messages.length === 0 && (
          <div className="mx-auto mt-10 max-w-lg text-center">
            <div className="text-4xl">🐍</div>
            <h2 className="mt-3 text-lg font-semibold text-slate-200">
              Ask me anything about Python
            </h2>
            <p className="mt-1 text-sm text-slate-400">
              Answers are grounded in real Stack Overflow questions and answers — with
              sources you can verify.
            </p>
            <div className="mt-6 grid gap-2 sm:grid-cols-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="rounded-xl border border-slate-700 bg-slate-800/60 px-3 py-2 text-left text-xs text-slate-300 transition hover:border-indigo-500 hover:text-white"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <MessageBubble key={i} message={m} />
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="flex items-center gap-2 rounded-2xl border border-slate-700 bg-slate-800/80 px-4 py-3 text-sm text-slate-400">
              <span className="flex gap-1">
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-indigo-400 [animation-delay:0ms]" />
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-indigo-400 [animation-delay:150ms]" />
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-indigo-400 [animation-delay:300ms]" />
              </span>
              Searching Stack Overflow knowledge base…
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
        className="border-t border-slate-800 bg-slate-900/80 p-4 backdrop-blur"
      >
        <div className="mx-auto flex max-w-3xl gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a Python question…"
            maxLength={2000}
            disabled={loading}
            className="flex-1 rounded-xl border border-slate-700 bg-slate-800 px-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 outline-none transition focus:border-indigo-500 disabled:opacity-60"
          />
          <button
            type="submit"
            disabled={loading || input.trim().length < 3}
            className="rounded-xl bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Ask
          </button>
        </div>
      </form>
    </div>
  );
}
