'use client';

import { useCallback, useEffect, useState } from 'react';
import ProtectedRoute from '@/components/ProtectedRoute';
import Sidebar from '@/components/Sidebar';
import ChatWindow from '@/components/ChatWindow';
import {
  type Session,
  createSession,
  deleteSession,
  listSessions,
  renameSession,
} from '@/lib/api';


export default function Home() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  // Load sessions on mount
  useEffect(() => {
    listSessions()
      .then((data) => {
        setSessions(data);
        if (data.length > 0) setActiveSessionId(data[0].id);
      })
      .catch(() => {});
  }, []);

  const handleNewChat = useCallback(async () => {
    try {
      const session = await createSession();
      setSessions((prev) => [session, ...prev]);
      setActiveSessionId(session.id);
    } catch {}
  }, []);

  const handleSelectSession = useCallback((id: string) => {
    setActiveSessionId(id);
    // Close sidebar on mobile after selection
    if (window.innerWidth < 768) setSidebarOpen(false);
  }, []);

  const handleDeleteSession = useCallback(
    async (id: string) => {
      try {
        await deleteSession(id);
        setSessions((prev) => {
          const remaining = prev.filter((s) => s.id !== id);
          if (activeSessionId === id) {
            setActiveSessionId(remaining.length > 0 ? remaining[0].id : null);
          }
          return remaining;
        });
      } catch {}
    },
    [activeSessionId],
  );

  const handleRenameSession = useCallback(async (id: string, title: string) => {
    try {
      const updated = await renameSession(id, title);
      setSessions((prev) => prev.map((s) => (s.id === id ? updated : s)));
    } catch {}
  }, []);

  // Called by ChatWindow when it auto-creates a new session on first send
  const handleNewSession = useCallback((session: Session) => {
    setSessions((prev) => [session, ...prev]);
    setActiveSessionId(session.id);
  }, []);

  // Called by ChatWindow after first message so the sidebar refreshes the auto-generated title
  const handleSessionFirstMessage = useCallback(() => {
    listSessions()
      .then(setSessions)
      .catch(() => {});
  }, []);

  return (
    <ProtectedRoute>
      <div className="flex h-dvh overflow-hidden bg-[#212121]">
        {/* Sidebar */}
        <Sidebar
          sessions={sessions}
          activeSessionId={activeSessionId}
          onNewChat={handleNewChat}
          onSelectSession={handleSelectSession}
          onDeleteSession={handleDeleteSession}
          onRenameSession={handleRenameSession}
          isOpen={sidebarOpen}
          onToggle={() => setSidebarOpen((o) => !o)}
        />

        {/* Main area */}
        <div className="flex flex-1 flex-col overflow-hidden">
          {/* Top bar */}
          <header className="flex h-12 shrink-0 items-center justify-between border-b border-white/10 bg-[#212121] px-4">
            <div className="flex items-center gap-3">
              {/* Hamburger — always visible */}
              <button
                onClick={() => setSidebarOpen((o) => !o)}
                className="rounded-lg p-1.5 text-[#ececec]/50 hover:bg-white/10 hover:text-white"
                title={sidebarOpen ? 'Close sidebar' : 'Open sidebar'}
              >
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              </button>

              <span className="text-sm font-semibold text-[#ececec]">Python Q&A Assistant</span>
            </div>

          </header>

          {/* Chat — always rendered; auto-creates a session on first send */}
          <div className="flex-1 overflow-hidden">
            <ChatWindow
              sessionId={activeSessionId}
              onNewSession={handleNewSession}
              onSessionFirstMessage={handleSessionFirstMessage}
              onDeleteSession={handleDeleteSession}
            />
          </div>
        </div>
      </div>
    </ProtectedRoute>
  );
}
