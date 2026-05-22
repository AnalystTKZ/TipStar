import { useEffect, useState } from 'react'
import {
  PostsOverTimeChart,
  PostTypeChart,
  CoverageBarChart,
  TopPlayersChart,
} from '../components/StatsChart'
import {
  getAnalyticsSummary,
  getPostsOverTime,
  getCoverageRatio,
  getPostTypeBreakdown,
  getTopPlayers,
} from '../api/client'

function MetricCard({ label, value, sub }) {
  return (
    <div className="card text-center">
      <p className="text-3xl font-bold text-primary">{value ?? '--'}</p>
      <p className="text-sm text-white mt-1">{label}</p>
      {sub && <p className="text-xs text-muted mt-0.5">{sub}</p>}
    </div>
  )
}

export default function Analytics() {
  const [summary, setSummary]     = useState(null)
  const [overtime, setOvertime]   = useState([])
  const [coverage, setCoverage]   = useState(null)
  const [types, setTypes]         = useState([])
  const [topPlayers, setTopPlayers] = useState([])

  useEffect(() => {
    getAnalyticsSummary().then(r => setSummary(r.data)).catch(() => {})
    getPostsOverTime().then(r => setOvertime(r.data)).catch(() => {})
    getCoverageRatio().then(r => setCoverage(r.data)).catch(() => {})
    getPostTypeBreakdown().then(r => setTypes(r.data)).catch(() => {})
    getTopPlayers().then(r => setTopPlayers(r.data)).catch(() => {})
  }, [])

  const approvalRate = summary
    ? Math.round((summary.approved / (summary.approved + summary.rejected || 1)) * 100)
    : null

  return (
    <div>
      <h1 className="text-2xl font-bold text-primary mb-6">Analytics</h1>

      {/* Metric row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <MetricCard label="Generated Today"  value={summary?.total_today} />
        <MetricCard label="Approved All Time" value={summary?.approved} />
        <MetricCard label="Rejected All Time" value={summary?.rejected} />
        <MetricCard label="Approval Rate" value={approvalRate !== null ? `${approvalRate}%` : null} />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card">
          <h2 className="text-sm font-semibold text-muted uppercase tracking-wider mb-4">Posts Generated Over Time</h2>
          {overtime.length ? <PostsOverTimeChart data={overtime} /> : <p className="text-muted text-sm">No data yet.</p>}
        </div>

        <div className="card">
          <h2 className="text-sm font-semibold text-muted uppercase tracking-wider mb-4">Post Type Breakdown</h2>
          {types.length ? <PostTypeChart data={types} /> : <p className="text-muted text-sm">No data yet.</p>}
        </div>

        <div className="card">
          <h2 className="text-sm font-semibold text-muted uppercase tracking-wider mb-4">World Cup vs Regular Coverage</h2>
          {coverage ? <CoverageBarChart data={coverage} /> : <p className="text-muted text-sm">No data yet.</p>}
        </div>

        <div className="card">
          <h2 className="text-sm font-semibold text-muted uppercase tracking-wider mb-4">Most Mentioned Players</h2>
          {topPlayers.length ? <TopPlayersChart data={topPlayers} /> : <p className="text-muted text-sm">No data yet.</p>}
        </div>
      </div>

      {/* Top post type callout */}
      {summary?.top_post_type && summary.top_post_type !== 'N/A' && (
        <div className="card mt-6 flex items-center gap-4">
          <p className="text-muted text-sm">Most approved post type:</p>
          <span className="text-primary font-bold capitalize">
            {summary.top_post_type.replace(/_/g, ' ')}
          </span>
        </div>
      )}
    </div>
  )
}
