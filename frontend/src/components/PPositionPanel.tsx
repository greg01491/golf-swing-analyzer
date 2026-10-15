import type { PPosition } from '../api'

interface Props {
  positions: PPosition[]
  selected: string | null
  onSelect: (position: PPosition) => void
  showIdeal: boolean
  onToggleIdeal: (show: boolean) => void
  reliable: boolean
}

export default function PPositionPanel({
  positions,
  selected,
  onSelect,
  showIdeal,
  onToggleIdeal,
  reliable,
}: Props) {
  const current = positions.find((p) => p.name === selected)
  const unavailableCount = positions.filter((position) => position.available === false).length
  const estimatedCount = positions.filter(
    (position) => position.available !== false && position.detected === false,
  ).length

  return (
    <div className="panel">
      <h3>P-positions</h3>
      <p className="muted">
        The 10 checkpoints of golf's "P-System" swing framework. Positions are approximated
        from body pose (no club tracking) — click one to freeze the video and skeleton there.
      </p>
      {!reliable && (
        <p className="muted" role="status">
          Low tracking quality can make detected checkpoint frames imprecise. Available
          checkpoints remain selectable for review.
        </p>
      )}
      {unavailableCount > 0 && (
        <p className="muted" role="status">
          {unavailableCount} checkpoint{unavailableCount === 1 ? ' was' : 's were'} not detected
          from the body-pose proxy and cannot be selected.
        </p>
      )}
      {estimatedCount > 0 && (
        <p className="muted" role="status">
          {estimatedCount} checkpoint{estimatedCount === 1 ? ' uses' : 's use'} a phase-progress
          estimate because the proxy target wasn’t crossed.
        </p>
      )}
      <div className="p-position-strip">
        {positions.map((p) => (
          <button
            key={p.name}
            className={p.name === selected ? 'active' : ''}
            disabled={p.available === false}
            title={p.unavailable_reason ?? p.estimate_reason ?? undefined}
            onClick={() => onSelect(p)}
          >
            <span className="p-name">{p.name}</span>
            <span className="p-label">{p.label}</span>
            {p.available === false && <span className="p-unavailable">not detected</span>}
            {p.available !== false && p.detected === false && (
              <span className="p-estimated">estimated</span>
            )}
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
