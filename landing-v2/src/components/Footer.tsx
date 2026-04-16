import Logo from './Logo'
import { GitBranch, FileText, HeadphonesIcon, Settings } from 'lucide-react'

const links = [
  {
    icon: GitBranch,
    label: 'GitHub',
    href: 'https://github.com/Teketkom3026/rossi-siteguard-monitor/releases',
  },
  {
    icon: FileText,
    label: 'Документация',
    href: 'https://github.com/Teketkom3026/rossi-siteguard-monitor',
  },
  {
    icon: HeadphonesIcon,
    label: 'Поддержка',
    href: 'mailto:support@rossi-siteguard.ru',
  },
  {
    icon: Settings,
    label: 'Админ панель',
    href: 'http://87.228.29.55/admin',
  },
]

export default function Footer() {
  return (
    <footer className="relative z-10 border-t border-sg-border">
      <div className="section-container py-12 sm:py-16">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-8">
          <div>
            <Logo />
            <p className="text-sm text-sg-muted mt-3 max-w-xs">
              Профессиональный мониторинг и защита веб-сайтов для бизнеса
            </p>
          </div>

          <div className="flex flex-wrap gap-6">
            {links.map((link, i) => {
              const Icon = link.icon
              return (
                <a
                  key={i}
                  href={link.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 text-sm text-sg-muted hover:text-sg-text transition-colors no-underline"
                >
                  <Icon size={16} />
                  {link.label}
                </a>
              )
            })}
          </div>
        </div>

        <div className="border-t border-sg-border mt-8 pt-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <p className="text-xs text-sg-muted">
            &copy; 2026 Rossi SiteGuard Monitor. Все права защищены.
          </p>
          <a
            href="#/admin-panel"
            className="text-xs text-sg-muted hover:text-sg-blue transition-colors no-underline"
          >
            Панель администратора (UI Demo)
          </a>
        </div>
      </div>
    </footer>
  )
}
