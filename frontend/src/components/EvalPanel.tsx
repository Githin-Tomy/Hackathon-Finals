import { useState, useEffect } from 'react'
import { FlaskConical, Play, RefreshCw, TrendingUp, Target, Award } from 'lucide-react'
import {
  RadarChart, PolarGrid, PolarAngleAxis, Radar,
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell
} from 'recharts'
import { fetchEvalResults, runEval, type EvalResult } from '../api/client'

function MetricCard({ label, value, icon: Icon, color }: {
  label: string; value: string; icon: React.ElementType; color: string
}) {
  return (
    <div className="card flex items-center gap-4">
      <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${color}`}>
        <Icon size={18} className="text-white" />
      </div>
      <div>
        <p className="text-xs text-slate-500">{label}</p>
        <p className="text-2xl font-bold text-white">{value}</p>
      </div>
    </div>
  )
}

const SEVERITY_COLORS: Record<number, string> = {
  0: '#4f72f5',
  1: '#22d3ee',
  2: '#a78bfa',
  3: '#f59e0b',
  4: '#ef4444',
}

export default function EvalPage() {
  const [results, setResults] = useState<EvalResult[]>([])
  const [running, setRunning] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchEvalResults().then(setResults).finally(() => setLoading(false))
  }, [])

  const handleRun = async () => {
    setRunning(true)
    try {
      const r = await runEval()
      setResults(r)
    } finally {
      setRunning(false)
    }
  }

  const avgP = results.length ? results.reduce((s, r) => s + r.precision, 0) / results.length : 0
  const avgR = results.length ? results.reduce((s, r) => s + r.recall, 0) / results.length : 0
  const avgF1 = results.length ? results.reduce((s, r) => s + r.f1, 0) / results.length : 0

  const radarData = results.map(r => ({
    fixture: r.fixture_name.replace('.py', '').replace('pr_00', 'PR#'),
    Precision: Math.round(r.precision * 100),
    Recall:    Math.round(r.recall * 100),
    F1:        Math.round(r.f1 * 100),
  }))

  const barData = results.map(r => ({
    name: r.fixture_name.replace('_', '\n').replace('.py', ''),
    TP: r.true_positives,
    FP: r.false_positives,
    FN: r.false_negatives,
  }))

  return (
    <div className="animate-fade-in-up space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white flex items-center gap-2">
            <FlaskConical size={20} className="text-purple-400" />
            Eval Harness
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">Precision / Recall / F1 against 5 synthetic fixtures</p>
        </div>
        <button id="run-eval" onClick={handleRun} disabled={running} className="btn-primary flex items-center gap-2">
          {running
            ? <><RefreshCw size={14} className="animate-spin" /> Running…</>
            : <><Play size={14} /> Run Eval</>
          }
        </button>
      </div>

      {/* Avg metrics */}
      {results.length > 0 && (
        <div className="grid grid-cols-3 gap-4">
          <MetricCard label="Avg Precision" value={`${(avgP * 100).toFixed(1)}%`} icon={Target}     color="bg-brand-500" />
          <MetricCard label="Avg Recall"    value={`${(avgR * 100).toFixed(1)}%`} icon={TrendingUp} color="bg-purple-500" />
          <MetricCard label="Avg F1"        value={`${(avgF1 * 100).toFixed(1)}%`} icon={Award}     color="bg-cyan-600"  />
        </div>
      )}

      {/* Charts */}
      {results.length > 0 && (
        <div className="grid grid-cols-2 gap-5">
          {/* Radar */}
          <div className="card">
            <h3 className="text-sm font-semibold text-slate-300 mb-4">Per-Fixture Radar</h3>
            <ResponsiveContainer width="100%" height={220}>
              <RadarChart data={radarData}>
                <PolarGrid stroke="rgba(255,255,255,0.05)" />
                <PolarAngleAxis dataKey="fixture" tick={{ fill: '#64748b', fontSize: 11 }} />
                <Radar name="Precision" dataKey="Precision" stroke="#4f72f5" fill="#4f72f5" fillOpacity={0.15} />
                <Radar name="Recall"    dataKey="Recall"    stroke="#a78bfa" fill="#a78bfa" fillOpacity={0.15} />
                <Radar name="F1"        dataKey="F1"        stroke="#22d3ee" fill="#22d3ee" fillOpacity={0.15} />
              </RadarChart>
            </ResponsiveContainer>
          </div>

          {/* TP/FP/FN bars */}
          <div className="card">
            <h3 className="text-sm font-semibold text-slate-300 mb-4">TP / FP / FN per Fixture</h3>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={barData} barSize={12}>
                <XAxis dataKey="name" tick={{ fill: '#64748b', fontSize: 10 }} />
                <YAxis tick={{ fill: '#64748b', fontSize: 10 }} />
                <Tooltip
                  contentStyle={{ background: '#1c2036', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8 }}
                  labelStyle={{ color: '#94a3b8' }}
                />
                <Bar dataKey="TP" fill="#22c55e" radius={[2, 2, 0, 0]} name="True Positives" />
                <Bar dataKey="FP" fill="#ef4444" radius={[2, 2, 0, 0]} name="False Positives" />
                <Bar dataKey="FN" fill="#f59e0b" radius={[2, 2, 0, 0]} name="False Negatives" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Results table */}
      {results.length > 0 && (
        <div className="card overflow-hidden p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/5 text-xs text-slate-500 uppercase tracking-wider">
                {['Fixture', 'Precision', 'Recall', 'F1', 'TP', 'FP', 'FN'].map(h => (
                  <th key={h} className="text-left px-5 py-3 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {results.map((r, i) => (
                <tr key={r.id} id={`eval-row-${r.id}`}
                  className="border-b border-white/5 last:border-0 hover:bg-white/3 transition-colors">
                  <td className="px-5 py-3 font-mono text-xs text-brand-400">{r.fixture_name}</td>
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-2">
                      <div className="w-16 h-1 bg-white/10 rounded-full overflow-hidden">
                        <div className="h-full bg-brand-500 rounded-full" style={{ width: `${r.precision * 100}%` }} />
                      </div>
                      <span className="text-slate-200">{(r.precision * 100).toFixed(1)}%</span>
                    </div>
                  </td>
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-2">
                      <div className="w-16 h-1 bg-white/10 rounded-full overflow-hidden">
                        <div className="h-full bg-purple-500 rounded-full" style={{ width: `${r.recall * 100}%` }} />
                      </div>
                      <span className="text-slate-200">{(r.recall * 100).toFixed(1)}%</span>
                    </div>
                  </td>
                  <td className="px-5 py-3 font-semibold text-cyan-400">{(r.f1 * 100).toFixed(1)}%</td>
                  <td className="px-5 py-3 text-green-400 font-medium">{r.true_positives}</td>
                  <td className="px-5 py-3 text-red-400 font-medium">{r.false_positives}</td>
                  <td className="px-5 py-3 text-orange-400 font-medium">{r.false_negatives}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Empty state */}
      {!loading && results.length === 0 && (
        <div className="card text-center py-16">
          <FlaskConical size={40} className="text-slate-600 mx-auto mb-3" />
          <p className="text-slate-400 font-medium">No eval results yet</p>
          <p className="text-slate-600 text-sm mt-1 mb-5">Click "Run Eval" to analyse the synthetic fixtures</p>
          <button id="run-eval-empty" onClick={handleRun} disabled={running} className="btn-primary mx-auto">
            {running ? 'Running…' : 'Run Eval Now'}
          </button>
        </div>
      )}
    </div>
  )
}
