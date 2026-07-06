import { useState, useEffect, useCallback } from 'react';
import { getFacilities } from './api';

// ── Facility type → icon + colour config ─────────────────────────────────────
const TYPE_CONFIG = {
  auditorium:       { label: 'Auditorium',       bg: 'bg-indigo-100',  text: 'text-indigo-700',  iconPath: 'M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2z' },
  seminar_hall:     { label: 'Seminar Hall',     bg: 'bg-sky-100',     text: 'text-sky-700',     iconPath: 'M17 20h5v-2a3 3 0 0 0-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 0 1 5.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 0 1 9.288 0M15 7a3 3 0 1 1-6 0 3 3 0 0 1 6 0z' },
  computer_lab:     { label: 'Computer Lab',     bg: 'bg-violet-100',  text: 'text-violet-700',  iconPath: 'M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 0 0 2-2V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2z' },
  science_lab:      { label: 'Science Lab',      bg: 'bg-teal-100',    text: 'text-teal-700',    iconPath: 'M19.428 15.428a2 2 0 0 0-1.022-.547l-2.387-.477a6 6 0 0 0-3.86.517l-.318.158a6 6 0 0 1-3.86.517L6.05 15.21a2 2 0 0 0-1.806.547M8 4h8l-1 1v5.172a2 2 0 0 0 .586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 0 0 9 10.172V5L8 4z' },
  conference_room:  { label: 'Conference Room',  bg: 'bg-amber-100',   text: 'text-amber-700',   iconPath: 'M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 0 1-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z' },
  discussion_room:  { label: 'Discussion Room',  bg: 'bg-lime-100',    text: 'text-lime-700',    iconPath: 'M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-3l-4 4z' },
  sports_facility:  { label: 'Sports Facility',  bg: 'bg-emerald-100', text: 'text-emerald-700', iconPath: 'M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z' },
  amphitheatre:     { label: 'Amphitheatre',     bg: 'bg-orange-100',  text: 'text-orange-700',  iconPath: 'M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2z' },
  studio:           { label: 'Studio',           bg: 'bg-rose-100',    text: 'text-rose-700',    iconPath: 'M15 10l4.553-2.069A1 1 0 0 1 21 8.87v6.26a1 1 0 0 1-1.447.894L15 14M3 8a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8z' },
};

const fallbackType = { label: 'Facility', bg: 'bg-slate-100', text: 'text-slate-600', iconPath: 'M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z' };

// Returns today's date as "YYYY-MM-DD" in local time (avoids UTC day-shift)
function todayLocalISO() {
  const d = new Date();
  return [
    d.getFullYear(),
    String(d.getMonth() + 1).padStart(2, '0'),
    String(d.getDate()).padStart(2, '0'),
  ].join('-');
}

// ── Skeleton card ────────────────────────────────────────────────────────────
function SkeletonCard() {
  return (
    <div className="bg-white rounded-2xl border border-slate-100 p-5 flex flex-col gap-3 animate-pulse">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 bg-slate-200 rounded-xl flex-shrink-0" />
        <div className="flex-1">
          <div className="h-5 w-40 bg-slate-200 rounded-lg mb-2" />
          <div className="h-3.5 w-24 bg-slate-100 rounded" />
        </div>
      </div>
      <div className="flex gap-2 mt-1">
        <div className="h-5 w-16 bg-slate-100 rounded-full" />
        <div className="h-5 w-20 bg-slate-100 rounded-full" />
        <div className="h-5 w-14 bg-slate-100 rounded-full" />
      </div>
      <div className="h-4 w-full bg-slate-100 rounded mt-1" />
      <div className="mt-auto pt-3 border-t border-slate-100">
        <div className="h-9 w-full bg-slate-200 rounded-xl" />
      </div>
    </div>
  );
}

// ── Facility card ────────────────────────────────────────────────────────────
function FacilityCard({ facility, onCheckAvailability }) {
  const cfg = TYPE_CONFIG[facility.type] ?? fallbackType;

  // Inline date/time picker state
  const today = todayLocalISO();
  const [showPicker, setShowPicker] = useState(false);
  const [date, setDate]             = useState(today);
  const [time, setTime]             = useState('09:00');

  const handleAskAgent = () => {
    onCheckAvailability(facility.name, date, time);
    setShowPicker(false);
  };

  return (
    <div className="bg-white rounded-2xl border border-slate-100 shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-200 flex flex-col overflow-hidden group">

      <div className="p-5 flex flex-col gap-3 flex-1">
        {/* Icon + name */}
        <div className="flex items-start gap-3">
          <div className={`w-10 h-10 rounded-xl ${cfg.bg} flex items-center justify-center flex-shrink-0`}>
            <svg className={`w-5 h-5 ${cfg.text}`} fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d={cfg.iconPath} />
            </svg>
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="text-base font-bold text-slate-800 leading-snug group-hover:text-violet-700 transition-colors truncate">
              {facility.name}
            </h3>
            <p className="text-xs text-slate-500 mt-0.5 flex items-center gap-1">
              <svg className="w-3 h-3 text-slate-400 flex-shrink-0" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path d="M12 22s-8-5.686-8-12a8 8 0 1 1 16 0c0 6.314-8 12-8 12z" />
                <circle cx="12" cy="10" r="3" />
              </svg>
              {facility.location}
            </p>
          </div>
        </div>

        {/* Type badge + capacity */}
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${cfg.bg} ${cfg.text}`}>
            {cfg.label}
          </span>
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-600">
            <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
              <circle cx="9" cy="7" r="4" />
              <path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" />
            </svg>
            Capacity {facility.capacity}
          </span>
        </div>

        {/* Equipment chips */}
        {facility.equipment && facility.equipment.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {facility.equipment.slice(0, 4).map((item) => (
              <span
                key={item}
                className="text-[11px] font-medium bg-slate-50 border border-slate-200 text-slate-600 px-2 py-0.5 rounded-md"
              >
                {item}
              </span>
            ))}
            {facility.equipment.length > 4 && (
              <span className="text-[11px] font-medium text-slate-400 px-1 py-0.5">
                +{facility.equipment.length - 4} more
              </span>
            )}
          </div>
        )}
      </div>

      {/* ── Button area ───────────────────────────────────────────────── */}
      <div className="px-5 pb-5">
        {!showPicker ? (
          /* Default state: single "Check Availability" button */
          <button
            id={`avail-btn-${facility.id}`}
            className="w-full bg-violet-600 hover:bg-violet-700 text-white text-sm font-semibold py-2.5 rounded-xl transition-colors duration-150 active:scale-95 shadow-sm"
            onClick={() => setShowPicker(true)}
          >
            Check Availability
          </button>
        ) : (
          /* Expanded state: inline date + time pickers → Ask Agent */
          <div className="bg-slate-50 border border-slate-200 rounded-xl p-3 flex flex-col gap-2">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
              Pick a date &amp; time
            </p>

            <div className="flex gap-2">
              {/* Date picker */}
              <div className="flex-1">
                <label className="text-[10px] text-slate-400 font-medium block mb-1">Date</label>
                <input
                  type="date"
                  value={date}
                  min={today}
                  onChange={(e) => setDate(e.target.value)}
                  className="w-full text-xs text-slate-700 bg-white border border-slate-200 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-violet-500/30 focus:border-violet-400 transition-colors"
                />
              </div>

              {/* Time picker */}
              <div className="flex-1">
                <label className="text-[10px] text-slate-400 font-medium block mb-1">Time</label>
                <input
                  type="time"
                  value={time}
                  onChange={(e) => setTime(e.target.value)}
                  className="w-full text-xs text-slate-700 bg-white border border-slate-200 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-violet-500/30 focus:border-violet-400 transition-colors"
                />
              </div>
            </div>

            <div className="flex gap-2 mt-1">
              <button
                onClick={handleAskAgent}
                className="flex-1 bg-violet-600 hover:bg-violet-700 text-white text-xs font-semibold py-2 rounded-lg transition-colors active:scale-95"
              >
                Ask Agent →
              </button>
              <button
                onClick={() => setShowPicker(false)}
                className="text-xs text-slate-500 hover:text-slate-700 px-3 py-2 rounded-lg hover:bg-slate-100 transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
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
        <p className="text-rose-700 font-semibold text-sm">Couldn't load facilities</p>
        <p className="text-rose-500 text-xs mt-1">Make sure the backend is reachable</p>
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
export default function FacilitiesGrid({ onCheckAvailability }) {
  const [facilities, setFacilities] = useState([]);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState(false);

  const fetchFacilities = useCallback(() => {
    setLoading(true);
    setError(false);
    getFacilities()
      .then((data) => {
        setFacilities(data);
        setLoading(false);
      })
      .catch(() => {
        setError(true);
        setLoading(false);
      });
  }, []);

  useEffect(() => { fetchFacilities(); }, [fetchFacilities]);

  return (
    <section id="facilities" className="py-10">
      {/* Section header */}
      <div className="mb-7 flex items-end justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-slate-800 tracking-tight">Campus Facilities</h2>
          <p className="text-slate-500 text-sm mt-1">
            {loading ? 'Loading facilities…' : error ? 'Could not load facilities' : `${facilities.length} bookable spaces`}
          </p>
        </div>
      </div>

      {/* Grid */}
      {error ? (
        <ErrorState onRetry={fetchFacilities} />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {loading
            ? Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)
            : facilities.map((facility) => (
                <FacilityCard
                  key={facility.id}
                  facility={facility}
                  onCheckAvailability={onCheckAvailability}
                />
              ))
          }
        </div>
      )}
    </section>
  );
}
