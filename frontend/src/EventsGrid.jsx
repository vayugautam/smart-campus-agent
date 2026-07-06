import { useState, useEffect, useCallback } from 'react';
import { getEvents } from './api';

// ── Category config ──────────────────────────────────────────────────────────
const CATEGORY = {
  academic:    { label: 'Academic',    bg: 'bg-indigo-100',  text: 'text-indigo-700',  dot: 'bg-indigo-500'  },
  technology:  { label: 'Technology',  bg: 'bg-violet-100',  text: 'text-violet-700',  dot: 'bg-violet-500'  },
  cultural:    { label: 'Cultural',    bg: 'bg-pink-100',    text: 'text-pink-700',    dot: 'bg-pink-500'    },
  sports:      { label: 'Sports',      bg: 'bg-emerald-100', text: 'text-emerald-700', dot: 'bg-emerald-500' },
  networking:  { label: 'Networking',  bg: 'bg-amber-100',   text: 'text-amber-700',   dot: 'bg-amber-500'   },
  social:      { label: 'Social',      bg: 'bg-rose-100',    text: 'text-rose-700',    dot: 'bg-rose-500'    },
};

const fallbackCategory = { label: 'General', bg: 'bg-slate-100', text: 'text-slate-600', dot: 'bg-slate-400' };

// ── Helpers ──────────────────────────────────────────────────────────────────
function formatDate(dateStr) {
  // dateStr is "YYYY-MM-DD"
  const d = new Date(dateStr + 'T00:00:00');
  return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
}

function formatTime(timeStr) {
  // timeStr is "HH:MM"
  const [h, m] = timeStr.split(':').map(Number);
  const ampm = h >= 12 ? 'PM' : 'AM';
  const hour = h % 12 || 12;
  return `${hour}:${m.toString().padStart(2, '0')} ${ampm}`;
}

// ── Skeleton card ────────────────────────────────────────────────────────────
function SkeletonCard() {
  return (
    <div className="bg-white rounded-2xl border border-slate-100 p-5 flex flex-col gap-3 animate-pulse">
      <div className="flex items-center justify-between">
        <div className="h-5 w-24 bg-slate-200 rounded-full" />
        <div className="h-4 w-16 bg-slate-100 rounded-full" />
      </div>
      <div className="h-6 w-3/4 bg-slate-200 rounded-lg" />
      <div className="h-4 w-full bg-slate-100 rounded-lg" />
      <div className="h-4 w-5/6 bg-slate-100 rounded-lg" />
      <div className="mt-2 flex items-center gap-3">
        <div className="h-4 w-28 bg-slate-100 rounded" />
        <div className="h-4 w-20 bg-slate-100 rounded" />
      </div>
      <div className="mt-auto pt-3 border-t border-slate-100">
        <div className="h-9 w-full bg-slate-200 rounded-xl" />
      </div>
    </div>
  );
}

// ── Event card ───────────────────────────────────────────────────────────────
function EventCard({ event, onRegister }) {
  const cat = CATEGORY[event.category] ?? fallbackCategory;

  return (
    <div className="bg-white rounded-2xl border border-slate-100 shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-200 flex flex-col overflow-hidden group">

      {/* Top accent line */}
      <div className={`h-1 w-full ${cat.dot}`} />

      <div className="p-5 flex flex-col gap-3 flex-1">
        {/* Category badge + registration tag */}
        <div className="flex items-center justify-between gap-2">
          <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold ${cat.bg} ${cat.text}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${cat.dot}`} />
            {cat.label}
          </span>
          {event.registration_required && (
            <span className="text-[11px] font-medium text-amber-600 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded-full">
              Registration required
            </span>
          )}
        </div>

        {/* Event name */}
        <h3 className="text-base font-bold text-slate-800 leading-snug group-hover:text-indigo-700 transition-colors">
          {event.name}
        </h3>

        {/* Description */}
        <p className="text-sm text-slate-500 leading-relaxed line-clamp-2">
          {event.description}
        </p>

        {/* Meta row */}
        <div className="flex flex-wrap gap-3 text-xs text-slate-500 mt-auto">
          <span className="flex items-center gap-1">
            <svg className="w-3.5 h-3.5 text-slate-400" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
              <rect x="3" y="4" width="18" height="18" rx="2" />
              <path d="M16 2v4M8 2v4M3 10h18" />
            </svg>
            {formatDate(event.date)}
          </span>
          <span className="flex items-center gap-1">
            <svg className="w-3.5 h-3.5 text-slate-400" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
              <circle cx="12" cy="12" r="10" />
              <path d="M12 6v6l4 2" />
            </svg>
            {formatTime(event.time)}
          </span>
          <span className="flex items-center gap-1">
            <svg className="w-3.5 h-3.5 text-slate-400" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
              <path d="M12 22s-8-5.686-8-12a8 8 0 1 1 16 0c0 6.314-8 12-8 12z" />
              <circle cx="12" cy="10" r="3" />
            </svg>
            {event.venue}
          </span>
        </div>
      </div>

      {/* Register button — opens chat with pre-filled message */}
      <div className="px-5 pb-5">
        <button
          id={`register-btn-${event.id}`}
          className="w-full bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold py-2.5 rounded-xl transition-colors duration-150 active:scale-95 shadow-sm"
          onClick={() => onRegister(event.name)}
        >
          Register
        </button>
      </div>
    </div>
  );
}

// ── Error state ──────────────────────────────────────────────────────────────
function ErrorState({ onRetry }) {
  return (
    <div className="rounded-2xl border border-rose-100 bg-rose-50 flex flex-col items-center justify-center py-20 gap-4">
      <div className="w-12 h-12 bg-rose-100 rounded-xl flex items-center justify-center">
        <svg className="w-6 h-6 text-rose-500" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
          <circle cx="12" cy="12" r="10" />
          <path d="M12 8v4M12 16h.01" />
        </svg>
      </div>
      <div className="text-center">
        <p className="text-rose-700 font-semibold text-sm">Couldn't load events</p>
        <p className="text-rose-500 text-xs mt-1">Make sure the backend is running at localhost:8000</p>
      </div>
      <button
        onClick={onRetry}
        className="text-sm font-medium text-rose-600 hover:text-rose-800 underline underline-offset-2 transition-colors"
      >
        Try again
      </button>
    </div>
  );
}

// ── Main component ───────────────────────────────────────────────────────────
export default function EventsGrid({ onRegister }) {
  const [events, setEvents]   = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState(false);

  const fetchEvents = useCallback(() => {
    setLoading(true);
    setError(false);
    getEvents()
      .then((data) => {
        setEvents(data);
        setLoading(false);
      })
      .catch(() => {
        setError(true);
        setLoading(false);
      });
  }, []);

  useEffect(() => { fetchEvents(); }, [fetchEvents]);

  return (
    <section id="events" className="py-10">
      {/* Section header */}
      <div className="mb-7 flex items-end justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-slate-800 tracking-tight">Campus Events</h2>
          <p className="text-slate-500 text-sm mt-1">
            {loading ? 'Loading events…' : error ? 'Could not load events' : `${events.length} upcoming events`}
          </p>
        </div>
      </div>

      {/* Grid */}
      {error ? (
        <ErrorState onRetry={fetchEvents} />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {loading
            ? Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)
            : events.map((event) => <EventCard key={event.id} event={event} onRegister={onRegister} />)
          }
        </div>
      )}
    </section>
  );
}
