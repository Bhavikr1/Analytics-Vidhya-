import ChatWindow from "@/components/ChatWindow";
import HealthBadge from "@/components/HealthBadge";

export default function Home() {
  return (
    <main className="flex h-dvh flex-col bg-slate-950">
      <header className="flex items-center justify-between border-b border-slate-800 bg-slate-900/80 px-4 py-3 backdrop-blur sm:px-6">
        <div className="flex items-center gap-2.5">
          <span className="text-xl">🐍</span>
          <div>
            <h1 className="text-sm font-bold text-slate-100 sm:text-base">
              Python Q&A Assistant
            </h1>
            <p className="hidden text-[11px] text-slate-400 sm:block">
              Grounded answers from Stack Overflow&apos;s Python knowledge base
            </p>
          </div>
        </div>
        <HealthBadge />
      </header>
      <div className="mx-auto flex w-full max-w-4xl flex-1 flex-col overflow-hidden">
        <ChatWindow />
      </div>
    </main>
  );
}
