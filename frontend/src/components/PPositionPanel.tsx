import type { PPosition } from '../api'

interface Props {
  positions: PPosition[]
  selected: string | null
  onSelect: (position: PPosition) => void
  showIdeal: boolean
  onToggleIdeal: (show: boolean) => void
}

export default function PPositionPanel({
  positions,
  selected,
  onSelect,
  showIdeal,
  onToggleIdeal,
}: Props) {
  const current = positions.find((p) => p.name === selected)

  return (
    <div className="panel">
      <h3>P-positions</h3>
      <p className="muted">
        The 10 checkpoints of golf's "P-System" swing framework. Positions are approximated
        from body pose (no club tracking) — click one to freeze the video and skeleton there.
      </p>
      <div className="p-position-strip">
        {positions.map((p) => (
          <button
            key={p.name}
            className={p.name === selected ? 'active' : ''}
            onClick={() => onSelect(p)}
          >
            <span className="p-name">{p.name}</span>
            <span className="p-label">{p.label}</span>
          </button>
        ))}
      </div>
      {current && (
        <label className="field ideal-toggle">
          show reference overlay ("where you should be" at {current.name})
          <input
            type="checkbox"
            checked={showIdeal}
            onChange={(e) => onToggleIdeal(e.target.checked)}
          />
        </label>
      )}
    </div>
  )
}
