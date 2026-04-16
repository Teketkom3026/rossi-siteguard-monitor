import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Menu, X } from 'lucide-react'
import Logo from './Logo'

const navLinks = [
  { label: 'О продукте', href: '#about' },
  { label: 'Возможности', href: '#features' },
  { label: 'Тарифы', href: '#pricing' },
  { label: 'Документация', href: 'https://github.com/Teketkom3026/rossi-siteguard-monitor' },
  { label: 'Войти', href: 'http://87.228.29.55/admin' },
]

export default function Nav() {
  const [scrolled, setScrolled] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 40)
    window.addEventListener('scroll', handleScroll, { passive: true })
    return () => window.removeEventListener('scroll', handleScroll)
  }, [])

  const scrollTo = (href: string) => {
    setMobileOpen(false)
    if (href.startsWith('#')) {
      const el = document.getElementById(href.slice(1))
      if (el) el.scrollIntoView({ behavior: 'smooth' })
    } else {
      window.open(href, '_blank', 'noopener')
    }
  }

  return (
    <>
      <motion.nav
        initial={{ y: -80 }}
        animate={{ y: 0 }}
        transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
        className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
          scrolled
            ? 'glass shadow-lg shadow-black/20'
            : 'bg-transparent'
        }`}
      >
        <div className="section-container flex items-center justify-between h-[72px]">
          <Logo />

          {/* Desktop links */}
          <div className="hidden lg:flex items-center gap-8">
            {navLinks.map((link) => (
              <button
                key={link.label}
                onClick={() => scrollTo(link.href)}
                className="text-sm font-body text-sg-muted hover:text-sg-text transition-colors duration-200 cursor-pointer bg-transparent border-none"
              >
                {link.label}
              </button>
            ))}
          </div>

          <div className="hidden lg:flex items-center gap-3">
            <a
              href="http://87.228.29.55/SiteGuard_Monitor_Pro.exe"
              className="glow-btn text-sm !py-2.5 !px-6 inline-flex items-center gap-2 no-underline"
            >
              Скачать
            </a>
          </div>

          {/* Mobile burger */}
          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            className="lg:hidden text-sg-text bg-transparent border-none cursor-pointer p-2"
            aria-label="Меню"
          >
            {mobileOpen ? <X size={24} /> : <Menu size={24} />}
          </button>
        </div>
      </motion.nav>

      {/* Mobile menu */}
      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ duration: 0.3 }}
            className="fixed inset-0 top-[72px] z-40 glass"
            style={{ background: 'rgba(4, 6, 16, 0.95)' }}
          >
            <div className="flex flex-col items-center gap-6 pt-12">
              {navLinks.map((link) => (
                <button
                  key={link.label}
                  onClick={() => scrollTo(link.href)}
                  className="text-lg font-body text-sg-text hover:text-sg-blue transition-colors bg-transparent border-none cursor-pointer"
                >
                  {link.label}
                </button>
              ))}
              <a
                href="http://87.228.29.55/SiteGuard_Monitor_Pro.exe"
                className="glow-btn mt-4 no-underline"
              >
                Скачать
              </a>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
