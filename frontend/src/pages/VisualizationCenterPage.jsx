import React, { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import axios from 'axios';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  LineChart,
  Line,
  AreaChart,
  Area,
  PieChart,
  Pie,
  Cell
} from 'recharts';

const formatPct = (v) => {
  const n = Number(v ?? 0);
  return Number.isFinite(n) ? `${n.toFixed(1)}%` : '0.0%';
};

const safeLabel = (v) => {
  if (v === null || v === undefined) return 'Null/Missing';
  return String(v);
};

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    const item = payload[0].payload;
    return (
      <div
        style={{
          background: '#0f172a',
          color: '#ffffff',
          padding: '10px 14px',
          borderRadius: '10px',
          boxShadow: '0 8px 24px rgba(0,0,0,0.25)',
          fontSize: '12px'
        }}
      >
        <div style={{ fontWeight: 800, marginBottom: 4, color: '#e2e8f0' }}>
          {safeLabel(item.label || item.value || label)}
        </div>
        <div style={{ display: 'flex', gap: 14 }}>
          <span>Count: <strong style={{ color: '#38bdf8' }}>{item.count}</strong></span>
          <span>Share: <strong style={{ color: '#818cf8' }}>{formatPct(item.percentage)}</strong></span>
        </div>
      </div>
    );
  }
  return null;
};

const VisualizationCenterPage = () => {
  const [searchParams] = useSearchParams();
  const urlDatasetId = parseInt(searchParams.get('dataset')) || null;
  const urlVersionId = parseInt(searchParams.get('version')) || null;

  const [datasets, setDatasets] = useState([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState(null);
  const [versions, setVersions] = useState([]);
  const [selectedVersionId, setSelectedVersionId] = useState(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [vizData, setVizData] = useState(null);

  const [tab, setTab] = useState('distributions');
  const [columnSearch, setColumnSearch] = useState('');
  const [selectedColumnName, setSelectedColumnName] = useState(null);

  const [corrThreshold, setCorrThreshold] = useState(0.35);
  const [corrFocusColumn, setCorrFocusColumn] = useState(null);
  const [corrTopN, setCorrTopN] = useState(12);

  // Distribution chart method selection (changes only after clicking Visualize)
  const [vizMethod, setVizMethod] = useState('bar');
  const [vizMethodApplied, setVizMethodApplied] = useState('bar');
  const [vizPendingKey, setVizPendingKey] = useState(0); // ensures remount of chart on visualize

  const availableVizMethods = useMemo(
    () => [
      { value: 'bar', label: 'Bar histogram' },
      { value: 'line', label: 'Line chart' },
      { value: 'area', label: 'Area chart' },
      { value: 'pie', label: 'Pie share' }
    ],
    []
  );

  useEffect(() => {
    // When user switches columns, reset the applied method to keep UX predictable.
    setVizMethodApplied('bar');
    setVizMethod('bar');
    setVizPendingKey((k) => k + 1);
  }, [selectedColumnName]);

  const applyVisualization = () => {
    setVizMethodApplied(vizMethod);
    setVizPendingKey((k) => k + 1);
  };

  useEffect(() => {
    const fetchDatasets = async () => {
      setError(null);
      setLoading(true);
      try {
        const response = await axios.get('/api/datasets/');
        const payload = response.data;
        const data = Array.isArray(payload) ? payload : payload?.value || [];
        setDatasets(data);
        if (data.length > 0) {
          const targetId = (urlDatasetId && data.find((d) => d.id === urlDatasetId))
            ? urlDatasetId
            : data[0].id;
          await selectDataset(targetId, urlVersionId);
        }
      } catch (e) {
        console.error(e);
        setError('Failed to fetch datasets. Check that the backend is running.');
      } finally {
        setLoading(false);
      }
    };

    fetchDatasets();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selectDataset = async (datasetId, preferredVersionId = null) => {
    setSelectedDatasetId(datasetId);
    setSelectedVersionId(null);
    setVersions([]);
    setVizData(null);
    setTab('distributions');
    setColumnSearch('');
    setSelectedColumnName(null);

    if (!datasetId) return;

    try {
      setError(null);
      const response = await axios.get(`/api/datasets/${datasetId}/versions`);
      const vList = response.data || [];
      setVersions(vList);
      if (vList.length > 0) {
        const targetVersion = (preferredVersionId && vList.find((v) => v.id === preferredVersionId))
          ? preferredVersionId
          : vList[0].id;
        setSelectedVersionId(targetVersion);
      }
    } catch (e) {
      console.error(e);
      setError('Failed to load dataset versions');
    }
  };

  useEffect(() => {
    if (!selectedDatasetId || !selectedVersionId) return;
    loadVisualization(selectedVersionId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedDatasetId, selectedVersionId]);

  const loadVisualization = async (versionId) => {
    if (!selectedDatasetId || !versionId) return;

    setLoading(true);
    setError(null);
    setVizData(null);

    try {
      const response = await axios.get(
        `/api/profiling/${selectedDatasetId}/versions/${versionId}/visualization-data`
      );
      const data = response.data || {};
      setVizData(data);

      const distributions = Array.isArray(data.column_distributions) ? data.column_distributions : [];
      setSelectedColumnName((prev) => {
        if (prev && distributions.some((c) => c?.name === prev)) return prev;
        return distributions[0]?.name || null;
      });

      const corrCols = new Set((data.correlations || []).map((p) => p?.column).filter(Boolean));
      const corrFirst = corrCols.values().next().value || null;
      setCorrFocusColumn((prev) => {
        if (prev && corrCols.has(prev)) return prev;
        return corrFirst;
      });
    } catch (e) {
      console.error(e);
      setError('Failed to load visualization data');
    } finally {
      setLoading(false);
    }
  };

  const distributions = useMemo(() => {
    return Array.isArray(vizData?.column_distributions) ? vizData.column_distributions : [];
  }, [vizData]);

  const filteredColumns = useMemo(() => {
    const term = columnSearch.trim().toLowerCase();
    if (!term) return distributions;
    return distributions.filter((c) => String(c?.name ?? '').toLowerCase().includes(term));
  }, [distributions, columnSearch]);

  const selectedColumn = useMemo(() => {
    if (!selectedColumnName) return null;
    return distributions.find((c) => c?.name === selectedColumnName) || null;
  }, [distributions, selectedColumnName]);

  const correlations = useMemo(() => {
    return Array.isArray(vizData?.correlations) ? vizData.correlations : [];
  }, [vizData]);

  const correlationsForFocus = useMemo(() => {
    if (!corrFocusColumn) return [];
    const list = correlations
      .filter((p) => p?.column === corrFocusColumn)
      .filter((p) => typeof p?.value === 'number' && Math.abs(p.value) >= corrThreshold)
      .map((p) => ({
        correlated_with: p.correlated_with,
        value: p.value
      }))
      .filter((p) => p.correlated_with && p.correlated_with !== corrFocusColumn)
      .sort((a, b) => Math.abs(b.value) - Math.abs(a.value));

    return list.slice(0, Math.max(1, Number(corrTopN) || 12));
  }, [correlations, corrFocusColumn, corrThreshold, corrTopN]);

  const qualityIssues = useMemo(() => {
    const qi = vizData?.quality_issues;
    if (!qi) return null;
    return qi;
  }, [vizData]);

  if (loading && !vizData) {
    return (
      <div className="quality-report-page">
        <div className="repair-empty">
          <div className="empty-sparkle-box">📈</div>
          <h3>Loading Visualization Center…</h3>
          <p>Profiling, quality signals, and distributions are being prepared.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="viz-page">
      <div className="viz-header">
        <div>
          <div className="header-badge"><span>📈</span> VISUALIZATION CENTER</div>
          <h1>Visual insights for every dataset version</h1>
          <p>Explore distributions, quality signals, and correlations — without losing evidence back to the source.</p>
        </div>
        {vizData?.overview && (
          <div className="viz-overview-score">
            <div className="q-pill success">
              Quality: {formatPct(vizData.overview.quality_percentage)}
            </div>
          </div>
        )}
      </div>

      {error && (
        <div className="repair-alert error" style={{ marginTop: 0 }}>
          <span>⚠️</span> {error}
        </div>
      )}

      <section className="viz-controls-card">
        <div className="viz-controls-grid">
          <label className="viz-field">
            <span className="field-label">Choose dataset</span>
            <select
              className="quality-select"
              value={selectedDatasetId || ''}
              onChange={(e) => selectDataset(parseInt(e.target.value) || null)}
              disabled={loading}
            >
              <option value="">-- Select Dataset --</option>
              {datasets.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
          </label>

          <label className="viz-field">
            <span className="field-label">Select version</span>
            <select
              className="quality-select"
              value={selectedVersionId || ''}
              onChange={(e) => setSelectedVersionId(parseInt(e.target.value) || null)}
              disabled={loading || versions.length === 0}
            >
              <option value="">-- Select Version --</option>
              {versions.map((v) => (
                <option key={v.id} value={v.id}>
                  Version {v.version_number} ({v.version_type})
                </option>
              ))}
            </select>
          </label>
        </div>

        {vizData?.overview && (
          <div className="viz-kpi-row">
            <div className="viz-kpi">
              <div className="viz-kpi-label">Total records</div>
              <div className="viz-kpi-value">{vizData.overview.total_records || 0}</div>
            </div>
            <div className="viz-kpi">
              <div className="viz-kpi-label">Clean records</div>
              <div className="viz-kpi-value">{vizData.overview.clean_records || 0}</div>
            </div>
            <div className="viz-kpi">
              <div className="viz-kpi-label">Dirty records</div>
              <div className="viz-kpi-value">{vizData.overview.dirty_records || 0}</div>
            </div>
            <div className="viz-kpi">
              <div className="viz-kpi-label">Quality score</div>
              <div className="viz-kpi-value">{formatPct(vizData.overview.quality_percentage)}</div>
            </div>
          </div>
        )}
      </section>

      {vizData && (
        <section>
          <div className="viz-tabs">
            <button
              type="button"
              className={`viz-tab ${tab === 'distributions' ? 'active' : ''}`}
              onClick={() => setTab('distributions')}
            >
              Distributions
            </button>
            <button
              type="button"
              className={`viz-tab ${tab === 'quality' ? 'active' : ''}`}
              onClick={() => setTab('quality')}
            >
              Quality issues
            </button>
            <button
              type="button"
              className={`viz-tab ${tab === 'correlations' ? 'active' : ''}`}
              onClick={() => setTab('correlations')}
            >
              Correlations
            </button>
          </div>

          {tab === 'distributions' && (
            <div className="viz-grid-2">
              <div className="viz-card">
                <div className="viz-card-head">
                  <div>
                    <div className="viz-card-title">Columns</div>
                    <div className="viz-card-sub">Choose a column to visualize its distribution.</div>
                  </div>
                  <div className="viz-search">
                    <input
                      className="quality-input"
                      value={columnSearch}
                      onChange={(e) => setColumnSearch(e.target.value)}
                      placeholder="Search columns…"
                    />
                  </div>
                </div>

                <div className="viz-column-list">
                  {filteredColumns.length === 0 && (
                    <div className="quality-empty">
                      <div className="empty-sparkle-box">🔎</div>
                      <h3>No matching columns</h3>
                      <p>Try a different search term.</p>
                    </div>
                  )}

                  {filteredColumns.map((col) => {
                    const active = selectedColumnName === col.name;
                    return (
                      <button
                        key={col.name}
                        type="button"
                        className={`viz-column-item ${active ? 'active' : ''}`}
                        onClick={() => setSelectedColumnName(col.name)}
                      >
                        <div className="viz-column-item-name">{col.name}</div>
                        <div className="viz-column-item-type">{col.data_type}</div>
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="viz-card">
                <div className="viz-card-head">
                  <div>
                    <div className="viz-card-title">Distribution</div>
                    <div className="viz-card-sub">
                      {selectedColumn ? `For ${selectedColumn.name} (${selectedColumn.data_type})` : 'Select a column'}
                    </div>
                  </div>
                </div>

                {selectedColumn && (
                  <div style={{ marginBottom: 14 }}>
                    <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                      <label className="viz-field" style={{ minWidth: 240 }}>
                        <span className="field-label">Visualization method</span>
                        <select
                          className="quality-select"
                          value={vizMethod}
                          onChange={(e) => setVizMethod(e.target.value)}
                        >
                          {availableVizMethods.map((m) => (
                            <option key={m.value} value={m.value}>
                              {m.label}
                            </option>
                          ))}
                        </select>
                      </label>
                      <div style={{ display: 'flex', alignItems: 'end' }}>
                        <button
                          type="button"
                          className="primary-button"
                          onClick={applyVisualization}
                          style={{ height: 42, padding: '0 18px' }}
                        >
                          Visualize
                        </button>
                      </div>
                    </div>
                  </div>
                )}

                {!selectedColumn ? (
                  <div className="quality-empty">
                    <div className="empty-sparkle-box">📊</div>
                    <h3>No column selected</h3>
                    <p>Select a column from the left panel.</p>
                  </div>
                ) : (
                  <>
                    <div className="viz-chart-wrap">
                      <ResponsiveContainer width="100%" height={310}>
                        {vizMethodApplied === 'bar' && (
                          <BarChart
                            data={selectedColumn.distribution || []}
                            margin={{ top: 12, right: 16, left: 0, bottom: 28 }}
                          >
                            <defs>
                              <linearGradient id="barGradient" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor="#6366f1" stopOpacity={0.95} />
                                <stop offset="100%" stopColor="#3b82f6" stopOpacity={0.8} />
                              </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                            <XAxis
                              dataKey="label"
                              tick={{ fontSize: 11, fill: '#64748b' }}
                              interval={0}
                              angle={-22}
                              textAnchor="end"
                              height={42}
                            />
                            <YAxis tick={{ fontSize: 11, fill: '#64748b' }} allowDecimals={false} />
                            <Tooltip content={<CustomTooltip />} />
                            <Bar dataKey="count" fill="url(#barGradient)" radius={[6, 6, 0, 0]} />
                          </BarChart>
                        )}

                        {vizMethodApplied === 'line' && (
                          <LineChart
                            data={selectedColumn.distribution || []}
                            margin={{ top: 12, right: 16, left: 0, bottom: 28 }}
                          >
                            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                            <XAxis
                              dataKey="label"
                              tick={{ fontSize: 11, fill: '#64748b' }}
                              interval={0}
                              angle={-22}
                              textAnchor="end"
                              height={42}
                            />
                            <YAxis tick={{ fontSize: 11, fill: '#64748b' }} allowDecimals={false} />
                            <Tooltip content={<CustomTooltip />} />
                            <Line
                              type="monotone"
                              dataKey="count"
                              stroke="#3b82f6"
                              strokeWidth={3}
                              dot={{ r: 3, fill: '#3b82f6' }}
                              activeDot={{ r: 5 }}
                            />
                          </LineChart>
                        )}

                        {vizMethodApplied === 'area' && (
                          <AreaChart
                            data={selectedColumn.distribution || []}
                            margin={{ top: 12, right: 16, left: 0, bottom: 28 }}
                          >
                            <defs>
                              <linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor="#6366f1" stopOpacity={0.65} />
                                <stop offset="100%" stopColor="#3b82f6" stopOpacity={0.08} />
                              </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                            <XAxis
                              dataKey="label"
                              tick={{ fontSize: 11, fill: '#64748b' }}
                              interval={0}
                              angle={-22}
                              textAnchor="end"
                              height={42}
                            />
                            <YAxis tick={{ fontSize: 11, fill: '#64748b' }} allowDecimals={false} />
                            <Tooltip content={<CustomTooltip />} />
                            <Area
                              type="monotone"
                              dataKey="count"
                              stroke="#6366f1"
                              fill="url(#areaGradient)"
                              strokeWidth={2}
                            />
                          </AreaChart>
                        )}

                        {vizMethodApplied === 'pie' && (
                          <PieChart>
                            <Tooltip content={<CustomTooltip />} />
                            <Pie
                              data={(selectedColumn.distribution || []).slice(0, 12)}
                              dataKey="count"
                              nameKey="label"
                              outerRadius={120}
                              innerRadius={55}
                              paddingAngle={2}
                              stroke="#0f172a"
                              strokeWidth={1}
                            >
                              {(selectedColumn.distribution || []).slice(0, 12).map((_, i) => (
                                <Cell
                                  key={i}
                                  fill={[
                                    '#6366f1',
                                    '#3b82f6',
                                    '#22c55e',
                                    '#10b981',
                                    '#f59e0b',
                                    '#f97316',
                                    '#ef4444',
                                    '#8b5cf6',
                                    '#06b6d4',
                                    '#14b8a6',
                                    '#a3e635',
                                    '#eab308'
                                  ][i % 12]}
                                />
                              ))}
                            </Pie>
                          </PieChart>
                        )}
                      </ResponsiveContainer>
                    </div>

                    <div className="viz-bucket-table">
                      {(selectedColumn.distribution || []).slice(0, 15).map((b, idx) => (
                        <div key={idx} className="viz-bucket-row">
                          <div className="viz-bucket-label">{safeLabel(b.label || b.value)}</div>
                          <div className="viz-bucket-count">{b.count} rows</div>
                          <div className="viz-bucket-pct">{formatPct(b.percentage)}</div>
                        </div>
                      ))}
                      {(selectedColumn.distribution || []).length === 0 && (
                        <div className="quality-empty">
                          <div className="empty-sparkle-box">🫥</div>
                          <h3>No distribution data</h3>
                          <p>Try another version or column.</p>
                        </div>
                      )}
                    </div>
                  </>
                )}
              </div>
            </div>
          )}

          {tab === 'quality' && (
            <div className="viz-card">
              <div className="viz-card-head">
                <div>
                  <div className="viz-card-title">Quality overview</div>
                  <div className="viz-card-sub">Issue counts and severity distribution for this version.</div>
                </div>
              </div>

              {!qualityIssues?.issue_types?.length ? (
                <div className="quality-empty">
                  <div className="empty-sparkle-box">✅</div>
                  <h3>No quality issues</h3>
                  <p>This dataset version passed all quality detection checks.</p>
                </div>
              ) : (
                <>
                  <div className="viz-issue-grid">
                    {qualityIssues.issue_types.map((issue) => {
                      const total = qualityIssues.total_issues || 0;
                      const pct = total > 0 ? (issue.count / total) * 100 : 0;
                      return (
                        <div key={issue.type} className="viz-issue-card">
                          <div className="viz-issue-count">{issue.count}</div>
                          <div className="viz-issue-type">{String(issue.type || '').replace(/_/g, ' ')}</div>
                          <div className="viz-issue-sub">{pct.toFixed(1)}% of detected issues</div>
                        </div>
                      );
                    })}
                  </div>

                  <div className="viz-sev-row">
                    {(qualityIssues.severity_distribution || []).map((s) => (
                      <div key={s.level} className="viz-sev-card">
                        <div className="viz-sev-level">{String(s.level || '').toUpperCase()} SEVERITY</div>
                        <div className="viz-sev-count">{s.count}</div>
                        <div className="viz-sev-pct">{formatPct(s.percentage)}</div>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>
          )}

          {tab === 'correlations' && (
            <div className="viz-grid-2">
              <div className="viz-card">
                <div className="viz-card-head">
                  <div>
                    <div className="viz-card-title">Correlation filters</div>
                    <div className="viz-card-sub">Focus on relationships for numeric columns.</div>
                  </div>
                </div>

                <div className="viz-filter-block">
                  <label className="viz-field">
                    <span className="field-label">Focus column</span>
                    <select
                      className="quality-select"
                      value={corrFocusColumn || ''}
                      onChange={(e) => setCorrFocusColumn(e.target.value || null)}
                      disabled={(correlations || []).length === 0}
                    >
                      <option value="">-- Select --</option>
                      {Array.from(new Set(correlations.map((p) => p?.column).filter(Boolean))).map((c) => (
                        <option key={c} value={c}>
                          {c}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label className="viz-field">
                    <span className="field-label">Min |correlation| ({corrThreshold})</span>
                    <input
                      className="quality-select"
                      style={{ padding: '10px 12px' }}
                      type="number"
                      step="0.05"
                      min="0"
                      max="1"
                      value={corrThreshold}
                      onChange={(e) => setCorrThreshold(Math.min(1, Math.max(0, Number(e.target.value) || 0)))}
                      disabled={(correlations || []).length === 0}
                    />
                  </label>

                  <label className="viz-field">
                    <span className="field-label">Top results ({corrTopN})</span>
                    <input
                      className="quality-select"
                      style={{ padding: '10px 12px' }}
                      type="number"
                      step="1"
                      min="3"
                      max="50"
                      value={corrTopN}
                      onChange={(e) => setCorrTopN(Math.min(50, Math.max(3, Number(e.target.value) || 12)))}
                      disabled={(correlations || []).length === 0}
                    />
                  </label>
                </div>
              </div>

              <div className="viz-card">
                <div className="viz-card-head">
                  <div>
                    <div className="viz-card-title">Top correlated pairs</div>
                    <div className="viz-card-sub">
                      {corrFocusColumn ? `For ${corrFocusColumn}` : 'Pick a focus column'}
                    </div>
                  </div>
                </div>

                {!correlations.length ? (
                  <div className="quality-empty">
                    <div className="empty-sparkle-box">🧠</div>
                    <h3>No correlation data</h3>
                    <p>This dataset version does not have multiple numeric columns.</p>
                  </div>
                ) : correlationsForFocus.length === 0 ? (
                  <div className="quality-empty">
                    <div className="empty-sparkle-box">🎯</div>
                    <h3>No pairs meet the threshold</h3>
                    <p>Try lowering the min |correlation| value.</p>
                  </div>
                ) : (
                  <div className="viz-corr-list">
                    {correlationsForFocus.map((p) => {
                      const pctWidth = Math.min(100, Math.max(4, Math.round(Math.abs(p.value) * 100)));
                      const isPos = p.value >= 0;
                      return (
                        <div key={`${corrFocusColumn}-${p.correlated_with}`} className="viz-corr-row">
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div className="viz-corr-col">{p.correlated_with}</div>
                            <div
                              style={{
                                height: 4,
                                width: '100%',
                                background: '#e2e8f0',
                                borderRadius: 2,
                                marginTop: 6,
                                overflow: 'hidden'
                              }}
                            >
                              <div
                                style={{
                                  height: '100%',
                                  width: `${pctWidth}%`,
                                  background: isPos ? '#10b981' : '#ef4444',
                                  borderRadius: 2
                                }}
                              />
                            </div>
                          </div>
                          <div className={`viz-corr-val ${isPos ? 'pos' : 'neg'}`}>
                            {p.value > 0 ? `+${p.value.toFixed(4)}` : p.value.toFixed(4)}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          )}
        </section>
      )}
    </div>
  );
};

export default VisualizationCenterPage;

