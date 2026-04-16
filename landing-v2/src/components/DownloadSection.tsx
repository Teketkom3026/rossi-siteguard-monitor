import { motion } from 'framer-motion'
import { Download, Smartphone, Monitor } from 'lucide-react'

export default function DownloadSection() {
  return (
    <section className="relative z-10 py-24 sm:py-32" id="download">
      <div className="section-container">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-100px' }}
          transition={{ duration: 0.7 }}
          className="text-center max-w-2xl mx-auto"
        >
          <h2 className="font-display font-bold text-3xl sm:text-4xl md:text-5xl text-sg-text tracking-tight mb-4">
            ГОТОВЫ<br />
            <span className="text-gradient-blue">НАЧАТЬ?</span>
          </h2>
          <p className="font-body text-base text-sg-muted mb-8">
            Скачайте SiteGuard Monitor Pro прямо сейчас
          </p>

          {/* Version badge */}
          <div className="inline-flex items-center gap-2 glass-card !rounded-full px-4 py-1.5 mb-10">
            <span className="w-1.5 h-1.5 rounded-full bg-sg-blue" />
            <span className="text-xs font-mono text-sg-muted">v1.0.9 — Последний релиз</span>
          </div>

          {/* Download buttons */}
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-8">
            <a
              href="http://87.228.29.55/SiteGuard_Monitor_Pro.exe"
              className="glow-btn inline-flex items-center gap-3 text-base no-underline !px-8 !py-4"
              data-testid="download-windows-main"
            >
              <Download size={20} />
              <div className="text-left">
                <div className="font-semibold">Скачать для Windows</div>
                <div className="text-xs opacity-70">43 MB — Установщик</div>
              </div>
            </a>

            <a
              href="https://github.com/Teketkom3026/rossi-siteguard-monitor/releases/tag/v1.0.9"
              target="_blank"
              rel="noopener noreferrer"
              className="outline-btn inline-flex items-center gap-3 text-base no-underline"
              data-testid="download-android"
            >
              <Smartphone size={20} />
              <div className="text-left">
                <div className="font-medium">Android APK</div>
                <div className="text-xs text-sg-muted">GitHub Releases</div>
              </div>
            </a>
          </div>

          {/* System requirements */}
          <div className="glass-card !rounded-xl p-6 max-w-md mx-auto">
            <div className="flex items-center gap-2 mb-3">
              <Monitor size={16} className="text-sg-blue" />
              <span className="font-display font-semibold text-sm text-sg-text">
                Системные требования
              </span>
            </div>
            <ul className="text-sm text-sg-muted space-y-1 text-left">
              <li>• Windows 10 / 11 (64-bit)</li>
              <li>• 4 GB RAM минимум</li>
              <li>• 100 MB свободного места</li>
              <li>• Подключение к интернету (для мониторинга)</li>
            </ul>
          </div>
        </motion.div>
      </div>
    </section>
  )
}
