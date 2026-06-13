'use client';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import SourceList from './SourceList';
import type { ChatMessage } from '@/lib/api';

export type { ChatMessage };

export default function MessageBubble({ message }: { message: ChatMessage }) {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end py-1">
        <div className="max-w-[75%] rounded-2xl rounded-br-sm bg-[#2f2f2f] px-4 py-3 text-sm text-[#ececec] shadow">
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start py-1">
      <div className="flex gap-4 max-w-3xl w-full">
        {/* Avatar */}
        <div className="mt-1 h-7 w-7 shrink-0 rounded-full bg-[#19c37d]/20 flex items-center justify-center text-sm">
          🐍
        </div>

        <div className="flex-1 min-w-0">
          <div
            className={`rounded-2xl rounded-tl-sm px-4 py-3 text-sm shadow ${
              message.isError
                ? 'bg-red-950/40 text-red-300 border border-red-800/50'
                : 'bg-[#2f2f2f] text-[#ececec]'
            }`}
          >
            <div className="prose prose-sm prose-invert max-w-none [&_pre]:p-0!">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  code(props) {
                    const { children, className, ...rest } = props;
                    const match = /language-(\w+)/.exec(className ?? '');
                    const text = String(children).replace(/\n$/, '');
                    if (match || text.includes('\n')) {
                      return (
                        <SyntaxHighlighter
                          language={match?.[1] ?? 'python'}
                          style={oneDark}
                          customStyle={{ borderRadius: '0.5rem', fontSize: '0.8rem', margin: 0 }}
                        >
                          {text}
                        </SyntaxHighlighter>
                      );
                    }
                    return (
                      <code
                        className="rounded bg-white/10 px-1 py-0.5 text-[0.8rem] text-amber-300"
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

            {/* Sources */}
            {message.sources && message.sources.length > 0 && (
              <SourceList sources={message.sources} />
            )}

            {/* Metadata bar */}
            {(message.grounded !== undefined || message.latency_ms !== undefined || message.model) && (
              <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-white/10 pt-2.5 text-[11px] text-[#ececec]/40">
                {message.grounded !== undefined && (
                  <span
                    className={`flex items-center gap-1 rounded-full px-2 py-0.5 font-medium ${
                      message.grounded
                        ? 'bg-emerald-900/40 text-emerald-400'
                        : 'bg-amber-900/40 text-amber-400'
                    }`}
                  >
                    <span className={`h-1.5 w-1.5 rounded-full ${message.grounded ? 'bg-emerald-400' : 'bg-amber-400'}`} />
                    {message.grounded ? 'Grounded · Stack Overflow' : 'Out of knowledge base'}
                  </span>
                )}
                {message.latency_ms !== undefined && (
                  <span className="flex items-center gap-1">
                    <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    {message.latency_ms} ms
                  </span>
                )}
                {message.model && (
                  <span className="flex items-center gap-1">
                    <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17H3a2 2 0 01-2-2V5a2 2 0 012-2h14a2 2 0 012 2v10a2 2 0 01-2 2h-2" />
                    </svg>
                    {message.model}
                  </span>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
