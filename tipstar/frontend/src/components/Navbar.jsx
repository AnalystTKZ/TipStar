import { NavLink } from 'react-router-dom'
import { LayoutDashboard, Inbox, BookOpen, BarChart2, Clock } from 'lucide-react'

const links = [
  { to: '/command-center', label: 'Command Center', icon: LayoutDashboard },
  { to: '/inbox',          label: 'Approval Inbox', icon: Inbox },
  { to: '/knowledge',      label: 'Knowledge Base', icon: BookOpen },
  { to: '/analytics',      label: 'Analytics',      icon: BarChart2 },
  { to: '/history',        label: 'Post History',   icon: Clock },
]

export default function Navbar() {
  return (
    <nav className="bg-secondary border-b border-border sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 flex items-center justify-between h-16">
        <div className="flex items-center gap-3">
          <span className="text-2xl font-bold text-primary">TipStar</span>
          <span className="text-muted text-sm hidden sm:block">Football Intelligence</span>
        </div>
        <div className="flex items-center gap-1 overflow-x-auto">
          {links.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors whitespace-nowrap ${
                  isActive
                    ? 'bg-primary text-secondary'
                    : 'text-muted hover:text-primary hover:bg-surface'
                }`
              }
            >
              <Icon size={16} />
              <span className="hidden md:block">{label}</span>
            </NavLink>
          ))}
        </div>
      </div>
    </nav>
  )
}
