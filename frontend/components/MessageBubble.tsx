"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import SourceList from "./SourceList";
import type { Source } from "@/lib/api";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  grounded?: boolean;
  latencyMs?: number;
  isError?: boolean;
}

export default function MessageBubble({ message }: { message: ChatMessage }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-indigo-600 px-4 py-2.5 text-sm text-white shadow">
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div
        className={`max-w-[95%] rounded-2xl rounded-bl-sm border px-4 py-3 text-sm shadow sm:max-w-[85%] ${
          message.isError
            ? "border-red-800 bg-red-950/50 text-red-200"
            : "border-slate-700 bg-slate-800/80 text-slate-100"
        }`}
      >
        <div className="prose prose-sm prose-invert max-w-none [&_pre]:!p-0">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              code(props) {
                const { children, className, ...rest } = props;
                const match = /language-(\w+)/.exec(className ?? "");
                const text = String(children).replace(/\n$/, "");
                if (match || text.includes("\n")) {
                  return (
                    <SyntaxHighlighter
                      language={match?.[1] ?? "python"}
                      style={oneDark}
                      customStyle={{ borderRadius: "0.5rem", fontSize: "0.8rem", margin: 0 }}
                    >
                      {text}
                    </SyntaxHighlighter>
                  );
                }
                return (
                  <code
                    className="rounded bg-slate-700 px-1 py-0.5 text-[0.8rem] text-amber-300"
                    {...rest}
                  >
                    {children}
                  </code>
                );
              },
            }}
          >
            {message.content}
          </ReactMarkdown>
        </div>

        {message.sources && message.sources.length > 0 && (
          <SourceList sources={message.sources} />
        )}

        {(message.latencyMs !== undefined || message.grounded !== undefined) && (
          <div className="mt-2 flex items-center gap-3 border-t border-slate-700/60 pt-2 text-[11px] text-slate-400">
            {message.grounded !== undefined && (
              <span
                className={`rounded-full px-2 py-0.5 ${
                  message.grounded
                    ? "bg-emerald-900/60 text-emerald-300"
                    : "bg-amber-900/60 text-amber-300"
                }`}
              >
                {message.grounded ? "Grounded in Stack Overflow" : "Out of knowledge base"}
              </span>
            )}
            {message.latencyMs !== undefined && <span>{message.latencyMs} ms</span>}
          </div>
        )}
      </div>
    </div>
  );
}
