import { Zap } from 'lucide-react'
import { severityColors } from '../styles/theme'

export default function DramaCard({ drama }) {
  const sev = severityColors[drama.severity?.toLowerCase()] || severityColors.low

  return (
    <div
      className="card hover:border-primary transition-colors"
      style={{ borderLeftWidth: 3, borderLeftColor: sev.text }}
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <p className="font-semibold text-white text-sm">{drama.title}</p>
        <span
          className="badge flex-shrink-0 text-xs font-bold"
          style={{ background: sev.bg, color: sev.text }}
        >
          <Zap size={10} className="mr-1" />
          {(drama.severity || 'low').toUpperCase()}
        </span>
      </div>

      {drama.summary && (
        <p className="text-xs text-muted line-clamp-3 mb-3">{drama.summary}</p>
      )}

      <div className="flex flex-wrap gap-3 text-xs text-muted">
        {drama.players_involved && (
          <span>Players: <span className="text-white">{drama.players_involved}</span></span>
        )}
        {drama.teams_involved && (
          <span>Teams: <span className="text-white">{drama.teams_involved}</span></span>
        )}
        {drama.category && (
          <span>Category: <span className="text-primary">{drama.category}</span></span>
        )}
        <span
          className="ml-auto font-medium"
          style={{ color: drama.status === 'Resolved' ? '#22C55E' : '#F59E0B' }}
        >
          {drama.status}
        </span>
      </div>
    </div>
  )
}
