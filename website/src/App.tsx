import { useEffect } from 'react'

import CapabilityMatrix from './components/CapabilityMatrix'
import Comparison from './components/Comparison'
import Contribute from './components/Contribute'
import DeviceCoverage from './components/DeviceCoverage'
import Footer from './components/Footer'
import Gallery from './components/Gallery'
import Hero from './components/Hero'
import QuickStart from './components/QuickStart'
import Releases from './components/Releases'
import Safety from './components/Safety'
import TopBar from './components/TopBar'
import Transports from './components/Transports'
import { t } from './i18n'

export default function App() {
  useEffect(() => {
    if (typeof window === 'undefined') return
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const sections = Array.from(document.querySelectorAll('section, .hero, .footer'))
    if (reduced) {
      sections.forEach((el) => el.classList.add('reveal--visible'))
      return
    }
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            entry.target.classList.add('reveal--visible')
            observer.unobserve(entry.target)
          }
        }
      },
      { threshold: 0.1, rootMargin: '0px 0px -60px 0px' },
    )
    sections.forEach((el) => {
      el.classList.add('reveal')
      observer.observe(el)
    })
    return () => observer.disconnect()
  }, [])

  return (
    <>
      <a className="skip-link" href="#main">
        {t('Skip to content')}
      </a>
      <TopBar />
      <main id="main">
        <Hero />
        <Comparison />
        <Transports />
        <CapabilityMatrix />
        <DeviceCoverage />
        <Gallery />
        <QuickStart />
        <Releases />
        <Contribute />
        <Safety />
      </main>
      <Footer />
    </>
  )
}
