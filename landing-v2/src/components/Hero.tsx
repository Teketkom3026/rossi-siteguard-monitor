import { motion } from 'framer-motion'
import { Download, Play, ChevronDown } from 'lucide-react'

const stats = [
  { value: '99.9%', label: 'Uptime' },
  { value: '< 30 сек', label: 'Реакция' },
  { value: '247', label: 'Угроз заблокировано' },
]

export default function Hero() {
  return (
    <section className="relative min-h-screen flex flex-col items-center justify-center overflow-hidden" id="hero">
      <div className="section-container relative z-10 text-center pt-24 pb-16">
        {/* Version badge */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3, duration: 0.6 }}
          className="inline-flex items-center gap-2 glass-card !rounded-full px-5 py-2 mb-8"
        >
          <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
          <span className="text-xs font-mono text-sg-muted">v1.0.9 — Мониторинг активен</span>
        </motion.div>

        {/* Main headline */}
        <motion.h1
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5, duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
          className="font-display font-bold text-5xl sm:text-7xl md:text-8xl lg:text-[112px] leading-[0.9] tracking-tight mb-6"
        >
          <span className="text-gradient block">ЗАЩИТА САЙТОВ</span>
          <span className="text-gradient-blue block mt-2">НОВОГО УРОВНЯ</span>
        </motion.h1>

        {/* Subtitle */}
        <motion.p
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.7, duration: 0.7 }}
          className="font-body text-base sm:text-lg text-sg-muted max-w-[600px] mx-auto mb-10 leading-relaxed"
        >
          Профессиональный мониторинг, обнаружение угроз и защита вашего сайта в реальном времени
        </motion.p>

        {/* CTAs */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.9, duration: 0.7 }}
          className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-16"
        >
          <a
            href="http://87.228.29.55/SiteGuard_Monitor_Pro.exe"
            className="glow-btn inline-flex items-center gap-2 text-base no-underline"
            data-testid="download-windows-hero"
          >
            <Download size={18} />
            Скачать для Windows
          </a>
          <button
            onClick={() => {
              const el = document.getElementById('features')
              if (el) el.scrollIntoView({ behavior: 'smooth' })
            }}
            className="outline-btn inline-flex items-center gap-2 text-base cursor-pointer"
            data-testid="demo-btn"
          >
            <Play size={16} />
            Смотреть демо
          </button>
        </motion.div>

        {/* Stats row */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 1.1, duration: 0.7 }}
          className="flex items-center justify-center gap-8 sm:gap-16"
        >
          {stats.map((stat, i) => (
            <div key={i} className="text-center">
              <div className="font-display font-bold text-2xl sm:text-3xl text-sg-text">{stat.value}</div>
              <div className="text-xs font-mono text-sg-muted mt-1 uppercase tracking-wider">{stat.label}</div>
            </div>
          ))}
        </motion.div>
      </div>

      {/* Scroll indicator */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1.5, duration: 0.5 }}
        className="absolute bottom-8 left-1/2 -translate-x-1/2 z-10"
      >
        <button
          onClick={() => {
            const el = document.getElementById('about')
            if (el) el.scrollIntoView({ behavior: 'smooth' })
          }}
          className="text-sg-muted hover:text-sg-blue transition-colors bg-transparent border-none cursor-pointer animate-scroll-hint"
          aria-label="Прокрутить вниз"
        >
          <ChevronDown size={28} />
        </button>
      </motion.div>
    </section>
  )
}
