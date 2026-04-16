import { useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  LogOut,
  Key,
  Users,
  CreditCard,
  TrendingUp,
  Plus,
  Copy,
  Check,
  Search,
  Trash2,
  Eye,
  EyeOff,
  ArrowLeft,
} from 'lucide-react'
import Logo from '../components/Logo'
import AnimatedBackground from '../components/AnimatedBackground'

// --------------- HMAC KEY GENERATION ---------------
const SECRET = 'RossiSiteGuard_2024_PROD_SECRET_KEY_v1'

const planChars: Record<string, string> = {
  trial: 'T',
  starter: 'S',
  professional: 'P',
  business: 'B',
  enterprise: 'E',
}

function randomAlphaNum(len: number): string {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
  let result = ''
  const arr = new Uint8Array(len)
  crypto.getRandomValues(arr)
  for (let i = 0; i < len; i++) {
    result += chars[arr[i] % chars.length]
  }
  return result
}

async function computeHMAC(body: string): Promise<string> {
  const enc = new TextEncoder()
  const keyData = enc.encode(SECRET)
  const key = await crypto.subtle.importKey(
    'raw',
    keyData,
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign']
  )
  const sig = await crypto.subtle.sign('HMAC', key, enc.encode(body))
  const hex = Array.from(new Uint8Array(sig))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('')
  return hex.slice(0, 5).toUpperCase()
}

async function generateKey(plan: string): Promise<string> {
  const pc = planChars[plan] || 'T'
  const g1 = pc + randomAlphaNum(4)
  const g2 = randomAlphaNum(5)
  const g3 = randomAlphaNum(5)
  const g4 = randomAlphaNum(5)
  const body = `SG-${g1}-${g2}-${g3}-${g4}`
  const checksum = await computeHMAC(body)
  return `${body}-${checksum}`
}

// --------------- TYPES ---------------
interface License {
  id: string
  key: string
  plan: string
  org: string
  status: 'active' | 'expired' | 'revoked'
  created: string
  expires: string
}

// --------------- DEMO DATA ---------------
const demoLicenses: License[] = [
  {
    id: '1',
    key: 'SG-P7KMN-XRQWT-9H3PL-BVZD5-A3F21',
    plan: 'Professional',
    org: 'ООО "Технодом"',
    status: 'active',
    created: '2025-01-15',
    expires: '2026-01-15',
  },
  {
    id: '2',
    key: 'SG-BQWER-PLMKJ-7HNBT-RVXZ3-D8E4C',
    plan: 'Business',
    org: 'АО "СибИнфоТех"',
    status: 'active',
    created: '2025-02-20',
    expires: '2026-02-20',
  },
  {
    id: '3',
    key: 'SG-S3RTY-WQASD-ZXCVB-NM098-F7B2A',
    plan: 'Starter',
    org: 'ИП Иванов',
    status: 'active',
    created: '2025-03-10',
    expires: '2025-09-10',
  },
  {
    id: '4',
    key: 'SG-T5YUI-DFGHJ-KLMNB-VCXZQ-E1C9D',
    plan: 'Trial',
    org: 'Тест',
    status: 'expired',
    created: '2025-01-01',
    expires: '2025-01-15',
  },
  {
    id: '5',
    key: 'SG-E9OPQ-RSTUW-XYZAB-CDEFG-B4A7F',
    plan: 'Enterprise',
    org: 'ПАО "Газпромбанк"',
    status: 'active',
    created: '2024-12-01',
    expires: '2025-12-01',
  },
]

// --------------- AUTH CONSTANTS ---------------
const ADMIN_LOGIN = 'admin'
const ADMIN_PASSWORD = 'SiteGuard2024Admin!'

// --------------- LOGIN SCREEN ---------------
function LoginScreen({ onLogin }: { onLogin: () => void }) {
  const [login, setLogin] = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (login === ADMIN_LOGIN && password === ADMIN_PASSWORD) {
      setError('')
      onLogin()
    } else if (!login || !password) {
      setError('Введите логин и пароль')
    } else {
      setError('Неверный логин или пароль')
    }
  }

  return (
    <div className="relative min-h-screen flex items-center justify-center bg-sg-bg">
      <AnimatedBackground />
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className="relative z-10 glass-card p-8 sm:p-10 w-full max-w-md mx-4"
      >
        <div className="flex justify-center mb-8">
          <Logo />
        </div>
        <h1 className="font-display font-bold text-2xl text-sg-text text-center mb-2">
          Вход в панель
        </h1>
        <p className="text-sm text-sg-muted text-center mb-8">
          Администрирование лицензий SiteGuard
        </p>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <label className="text-xs text-sg-muted font-mono mb-1.5 block">Логин</label>
            <input
              type="text"
              value={login}
              onChange={(e) => setLogin(e.target.value)}
              placeholder="admin"
              autoComplete="username"
              className="w-full bg-sg-surface border border-sg-border rounded-xl px-4 py-3 text-sm text-sg-text placeholder:text-sg-muted/50 focus:outline-none focus:border-sg-blue/40 transition-colors font-body"
              data-testid="input-login"
            />
          </div>
          <div>
            <label className="text-xs text-sg-muted font-mono mb-1.5 block">Пароль</label>
            <div className="relative">
              <input
                type={showPw ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full bg-sg-surface border border-sg-border rounded-xl px-4 py-3 text-sm text-sg-text placeholder:text-sg-muted/50 focus:outline-none focus:border-sg-blue/40 transition-colors font-body pr-10"
                data-testid="input-password"
              />
              <button
                type="button"
                onClick={() => setShowPw(!showPw)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-sg-muted hover:text-sg-text transition-colors bg-transparent border-none cursor-pointer"
              >
                {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          {error && <p className="text-red-400 text-xs">{error}</p>}

          <button
            type="submit"
            className="glow-btn w-full mt-2 text-sm cursor-pointer"
            data-testid="button-login"
          >
            Войти
          </button>
        </form>

        <p className="text-xs text-sg-muted text-center mt-6">
          Доступ только для администратора
        </p>
      </motion.div>
    </div>
  )
}

// --------------- STAT CARD ---------------
function StatCard({
  icon: Icon,
  label,
  value,
  trend,
}: {
  icon: any
  label: string
  value: string
  trend?: string
}) {
  return (
    <div className="glass-card p-5 sm:p-6">
      <div className="flex items-center justify-between mb-3">
        <div className="w-9 h-9 rounded-xl bg-sg-blue/10 flex items-center justify-center">
          <Icon size={18} className="text-sg-blue" />
        </div>
        {trend && (
          <span className="text-xs font-mono text-green-400 flex items-center gap-1">
            <TrendingUp size={12} />
            {trend}
          </span>
        )}
      </div>
      <div className="font-display font-bold text-2xl text-sg-text">{value}</div>
      <div className="text-xs text-sg-muted mt-1">{label}</div>
    </div>
  )
}

// --------------- DASHBOARD ---------------
function Dashboard({ onLogout }: { onLogout: () => void }) {
  const [licenses, setLicenses] = useState<License[]>(demoLicenses)
  const [searchQuery, setSearchQuery] = useState('')
  const [showGenerator, setShowGenerator] = useState(false)
  const [genPlan, setGenPlan] = useState('trial')
  const [genOrg, setGenOrg] = useState('')
  const [genExpiry, setGenExpiry] = useState('2026-12-31')
  const [generatedKey, setGeneratedKey] = useState('')
  const [copied, setCopied] = useState(false)
  const [generating, setGenerating] = useState(false)

  const filteredLicenses = licenses.filter(
    (l) =>
      l.key.toLowerCase().includes(searchQuery.toLowerCase()) ||
      l.org.toLowerCase().includes(searchQuery.toLowerCase()) ||
      l.plan.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const activeCount = licenses.filter((l) => l.status === 'active').length

  const handleGenerate = useCallback(async () => {
    setGenerating(true)
    try {
      const key = await generateKey(genPlan)
      setGeneratedKey(key)

      // Add to table
      const newLicense: License = {
        id: String(Date.now()),
        key,
        plan: genPlan.charAt(0).toUpperCase() + genPlan.slice(1),
        org: genOrg || 'Не указана',
        status: 'active',
        created: new Date().toISOString().split('T')[0],
        expires: genExpiry,
      }
      setLicenses((prev) => [newLicense, ...prev])
    } finally {
      setGenerating(false)
    }
  }, [genPlan, genOrg, genExpiry])

  const copyKey = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(generatedKey)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // fallback
      const ta = document.createElement('textarea')
      ta.value = generatedKey
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }, [generatedKey])

  const removeLicense = (id: string) => {
    setLicenses((prev) => prev.filter((l) => l.id !== id))
  }

  const statusColors: Record<string, string> = {
    active: 'text-green-400 bg-green-400/10',
    expired: 'text-yellow-400 bg-yellow-400/10',
    revoked: 'text-red-400 bg-red-400/10',
  }

  const statusLabels: Record<string, string> = {
    active: 'Активна',
    expired: 'Истекла',
    revoked: 'Отозвана',
  }

  return (
    <div className="relative min-h-screen bg-sg-bg">
      <AnimatedBackground />

      {/* Admin nav */}
      <nav className="glass sticky top-0 z-50">
        <div className="section-container flex items-center justify-between h-[64px]">
          <div className="flex items-center gap-4">
            <a
              href="#/"
              className="text-sg-muted hover:text-sg-text transition-colors no-underline"
            >
              <ArrowLeft size={18} />
            </a>
            <Logo />
            <span className="hidden sm:inline-flex items-center gap-2 ml-4 px-3 py-1 rounded-full bg-sg-blue/10 text-sg-blue text-xs font-mono">
              Админ панель
            </span>
          </div>
          <button
            onClick={onLogout}
            className="flex items-center gap-2 text-sm text-sg-muted hover:text-sg-text transition-colors bg-transparent border-none cursor-pointer"
            data-testid="button-logout"
          >
            <LogOut size={16} />
            <span className="hidden sm:inline">Выйти</span>
          </button>
        </div>
      </nav>

      <div className="relative z-10 section-container py-8">
        {/* Stats row */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <StatCard icon={Key} label="Всего лицензий" value={String(licenses.length)} trend="+12%" />
          <StatCard icon={Users} label="Активных" value={String(activeCount)} trend="+8%" />
          <StatCard icon={CreditCard} label="Выручка" value="354 000 ₽" trend="+23%" />
          <StatCard icon={TrendingUp} label="Новых за месяц" value="18" />
        </div>

        {/* Key generator */}
        <div className="glass-card p-6 sm:p-8 mb-8">
          <div className="flex items-center justify-between mb-6">
            <h2 className="font-display font-semibold text-lg text-sg-text flex items-center gap-2">
              <Plus size={18} className="text-sg-blue" />
              Генерация ключей
            </h2>
            <button
              onClick={() => setShowGenerator(!showGenerator)}
              className="text-xs font-mono text-sg-blue bg-transparent border-none cursor-pointer hover:underline"
            >
              {showGenerator ? 'Скрыть' : 'Показать'}
            </button>
          </div>

          <AnimatePresence>
            {showGenerator && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.3 }}
                className="overflow-hidden"
              >
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4">
                  <div>
                    <label className="text-xs text-sg-muted font-mono mb-1.5 block">Тариф</label>
                    <select
                      value={genPlan}
                      onChange={(e) => setGenPlan(e.target.value)}
                      className="w-full bg-sg-surface border border-sg-border rounded-xl px-4 py-3 text-sm text-sg-text focus:outline-none focus:border-sg-blue/40 transition-colors font-body appearance-none cursor-pointer"
                      data-testid="select-plan"
                    >
                      <option value="trial">Trial</option>
                      <option value="starter">Starter</option>
                      <option value="professional">Professional</option>
                      <option value="business">Business</option>
                      <option value="enterprise">Enterprise</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-sg-muted font-mono mb-1.5 block">Организация</label>
                    <input
                      type="text"
                      value={genOrg}
                      onChange={(e) => setGenOrg(e.target.value)}
                      placeholder='ООО "Компания"'
                      className="w-full bg-sg-surface border border-sg-border rounded-xl px-4 py-3 text-sm text-sg-text placeholder:text-sg-muted/50 focus:outline-none focus:border-sg-blue/40 transition-colors font-body"
                      data-testid="input-org"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-sg-muted font-mono mb-1.5 block">Истекает</label>
                    <input
                      type="date"
                      value={genExpiry}
                      onChange={(e) => setGenExpiry(e.target.value)}
                      className="w-full bg-sg-surface border border-sg-border rounded-xl px-4 py-3 text-sm text-sg-text focus:outline-none focus:border-sg-blue/40 transition-colors font-body"
                      data-testid="input-expiry"
                    />
                  </div>
                </div>

                <button
                  onClick={handleGenerate}
                  disabled={generating}
                  className="glow-btn text-sm inline-flex items-center gap-2 cursor-pointer disabled:opacity-50"
                  data-testid="button-generate"
                >
                  <Key size={16} />
                  {generating ? 'Генерация...' : 'Создать ключ'}
                </button>

                {generatedKey && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="mt-4 p-4 bg-sg-surface rounded-xl border border-sg-blue/20"
                  >
                    <div className="flex items-center justify-between gap-4">
                      <code className="font-mono text-sm text-sg-blue break-all" data-testid="text-generated-key">
                        {generatedKey}
                      </code>
                      <button
                        onClick={copyKey}
                        className="flex-shrink-0 text-sg-muted hover:text-sg-text transition-colors bg-transparent border-none cursor-pointer"
                        data-testid="button-copy-key"
                      >
                        {copied ? <Check size={16} className="text-green-400" /> : <Copy size={16} />}
                      </button>
                    </div>
                  </motion.div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* License table */}
        <div className="glass-card p-6 sm:p-8">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6">
            <h2 className="font-display font-semibold text-lg text-sg-text">
              Лицензии
            </h2>
            <div className="relative w-full sm:w-64">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-sg-muted" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Поиск..."
                className="w-full bg-sg-surface border border-sg-border rounded-xl pl-9 pr-4 py-2.5 text-sm text-sg-text placeholder:text-sg-muted/50 focus:outline-none focus:border-sg-blue/40 transition-colors font-body"
                data-testid="input-search"
              />
            </div>
          </div>

          {/* Desktop table */}
          <div className="hidden md:block overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-sg-border">
                  <th className="text-xs font-mono text-sg-muted pb-3 pr-4">Ключ</th>
                  <th className="text-xs font-mono text-sg-muted pb-3 pr-4">Тариф</th>
                  <th className="text-xs font-mono text-sg-muted pb-3 pr-4">Организация</th>
                  <th className="text-xs font-mono text-sg-muted pb-3 pr-4">Статус</th>
                  <th className="text-xs font-mono text-sg-muted pb-3 pr-4">Создан</th>
                  <th className="text-xs font-mono text-sg-muted pb-3 pr-4">Истекает</th>
                  <th className="text-xs font-mono text-sg-muted pb-3">Действия</th>
                </tr>
              </thead>
              <tbody>
                {filteredLicenses.map((lic) => (
                  <tr
                    key={lic.id}
                    className="border-b border-sg-border/50 hover:bg-sg-surface/50 transition-colors"
                    data-testid={`row-license-${lic.id}`}
                  >
                    <td className="py-3 pr-4">
                      <code className="text-xs font-mono text-sg-text">{lic.key}</code>
                    </td>
                    <td className="py-3 pr-4 text-sm text-sg-text">{lic.plan}</td>
                    <td className="py-3 pr-4 text-sm text-sg-muted">{lic.org}</td>
                    <td className="py-3 pr-4">
                      <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-mono ${statusColors[lic.status]}`}>
                        {statusLabels[lic.status]}
                      </span>
                    </td>
                    <td className="py-3 pr-4 text-xs font-mono text-sg-muted">{lic.created}</td>
                    <td className="py-3 pr-4 text-xs font-mono text-sg-muted">{lic.expires}</td>
                    <td className="py-3">
                      <button
                        onClick={() => removeLicense(lic.id)}
                        className="text-sg-muted hover:text-red-400 transition-colors bg-transparent border-none cursor-pointer p-1"
                        aria-label="Удалить"
                        data-testid={`button-delete-${lic.id}`}
                      >
                        <Trash2 size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobile cards */}
          <div className="md:hidden flex flex-col gap-3">
            {filteredLicenses.map((lic) => (
              <div key={lic.id} className="bg-sg-surface rounded-xl p-4 border border-sg-border/50">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-semibold text-sg-text">{lic.plan}</span>
                  <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-mono ${statusColors[lic.status]}`}>
                    {statusLabels[lic.status]}
                  </span>
                </div>
                <code className="text-xs font-mono text-sg-blue block mb-2 break-all">{lic.key}</code>
                <div className="text-xs text-sg-muted">{lic.org}</div>
                <div className="flex items-center justify-between mt-2">
                  <span className="text-xs font-mono text-sg-muted">{lic.created} → {lic.expires}</span>
                  <button
                    onClick={() => removeLicense(lic.id)}
                    className="text-sg-muted hover:text-red-400 transition-colors bg-transparent border-none cursor-pointer p-1"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            ))}
          </div>

          {filteredLicenses.length === 0 && (
            <p className="text-center text-sm text-sg-muted py-12">
              Лицензии не найдены
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

// --------------- MAIN COMPONENT ---------------
export default function AdminPanel() {
  const [loggedIn, setLoggedIn] = useState(false)

  if (!loggedIn) {
    return <LoginScreen onLogin={() => setLoggedIn(true)} />
  }

  return <Dashboard onLogout={() => setLoggedIn(false)} />
}
