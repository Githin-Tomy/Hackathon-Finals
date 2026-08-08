import { useState, useEffect } from 'react'
import { ChevronDown, Cpu, Sparkles, Check, AlertCircle, Loader } from 'lucide-react'
import { fetchModelConfig, updateModelConfig, type ModelConfig, type ModelOption } from '../api/client'

const PROVIDER_META: Record<string, { label: string; icon: string; color: string; ring: string }> = {
  openai: {
    label: 'OpenAI',
    icon: '⬡',
    color: 'text-emerald-400',
    ring:  'border-emerald-500/40 bg-emerald-500/10',
  },
  google: {
    label: 'Google Gemini',
    icon: '✦',
    color: 'text-blue-400',
    ring:  'border-blue-500/40 bg-blue-500/10',
  },
}

export default function ModelSelector() {
  const [config, setConfig]     = useState<ModelConfig | null>(null)
  const [open, setOpen]         = useState(false)
  const [saving, setSaving]     = useState(false)
  const [saved, setSaved]       = useState(false)
  const [error, setError]       = useState('')

  // Pending selection (not yet confirmed)
  const [pendingProvider, setPendingProvider] = useState<string>('')
  const [pendingModel, setPendingModel]       = useState<string>('')

  useEffect(() => {
    fetchModelConfig()
      .then(c => {
        setConfig(c)
        setPendingProvider(c.provider)
        setPendingModel(c.model)
      })
      .catch(() => setError('Could not load model config'))
  }, [])

  const handleSave = async () => {
    if (!config) return
    if (pendingProvider === config.provider && pendingModel === config.model) {
      setOpen(false)
      return
    }
    setSaving(true)
    setError('')
    try {
      const updated = await updateModelConfig(pendingProvider, pendingModel)
      setConfig(updated)
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
      setOpen(false)
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Failed to update model')
    } finally {
      setSaving(false)
    }
  }

  if (!config) {
    return (
      <div className="px-3 py-2 flex items-center gap-2 text-xs text-slate-500">
        <Loader size={11} className="animate-spin" /> Loading model…
      </div>
    )
  }

  const meta = PROVIDER_META[config.provider] || PROVIDER_META.openai
  const allModels: ModelOption[] = config.available_models[pendingProvider] || []

  return (
    <div className="relative">
      {/* Trigger button */}
      <button
        id="model-selector-trigger"
        onClick={() => setOpen(o => !o)}
        className={`w-full flex items-center gap-2 px-3 py-2.5 rounded-lg border text-xs 
                    transition-all duration-150 ${open ? meta.ring : 'border-white/10 bg-white/3 hover:bg-white/5'}`}
      >
        <span className={`text-base leading-none ${meta.color}`}>{meta.icon}</span>
        <div className="flex-1 text-left min-w-0">
          <p className={`font-semibold truncate ${meta.color}`}>{meta.label}</p>
          <p className="text-slate-500 font-mono truncate">{config.model}</p>
        </div>
        {saved
          ? <Check size={12} className="text-green-400 shrink-0" />
          : <ChevronDown size={12} className={`text-slate-500 shrink-0 transition-transform ${open ? 'rotate-180' : ''}`} />
        }
      </button>

      {/* Dropdown panel */}
      {open && (
        <div className="absolute bottom-full left-0 right-0 mb-2 z-50 
                        bg-surface-700 border border-white/10 rounded-xl shadow-2xl 
                        shadow-black/50 overflow-hidden animate-fade-in-up">
          
          {/* Provider tabs */}
          <div className="flex border-b border-white/10">
            {Object.entries(PROVIDER_META).map(([pid, pm]) => (
              <button
                key={pid}
                id={`provider-tab-${pid}`}
                onClick={() => {
                  setPendingProvider(pid)
                  // Auto-select first model of this provider
                  const models = config.available_models[pid] || []
                  if (models.length) setPendingModel(models[0].id)
                }}
                className={`flex-1 px-3 py-2.5 text-xs font-medium flex items-center justify-center gap-1.5
                            transition-colors ${
                              pendingProvider === pid
                                ? `${pm.color} border-b-2 border-current bg-white/3`
                                : 'text-slate-500 hover:text-slate-300'
                            }`}
              >
                <span className="text-sm">{pm.icon}</span> {pm.label}
              </button>
            ))}
          </div>

          {/* Model list */}
          <div className="p-2 space-y-1 max-h-52 overflow-y-auto">
            {allModels.map(m => {
              const isActive = pendingModel === m.id && pendingProvider === config.provider
              const isPending = pendingModel === m.id
              return (
                <button
                  key={m.id}
                  id={`model-option-${m.id}`}
                  onClick={() => setPendingModel(m.id)}
                  className={`w-full text-left px-3 py-2.5 rounded-lg flex items-start gap-2.5 
                              transition-colors text-xs ${
                                isPending
                                  ? 'bg-brand-500/15 border border-brand-500/30'
                                  : 'hover:bg-white/5 border border-transparent'
                              }`}
                >
                  <div className="mt-0.5">
                    {isPending
                      ? <div className="w-3.5 h-3.5 rounded-full bg-brand-500 flex items-center justify-center">
                          <Check size={8} className="text-white" />
                        </div>
                      : <div className="w-3.5 h-3.5 rounded-full border border-white/20" />
                    }
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span className="font-semibold text-slate-100">{m.label}</span>
                      {isActive && (
                        <span className="px-1.5 py-0.5 rounded text-[9px] font-medium bg-green-500/20 text-green-400 border border-green-500/30">
                          ACTIVE
                        </span>
                      )}
                    </div>
                    <span className="text-slate-500 font-mono">{m.id}</span>
                    <p className="text-slate-500 mt-0.5">{m.description}</p>
                  </div>
                </button>
              )
            })}
          </div>

          {/* Error */}
          {error && (
            <div className="px-3 py-2 flex items-center gap-2 text-xs text-red-400 border-t border-white/10">
              <AlertCircle size={11} /> {error}
            </div>
          )}

          {/* Actions */}
          <div className="p-2 border-t border-white/10 flex gap-2">
            <button
              onClick={() => { setOpen(false); setPendingProvider(config.provider); setPendingModel(config.model) }}
              className="flex-1 py-2 rounded-lg text-xs text-slate-400 hover:text-slate-200 hover:bg-white/5 transition-colors"
            >
              Cancel
            </button>
            <button
              id="model-apply-btn"
              onClick={handleSave}
              disabled={saving}
              className="flex-1 py-2 rounded-lg text-xs font-semibold bg-brand-500 hover:bg-brand-600 
                         text-white transition-colors disabled:opacity-50 flex items-center justify-center gap-1.5"
            >
              {saving ? <><Loader size={11} className="animate-spin" /> Applying…</> : 'Apply Model'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
