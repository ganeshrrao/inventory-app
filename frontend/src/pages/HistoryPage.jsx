import { useState, useEffect, useCallback } from 'react';
import { apiFetch } from '../api.js';
import { ACTION_META, formatRelative, formatAbsolute, ChangeDetail } from '../historyUtils.jsx';

const FILTERS = [
  { value: '',                  label: 'All Actions'  },
  { value: 'created',           label: 'Created'      },
  { value: 'updated',           label: 'Updated'      },
  { value: 'deleted',           label: 'Deleted'      },
  { value: 'quantity_adjusted', label: 'Qty Adjusted' },
];

export default function HistoryPage() {
  const [entries, setEntries]     = useState([]);
  const [total, setTotal]         = useState(0);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState('');
  const [actionFilter, setFilter] = useState('');
  const [skip, setSkip]           = useState(0);

  const PAGE = 50;

  const load = useCallback(async (newSkip = 0, filter = actionFilter) => {
    setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams({ skip: newSkip, limit: PAGE });
      if (filter) params.set('action', filter);
      const data = await apiFetch(`/history?${params}`);
      if (newSkip === 0) {
        setEntries(data.entries);
      } else {
        setEntries(prev => [...prev, ...data.entries]);
      }
      setTotal(data.total);
      setSkip(newSkip);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [actionFilter]);

  useEffect(() => { load(0, actionFilter); }, [actionFilter]);

  const hasMore = entries.length < total;

  return (
    <div className="page-container">
      <div className="page-header">
        <h1 className="page-title">Activity History</h1>
        <p className="page-subtitle">{total} event{total !== 1 ? 's' : ''} recorded</p>
      </div>

      <div className="hist-toolbar">
        {FILTERS.map(f => (
          <button
            key={f.value}
            className={`hist-filter-btn${actionFilter === f.value ? ' active' : ''}`}
            onClick={() => setFilter(f.value)}
          >
            {f.label}
          </button>
        ))}
      </div>

      {error && <div className="error-banner">{error}</div>}

      {!loading && entries.length === 0 && (
        <div className="empty-state">
          <p>No history yet. Changes to inventory items will appear here.</p>
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
                <div className="hist-entry-title">
                  <span className="hist-item-name">{entry.item_name}</span>
                  {entry.action === 'deleted' && (
                    <span className="hist-deleted-tag">deleted</span>
                  )}
                </div>
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

      {loading && <div className="loading-spinner">Loading…</div>}

      {hasMore && !loading && (
        <div className="hist-load-more">
          <button className="btn-secondary" onClick={() => load(skip + PAGE)}>
            Load more ({total - entries.length} remaining)
          </button>
        </div>
      )}
    </div>
  );
}
