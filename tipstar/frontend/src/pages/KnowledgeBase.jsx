import { useEffect, useState } from 'react'
import { Plus, RefreshCw, Search, X, CheckCircle, Trash2, Flame } from 'lucide-react'
import DramaCard from '../components/DramaCard'
import {
  getPlayers, getTeams, getMatches, getDrama, getTournaments,
  scrapePlayer, scrapeTeam, createPlayer, createTeam,
  deletePlayer, deleteTeam, deleteTournament,
  syncPlayers, syncTeams, syncTournaments, importAllFromNotion, getTrending,
} from '../api/client'

const TABS = ['Players', 'Teams', 'Tournaments', 'Matches', 'Drama', 'Trending']

// ── Ranking helpers ──────────────────────────────────────────────────────────

const TIER_RANK = { 'Tier 1 Superstar': 0, 'Tier 2 Elite': 1, 'Tier 3 Notable': 2, tier1: 0, tier2: 1, tier3: 2 }
const PRIORITY_RANK = { High: 0, Medium: 1, Low: 2 }
const STATUS_RANK = { Active: 0, Upcoming: 1, Completed: 2 }
const COVERAGE_RANK = { 'Tier 1 - High': 0, 'Tier 2 - Medium': 1, 'Tier 3 - Low': 2, 'Tier 4 - Low': 3 }
const WC_STATUS_RANK = { Final: 0, 'Semi-Final': 1, 'Quarter-Final': 2, 'Round of 16': 3, 'Group Stage': 4, TBC: 5, Eliminated: 6 }

function rankPlayers(list) {
  return [...list].sort((a, b) => {
    const ta = TIER_RANK[a.tier] ?? 9
    const tb = TIER_RANK[b.tier] ?? 9
    if (ta !== tb) return ta - tb
    return (b.world_cup_appearances ?? 0) - (a.world_cup_appearances ?? 0)
  })
}

function rankTeams(list) {
  return [...list].sort((a, b) => {
    const pa = PRIORITY_RANK[a.priority] ?? 9
    const pb = PRIORITY_RANK[b.priority] ?? 9
    if (pa !== pb) return pa - pb
    const wa = WC_STATUS_RANK[a.world_cup_status] ?? 9
    const wb = WC_STATUS_RANK[b.world_cup_status] ?? 9
    return wa - wb
  })
}

function rankTournaments(list) {
  return [...list].sort((a, b) => {
    const sa = STATUS_RANK[a.status] ?? 9
    const sb = STATUS_RANK[b.status] ?? 9
    if (sa !== sb) return sa - sb
    const ca = COVERAGE_RANK[a.coverage_priority] ?? 9
    const cb = COVERAGE_RANK[b.coverage_priority] ?? 9
    return ca - cb
  })
}

// ── Tier / status badges ─────────────────────────────────────────────────────

const TIER_STYLE = {
  'Tier 1 Superstar': 'text-yellow-400 border-yellow-600',
  'Tier 2 Elite':     'text-primary border-primary/60',
  'Tier 3 Notable':   'text-muted border-border',
  tier1: 'text-yellow-400 border-yellow-600',
  tier2: 'text-primary border-primary/60',
  tier3: 'text-muted border-border',
}

function TierBadge({ tier }) {
  if (!tier) return null
  const label = tier.replace('Tier 1 Superstar', 'T1').replace('Tier 2 Elite', 'T2').replace('Tier 3 Notable', 'T3').replace('tier', 'T')
  return <span className={`text-xs font-bold px-1.5 py-0.5 rounded border ${TIER_STYLE[tier] || 'text-muted border-border'}`}>{label}</span>
}

function StatusDot({ status }) {
  const color = status === 'Active' ? 'bg-green-500' : status === 'Upcoming' ? 'bg-primary' : 'bg-muted'
  return <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${color}`} />
}

// ── Row components ────────────────────────────────────────────────────────────

function PlayerRow({ player, rank, onDelete }) {
  const [confirming, setConfirming] = useState(false)
  const handleDelete = async () => {
    if (!confirming) { setConfirming(true); setTimeout(() => setConfirming(false), 3000); return }
    await onDelete(player.id)
  }
  return (
    <div className="flex items-center gap-3 px-4 py-3 border-b border-border last:border-0 hover:bg-surface/40 transition-colors group">
      <span className="text-xs text-muted w-5 text-right flex-shrink-0">{rank}</span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-medium text-white text-sm">{player.name}</span>
          <TierBadge tier={player.tier} />
          {player.status && player.status !== 'Active' && (
            <span className="text-xs text-warning">{player.status}</span>
          )}
        </div>
        <p className="text-xs text-muted truncate">
          {player.current_club || '-'}{player.position ? ` · ${player.position}` : ''}{player.nationality ? ` · ${player.nationality}` : ''}
        </p>
      </div>
      <div className="flex items-center gap-3 flex-shrink-0 text-xs text-muted">
        {player.world_cup_appearances > 0 && (
          <span className="hidden sm:block">{player.world_cup_appearances} WC</span>
        )}
        {player.age && <span className="hidden md:block">Age {player.age}</span>}
        <button
          onClick={handleDelete}
          className={`opacity-0 group-hover:opacity-100 p-1 transition-all ${confirming ? 'text-danger opacity-100' : 'text-muted hover:text-danger'}`}
          title={confirming ? 'Click again to confirm' : 'Remove'}
        >
          <Trash2 size={13} />
        </button>
      </div>
    </div>
  )
}

function TeamRow({ team, rank, onDelete }) {
  const [confirming, setConfirming] = useState(false)
  const handleDelete = async () => {
    if (!confirming) { setConfirming(true); setTimeout(() => setConfirming(false), 3000); return }
    await onDelete(team.id)
  }
  const priorityColor = team.priority === 'High' ? 'text-yellow-400' : team.priority === 'Medium' ? 'text-primary' : 'text-muted'
  return (
    <div className="flex items-center gap-3 px-4 py-3 border-b border-border last:border-0 hover:bg-surface/40 transition-colors group">
      <span className="text-xs text-muted w-5 text-right flex-shrink-0">{rank}</span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium text-white text-sm">{team.name}</span>
          {team.priority && <span className={`text-xs font-bold ${priorityColor}`}>{team.priority}</span>}
        </div>
        <p className="text-xs text-muted truncate">
          {team.country || '-'}{team.league ? ` · ${team.league}` : ''}{team.manager ? ` · ${team.manager}` : ''}
        </p>
      </div>
      <div className="flex items-center gap-3 flex-shrink-0 text-xs">
        {team.world_cup_group && <span className="text-primary font-bold">Grp {team.world_cup_group}</span>}
        {team.world_cup_status && team.world_cup_status !== 'TBC' && (
          <span className="text-muted hidden sm:block">{team.world_cup_status}</span>
        )}
        <button
          onClick={handleDelete}
          className={`opacity-0 group-hover:opacity-100 p-1 transition-all ${confirming ? 'text-danger opacity-100' : 'text-muted hover:text-danger'}`}
          title={confirming ? 'Click again to confirm' : 'Remove'}
        >
          <Trash2 size={13} />
        </button>
      </div>
    </div>
  )
}

function TournamentRow({ tournament, rank, onDelete }) {
  const [confirming, setConfirming] = useState(false)
  const handleDelete = async () => {
    if (!confirming) { setConfirming(true); setTimeout(() => setConfirming(false), 3000); return }
    await onDelete(tournament.id)
  }
  return (
    <div className="flex items-center gap-3 px-4 py-3 border-b border-border last:border-0 hover:bg-surface/40 transition-colors group">
      <span className="text-xs text-muted w-5 text-right flex-shrink-0">{rank}</span>
      <StatusDot status={tournament.status} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-medium text-white text-sm">{tournament.name}</span>
          <span className="text-xs text-muted">{tournament.type}</span>
        </div>
        <p className="text-xs text-muted truncate">
          {tournament.current_stage || tournament.status || '-'}
          {tournament.current_leader ? ` · Leader: ${tournament.current_leader}` : ''}
          {tournament.host_country ? ` · ${tournament.host_country}` : ''}
        </p>
      </div>
      <div className="flex items-center gap-3 flex-shrink-0 text-xs">
        {tournament.coverage_priority && (
          <span className="text-muted hidden md:block">{tournament.coverage_priority.replace('Tier ', 'T').split(' -')[0]}</span>
        )}
        <button
          onClick={handleDelete}
          className={`opacity-0 group-hover:opacity-100 p-1 transition-all ${confirming ? 'text-danger opacity-100' : 'text-muted hover:text-danger'}`}
          title={confirming ? 'Click again to confirm' : 'Remove'}
        >
          <Trash2 size={13} />
        </button>
      </div>
    </div>
  )
}

function MatchRow({ match }) {
  return (
    <div className="flex items-center gap-3 px-4 py-3 border-b border-border last:border-0 hover:bg-surface/40 transition-colors">
      <div className="flex-1 text-right text-sm font-medium text-white truncate">{match.home_team}</div>
      <div className="text-center px-3 flex-shrink-0">
        {match.home_score !== null ? (
          <span className="text-sm font-bold text-primary">{match.home_score}-{match.away_score}</span>
        ) : (
          <span className="text-xs text-muted">vs</span>
        )}
      </div>
      <div className="flex-1 text-sm font-medium text-white truncate">{match.away_team}</div>
      <div className="text-xs text-muted hidden sm:block flex-shrink-0 max-w-32 truncate">{match.tournament}</div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function KnowledgeBase() {
  const [tab, setTab]                   = useState('Players')
  const [search, setSearch]             = useState('')
  const [players, setPlayers]           = useState([])
  const [teams, setTeams]               = useState([])
  const [tournaments, setTournaments]   = useState([])
  const [matches, setMatches]           = useState([])
  const [drama, setDrama]               = useState([])
  const [loading, setLoading]           = useState(false)
  const [syncing, setSyncing]           = useState(false)
  const [syncingTournaments, setSyncingTournaments] = useState(false)
  const [importing, setImporting]       = useState(false)
  const [trending, setTrending]         = useState([])
  const [trendingDays, setTrendingDays] = useState(7)
  const [trendingLoading, setTrendingLoading] = useState(false)
  const [addingEntity, setAddingEntity] = useState(null)
  const [profileOpen, setProfileOpen]   = useState(false)
  const [saving, setSaving]             = useState(false)
  const [profileName, setProfileName]   = useState('')
  const [tier, setTier]                 = useState('')
  const [priority, setPriority]         = useState('')
  const [status, setStatus]             = useState('')

  const loadTab = (target = tab) => {
    setLoading(true)
    const fetchers = {
      Players:     () => getPlayers().then(r => setPlayers(r.data)),
      Teams:       () => getTeams().then(r => setTeams(r.data)),
      Tournaments: () => getTournaments().then(r => setTournaments(r.data)),
      Matches:     () => getMatches().then(r => setMatches(r.data)),
      Drama:       () => getDrama().then(r => setDrama(r.data)),
    }
    return fetchers[target]?.().catch(() => {}).finally(() => setLoading(false))
  }

  useEffect(() => {
    if (tab === 'Trending') loadTrending(trendingDays)
    else loadTab(tab)
  }, [tab])

  const loadTrending = (days = trendingDays) => {
    setTrendingLoading(true)
    getTrending(days, 50).then(r => setTrending(r.data.items || [])).catch(() => {}).finally(() => setTrendingLoading(false))
  }

  const handleImportNotion = async () => {
    setImporting(true); setStatus('')
    try {
      const result = await importAllFromNotion()
      const p  = result.data?.players?.imported ?? 0
      const t  = result.data?.teams?.imported ?? 0
      const d  = result.data?.drama?.imported ?? 0
      const tr = result.data?.tournaments?.imported ?? 0
      await loadTab(tab)
      setStatus(`Imported: ${p} players, ${t} teams, ${tr} tournaments, ${d} drama.`)
    } catch { setStatus('Notion import failed.') }
    finally { setImporting(false) }
  }

  const handleSync = async () => {
    setSyncing(true); setStatus('')
    try {
      await syncPlayers(); await syncTeams()
      setStatus('Sync running in background (~2 min). Refresh the tab when done.')
    } catch { setStatus('Sync failed - check backend logs.') }
    finally { setSyncing(false) }
  }

  const handleSyncTournaments = async () => {
    setSyncingTournaments(true); setStatus('')
    try {
      await syncTournaments()
      setStatus('Tournament sync started - standings, leaders, and stage data pulling now (~30s). Refresh when done.')
    } catch { setStatus('Tournament sync failed - check backend logs.') }
    finally { setSyncingTournaments(false) }
  }

  const handleDeletePlayer = async (id) => {
    await deletePlayer(id)
    setPlayers(prev => prev.filter(p => p.id !== id))
    setStatus('Player removed.')
  }
  const handleDeleteTeam = async (id) => {
    await deleteTeam(id)
    setTeams(prev => prev.filter(t => t.id !== id))
    setStatus('Club removed.')
  }
  const handleDeleteTournament = async (id) => {
    await deleteTournament(id)
    setTournaments(prev => prev.filter(t => t.id !== id))
    setStatus('Tournament removed.')
  }

  const handleAddTrendingEntity = async (entity) => {
    setAddingEntity(entity.name); setStatus('')
    try {
      if (entity.type === 'player') {
        try { await scrapePlayer({ name: entity.name }) } catch { await createPlayer({ name: entity.name }) }
      } else if (entity.type === 'club') {
        try { await scrapeTeam({ name: entity.name }) } catch { await createTeam({ name: entity.name }) }
      }
      setTrending(prev => prev.map(e => e.name === entity.name ? { ...e, in_db: true } : e))
      setStatus(`Added ${entity.name}.`)
    } catch { setStatus(`Could not add ${entity.name}.`) }
    finally { setAddingEntity(null) }
  }

  const handleAddProfile = async e => {
    e.preventDefault()
    const name = profileName.trim()
    if (!name) return
    setSaving(true); setStatus('')
    try {
      if (tab === 'Players') await scrapePlayer({ name, tier: tier || undefined })
      else await scrapeTeam({ name, priority: priority || undefined })
      setProfileName(''); setTier(''); setPriority(''); setProfileOpen(false)
      await loadTab(tab)
      setStatus(`${tab === 'Players' ? 'Player' : 'Club'} saved.`)
    } catch { setStatus(`${tab === 'Players' ? 'Player' : 'Club'} not found.`) }
    finally { setSaving(false) }
  }

  const q = search.toLowerCase()
  const filteredPlayers     = rankPlayers(players).filter(p => !q || p.name?.toLowerCase().includes(q) || p.current_club?.toLowerCase().includes(q))
  const filteredTeams       = rankTeams(teams).filter(t => !q || t.name?.toLowerCase().includes(q) || t.country?.toLowerCase().includes(q))
  const filteredTournaments = rankTournaments(tournaments)
  const filteredMatches     = matches.filter(m => !q || m.home_team?.toLowerCase().includes(q) || m.away_team?.toLowerCase().includes(q))
  const filteredDrama       = drama.filter(d => !q || d.title?.toLowerCase().includes(q))

  return (
    <div>
      {/* Header */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between mb-6">
        <h1 className="text-2xl font-bold text-primary">Knowledge Base</h1>
        <div className="flex flex-wrap gap-2">
          <button onClick={handleImportNotion} disabled={importing || syncing}
            className="btn-ghost inline-flex items-center gap-2 disabled:opacity-60 text-sm">
            <RefreshCw size={14} className={importing ? 'animate-spin' : ''} />
            {importing ? 'Importing…' : 'Import from Notion'}
          </button>
          {tab === 'Tournaments' ? (
            <button onClick={handleSyncTournaments} disabled={syncingTournaments || importing}
              className="btn-primary inline-flex items-center gap-2 disabled:opacity-60 text-sm">
              <RefreshCw size={14} className={syncingTournaments ? 'animate-spin' : ''} />
              {syncingTournaments ? 'Starting…' : 'Sync live data'}
            </button>
          ) : (
            <button onClick={handleSync} disabled={syncing || importing}
              className="btn-primary inline-flex items-center gap-2 disabled:opacity-60 text-sm">
              <RefreshCw size={14} className={syncing ? 'animate-spin' : ''} />
              {syncing ? 'Starting…' : 'Sync live data'}
            </button>
          )}
          {['Players', 'Teams'].includes(tab) && (
            <button onClick={() => setProfileOpen(v => !v)}
              className="btn-ghost inline-flex items-center gap-2 text-sm">
              {profileOpen ? <X size={14} /> : <Plus size={14} />}
              {profileOpen ? 'Close' : `Add ${tab === 'Players' ? 'player' : 'club'}`}
            </button>
          )}
        </div>
      </div>

      {status && (
        <div className="mb-4 border border-border bg-card rounded-lg px-4 py-2.5 text-sm text-muted">{status}</div>
      )}

      {profileOpen && ['Players', 'Teams'].includes(tab) && (
        <form onSubmit={handleAddProfile} className="card mb-6 flex flex-wrap gap-3 items-end">
          <input type="text" value={profileName} onChange={e => setProfileName(e.target.value)}
            placeholder={tab === 'Players' ? 'Player name' : 'Club name'}
            className="flex-1 min-w-48 bg-background border border-border rounded-lg px-3 py-2 text-white text-sm focus:border-primary outline-none" />
          {tab === 'Players' ? (
            <select value={tier} onChange={e => setTier(e.target.value)}
              className="bg-background border border-border rounded-lg px-3 py-2 text-white text-sm focus:border-primary outline-none">
              <option value="">Tier</option>
              <option value="tier1">Tier 1</option>
              <option value="tier2">Tier 2</option>
              <option value="tier3">Tier 3</option>
            </select>
          ) : (
            <select value={priority} onChange={e => setPriority(e.target.value)}
              className="bg-background border border-border rounded-lg px-3 py-2 text-white text-sm focus:border-primary outline-none">
              <option value="">Priority</option>
              <option value="High">High</option>
              <option value="Medium">Medium</option>
              <option value="Low">Low</option>
            </select>
          )}
          <button type="submit" disabled={saving || !profileName.trim()}
            className="btn-primary inline-flex items-center gap-2 text-sm disabled:opacity-60">
            <Plus size={14} />{saving ? 'Saving…' : 'Save'}
          </button>
        </form>
      )}

      {/* Search */}
      {!['Trending', 'Tournaments', 'Matches'].includes(tab) && (
        <div className="relative mb-4">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
          <input type="text" placeholder={`Search ${tab.toLowerCase()}…`} value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full bg-card border border-border rounded-xl pl-10 pr-4 py-2.5 text-white text-sm focus:border-primary outline-none" />
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 mb-4 border-b border-border overflow-x-auto">
        {TABS.map(t => (
          <button key={t} onClick={() => { setTab(t); setSearch('') }}
            className={`px-4 py-2 text-sm font-medium whitespace-nowrap transition-colors border-b-2 -mb-px ${
              tab === t ? 'border-primary text-primary' : 'border-transparent text-muted hover:text-white'
            }`}>
            {t}{t === 'Players' && players.length ? ` (${players.length})` : ''}
            {t === 'Teams' && teams.length ? ` (${teams.length})` : ''}
            {t === 'Tournaments' && tournaments.length ? ` (${tournaments.length})` : ''}
          </button>
        ))}
      </div>

      {loading && <p className="text-muted text-sm py-8 text-center">Loading…</p>}

      {/* Players list */}
      {!loading && tab === 'Players' && (
        <div className="bg-card border border-border rounded-xl overflow-hidden">
          {filteredPlayers.length
            ? filteredPlayers.map((p, i) => <PlayerRow key={p.id} player={p} rank={i + 1} onDelete={handleDeletePlayer} />)
            : <p className="text-muted text-sm p-6 text-center">No players found.</p>}
        </div>
      )}

      {/* Teams list */}
      {!loading && tab === 'Teams' && (
        <div className="bg-card border border-border rounded-xl overflow-hidden">
          {filteredTeams.length
            ? filteredTeams.map((t, i) => <TeamRow key={t.id} team={t} rank={i + 1} onDelete={handleDeleteTeam} />)
            : <p className="text-muted text-sm p-6 text-center">No teams found.</p>}
        </div>
      )}

      {/* Tournaments list */}
      {!loading && tab === 'Tournaments' && (
        <div className="bg-card border border-border rounded-xl overflow-hidden">
          {filteredTournaments.length
            ? filteredTournaments.map((t, i) => <TournamentRow key={t.id} tournament={t} rank={i + 1} onDelete={handleDeleteTournament} />)
            : <p className="text-muted text-sm p-6 text-center">No tournaments. Click "Import from Notion" to load.</p>}
        </div>
      )}

      {/* Matches list */}
      {!loading && tab === 'Matches' && (
        <div className="bg-card border border-border rounded-xl overflow-hidden">
          {filteredMatches.length
            ? filteredMatches.map(m => <MatchRow key={m.id} match={m} />)
            : <p className="text-muted text-sm p-6 text-center">No matches found.</p>}
        </div>
      )}

      {/* Drama */}
      {!loading && tab === 'Drama' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {filteredDrama.length
            ? filteredDrama.map(d => <DramaCard key={d.id} drama={d} />)
            : <p className="text-muted text-sm col-span-2 text-center py-8">No drama entries.</p>}
        </div>
      )}

      {/* Trending */}
      {tab === 'Trending' && (
        <div>
          <div className="flex flex-wrap items-center gap-3 mb-5">
            <span className="text-sm text-muted">Scan last</span>
            {[1, 3, 7, 14].map(d => (
              <button key={d} onClick={() => { setTrendingDays(d); loadTrending(d) }}
                className={`px-3 py-1 rounded-lg text-sm font-medium transition-colors ${
                  trendingDays === d ? 'bg-primary text-black' : 'bg-card border border-border text-muted hover:text-white'
                }`}>{d}d</button>
            ))}
            <button onClick={() => loadTrending(trendingDays)} disabled={trendingLoading}
              className="btn-ghost inline-flex items-center gap-1 text-sm ml-auto">
              <RefreshCw size={13} className={trendingLoading ? 'animate-spin' : ''} />Refresh
            </button>
          </div>

          {trendingLoading && <p className="text-muted text-sm">Scanning news…</p>}
          {!trendingLoading && trending.length === 0 && (
            <p className="text-muted text-sm">No trending entities found. Fetch latest news first.</p>
          )}

          {!trendingLoading && trending.length > 0 && (
            ['player', 'club', 'event'].map(type => {
              const group = trending.filter(e => e.type === type)
              if (!group.length) return null
              return (
                <div key={type} className="mb-6">
                  <h3 className="text-xs font-semibold uppercase tracking-widest text-muted mb-2 flex items-center gap-2">
                    <Flame size={12} />
                    {type === 'player' ? 'Players' : type === 'club' ? 'Clubs' : 'Events & Topics'}
                  </h3>
                  <div className="bg-card border border-border rounded-xl overflow-hidden">
                    {group.map((entity, i) => (
                      <div key={entity.name}
                        className={`flex items-center gap-3 px-4 py-2.5 border-b border-border last:border-0 ${entity.in_db ? '' : 'hover:bg-surface/40'} transition-colors`}>
                        <span className="text-xs text-muted w-4 text-right">{i + 1}</span>
                        <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${entity.in_db ? 'bg-green-500' : 'bg-yellow-400'}`} />
                        <span className="flex-1 text-sm text-white">{entity.name}</span>
                        <span className="text-xs text-muted">{entity.mentions}×</span>
                        {!entity.in_db && entity.type !== 'event' && (
                          <button onClick={() => handleAddTrendingEntity(entity)}
                            disabled={addingEntity === entity.name}
                            className="text-xs px-2 py-0.5 rounded bg-primary/20 text-primary hover:bg-primary/40 disabled:opacity-50 transition-colors">
                            {addingEntity === entity.name ? '…' : 'Add'}
                          </button>
                        )}
                        {entity.in_db && <CheckCircle size={13} className="text-green-500" />}
                      </div>
                    ))}
                  </div>
                </div>
              )
            })
          )}
        </div>
      )}
    </div>
  )
}
