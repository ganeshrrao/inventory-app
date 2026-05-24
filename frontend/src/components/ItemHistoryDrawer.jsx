import { useState, useEffect } from 'react';
import { apiFetch } from '../api.js';
import { ACTION_META, formatRelative, formatAbsolute, ChangeDetail } from '../historyUtils.jsx';

export default function ItemHistoryDrawer({ item, onClose }) {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState('');

  useEffect(() => {
    setLoading(true);
    setError('');
    apiFetch(`/items/${item.id}/history`)
      .then(setEntries)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [item.id]);

  return (
    <>
      <div className="drawer-overlay" onClick={onClose} />
      <div className="drawer">
        <div className="drawer-header">
          <div>
            <div className="drawer-title">{item.name}</div>
            <div className="drawer-subtitle">Item history</div>
          </div>
          <button className="drawer-close" onClick={onClose} aria-label="Close">✕</button>
        </div>

        <div className="drawer-body">
          {loading && <div className="empty-state"><div className="spinner" /></div>}
          {error   && <div className="error-banner">{error}</div>}

          {!loading && !error && entries.length === 0 && (
            <div className="empty-state">
              <p>No history recorded for this item yet.</p>
            </div>
          )}

          <div className="hist-feed">
            {entries.map(entry => {
              const meta = ACTION_META[entry.action] ?? { label: entry.action, cls: 'hist-badge-updated' };
              return (
                <div key={entry.id} className="hist-entry">
                  <div className="hist-entry-left">
                    <span className={`hist-badge ${meta.cls}`}>{meta.label}</span>
                  </div>
                  <div className="hist-entry-body">
                    {entry.user_email && (
                      <div className="hist-user">{entry.user_email}</div>
                    )}
                    <ChangeDetail changes={entry.changes} action={entry.action} />
                  </div>
                  <div className="hist-entry-time" title={formatAbsolute(entry.created_at)}>
                    {formatRelative(entry.created_at)}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </>
  );
}
