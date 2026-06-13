"use client";

import { useState } from "react";
import type { Source } from "@/lib/api";

export default function SourceList({ sources }: { sources: Source[] }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="mt-3">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 text-xs font-medium text-indigo-300 hover:text-indigo-200"
      >
        <span
          className={`inline-block transition-transform ${open ? "rotate-90" : ""}`}
        >
          ▸
        </span>
        {sources.length} source{sources.length > 1 ? "s" : ""} from Stack Overflow
      </button>

      {open && (
        <ul className="mt-2 space-y-2">
          {sources.map((s, i) => (
            <li
              key={s.link + i}
              className="rounded-lg border border-slate-700 bg-slate-900/70 p-2.5"
            >
              <a
                href={s.link}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs font-semibold text-indigo-300 hover:underline"
              >
                [{i + 1}] {s.title}
              </a>
              <p className="mt-1 line-clamp-2 text-[11px] text-slate-400">{s.snippet}</p>
              <p className="mt-1 text-[10px] text-slate-500">
                ▲ {s.question_score} question · ▲ {s.answer_score} answer
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
