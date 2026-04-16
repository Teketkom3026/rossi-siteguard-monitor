import { motion } from 'framer-motion'
import {
  Activity,
  Lock,
  Shield,
  Bell,
  BarChart3,
  Globe,
  Key,
  Smartphone,
} from 'lucide-react'

const features = [
  {
    icon: Activity,
    title: 'Мониторинг 24/7',
    desc: 'Непрерывный контроль доступности сайтов каждые 30 секунд',
    span: 'md:col-span-2',
  },
  {
    icon: Lock,
    title: 'SSL Мониторинг',
    desc: 'Автоматическое отслеживание SSL-сертификатов и уведомления об истечении',
    span: '',
  },
  {
    icon: Shield,
    title: 'Сканирование угроз',
    desc: 'Обнаружение вредоносного кода, SQL-инъекций и XSS-атак',
    span: '',
  },
  {
    icon: Bell,
    title: 'Мгновенные уведомления',
    desc: 'Email, Telegram и webhook-оповещения при обнаружении проблем',
    span: 'md:col-span-2',
  },
  {
    icon: BarChart3,
    title: 'Детальная аналитика',
    desc: 'Графики uptime, времени ответа и статистика угроз',
    span: '',
  },
  {
    icon: Globe,
    title: 'Управление доменами',
    desc: 'Мониторинг до 999 доменов одновременно в Enterprise-тарифе',
    span: '',
  },
  {
    icon: Key,
    title: 'Офлайн активация',
    desc: 'Лицензия активируется без интернета по HMAC-ключу',
    span: '',
  },
  {
    icon: Smartphone,
    title: 'Мобильное приложение',
    desc: 'Android-приложение для мониторинга на ходу',
    span: '',
  },
]

const containerVariants = {
  hidden: {},
  visible: {
    transition: {
      staggerChildren: 0.08,
    },
  },
}

const itemVariants = {
  hidden: { opacity: 0, y: 30 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.6, ease: [0.22, 1, 0.36, 1] as [number, number, number, number] },
  },
}

export default function Features() {
  return (
    <section className="relative z-10 py-24 sm:py-32" id="features">
      <div className="section-container">
        {/* Section header */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-100px' }}
          transition={{ duration: 0.7 }}
          className="text-center mb-16"
        >
          <span className="font-mono text-xs text-sg-blue tracking-[0.2em] uppercase block mb-4">
            Возможности
          </span>
          <h2 className="font-display font-bold text-3xl sm:text-4xl md:text-5xl text-sg-text tracking-tight">
            ВСЁ ЧТО НУЖНО<br />
            <span className="text-gradient-blue">ДЛЯ ЗАЩИТЫ</span>
          </h2>
        </motion.div>

        {/* Bento grid */}
        <motion.div
          variants={containerVariants}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-50px' }}
          className="grid grid-cols-1 md:grid-cols-4 gap-4"
        >
          {features.map((feat, i) => {
            const Icon = feat.icon
            return (
              <motion.div
                key={i}
                variants={itemVariants}
                className={`glass-card p-6 sm:p-8 group ${feat.span}`}
                data-testid={`feature-card-${i}`}
              >
                <div className="w-10 h-10 rounded-xl bg-sg-blue/10 flex items-center justify-center mb-5 group-hover:bg-sg-blue/20 transition-colors">
                  <Icon size={20} className="text-sg-blue" />
                </div>
                <h3 className="font-display font-semibold text-lg text-sg-text mb-2">
                  {feat.title}
                </h3>
                <p className="font-body text-sm text-sg-muted leading-relaxed">
                  {feat.desc}
                </p>
              </motion.div>
            )
          })}
        </motion.div>
      </div>
    </section>
  )
}
