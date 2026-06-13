"use client";

import { useEffect, useState } from "react";
import { getHealth, type HealthResponse } from "@/lib/api";

export default function HealthBadge() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const check = async () => {
      try {
        const h = await getHealth();
        if (!cancelled) {
          setHealth(h);
          setError(false);
        }
      } catch {
        if (!cancelled) setError(true);
      }
    };
    check();
    const id = setInterval(check, 30_000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const status = error ? "offline" : health?.status ?? "checking";
  const dot =
    status === "ok"
      ? "bg-emerald-400"
      : status === "checking"
        ? "bg-amber-400 animate-pulse"
        : "bg-red-500";

  return (
    <div className="flex items-center gap-2 rounded-full border border-slate-700 bg-slate-800/60 px-3 py-1 text-xs text-slate-300">
      <span className={`h-2 w-2 rounded-full ${dot}`} />
      <span className="capitalize">{status === "ok" ? "API online" : status}</span>
      {health && status === "ok" && (
        <span className="hidden text-slate-500 sm:inline">
          · {health.vector_db.document_count.toLocaleString()} docs
        </span>
      )}
    </div>
  );
}
