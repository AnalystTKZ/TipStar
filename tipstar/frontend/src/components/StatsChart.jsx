import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import { theme } from '../styles/theme'

const COLORS = [theme.primary, theme.warning, '#22C55E', '#EF4444']

export function PostsOverTimeChart({ data }) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={data} margin={{ top: 5, right: 10, bottom: 5, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={theme.border} />
        <XAxis dataKey="date" tick={{ fill: theme.muted, fontSize: 11 }} />
        <YAxis tick={{ fill: theme.muted, fontSize: 11 }} />
        <Tooltip
          contentStyle={{ background: theme.card, border: `1px solid ${theme.border}`, borderRadius: 8 }}
          labelStyle={{ color: theme.primary }}
        />
        <Line type="monotone" dataKey="count" stroke={theme.primary} strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  )
}

export function PostTypeChart({ data }) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <PieChart>
        <Pie data={data} dataKey="count" nameKey="type" cx="50%" cy="50%" outerRadius={80} label>
          {data.map((_, i) => (
            <Cell key={i} fill={COLORS[i % COLORS.length]} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{ background: theme.card, border: `1px solid ${theme.border}`, borderRadius: 8 }}
        />
        <Legend wrapperStyle={{ color: theme.muted, fontSize: 12 }} />
      </PieChart>
    </ResponsiveContainer>
  )
}

export function CoverageBarChart({ data }) {
  const chartData = [
    { name: 'World Cup', value: data.world_cup },
    { name: 'Regular', value: data.regular },
  ]
  return (
    <ResponsiveContainer width="100%" height={180}>
      <BarChart data={chartData} margin={{ top: 5, right: 10, bottom: 5, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={theme.border} />
        <XAxis dataKey="name" tick={{ fill: theme.muted, fontSize: 12 }} />
        <YAxis tick={{ fill: theme.muted, fontSize: 12 }} />
        <Tooltip contentStyle={{ background: theme.card, border: `1px solid ${theme.border}`, borderRadius: 8 }} />
        <Bar dataKey="value" fill={theme.primary} radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}

export function TopPlayersChart({ data }) {
  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data} layout="vertical" margin={{ top: 5, right: 30, bottom: 5, left: 80 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={theme.border} />
        <XAxis type="number" tick={{ fill: theme.muted, fontSize: 11 }} />
        <YAxis dataKey="player" type="category" tick={{ fill: theme.muted, fontSize: 11 }} width={80} />
        <Tooltip contentStyle={{ background: theme.card, border: `1px solid ${theme.border}`, borderRadius: 8 }} />
        <Bar dataKey="mentions" fill={theme.warning} radius={[0, 4, 4, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}
