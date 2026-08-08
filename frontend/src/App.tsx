import { Routes, Route, NavLink } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { GitPullRequest, FlaskConical, Shield, LayoutDashboard } from 'lucide-react'
import PRListPage from './components/PRList'
import PRDetailPage from './components/DiffViewer'
import EvalPage from './components/EvalPanel'
import DashboardPage from './components/Dashboard'
import PipelineDetailPage from './components/PipelineDetail'


function Sidebar() {
  const navItems = [
    { to: '/',     icon: LayoutDashboard, label: 'Dashboard' },
    { to: '/prs',  icon: GitPullRequest, label: 'Pull Requests' },
  ]

  return (
    <aside className="w-64 shrink-0 bg-surface-800 border-r border-white/5 flex flex-col">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-white/5">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-brand-500 flex items-center justify-center shadow-lg shadow-brand-500/40">
            <Shield size={16} className="text-white" />
          </div>
          <div>
            <p className="text-sm font-semibold text-white">CodeReview AI</p>
            <p className="text-[10px] text-slate-500">Multi-Agent · LangGraph</p>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 p-3 space-y-1">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 ${
                isActive
                  ? 'bg-brand-500/20 text-brand-400 border border-brand-500/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
              }`
            }
          >
            <Icon size={16} />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Active Model Display */}
      <div className="p-3 border-t border-white/5">
        <p className="text-[10px] text-slate-600 uppercase tracking-wider font-medium px-1 mb-1">
          Active AI Engine
        </p>
        <div className="px-3 py-2 rounded-lg bg-surface-700 border border-white/10 text-xs">
          <p className="font-semibold text-emerald-400">OpenAI / Custom GPT</p>
          <p className="text-slate-500 font-mono text-[11px]">genailab.tcs.in</p>
        </div>
      </div>

      {/* Footer */}
      <div className="px-3 pb-3">
        <p className="text-[10px] text-slate-700 text-center">Hackathon MVP · v2.0</p>
      </div>
    </aside>
  )
}

export default function App() {
  return (
    <div className="h-screen flex overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden bg-surface-900">
        <main className="flex-1 overflow-y-auto p-8">
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/prs" element={<PRListPage />} />
            <Route path="/pr/:id" element={<PRDetailPage />} />
            <Route path="/pr/:id/pipeline" element={<PipelineDetailPage />} />
            <Route path="/eval" element={<EvalPage />} />
          </Routes>
        </main>
      </div>
    </div>
  )
}
