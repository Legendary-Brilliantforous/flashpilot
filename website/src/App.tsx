import CapabilityMatrix from './components/CapabilityMatrix'
import Comparison from './components/Comparison'
import DeviceCoverage from './components/DeviceCoverage'
import Footer from './components/Footer'
import Gallery from './components/Gallery'
import Hero from './components/Hero'
import QuickStart from './components/QuickStart'
import Safety from './components/Safety'
import TopBar from './components/TopBar'
import Transports from './components/Transports'

export default function App() {
  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
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
        <Safety />
      </main>
      <Footer />
    </>
  )
}
