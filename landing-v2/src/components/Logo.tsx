export default function Logo({ className = '' }: { className?: string }) {
  return (
    <div className={`flex items-center gap-3 ${className}`}>
      <svg
        viewBox="0 0 40 40"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="w-9 h-9"
        aria-label="Rossi SiteGuard Monitor"
      >
        {/* Shield shape */}
        <path
          d="M20 3L6 10v10c0 9 5.6 17.4 14 20 8.4-2.6 14-11 14-20V10L20 3z"
          fill="url(#shield-gradient)"
          opacity="0.15"
        />
        <path
          d="M20 3L6 10v10c0 9 5.6 17.4 14 20 8.4-2.6 14-11 14-20V10L20 3z"
          stroke="url(#shield-stroke)"
          strokeWidth="1.5"
          fill="none"
        />
        {/* Inner pulse circles */}
        <circle cx="20" cy="18" r="6" stroke="#60a5fa" strokeWidth="1" opacity="0.4" />
        <circle cx="20" cy="18" r="3" fill="#3b82f6" opacity="0.6" />
        <circle cx="20" cy="18" r="1.5" fill="#60a5fa" />
        {/* Signal waves */}
        <path d="M13 12a10 10 0 0 1 14 0" stroke="#60a5fa" strokeWidth="1" opacity="0.3" fill="none" />
        <path d="M15 14a7 7 0 0 1 10 0" stroke="#60a5fa" strokeWidth="1" opacity="0.5" fill="none" />
        <defs>
          <linearGradient id="shield-gradient" x1="6" y1="3" x2="34" y2="33">
            <stop offset="0%" stopColor="#3b82f6" />
            <stop offset="100%" stopColor="#8b5cf6" />
          </linearGradient>
          <linearGradient id="shield-stroke" x1="6" y1="3" x2="34" y2="33">
            <stop offset="0%" stopColor="#60a5fa" />
            <stop offset="100%" stopColor="#8b5cf6" />
          </linearGradient>
        </defs>
      </svg>
      <div className="flex flex-col leading-none">
        <span className="font-display font-bold text-[17px] tracking-wide text-sg-text">ROSSI</span>
        <span className="font-mono text-[9px] tracking-[0.2em] text-sg-muted uppercase">SiteGuard Monitor</span>
      </div>
    </div>
  )
}
