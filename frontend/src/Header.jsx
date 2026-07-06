export default function Header() {
  return (
    <header className="sticky top-0 z-40 bg-slate-900 border-b border-slate-700/60 shadow-lg">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16 min-w-0">

          {/* Logo + site name — truncates gracefully on xs */}
          <div className="flex items-center gap-3 min-w-0">
            {/* Shield / crest SVG mark */}
            <div className="flex-shrink-0 w-9 h-9 bg-indigo-600 rounded-lg flex items-center justify-center shadow-md">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="none"
                stroke="white"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="w-5 h-5"
              >
                <path d="M12 2L2 7l10 5 10-5-10-5z" />
                <path d="M2 17l10 5 10-5" />
                <path d="M2 12l10 5 10-5" />
              </svg>
            </div>
            <div className="min-w-0">
              <span className="text-white font-bold text-base sm:text-lg leading-tight tracking-tight truncate block">
                HBTU Campus Portal
              </span>
              <p className="text-slate-400 text-[10px] leading-none tracking-wide hidden sm:block">
                Harcourt Butler Technical University
              </p>
            </div>
          </div>

          {/* Nav links:
              - Hidden entirely on xs (< 640 px) to prevent overflow
              - Visible from sm (640 px) upward
              Links are static placeholders — no routing wired */}
          <nav className="hidden sm:flex items-center gap-0.5 flex-shrink-0">
            {["Home", "Events", "Facilities", "Contact"].map((link) => (
              <a
                key={link}
                href="#"
                onClick={(e) => e.preventDefault()}
                className="
                  text-slate-300 hover:text-white hover:bg-slate-700/70
                  px-3 py-2 rounded-lg text-sm font-medium
                  transition-colors duration-150 whitespace-nowrap
                "
              >
                {link}
              </a>
            ))}
          </nav>

          {/* xs-only: show three-bar icon as visual affordance (non-functional) */}
          <div className="sm:hidden flex-shrink-0 ml-3">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="w-6 h-6 text-slate-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
              strokeLinecap="round"
            >
              <line x1="3" y1="6"  x2="21" y2="6"  />
              <line x1="3" y1="12" x2="21" y2="12" />
              <line x1="3" y1="18" x2="21" y2="18" />
            </svg>
          </div>

        </div>
      </div>
    </header>
  );
}
