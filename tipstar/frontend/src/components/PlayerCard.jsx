import { User, Trophy, Star } from 'lucide-react'

const tierColors = {
  tier1: { text: '#F59E0B', label: 'Tier 1' },
  tier2: { text: '#6CABDD', label: 'Tier 2' },
  tier3: { text: '#8b949e', label: 'Tier 3' },
}

export default function PlayerCard({ player }) {
  const tier = tierColors[player.tier] || { text: '#8b949e', label: player.tier }

  return (
    <div className="card hover:border-primary transition-colors">
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="flex items-center gap-2">
          <div className="w-9 h-9 rounded-full bg-secondary flex items-center justify-center flex-shrink-0">
            <User size={18} className="text-primary" />
          </div>
          <div>
            <p className="font-semibold text-white">{player.name}</p>
            <p className="text-xs text-muted">{player.nationality}</p>
          </div>
        </div>
        {player.tier && (
          <span className="text-xs font-bold" style={{ color: tier.text }}>{tier.label}</span>
        )}
      </div>

      <div className="grid grid-cols-2 gap-2 text-xs text-muted mb-3">
        <span>{player.current_club || 'Unknown club'}</span>
        <span>{player.position || 'Unknown position'}</span>
        {player.age && <span>Age {player.age}</span>}
        <span
          className="font-medium"
          style={{ color: player.status === 'Active' ? '#22C55E' : '#8b949e' }}
        >
          {player.status}
        </span>
      </div>

      {(player.world_cup_appearances > 0 || player.world_cup_goals > 0) && (
        <div className="flex items-center gap-3 pt-2 border-t border-border text-xs">
          <Trophy size={12} className="text-warning" />
          <span className="text-muted">{player.world_cup_appearances} WC tournaments</span>
          <span className="text-warning font-bold">{player.world_cup_goals} WC goals</span>
        </div>
      )}

      {player.notes && (
        <p className="text-xs text-muted mt-2 line-clamp-2">{player.notes}</p>
      )}
    </div>
  )
}
