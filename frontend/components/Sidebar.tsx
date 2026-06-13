'use client';

import { useEffect, useRef, useState } from 'react';
import type { Session } from '@/lib/api';
import { AuthService } from '@/lib/auth';

interface Props {
  sessions: Session[];
  activeSessionId: string | null;
  onNewChat: () => void;
  onSelectSession: (id: string) => void;
  onDeleteSession: (id: string) => void;
  onRenameSession: (id: string, title: string) => void;
  isOpen: boolean;
  onToggle: () => void;
}

function groupSessions(sessions: Session[]): Record<string, Session[]> {
  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterdayStart = new Date(todayStart.getTime() - 86400000);
  const weekStart = new Date(todayStart.getTime() - 6 * 86400000);

  const groups: Record<string, Session[]> = {
    Today: [],
    Yesterday: [],
    'Previous 7 days': [],
    Older: [],
  };

  for (const s of sessions) {
    const d = new Date(s.updated_at);
    if (d >= todayStart) groups['Today'].push(s);
    else if (d >= yesterdayStart) groups['Yesterday'].push(s);
    else if (d >= weekStart) groups['Previous 7 days'].push(s);
    else groups['Older'].push(s);
  }

  return groups;
}

interface SessionItemProps {
  session: Session;
  isActive: boolean;
  onSelect: () => void;
  onDelete: () => void;
  onRename: (title: string) => void;
}

function SessionItem({ session, isActive, onSelect, onDelete, onRename }: SessionItemProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(session.title);
  const [hovered, setHovered] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  const commitRename = () => {
    const t = draft.trim();
    if (t && t !== session.title) onRename(t);
    setEditing(false);
  };

  return (
    <div
      className={`group relative flex items-center gap-2 rounded-lg px-3 py-2 cursor-pointer transition-colors ${
        isActive
          ? 'bg-[#2f2f2f] text-white'
          : 'text-[#ececec]/70 hover:bg-[#2f2f2f]/60 hover:text-white'
      }`}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={() => !editing && onSelect()}
    >
      <svg className="h-4 w-4 shrink-0 opacity-60" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
      </svg>

      {editing ? (
        <input
          ref={inputRef}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commitRename}
          onKeyDown={(e) => {
            if (e.key === 'Enter') commitRename();
            if (e.key === 'Escape') { setDraft(session.title); setEditing(false); }
          }}
          onClick={(e) => e.stopPropagation()}
          className="min-w-0 flex-1 bg-transparent text-sm text-white outline-none"
        />
      ) : (
        <span className="min-w-0 flex-1 truncate text-sm">{session.title}</span>
      )}

      {(hovered || isActive) && !editing && (
        <div className="flex shrink-0 items-center gap-0.5" onClick={(e) => e.stopPropagation()}>
          <button
            title="Rename"
            onClick={() => { setDraft(session.title); setEditing(true); }}
            className="rounded p-1 text-[#ececec]/50 hover:bg-white/10 hover:text-white"
          >
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
            </svg>
          </button>
          <button
            title="Delete"
            onClick={onDelete}
            className="rounded p-1 text-[#ececec]/50 hover:bg-red-500/20 hover:text-red-400"
          >
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        </div>
      )}
    </div>
  );
}

export default function Sidebar({
  sessions,
  activeSessionId,
  onNewChat,
  onSelectSession,
  onDeleteSession,
  onRenameSession,
  isOpen,
  onToggle,
}: Props) {
  const groups = groupSessions(sessions);

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 z-20 bg-black/50 md:hidden"
          onClick={onToggle}
        />
      )}

      {/* Sidebar panel */}
      <aside
        className={[
          'flex flex-col bg-[#171717] transition-all duration-200 ease-in-out',
          // Mobile: fixed overlay, slide in/out
          'fixed inset-y-0 left-0 z-30 w-64',
          isOpen ? 'translate-x-0' : '-translate-x-full',
          // Desktop: in document flow, toggle via width
          'md:relative md:inset-auto md:shrink-0 md:translate-x-0 md:h-full',
          isOpen ? 'md:w-64' : 'md:w-0 md:overflow-hidden',
        ].join(' ')}
      >
        {/* Top: new chat + close */}
        <div className="flex items-center gap-2 p-3">
          <button
            onClick={onNewChat}
            className="flex flex-1 items-center gap-2 rounded-lg px-3 py-2 text-sm text-[#ececec]/80 transition hover:bg-[#2f2f2f] hover:text-white"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            New Chat
          </button>
          <button
            onClick={onToggle}
            className="rounded-lg p-2 text-[#ececec]/50 hover:bg-[#2f2f2f] hover:text-white md:hidden"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Session list */}
        <nav className="flex-1 overflow-y-auto px-2 pb-2">
          {sessions.length === 0 ? (
            <p className="mt-4 text-center text-xs text-[#ececec]/30">No chats yet</p>
          ) : (
            Object.entries(groups).map(([label, group]) =>
              group.length === 0 ? null : (
                <div key={label} className="mb-3">
                  <p className="mb-1 px-3 text-[11px] font-medium uppercase tracking-wider text-[#ececec]/30">
                    {label}
                  </p>
                  {group.map((s) => (
                    <SessionItem
                      key={s.id}
                      session={s}
                      isActive={s.id === activeSessionId}
                      onSelect={() => onSelectSession(s.id)}
                      onDelete={() => onDeleteSession(s.id)}
                      onRename={(title) => onRenameSession(s.id, title)}
                    />
                  ))}
                </div>
              ),
            )
          )}
        </nav>

        {/* Bottom: user + logout */}
        <div className="border-t border-white/10 p-3">
          <button
            onClick={() => AuthService.logout()}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-[#ececec]/70 transition hover:bg-[#2f2f2f] hover:text-white"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
            Log out
          </button>
        </div>
      </aside>
    </>
  );
}
