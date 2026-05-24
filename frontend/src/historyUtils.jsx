export const ACTION_META = {
  created:           { label: 'Created',      cls: 'hist-badge-created' },
  updated:           { label: 'Updated',      cls: 'hist-badge-updated' },
  deleted:           { label: 'Deleted',      cls: 'hist-badge-deleted' },
  quantity_adjusted: { label: 'Qty Adjusted', cls: 'hist-badge-qty'     },
};

export function formatRelative(iso) {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1)   return '< 1m ago';
  if (m < 60)  return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24)  return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export function formatAbsolute(iso) {
  return new Date(iso).toLocaleString();
}

export function ChangeDetail({ changes, action }) {
  if (!changes) return null;

  if (action === 'quantity_adjusted') {
    const q = changes.quantity;
    if (!q) return null;
    const delta = q.delta ?? (q.new - q.old);
    const sign  = delta >= 0 ? '+' : '';
    return (
      <span className="hist-change-qty">
        {q.old} → {q.new}
        <span className={`hist-delta ${delta >= 0 ? 'pos' : 'neg'}`}>
          ({sign}{delta})
        </span>
      </span>
    );
  }

  const entries = Object.entries(changes);
  if (entries.length === 0) return null;
  return (
    <ul className="hist-change-list">
      {entries.map(([field, diff]) => (
        <li key={field}>
          <span className="hist-field">{field}</span>
          {diff.old !== null && diff.old !== undefined && (
            <span className="hist-old">{String(diff.old).slice(0, 60)}</span>
          )}
          <span className="hist-arrow">→</span>
          <span className="hist-new">{String(diff.new ?? '').slice(0, 60)}</span>
        </li>
      ))}
    </ul>
  );
}
