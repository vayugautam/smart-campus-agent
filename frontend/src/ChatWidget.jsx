import ChatWindow from './ChatWindow';

/**
 * Props (all controlled from App.jsx):
 *   isOpen         – whether the panel is visible
 *   onToggle       – called when the bubble or close button is clicked
 *   prefillMessage – text to pre-fill into the chat input (not auto-sent)
 *   hasUnread      – true when an agent reply arrived while panel was closed
 *   onAgentMessage – forwarded to ChatWindow; App uses it to set hasUnread
 */
export default function ChatWidget({ isOpen, onToggle, prefillMessage, hasUnread, onAgentMessage }) {
  return (
    <>
      {/* ── Expanded panel ───────────────────────────────────────────── */}
      {isOpen && (
        <div
          className="
            fixed bottom-24 right-4 sm:right-6
            w-[calc(100vw-2rem)] sm:w-[420px]
            h-[600px] max-h-[calc(100dvh-7rem)]
            z-50
            rounded-2xl shadow-2xl shadow-slate-900/30
            overflow-hidden
            border border-slate-200
            bg-white
          "
          style={{ animation: 'fadeSlideUp 0.18s ease-out' }}
        >
          <div className="h-full flex flex-col">
            <ChatWindow
              prefillMessage={prefillMessage}
              onAgentMessage={onAgentMessage}
            />
          </div>
        </div>
      )}

      {/* ── Toggle bubble ────────────────────────────────────────────── */}
      <button
        onClick={onToggle}
        aria-label={isOpen ? 'Close chat' : 'Open campus assistant'}
        className="
          fixed bottom-5 right-4 sm:right-6
          z-50
          w-14 h-14
          rounded-full
          bg-indigo-600 hover:bg-indigo-700
          text-white
          shadow-xl shadow-indigo-500/40
          flex items-center justify-center
          transition-all duration-200
          active:scale-95
          focus:outline-none focus:ring-4 focus:ring-indigo-500/30
        "
      >
        {isOpen ? (
          /* X / close icon */
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="w-6 h-6"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2.2}
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        ) : (
          /* Chat bubble icon */
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="w-6 h-6"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
        )}

        {/* Pulse ring — only while closed and no unread (unread dot takes over) */}
        {!isOpen && !hasUnread && (
          <span className="absolute inset-0 rounded-full animate-ping bg-indigo-500 opacity-30 pointer-events-none" />
        )}

        {/* ── Unread notification dot ───────────────────────────────── */}
        {!isOpen && hasUnread && (
          <span
            aria-label="New message"
            className="
              absolute -top-1 -right-1
              w-5 h-5
              rounded-full
              bg-rose-500
              border-2 border-white
              flex items-center justify-center
              shadow-md
            "
          >
            {/* Inner ping animation on the dot itself */}
            <span className="absolute inset-0 rounded-full bg-rose-400 animate-ping opacity-60 pointer-events-none" />
          </span>
        )}
      </button>

      {/* ── Keyframe for panel slide-up ───────────────────────────────── */}
      <style>{`
        @keyframes fadeSlideUp {
          from { opacity: 0; transform: translateY(16px) scale(0.97); }
          to   { opacity: 1; transform: translateY(0)   scale(1); }
        }
      `}</style>
    </>
  );
}
