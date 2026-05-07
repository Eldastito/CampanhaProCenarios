import { Link, useLocation, useNavigate } from 'react-router-dom'
import type { ReactNode } from 'react'
import { useAuth } from '../contexts/AuthContext'

interface NavItem {
  href: string
  label: string
  icon: string
}

const NAV: NavItem[] = [
  { href: '/', label: 'Dashboard', icon: '⬛' },
  { href: '/workspace', label: 'Bancada Mirofish', icon: '🔬' },
  { href: '/scenarios/new', label: 'Novo Cenário', icon: '＋' },
  { href: '/compare', label: 'Comparar', icon: '⇄' },
  { href: '/predictions', label: 'Predições', icon: '◎' },
  { href: '/saved-predictions', label: 'Pred. Salvas', icon: '💾' },
  { href: '/graph', label: 'Grafos', icon: '🕸' },
  { href: '/simulations/new', label: 'Simulações', icon: '▶' },
  { href: '/research', label: 'Pesquisa de Candidatos', icon: '🔍' },
  { href: '/chat', label: 'Chat com Agentes', icon: '🤖' },
]

export default function Layout({ children, wide = false }: { children: ReactNode; wide?: boolean }) {
  const { user, logout } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/login')
  }

  return (
    <div className="min-h-screen flex">
      {/* Sidebar */}
      <aside className="w-64 bg-gray-900 text-white flex flex-col shrink-0">
        {/* Logo */}
        <div className="px-6 py-5 border-b border-gray-700">
          <span className="text-lg font-bold tracking-wide">
            <span className="text-brand-500">FORGE</span>{' '}
            <span className="text-gray-300 font-normal text-sm">Scenario Lab</span>
          </span>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          {NAV.map((item) => {
            const active = location.pathname === item.href
            return (
              <Link
                key={item.href}
                to={item.href}
                className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                  active
                    ? 'bg-brand-700 text-white'
                    : 'text-gray-400 hover:bg-gray-800 hover:text-white'
                }`}
              >
                <span className="text-base">{item.icon}</span>
                {item.label}
              </Link>
            )
          })}
        </nav>

        {/* User info */}
        {user && (
          <div className="px-4 py-4 border-t border-gray-700">
            <p className="text-xs text-gray-400 truncate">{user.email}</p>
            <p className="text-xs text-gray-500 mt-0.5">
              {user.role} · {user.organization_id}
            </p>
            <button
              onClick={handleLogout}
              className="mt-2 text-xs text-gray-400 hover:text-red-400 transition-colors"
            >
              Sair
            </button>
          </div>
        )}
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-auto">
        <div className={wide ? 'px-4 py-4 h-full' : 'max-w-6xl mx-auto px-6 py-8'}>{children}</div>
      </main>
    </div>
  )
}
