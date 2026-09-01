import React, { useState } from 'react'
import { Settings as SettingsIcon, User, Bell, Sliders, Info, Check } from 'lucide-react'

function Toggle({ checked, onChange }) {
  return (
    <button
      onClick={() => onChange(!checked)}
      className={`w-10 h-[22px] rounded-full transition-colors relative flex-shrink-0 ${checked ? 'bg-primary-600' : 'bg-gray-300'}`}
    >
      <span
        className={`absolute top-0.5 w-[18px] h-[18px] bg-white rounded-full shadow transition-transform ${checked ? 'translate-x-[22px]' : 'translate-x-0.5'}`}
      />
    </button>
  )
}

export default function Settings() {
  const [name, setName] = useState('Student Account')
  const [email] = useState('')
  const [saved, setSaved] = useState(false)
  const [notifs, setNotifs] = useState({ corrections: true, processing: true, weeklyDigest: false })
  const [defaultDifficulty, setDefaultDifficulty] = useState('medium')
  const [autoJumpEvidence, setAutoJumpEvidence] = useState(true)

  const handleSave = (e) => {
    e.preventDefault()
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6 pb-8">
      <div className="border-b border-gray-200 pb-4">
        <h1 className="text-2xl font-extrabold text-ink-900 flex items-center gap-2">
          <SettingsIcon className="w-6 h-6 text-primary-600" />
          Settings
        </h1>
        <p className="text-sm text-ink-500 mt-1">Manage your profile and study preferences.</p>
      </div>

      <form onSubmit={handleSave} className="space-y-6">
        <div className="card space-y-4">
          <h2 className="text-sm font-bold text-ink-900 flex items-center gap-2">
            <User className="w-4 h-4 text-primary-600" /> Profile
          </h2>
          <div className="grid sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-ink-600 mb-1">Full Name</label>
              <input value={name} onChange={(e) => setName(e.target.value)} className="input" />
            </div>
            <div>
              <label className="block text-xs font-semibold text-ink-600 mb-1">Email</label>
              <input value={email} disabled placeholder="you@university.edu" className="input bg-gray-50 text-ink-400" />
            </div>
          </div>
        </div>

        <div className="card space-y-4">
          <h2 className="text-sm font-bold text-ink-900 flex items-center gap-2">
            <Bell className="w-4 h-4 text-primary-600" /> Notifications
          </h2>
          <div className="space-y-3">
            {[
              { key: 'corrections', label: 'Knowledge correction alerts', desc: 'Notify me when an instructor correction is detected.' },
              { key: 'processing', label: 'Processing complete', desc: 'Notify me when a source finishes indexing.' },
              { key: 'weeklyDigest', label: 'Weekly revision digest', desc: 'A weekly summary of what to review before exams.' },
            ].map((item) => (
              <div key={item.key} className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-sm font-medium text-ink-800">{item.label}</p>
                  <p className="text-xs text-ink-500">{item.desc}</p>
                </div>
                <Toggle checked={notifs[item.key]} onChange={(v) => setNotifs((p) => ({ ...p, [item.key]: v }))} />
              </div>
            ))}
          </div>
        </div>

        <div className="card space-y-4">
          <h2 className="text-sm font-bold text-ink-900 flex items-center gap-2">
            <Sliders className="w-4 h-4 text-primary-600" /> Study Preferences
          </h2>
          <div className="flex items-center justify-between gap-4">
            <div>
              <label className="text-sm font-medium text-ink-800 block">Default quiz difficulty</label>
              <p className="text-xs text-ink-500">Used when generating a new quiz.</p>
            </div>
            <select value={defaultDifficulty} onChange={(e) => setDefaultDifficulty(e.target.value)} className="select">
              <option value="easy">Easy</option>
              <option value="medium">Medium</option>
              <option value="hard">Hard</option>
            </select>
          </div>
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-sm font-medium text-ink-800">Auto-jump to evidence timestamp</p>
              <p className="text-xs text-ink-500">Automatically seek the video when you click a citation.</p>
            </div>
            <Toggle checked={autoJumpEvidence} onChange={setAutoJumpEvidence} />
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button type="submit" className="btn-primary px-5 py-2 text-sm font-semibold flex items-center gap-1.5">
            {saved ? <Check className="w-4 h-4" /> : null}
            {saved ? 'Saved' : 'Save Changes'}
          </button>
          <span className="text-xs text-ink-400 flex items-center gap-1">
            <Info className="w-3.5 h-3.5" /> Settings are stored locally for this demo session.
          </span>
        </div>
      </form>
    </div>
  )
}
