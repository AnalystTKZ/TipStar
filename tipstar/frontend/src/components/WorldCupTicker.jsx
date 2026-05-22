import { useEffect, useState } from 'react'
import { getMatches } from '../api/client'

export default function WorldCupTicker() {
  const [matches, setMatches] = useState([])

  useEffect(() => {
    getMatches()
      .then(r => setMatches(r.data.filter(m => m.tournament?.toLowerCase().includes('world cup')).slice(0, 8)))
      .catch(() => {})
  }, [])

  if (!matches.length) return null

  const items = matches.filter(m => m.home_score !== null && m.away_score !== null)
  if (!items.length) return null

  return (
    <div className="bg-secondary border border-primary/30 rounded-xl px-4 py-2 mb-6 overflow-hidden">
      <div className="flex items-center gap-3">
        <span className="text-primary text-xs font-bold flex-shrink-0">WORLD CUP LIVE</span>
        <div className="flex items-center gap-6 overflow-x-auto scrollbar-hide">
          {items.map(m => (
            <div key={m.id} className="flex items-center gap-2 whitespace-nowrap text-sm">
              <span className="text-white font-medium">{m.home_team}</span>
              <span className="text-primary font-bold px-2 py-0.5 bg-background rounded">
                {m.home_score} - {m.away_score}
              </span>
              <span className="text-white font-medium">{m.away_team}</span>
              {m.stage && <span className="text-muted text-xs">({m.stage})</span>}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
