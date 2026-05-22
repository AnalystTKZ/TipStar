import { useEffect, useState } from 'react'
import { Plus, RefreshCw, Search, X } from 'lucide-react'
import PlayerCard from '../components/PlayerCard'
import TeamCard from '../components/TeamCard'
import DramaCard from '../components/DramaCard'
import {
  getPlayers,
  getTeams,
  getMatches,
  getDrama,
  scrapePlayer,
  scrapeTeam,
  syncPlayers,
  syncTeams,
} from '../api/client'

const TABS = ['Players', 'Teams', 'Matches', 'Drama']

function MatchRow({ match }) {
  return (
    <div className="card flex items-center gap-4 py-3">
      <div className="flex-1 text-right">
        <span className="font-semibold text-white">{match.home_team}</span>
      </div>
      <div className="text-center px-4">
        {match.home_score !== null ? (
          <span className="text-lg font-bold text-primary">
            {match.home_score} - {match.away_score}
          </span>
        ) : (
          <span className="text-muted text-sm">vs</span>
        )}
        <p className="text-xs text-muted mt-0.5">{match.stage}</p>
      </div>
      <div className="flex-1">
        <span className="font-semibold text-white">{match.away_team}</span>
      </div>
      <div className="text-xs text-muted hidden sm:block">{match.tournament}</div>
    </div>
  )
}

export default function KnowledgeBase() {
  const [tab, setTab]                 = useState('Players')
  const [search, setSearch]           = useState('')
  const [players, setPlayers]         = useState([])
  const [teams, setTeams]             = useState([])
  const [matches, setMatches]         = useState([])
  const [drama, setDrama]             = useState([])
  const [loading, setLoading]         = useState(false)
  const [syncing, setSyncing]         = useState(false)
  const [profileOpen, setProfileOpen] = useState(false)
  const [saving, setSaving]           = useState(false)
  const [profileName, setProfileName] = useState('')
  const [tier, setTier]               = useState('')
  const [priority, setPriority]       = useState('')
  const [status, setStatus]           = useState('')

  const loadTab = (target = tab) => {
    setLoading(true)
    const fetchers = {
      Players: () => getPlayers().then(r => setPlayers(r.data)),
      Teams:   () => getTeams().then(r => setTeams(r.data)),
      Matches: () => getMatches().then(r => setMatches(r.data)),
      Drama:   () => getDrama().then(r => setDrama(r.data)),
    }
    return fetchers[target]?.()
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadTab(tab)
  }, [tab])

  const handleSync = async () => {
    setSyncing(true)
    setStatus('')
    try {
      const playerResult = await syncPlayers()
      const teamResult = await syncTeams()
      if (tab === 'Players' || tab === 'Teams') {
        await loadTab(tab)
      }
      const playerCount = playerResult.data?.updated ?? 0
      const teamCount = teamResult.data?.updated ?? 0
      setStatus(`Synced ${playerCount} players and ${teamCount} clubs.`)
    } catch {
      setStatus('Sync failed.')
    } finally {
      setSyncing(false)
    }
  }

  const handleAddProfile = async e => {
    e.preventDefault()
    const name = profileName.trim()
    if (!name || !['Players', 'Teams'].includes(tab)) return

    setSaving(true)
    setStatus('')
    try {
      if (tab === 'Players') {
        await scrapePlayer({ name, tier: tier || undefined })
      } else {
        await scrapeTeam({ name, priority: priority || undefined })
      }
      setProfileName('')
      setTier('')
      setPriority('')
      setProfileOpen(false)
      await loadTab(tab)
      setStatus(`${tab === 'Players' ? 'Player' : 'Club'} saved.`)
    } catch {
      setStatus(`${tab === 'Players' ? 'Player' : 'Club'} not found.`)
    } finally {
      setSaving(false)
    }
  }

  const q = search.toLowerCase()

  const filteredPlayers = players.filter(p =>
    !q || p.name?.toLowerCase().includes(q) || p.current_club?.toLowerCase().includes(q)
  )
  const filteredTeams = teams.filter(t =>
    !q || t.name?.toLowerCase().includes(q) || t.country?.toLowerCase().includes(q)
  )
  const filteredMatches = matches.filter(m =>
    !q || m.home_team?.toLowerCase().includes(q) || m.away_team?.toLowerCase().includes(q)
  )
  const filteredDrama = drama.filter(d =>
    !q || d.title?.toLowerCase().includes(q) || d.summary?.toLowerCase().includes(q)
  )

  return (
    <div>
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between mb-6">
        <h1 className="text-2xl font-bold text-primary">Knowledge Base</h1>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={handleSync}
            disabled={syncing}
            className="btn-primary inline-flex items-center gap-2 disabled:opacity-60"
          >
            <RefreshCw size={16} className={syncing ? 'animate-spin' : ''} />
            {syncing ? 'Syncing' : 'Sync all'}
          </button>
          {['Players', 'Teams'].includes(tab) && (
            <button
              type="button"
              onClick={() => setProfileOpen(v => !v)}
              className="btn-ghost inline-flex items-center gap-2"
            >
              {profileOpen ? <X size={16} /> : <Plus size={16} />}
              {profileOpen ? 'Close' : `Add ${tab === 'Players' ? 'player' : 'club'}`}
            </button>
          )}
        </div>
      </div>

      {status && (
        <div className="mb-4 border border-border bg-card rounded-lg px-4 py-3 text-sm text-muted">
          {status}
        </div>
      )}

      {profileOpen && ['Players', 'Teams'].includes(tab) && (
        <form onSubmit={handleAddProfile} className="card mb-6 grid gap-3 md:grid-cols-[minmax(0,1fr)_180px_auto]">
          <input
            type="text"
            value={profileName}
            onChange={e => setProfileName(e.target.value)}
            placeholder={tab === 'Players' ? 'Player name' : 'Club name'}
            className="bg-background border border-border rounded-lg px-3 py-2 text-white text-sm focus:border-primary outline-none"
          />
          {tab === 'Players' ? (
            <select
              value={tier}
              onChange={e => setTier(e.target.value)}
              className="bg-background border border-border rounded-lg px-3 py-2 text-white text-sm focus:border-primary outline-none"
            >
              <option value="">Tier</option>
              <option value="tier1">Tier 1</option>
              <option value="tier2">Tier 2</option>
              <option value="tier3">Tier 3</option>
            </select>
          ) : (
            <select
              value={priority}
              onChange={e => setPriority(e.target.value)}
              className="bg-background border border-border rounded-lg px-3 py-2 text-white text-sm focus:border-primary outline-none"
            >
              <option value="">Priority</option>
              <option value="High">High</option>
              <option value="Medium">Medium</option>
              <option value="Low">Low</option>
            </select>
          )}
          <button
            type="submit"
            disabled={saving || !profileName.trim()}
            className="btn-primary inline-flex items-center justify-center gap-2 disabled:opacity-60"
          >
            <Plus size={16} />
            {saving ? 'Saving' : 'Save'}
          </button>
        </form>
      )}

      {/* Search */}
      <div className="relative mb-6">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
        <input
          type="text"
          placeholder="Search players, teams, drama..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="w-full bg-card border border-border rounded-xl pl-10 pr-4 py-3 text-white text-sm focus:border-primary outline-none"
        />
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 border-b border-border">
        {TABS.map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
              tab === t
                ? 'border-primary text-primary'
                : 'border-transparent text-muted hover:text-white'
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {loading && <p className="text-muted text-sm">Loading...</p>}

      {!loading && tab === 'Players' && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredPlayers.length
            ? filteredPlayers.map(p => <PlayerCard key={p.id} player={p} />)
            : <p className="text-muted text-sm col-span-3">No players found.</p>
          }
        </div>
      )}

      {!loading && tab === 'Teams' && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredTeams.length
            ? filteredTeams.map(t => <TeamCard key={t.id} team={t} />)
            : <p className="text-muted text-sm col-span-3">No teams found.</p>
          }
        </div>
      )}

      {!loading && tab === 'Matches' && (
        <div className="space-y-2">
          {filteredMatches.length
            ? filteredMatches.map(m => <MatchRow key={m.id} match={m} />)
            : <p className="text-muted text-sm">No matches found.</p>
          }
        </div>
      )}

      {!loading && tab === 'Drama' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {filteredDrama.length
            ? filteredDrama.map(d => <DramaCard key={d.id} drama={d} />)
            : <p className="text-muted text-sm col-span-2">No drama entries found.</p>
          }
        </div>
      )}
    </div>
  )
}
