import AnimatedBackground from '../components/AnimatedBackground'
import Nav from '../components/Nav'
import Hero from '../components/Hero'
import Features from '../components/Features'
import HowItWorks from '../components/HowItWorks'
import Pricing from '../components/Pricing'
import DownloadSection from '../components/DownloadSection'
import Footer from '../components/Footer'

export default function LandingPage() {
  return (
    <div className="relative min-h-screen bg-sg-bg">
      <AnimatedBackground />
      <Nav />
      <Hero />
      <HowItWorks />
      <Features />
      <Pricing />
      <DownloadSection />
      <Footer />
    </div>
  )
}
