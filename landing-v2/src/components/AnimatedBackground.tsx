import { useEffect, useRef } from 'react'

interface Particle {
  x: number
  y: number
  vx: number
  vy: number
  life: number
  maxLife: number
  size: number
  hue: number
  trail: { x: number; y: number; alpha: number }[]
}

interface Stream {
  points: { x: number; y: number; angle: number }[]
  speed: number
  hue: number
  width: number
  phase: number
}

export default function AnimatedBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')!
    let animId: number
    let w = 0
    let h = 0

    const resize = () => {
      w = canvas.width = window.innerWidth
      h = canvas.height = window.innerHeight
    }
    resize()
    window.addEventListener('resize', resize)

    // Create flowing streams
    const streams: Stream[] = []
    const numStreams = 6

    for (let i = 0; i < numStreams; i++) {
      const stream: Stream = {
        points: [],
        speed: 0.3 + Math.random() * 0.5,
        hue: [195, 210, 220, 240, 260, 200][i],
        width: 1.5 + Math.random() * 2,
        phase: Math.random() * Math.PI * 2,
      }
      const numPoints = 80
      const startY = h * (0.15 + (i / numStreams) * 0.7)
      for (let j = 0; j < numPoints; j++) {
        stream.points.push({
          x: (j / numPoints) * (w + 400) - 200,
          y: startY,
          angle: 0,
        })
      }
      streams.push(stream)
    }

    // Create ambient particles
    const particles: Particle[] = []
    const maxParticles = 120

    function spawnParticle() {
      if (particles.length >= maxParticles) return
      const hue = [195, 210, 240, 260][Math.floor(Math.random() * 4)]
      particles.push({
        x: Math.random() * w,
        y: Math.random() * h,
        vx: (Math.random() - 0.5) * 0.3,
        vy: (Math.random() - 0.5) * 0.3 - 0.1,
        life: 0,
        maxLife: 200 + Math.random() * 300,
        size: 1 + Math.random() * 2,
        hue,
        trail: [],
      })
    }

    // Spawn initial particles
    for (let i = 0; i < 60; i++) spawnParticle()

    let time = 0

    function animate() {
      time += 0.005
      ctx.fillStyle = 'rgba(4, 6, 16, 0.15)'
      ctx.fillRect(0, 0, w, h)

      // Draw streams
      streams.forEach((stream, si) => {
        const t = time * stream.speed
        ctx.beginPath()
        ctx.strokeStyle = `hsla(${stream.hue}, 80%, 55%, 0.12)`
        ctx.lineWidth = stream.width * 3
        ctx.shadowColor = `hsla(${stream.hue}, 90%, 60%, 0.3)`
        ctx.shadowBlur = 40

        stream.points.forEach((p, i) => {
          const progress = i / stream.points.length
          const waveY = Math.sin(progress * 3 + t * 2 + stream.phase) * (60 + si * 15)
            + Math.sin(progress * 5 + t * 1.3) * 25
            + Math.cos(progress * 1.5 + t * 0.7) * 40
          const baseY = h * (0.2 + (si / streams.length) * 0.6)
          p.y = baseY + waveY

          if (i === 0) ctx.moveTo(p.x, p.y)
          else ctx.lineTo(p.x, p.y)
        })
        ctx.stroke()

        // Brighter core
        ctx.beginPath()
        ctx.strokeStyle = `hsla(${stream.hue}, 85%, 70%, 0.25)`
        ctx.lineWidth = stream.width
        ctx.shadowBlur = 20
        stream.points.forEach((p, i) => {
          if (i === 0) ctx.moveTo(p.x, p.y)
          else ctx.lineTo(p.x, p.y)
        })
        ctx.stroke()

        // Bright nodes along stream
        for (let i = 0; i < stream.points.length; i += 12) {
          const p = stream.points[i]
          const pulse = Math.sin(time * 3 + i * 0.3 + stream.phase) * 0.5 + 0.5
          const nodeSize = (1.5 + pulse * 2) * (stream.width / 2)
          ctx.beginPath()
          ctx.arc(p.x, p.y, nodeSize, 0, Math.PI * 2)
          ctx.fillStyle = `hsla(${stream.hue}, 90%, 75%, ${0.3 + pulse * 0.4})`
          ctx.shadowColor = `hsla(${stream.hue}, 90%, 65%, 0.6)`
          ctx.shadowBlur = 15
          ctx.fill()
        }
      })

      ctx.shadowBlur = 0

      // Update and draw particles
      if (Math.random() < 0.3) spawnParticle()

      for (let i = particles.length - 1; i >= 0; i--) {
        const p = particles[i]
        p.life++
        if (p.life > p.maxLife) {
          particles.splice(i, 1)
          continue
        }

        p.x += p.vx + Math.sin(time * 2 + p.y * 0.005) * 0.15
        p.y += p.vy

        // Wrap around
        if (p.x < -10) p.x = w + 10
        if (p.x > w + 10) p.x = -10
        if (p.y < -10) p.y = h + 10

        const lifeRatio = p.life / p.maxLife
        const alpha = lifeRatio < 0.1
          ? lifeRatio / 0.1
          : lifeRatio > 0.8
            ? (1 - lifeRatio) / 0.2
            : 1

        // Draw particle with glow
        ctx.beginPath()
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2)
        ctx.fillStyle = `hsla(${p.hue}, 80%, 65%, ${alpha * 0.6})`
        ctx.fill()

        // Outer glow
        ctx.beginPath()
        ctx.arc(p.x, p.y, p.size * 3, 0, Math.PI * 2)
        const grad = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.size * 3)
        grad.addColorStop(0, `hsla(${p.hue}, 80%, 65%, ${alpha * 0.15})`)
        grad.addColorStop(1, `hsla(${p.hue}, 80%, 65%, 0)`)
        ctx.fillStyle = grad
        ctx.fill()
      }

      // Subtle vignette overlay (drawn less frequently for perf)
      if (Math.floor(time * 100) % 50 === 0) {
        const vignette = ctx.createRadialGradient(w / 2, h / 2, w * 0.2, w / 2, h / 2, w * 0.8)
        vignette.addColorStop(0, 'rgba(4, 6, 16, 0)')
        vignette.addColorStop(1, 'rgba(4, 6, 16, 0.4)')
        ctx.fillStyle = vignette
        ctx.fillRect(0, 0, w, h)
      }

      animId = requestAnimationFrame(animate)
    }

    // Initial clear
    ctx.fillStyle = '#040610'
    ctx.fillRect(0, 0, w, h)
    animate()

    return () => {
      cancelAnimationFrame(animId)
      window.removeEventListener('resize', resize)
    }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 w-full h-full"
      style={{ zIndex: 0 }}
      aria-hidden="true"
    />
  )
}
