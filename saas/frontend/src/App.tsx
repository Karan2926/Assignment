import { useEffect, useState } from 'react'
import './App.css'

type Health = {
  status: string
  service: string
  phase: number
  message: string
}

const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000'

function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [error, setError] = useState<string>('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    async function ping() {
      setLoading(true)
      setError('')
      try {
        const res = await fetch(`${API_BASE}/api/health/`)
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const data = (await res.json()) as Health
        if (!cancelled) setHealth(data)
      } catch (e) {
        if (!cancelled) {
          setHealth(null)
          setError(
            e instanceof Error
              ? e.message
              : 'Cannot reach backend. Start Django on port 8000.',
          )
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    ping()
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <main className="page">
      <header className="hero">
        <p className="eyebrow">Startup product · Phase 1</p>
        <h1>Smart Attendance SaaS</h1>
        <p className="lead">
          One platform for colleges, offices, factories, and coaching centers.
          Django backend · React frontend · Face attendance next.
        </p>
      </header>

      <section className="card">
        <h2>Backend connection</h2>
        {loading && <p className="muted">Checking Django API…</p>}
        {!loading && health && (
          <div className="ok">
            <strong>Connected</strong>
            <p>{health.message}</p>
            <code>
              {health.service} · phase {health.phase} · {health.status}
            </code>
          </div>
        )}
        {!loading && error && (
          <div className="bad">
            <strong>Not connected</strong>
            <p>{error}</p>
            <p className="muted">
              Run: <code>cd saas/backend && python manage.py runserver 8000</code>
            </p>
          </div>
        )}
      </section>

      <section className="card">
        <h2>Build plan</h2>
        <ol>
          <li>Organization + users (this phase)</li>
          <li>People directory (students / employees)</li>
          <li>Face enrollment</li>
          <li>Live camera attendance</li>
          <li>Reports + billing</li>
        </ol>
      </section>
    </main>
  )
}

export default App
