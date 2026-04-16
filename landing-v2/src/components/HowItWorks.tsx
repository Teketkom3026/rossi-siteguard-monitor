import { motion } from 'framer-motion'
import { Download, Key, Globe } from 'lucide-react'

const steps = [
  {
    icon: Download,
    num: '01',
    title: 'Скачать и установить',
    desc: 'Загрузите SiteGuard Monitor Pro для Windows',
  },
  {
    icon: Key,
    num: '02',
    title: 'Активировать лицензию',
    desc: 'Введите ключ активации (работает без интернета)',
  },
  {
    icon: Globe,
    num: '03',
    title: 'Добавить сайты',
    desc: 'Настройте мониторинг ваших доменов',
  },
]

export default function HowItWorks() {
  return (
    <section className="relative z-10 py-24 sm:py-32" id="about">
      <div className="section-container">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-100px' }}
          transition={{ duration: 0.7 }}
          className="text-center mb-16"
        >
          <span className="font-mono text-xs text-sg-blue tracking-[0.2em] uppercase block mb-4">
            Начало работы
          </span>
          <h2 className="font-display font-bold text-3xl sm:text-4xl md:text-5xl text-sg-text tracking-tight">
            КАК ЭТО<br />
            <span className="text-gradient-blue">РАБОТАЕТ</span>
          </h2>
        </motion.div>

        <div className="relative max-w-3xl mx-auto">
          {/* Connecting line */}
          <div
            className="hidden md:block absolute left-1/2 top-0 bottom-0 w-px"
            style={{
              background: 'linear-gradient(to bottom, transparent, rgba(59, 130, 246, 0.3), rgba(59, 130, 246, 0.3), transparent)',
            }}
          />

          <div className="flex flex-col gap-12 md:gap-16">
            {steps.map((step, i) => {
              const Icon = step.icon
              const isEven = i % 2 === 0
              return (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: isEven ? -40 : 40 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true, margin: '-50px' }}
                  transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
                  className={`flex items-center gap-6 md:gap-10 ${
                    isEven ? 'md:flex-row' : 'md:flex-row-reverse'
                  }`}
                >
                  <div className={`flex-1 ${isEven ? 'md:text-right' : 'md:text-left'}`}>
                    <span className="font-mono text-xs text-sg-blue tracking-wider block mb-2">
                      {step.num}
                    </span>
                    <h3 className="font-display font-semibold text-xl text-sg-text mb-2">
                      {step.title}
                    </h3>
                    <p className="font-body text-sm text-sg-muted">{step.desc}</p>
                  </div>

                  {/* Center node */}
                  <div className="relative flex-shrink-0">
                    <div className="w-14 h-14 rounded-2xl glass-card flex items-center justify-center relative z-10">
                      <Icon size={22} className="text-sg-blue" />
                    </div>
                    <div className="absolute inset-0 rounded-2xl bg-sg-blue/10 blur-xl" />
                  </div>

                  <div className="flex-1 hidden md:block" />
                </motion.div>
              )
            })}
          </div>
        </div>
      </div>
    </section>
  )
}
