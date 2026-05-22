import { Shield } from 'lucide-react'

const wcStatusColor = {
  'Group Stage':     '#6CABDD',
  'Round of 16':     '#22C55E',
  'Quarter-Final':   '#F59E0B',
  'Semi-Final':      '#F59E0B',
  'Final':           '#EF4444',
  'Champions':       '#FFD700',
  'Eliminated':      '#8b949e',
  'TBC':             '#8b949e',
}

export default function TeamCard({ team }) {
  const statusColor = wcStatusColor[team.world_cup_status] || '#8b949e'

  return (
    <div className="card hover:border-primary transition-colors">
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="flex items-center gap-2">
          <div className="w-9 h-9 rounded-full bg-secondary flex items-center justify-center flex-shrink-0">
            <Shield size={18} className="text-primary" />
          </div>
          <div>
            <p className="font-semibold text-white">{team.name}</p>
            <p className="text-xs text-muted">{team.country} {team.league ? `- ${team.league}` : ''}</p>
          </div>
        </div>
        {team.world_cup_group && (
          <span className="badge bg-secondary text-primary border border-primary text-xs">
            Group {team.world_cup_group}
          </span>
        )}
      </div>

      <div className="grid grid-cols-2 gap-2 text-xs mb-3">
        <div>
          <span className="text-muted">Manager:</span>
          <span className="text-white ml-1">{team.manager || 'TBC'}</span>
        </div>
        <div>
          <span className="text-muted">WC Status:</span>
          <span className="ml-1 font-medium" style={{ color: statusColor }}>
            {team.world_cup_status}
          </span>
        </div>
        {team.priority && (
          <div>
            <span className="text-muted">Priority:</span>
            <span className="text-white ml-1">{team.priority}</span>
          </div>
        )}
      </div>

      {team.playing_style && (
        <p className="text-xs text-muted line-clamp-2">{team.playing_style}</p>
      )}
    </div>
  )
}
