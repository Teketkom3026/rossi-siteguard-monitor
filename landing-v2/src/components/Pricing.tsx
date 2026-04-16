import { motion } from 'framer-motion'
import { Check, Star } from 'lucide-react'

const plans = [
  {
    name: 'Trial',
    price: 'Бесплатно',
    period: '14 дней',
    sites: '3 сайта',
    features: [
      'Мониторинг доступности',
      'Проверка каждые 60 сек',
      'Email-уведомления',
    ],
    cta: 'Начать',
    popular: false,
    href: 'http://87.228.29.55/SiteGuard_Monitor_Pro.exe',
  },
  {
    name: 'Starter',
    price: '990 ₽',
    period: '/мес',
    sites: '10 сайтов',
    features: [
      'Мониторинг доступности',
      'SSL мониторинг',
      'Telegram-уведомления',
      'Проверка каждые 30 сек',
    ],
    cta: 'Начать',
    popular: false,
    href: 'http://87.228.29.55/SiteGuard_Monitor_Pro.exe',
  },
  {
    name: 'Professional',
    price: '2 490 ₽',
    period: '/мес',
    sites: '25 сайтов',
    features: [
      'Всё из Starter',
      'Сканирование угроз',
      'Детальная аналитика',
      'Webhook-оповещения',
      'Приоритетная поддержка',
    ],
    cta: 'Начать',
    popular: true,
    href: 'http://87.228.29.55/SiteGuard_Monitor_Pro.exe',
  },
  {
    name: 'Business',
    price: '5 990 ₽',
    period: '/мес',
    sites: '100 сайтов',
    features: [
      'Всё из Professional',
      'Сканирование malware',
      'API доступ',
      'Мобильное приложение',
      'Мультипользователи',
      'SLA 99.99%',
    ],
    cta: 'Связаться',
    popular: false,
    href: 'mailto:support@rossi-siteguard.ru',
  },
]

const containerVariants = {
  hidden: {},
  visible: {
    transition: { staggerChildren: 0.1 },
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

export default function Pricing() {
  return (
    <section className="relative z-10 py-24 sm:py-32" id="pricing">
      <div className="section-container">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-100px' }}
          transition={{ duration: 0.7 }}
          className="text-center mb-16"
        >
          <span className="font-mono text-xs text-sg-blue tracking-[0.2em] uppercase block mb-4">
            Тарифы
          </span>
          <h2 className="font-display font-bold text-3xl sm:text-4xl md:text-5xl text-sg-text tracking-tight">
            ТАРИФНЫЕ<br />
            <span className="text-gradient-blue">ПЛАНЫ</span>
          </h2>
        </motion.div>

        <motion.div
          variants={containerVariants}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-50px' }}
          className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4"
        >
          {plans.map((plan, i) => (
            <motion.div
              key={i}
              variants={itemVariants}
              className={`glass-card p-6 sm:p-8 flex flex-col relative ${
                plan.popular
                  ? '!border-sg-blue/40 shadow-[0_0_40px_rgba(59,130,246,0.1)]'
                  : ''
              }`}
              data-testid={`pricing-card-${plan.name.toLowerCase()}`}
            >
              {plan.popular && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                  <span className="inline-flex items-center gap-1.5 bg-sg-blue text-white text-xs font-semibold px-4 py-1.5 rounded-full">
                    <Star size={12} fill="currentColor" />
                    Популярный
                  </span>
                </div>
              )}

              <div className="mb-6">
                <h3 className="font-display font-semibold text-lg text-sg-text mb-1">
                  {plan.name}
                </h3>
                <p className="text-xs text-sg-muted">{plan.sites}</p>
              </div>

              <div className="mb-6">
                <span className="font-display font-bold text-3xl text-sg-text">
                  {plan.price}
                </span>
                <span className="text-sm text-sg-muted">{plan.period}</span>
              </div>

              <ul className="flex flex-col gap-3 mb-8 flex-1">
                {plan.features.map((feat, fi) => (
                  <li key={fi} className="flex items-start gap-2">
                    <Check size={16} className="text-sg-blue mt-0.5 flex-shrink-0" />
                    <span className="text-sm text-sg-muted">{feat}</span>
                  </li>
                ))}
              </ul>

              <a
                href={plan.href}
                className={`${
                  plan.popular ? 'glow-btn' : 'outline-btn'
                } text-center text-sm no-underline`}
                data-testid={`pricing-cta-${plan.name.toLowerCase()}`}
              >
                {plan.cta}
              </a>
            </motion.div>
          ))}
        </motion.div>

        <motion.p
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ delay: 0.5 }}
          className="text-center text-sm text-sg-muted mt-8"
        >
          Enterprise (999+ сайтов) —{' '}
          <a href="mailto:support@rossi-siteguard.ru" className="text-sg-blue hover:underline">
            свяжитесь с нами
          </a>
        </motion.p>
      </div>
    </section>
  )
}
