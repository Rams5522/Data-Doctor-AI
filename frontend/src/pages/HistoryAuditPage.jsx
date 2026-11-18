import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import {
  Filter,
  Search,
  Sparkles,
  Check,
  X,
  Wrench,
  RotateCcw,
  Clock,
  Database,
  Shield,
  AlertTriangle,
  ChevronRight,
  ChevronDown,
  ExternalLink
} from 'lucide-react';

const HistoryAuditPage = () => {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filterType, setFilterType] = useState('all');
  const [dateRange, setDateRange] = useState('all');
  const [datasets, setDatasets] = useState([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState(null);

  const [search, setSearch] = useState('');
  const [expandedId, setExpandedId] = useState(null);

  useEffect(() => {
    fetchDatasets();
  }, []);

  const fetchDatasets = async () => {
    try {
      const response = await axios.get('/api/datasets/');
      const data = response.data.value || response.data;
      setDatasets(data);
      if (data.length > 0) setSelectedDatasetId(data[0].id);
    } catch (err) {
      console.error('Failed to fetch datasets:', err);
      setError('Failed to load datasets. Is the backend running?');
    }
  };

  useEffect(() => {
    if (!selectedDatasetId) return;

    fetchHistory();
  }, [selectedDatasetId]);

  const fetchHistory = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await axios.get(`/api/repair/${selectedDatasetId}/repair-history`);
      setHistory(response.data.history || []);
    } catch (err) {
      console.error(err);
      setHistory([]);
      setError(err.response?.data?.detail || 'Could not load repair history.');
    } finally {
      setLoading(false);
    }
  };

  const operationTypes = useMemo(
    () => [
      { id: 'all', name: 'All Operations', icon: '📋' },
      { id: 'upload', name: 'Upload', icon: '📤' },
      { id: 'repair', name: 'Repair', icon: '🔧' },
      { id: 'approve', name: 'Approval', icon: '✅' },
      { id: 'reject', name: 'Rejection', icon: '❌' },
      { id: 'rollback', name: 'Rollback', icon: '⏪' }
    ],
    []
  );

  const filteredHistory = useMemo(() => {
    const normalizedQuery = search.trim().toLowerCase();

    const rangeStart = (d) => {
      const now = new Date();
      const copy = new Date(now);
      if (d === 'today') {
        copy.setHours(0, 0, 0, 0);
        return copy;
      }
      if (d === 'week') {
        copy.setDate(copy.getDate() - 7);
        return copy;
      }
      if (d === 'month') {
        copy.setDate(copy.getDate() - 30);
        return copy;
      }
      return null;
    };

    const start = rangeStart(dateRange);

    return history
      .filter((item) => {
        const typeMatch = filterType === 'all' ? true : item.event_type === filterType;

        let dateMatch = true;
        if (start) {
          const t = new Date(item.performed_at);
          dateMatch = t >= start;
        }

        let queryMatch = true;
        if (normalizedQuery) {
          const haystack = JSON.stringify({
            operation: item.event_data?.operation,
            parameters: item.event_data?.parameters,
            validation_status: item.event_data?.validation_status,
            new_version_id: item.event_data?.new_version_id,
            candidate_id: item.event_data?.candidate_id,
            approved_by: item.event_data?.approved_by
          }).toLowerCase();
          queryMatch = haystack.includes(normalizedQuery) || (item.performed_by || '').toLowerCase().includes(normalizedQuery);
        }

        return typeMatch && dateMatch && queryMatch;
      })
      .sort((a, b) => new Date(b.performed_at) - new Date(a.performed_at));
  }, [history, filterType, dateRange, search]);

  const counts = useMemo(() => {
    const base = history;
    const approved = base.filter((h) => h.event_type === 'approve').length;
    const rejected = base.filter((h) => h.event_type === 'reject').length;
    const repairs = base.filter((h) => h.event_type === 'repair').length;
    const rollbacks = base.filter((h) => h.event_type === 'rollback').length;
    return { total: base.length, approved, rejected, repairs, rollbacks };
  }, [history]);

  const formatEventType = (t) => {
    if (!t) return 'unknown';
    if (t === 'approve') return 'Approval';
    if (t === 'reject') return 'Rejection';
    if (t === 'repair') return 'Repair';
    if (t === 'rollback') return 'Rollback';
    if (t === 'upload') return 'Upload';
    return t;
  };

  const badgeClassFor = (t) => {
    if (t === 'approve') return 'ha-badge success';
    if (t === 'reject') return 'ha-badge danger';
    if (t === 'repair') return 'ha-badge info';
    if (t === 'rollback') return 'ha-badge warning';
    return 'ha-badge neutral';
  };

  const leftIconFor = (t) => {
    if (t === 'approve') return <Check size={16} />;
    if (t === 'reject') return <X size={16} />;
    if (t === 'repair') return <Wrench size={16} />;
    if (t === 'rollback') return <RotateCcw size={16} />;
    return <Shield size={16} />;
  };

  if (loading && !datasets.length) {
    return (
      <div className="ha-page">
        <div className="ha-header">
          <div className="header-badge"><span>🧾</span> HISTORY & AUDIT</div>
          <h1>History & Audit</h1>
          <p>Track repairs, approvals, and dataset versions</p>
        </div>
        <div className="ha-loading">
          <div className="empty-sparkle-box">🧾</div>
          <h3>Loading audit timeline…</h3>
          <p>Fetching datasets and repair events.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="ha-page">
      <div className="ha-header">
        <div>
          <div className="header-badge"><span>🧾</span> HISTORY & AUDIT</div>
          <h1>History & Audit</h1>
          <p>Track all repair operations, approvals, and dataset changes</p>
        </div>
        <div className="ha-header-right">
          <div className="ha-pill">
            <Sparkles size={16} /> {counts.total} events
          </div>
        </div>
      </div>

      {error && (
        <div className="ha-alert error">
          <AlertTriangle size={18} /> {error}
          <button onClick={() => setError(null)} aria-label="Dismiss">✕</button>
        </div>
      )}

      {/* Dataset Selector */}
      {datasets.length > 0 && (
        <section className="ha-section">
          <div className="ha-section-head">
            <h2><Database size={18} /> Dataset</h2>
          </div>
          <div className="ha-row">
            <div className="ha-field">
              <label>Choose dataset to view its audit trail</label>
              <select
                value={selectedDatasetId || ''}
                onChange={(e) => setSelectedDatasetId(parseInt(e.target.value) || null)}
              >
                <option value="">-- Select Dataset --</option>
                {datasets.map((dataset) => (
                  <option key={dataset.id} value={dataset.id}>
                    {dataset.name} {dataset.description ? `(${dataset.description})` : ''}
                  </option>
                ))}
              </select>
            </div>

            <div className="ha-field ha-field-grow">
              <label>Search events</label>
              <div className="ha-search">
                <Search size={16} />
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="operation, candidate_id, validation_status…"
                />
                {search.trim() && (
                  <button className="ha-search-clear" onClick={() => setSearch('')} aria-label="Clear search">✕</button>
                )}
              </div>
            </div>
          </div>
        </section>
      )}

      {!datasets.length && (
        <section className="ha-empty-inline">
          <div className="empty-sparkle-box">📭</div>
          <h3>No datasets available</h3>
          <p>Please upload a dataset first to see history.</p>
        </section>
      )}

      {selectedDatasetId && !loading && (
        <>
          {/* Filters */}
          <section className="ha-section">
            <div className="ha-section-head">
              <h2><Filter size={18} /> Filters</h2>
            </div>

            <div className="ha-filter-grid">
              <div className="ha-field">
                <label>Operation type</label>
                <select value={filterType} onChange={(e) => setFilterType(e.target.value)}>
                  {operationTypes.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.icon} {t.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="ha-field">
                <label>Date range</label>
                <select value={dateRange} onChange={(e) => setDateRange(e.target.value)}>
                  <option value="all">All Time</option>
                  <option value="today">Today</option>
                  <option value="week">Last 7 Days</option>
                  <option value="month">Last 30 Days</option>
                </select>
              </div>

              <div className="ha-field ha-field-actions">
                <button
                  className="outline-button"
                  onClick={() => {
                    setFilterType('all');
                    setDateRange('all');
                    setSearch('');
                  }}
                >
                  Reset filters
                </button>
              </div>
            </div>
          </section>

          {/* KPI cards */}
          <section className="ha-kpi-grid">
            <div className="ha-kpi">
              <div className="ha-kpi-icon blue">🧾</div>
              <div className="ha-kpi-meta">
                <small>Total</small>
                <b>{counts.total}</b>
              </div>
            </div>
            <div className="ha-kpi">
              <div className="ha-kpi-icon green">✅</div>
              <div className="ha-kpi-meta">
                <small>Approved</small>
                <b>{counts.approved}</b>
              </div>
            </div>
            <div className="ha-kpi">
              <div className="ha-kpi-icon red">❌</div>
              <div className="ha-kpi-meta">
                <small>Rejected</small>
                <b>{counts.rejected}</b>
              </div>
            </div>
            <div className="ha-kpi">
              <div className="ha-kpi-icon purple">🔧</div>
              <div className="ha-kpi-meta">
                <small>Repairs</small>
                <b>{counts.repairs}</b>
              </div>
            </div>
          </section>

          {/* Timeline / Table */}
          <section className="ha-section">
            <div className="ha-section-head">
              <h2>Audit Timeline</h2>
              <div className="ha-muted">
                Showing <b>{filteredHistory.length}</b> events
              </div>
            </div>

            {filteredHistory.length === 0 ? (
              <div className="ha-empty">
                <div className="empty-sparkle-box">📭</div>
                <h3>No history records found</h3>
                <p>Try changing filters, or run repairs in Repair Lab to generate audit events.</p>
                <div className="ha-empty-actions">
                  <a className="primary-button" href="/repair-lab">Go to Repair Lab</a>
                  <a className="outline-button" href="/quality-report">Run Quality Check</a>
                </div>
              </div>
            ) : (
              <div className="ha-list">
                {filteredHistory.map((item) => {
                  const isExpanded = expandedId === item.id;
                  const badgeClass = badgeClassFor(item.event_type);
                  const ev = item.event_data || {};

                  return (
                    <div key={item.id} className={`ha-event ${isExpanded ? 'expanded' : ''}`}>
                      <div
                        className="ha-event-top"
                        role="button"
                        tabIndex={0}
                        onClick={() => setExpandedId(isExpanded ? null : item.id)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') setExpandedId(isExpanded ? null : item.id);
                        }}
                      >
                        <div className="ha-event-left">
                          <div className={badgeClass}>
                            {leftIconFor(item.event_type)}
                            <span>{formatEventType(item.event_type)}</span>
                          </div>
                          <div className="ha-event-time">
                            <Clock size={16} /> {item.performed_at ? new Date(item.performed_at).toLocaleString() : 'N/A'}
                          </div>
                        </div>

                        <div className="ha-event-right">
                          <div className="ha-event-summary">
                            <span className="ha-event-chip">op: {ev.operation || '—'}</span>
                            {ev.validation_status && (
                              <span className={`ha-event-chip ${ev.validation_status === 'passed' ? 'ok' : ev.validation_status === 'warning' ? 'warn' : 'bad'}`}>
                                validation: {ev.validation_status}
                              </span>
                            )}
                          </div>

                          <div className="ha-expand">
                            {isExpanded ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
                          </div>
                        </div>
                      </div>

                      {isExpanded && (
                        <div className="ha-event-details">
                          <div className="ha-detail-grid">
                            <div className="ha-detail">
                              <small>Performed by</small>
                              <b>{item.performed_by || 'System'}</b>
                            </div>
                            <div className="ha-detail">
                              <small>Candidate</small>
                              <b>{ev.candidate_id ?? '—'}</b>
                            </div>
                            <div className="ha-detail">
                              <small>New version</small>
                              <b>{ev.new_version_id ?? '—'}</b>
                            </div>
                            <div className="ha-detail">
                              <small>Approved by</small>
                              <b>{ev.approved_by ?? '—'}</b>
                            </div>
                          </div>

                          <div className="ha-detail-block">
                            <small>Parameters</small>
                            <pre>{JSON.stringify(ev.parameters || {}, null, 2)}</pre>
                          </div>

                          <div className="ha-detail-block">
                            <small>Notes</small>
                            <p>
                              This audit event records who performed the action, which repair operation ran,
                              and the validation outcome (when applicable).
                            </p>
                          </div>

                          {ev.new_version_id && (
                            <div className="ha-detail-links">
                              <a className="outline-button" href={`/repair-lab?version=${ev.new_version_id}`}>
                                <ExternalLink size={16} /> View in Repair Lab
                              </a>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </section>

          <section className="ha-footnote">
            <div className="ha-footnote-inner">
              <Shield size={16} />
              <span>
                Audit trail is generated by the backend repair service. Approvals include validation status and a pointer to the newly committed dataset version.
              </span>
            </div>
          </section>
        </>
      )}
    </div>
  );
};

export default HistoryAuditPage;
