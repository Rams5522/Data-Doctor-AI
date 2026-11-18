import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';

const normalizeArray = (v) => (Array.isArray(v) ? v : []);

function qualityScoreVariant(score) {
  const s = Number(score ?? 0);
  if (s >= 80) return 'success';
  if (s >= 60) return 'warning';
  return 'danger';
}

function qualityScoreLabel(score) {
  const s = Number(score ?? 0);
  if (s >= 80) return 'Excellent';
  if (s >= 60) return 'Good';
  return 'Needs attention';
}

function severityToVariant(severity) {
  const s = String(severity ?? '').toLowerCase();
  if (s === 'high' || s === 'critical') return 'danger';
  if (s === 'medium' || s === 'med') return 'warning';
  if (s === 'low' || s === 'info' || s === 'informational') return 'info';
  return 'info';
}

function formatTypeLabel(type) {
  return String(type ?? '').replaceAll('_', ' ').trim() || 'Unknown issue';
}

const DataQualityReportPage = () => {
  const [datasets, setDatasets] = useState([]);
  const [availableVersions, setAvailableVersions] = useState([]);

  const [selectedDatasetId, setSelectedDatasetId] = useState(null);
  const [selectedVersionId, setSelectedVersionId] = useState(null);

  const [reportData, setReportData] = useState(null);
  const [rawFindings, setRawFindings] = useState([]);

  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState(null);

  const [issueTypeFilter, setIssueTypeFilter] = useState(null);
  const [activeColumn, setActiveColumn] = useState(null);
  const [columnSearch, setColumnSearch] = useState('');

  const filteredColumns = useMemo(() => {
    const cols = reportData?.column_details || [];
    const term = columnSearch.trim().toLowerCase();
    if (!term) return cols;
    return cols.filter((c) => String(c?.name ?? '').toLowerCase().includes(term));
  }, [reportData, columnSearch]);

  const filteredFindingsByIssueType = useMemo(() => {
    const findings = rawFindings;
    if (!issueTypeFilter) return findings;
    return findings.filter((f) => String(f?.issue_type ?? '').toLowerCase() === String(issueTypeFilter).toLowerCase());
  }, [rawFindings, issueTypeFilter]);

  useEffect(() => {
    const fetchDatasets = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await axios.get('/api/datasets/');
        const payload = response.data;
        const data = Array.isArray(payload) ? payload : payload?.value || [];
        setDatasets(data);

        if (data.length > 0) {
          await selectDataset(data[0].id);
        }
      } catch (err) {
        console.error('Failed to fetch datasets:', err);
        setError('Failed to fetch datasets. Check that the backend is running.');
      } finally {
        setLoading(false);
      }
    };

    fetchDatasets();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selectDataset = async (datasetId) => {
    setSelectedDatasetId(datasetId);
    setSelectedVersionId(null);
    setReportData(null);
    setRawFindings([]);
    setAvailableVersions([]);
    setIssueTypeFilter(null);
    setActiveColumn(null);
    setColumnSearch('');

    if (!datasetId) return;

    try {
      const versionResponse = await axios.get(`/api/datasets/${datasetId}/versions`);
      const versions = versionResponse.data || [];
      setAvailableVersions(versions);
      if (versions.length > 0) setSelectedVersionId(versions[0].id);
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || 'Failed to fetch dataset versions');
    }
  };

  const runQualityCheck = async (versionId) => {
    if (!selectedDatasetId || !versionId) return;

    setLoading(true);
    setRunning(true);
    setError(null);

    // Clear so the UI shows the loading state and doesn't look stale
    setReportData(null);
    setRawFindings([]);
    setIssueTypeFilter(null);
    setActiveColumn(null);
    setColumnSearch('');

    try {
      // 1) Trigger quality detection (response includes findings)
      const detectResponse = await axios.post(
        `/api/quality/${selectedDatasetId}/detect?version_id=${versionId}`
      );

      // 2) Use the returned findings directly (more reliable than re-fetching)
      const findings = normalizeArray(detectResponse.data?.findings);

      // Store raw findings for type filtering / detail
      setRawFindings(findings);

      // 3) Compute issue breakdown by type
      const issueTypes = {};
      findings.forEach((f) => {
        const type = String(f?.issue_type ?? 'unknown');
        if (!issueTypes[type]) issueTypes[type] = { type, count: 0, total_affected: 0 };
        issueTypes[type].count += 1;
        issueTypes[type].total_affected += f?.affected_count || 0;
      });

      // 4) Fetch profile (for column details)
      let profileData = null;
      try {
        const profileResponse = await axios.get(
          `/api/profiling/${selectedDatasetId}/profile?version_id=${versionId}`
        );
        profileData = profileResponse.data?.profile_data || null;
      } catch (profileErr) {
        console.warn('Could not fetch profile data:', profileErr);
      }

      const total_records =
        profileData?.dataset_info?.num_rows ??
        profileData?.dataset_info?.row_count ??
        0;

      const columnProfiles = profileData?.column_profiles || {};

      // If we don't have column profile data, still render something based on findings
      const fallbackColumns = (() => {
        if (columnProfiles && Object.keys(columnProfiles).length > 0) return null;
        const map = {};
        findings.forEach((f) => {
          (f?.affected_columns || []).forEach((colName) => {
            if (!map[colName]) map[colName] = { name: colName, dtype: 'unknown', missing_count: 0, missing_percentage: 0 };
          });
        });
        return map;
      })();

      const columnSource = fallbackColumns || columnProfiles;

      const columnDetails = Object.entries(columnSource).map(([name, col]) => {
        const colFindings = findings.filter(
          (f) => Array.isArray(f?.affected_columns) && f?.affected_columns?.includes(name)
        );

        const missingCount = col?.missing_count || 0;
        const missingPct = Number(col?.missing_percentage || 0);
        const invalidCount = colFindings.reduce((sum, f) => sum + (f?.affected_count || 0), 0);

        const invalidPct = total_records > 0 ? (invalidCount / total_records) * 100 : colFindings.length * 5;
        const invalidPctClamped = Math.max(0, Math.min(100, invalidPct));

        // Simple evidence-based score: start at 100 and penalize missing + invalid
        const qualityScore = Math.max(0, 100 - (missingPct || 0) - (invalidPctClamped || 0));

        return {
          name,
          data_type: col?.dtype || 'unknown',
          missing_count: missingCount,
          missing_percentage: missingPct,
          invalid_count: invalidCount,
          invalid_percentage: invalidPctClamped,
          quality_score: qualityScore,
          issues: colFindings.map((f) => ({
            type: f?.issue_type,
            count: f?.affected_count,
            severity: f?.severity || 'medium'
          }))
        };
      });

      const computedScore = (() => {
        const scores = columnDetails.map((c) => Number(c?.quality_score ?? 0)).filter((n) => Number.isFinite(n));
        if (scores.length === 0) return 100;
        const avg = scores.reduce((a, b) => a + b, 0) / scores.length;
        return Math.max(0, Math.min(100, avg));
      })();

      setReportData({
        total_records: Number(total_records || 0),
        issues_found: findings.length,
        columns_analyzed: columnDetails.length,
        quality_score: Number(computedScore),
        issue_breakdown: Object.values(issueTypes).map((t) => ({
          type: t.type,
          count: t.count,
          affected_count: t.total_affected
        })),
        column_details: columnDetails
      });

      setIssueTypeFilter(null);
      setActiveColumn(null);
      setColumnSearch('');
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || 'Failed to generate quality report');
    } finally {
      setRunning(false);
      setLoading(false);
    }
  };

  // Auto-run whenever dataset+version changes
  useEffect(() => {
    if (!selectedDatasetId || !selectedVersionId) return;
    setLoading(true);
    runQualityCheck(selectedVersionId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedDatasetId, selectedVersionId]);

  const isReady = !!selectedDatasetId && !!selectedVersionId;

  if (loading && !reportData) {
    return (
      <div className="quality-report-page">
        <div className="quality-loading">
          <div className="empty-sparkle-box">📊</div>
          <h3>Loading Data Quality Report…</h3>
          <p>Preparing dataset profile and running detection.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="quality-report-page">
      <div className="quality-header">
        <div>
          <div className="header-badge"><span>📊</span> DATA QUALITY REPORT</div>
          <h1>Data Quality Report</h1>
          <p>Detect issues, quantify impact, and review column-level quality signals.</p>
        </div>

        {reportData && (
          <div className="quality-header-score">
            <div className={`q-pill ${qualityScoreVariant(reportData.quality_score)}`}>
              {reportData.quality_score?.toFixed(1) || '0.0'}% · {qualityScoreLabel(reportData.quality_score)}
            </div>
          </div>
        )}
      </div>

      {error && (
        <div className="repair-alert error">
          <span>⚠️</span> {error}
        </div>
      )}

      <section className="quality-controls-card">
        <div className="quality-control-grid">
          <label className="quality-field">
            <span className="field-label">Choose dataset</span>
            <select
              className="quality-select"
              value={selectedDatasetId || ''}
              onChange={(e) => selectDataset(parseInt(e.target.value) || null)}
              disabled={running}
            >
              <option value="">-- Select Dataset --</option>
              {datasets.map((dataset) => (
                <option key={dataset.id} value={dataset.id}>
                  {dataset.name} {dataset.description ? `(${dataset.description})` : ''}
                </option>
              ))}
            </select>
          </label>

          <label className="quality-field">
            <span className="field-label">Select version</span>
            <select
              className="quality-select"
              value={selectedVersionId || ''}
              onChange={(e) => {
                const next = parseInt(e.target.value) || null;
                setSelectedVersionId(next);
                setReportData(null);
                setRawFindings([]);
                setIssueTypeFilter(null);
                setActiveColumn(null);
                setColumnSearch('');
                setError(null);
                setLoading(!!next);
              }}
              disabled={running || availableVersions.length === 0}
            >
              <option value="">-- Select Version --</option>
              {availableVersions.map((version) => (
                <option key={version.id} value={version.id}>
                  Version {version.version_number} ({version.version_type})
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="quality-controls-actions">
          <button
            className="primary-button"
            onClick={() => runQualityCheck(selectedVersionId)}
            disabled={!isReady || running}
          >
            {running ? 'Analyzing…' : 'Run Quality Check'}
          </button>
          <div className="quality-controls-hint">
            {isReady ? 'Report updates automatically when dataset/version changes.' : 'Select a dataset and version to generate a report.'}
          </div>
        </div>
      </section>

      {!datasets.length && (
        <div className="repair-alert error">
          <span>ℹ️</span> No datasets available. Please upload a dataset first.
        </div>
      )}

      {reportData && (
        <section className="quality-report-content">
          {/* Summary Metrics */}
          <div className="quality-metrics-grid">
            <div className="quality-metric">
              <div className="quality-metric-label">Total records</div>
              <div className="quality-metric-value">{reportData.total_records || 0}</div>
            </div>
            <div className="quality-metric">
              <div className="quality-metric-label">Issues found</div>
              <div className="quality-metric-value">{reportData.issues_found || 0}</div>
            </div>
            <div className="quality-metric">
              <div className="quality-metric-label">Columns analyzed</div>
              <div className="quality-metric-value">{reportData.columns_analyzed || 0}</div>
            </div>
            <div className="quality-metric">
              <div className="quality-metric-label">Quality score</div>
              <div className="quality-metric-value">
                {reportData.quality_score?.toFixed(1) || '0.0'}%
              </div>
              <div className="quality-metric-sub">
                <span className={`q-pill q-pill-small ${qualityScoreVariant(reportData.quality_score)}`}>
                  {qualityScoreLabel(reportData.quality_score)}
                </span>
              </div>
            </div>
          </div>

          <div className="quality-two-col">
            {/* Issue Breakdown */}
            <div className="quality-card">
              <div className="quality-card-head">
                <div>
                  <h2 className="quality-card-title">Issue breakdown</h2>
                  <p className="quality-card-sub">Click an issue type to filter findings.</p>
                </div>
                {issueTypeFilter && (
                  <button className="outline-button" onClick={() => setIssueTypeFilter(null)} disabled={running}>
                    Clear filter
                  </button>
                )}
              </div>

              <div className="quality-issue-grid">
                {(reportData.issue_breakdown || []).map((issue) => {
                  const isActive = issueTypeFilter && String(issue.type).toLowerCase() === String(issueTypeFilter).toLowerCase();
                  return (
                    <button
                      key={issue.type}
                      type="button"
                      className={`quality-issue-card ${isActive ? 'active' : ''}`}
                      onClick={() => setIssueTypeFilter(issue.type)}
                      disabled={running}
                    >
                      <div className="quality-issue-card-top">
                        <div className="quality-issue-count">{issue.count}</div>
                        <div className="quality-issue-pill">{formatTypeLabel(issue.type)}</div>
                      </div>
                      <div className="quality-issue-affected">{issue.affected_count || 0} items affected</div>
                    </button>
                  );
                })}

                {(reportData.issue_breakdown || []).length === 0 && (
                  <div className="quality-empty">
                    <div className="empty-sparkle-box">✅</div>
                    <h3>No quality issues detected</h3>
                    <p>This dataset version passed the quality checks.</p>
                  </div>
                )}
              </div>

              {/* Filtered findings list */}
              {(issueTypeFilter || filteredFindingsByIssueType.length > 0) && (
                <div className="quality-findings-panel">
                  <div className="quality-findings-head">
                    <div className="quality-findings-title">
                      Findings{issueTypeFilter ? ` · ${formatTypeLabel(issueTypeFilter)}` : ''}
                    </div>
                    <div className="quality-findings-count">{filteredFindingsByIssueType.length} items</div>
                  </div>

                  <div className="quality-findings-list">
                    {filteredFindingsByIssueType.slice(0, 10).map((f, idx) => (
                      <div key={`${f.issue_type || 'issue'}-${idx}`} className="quality-finding-row">
                        <div className="quality-finding-left">
                          <span className={`q-sev ${severityToVariant(f.severity)}`}>{String(f.severity || 'medium')}</span>
                          <div className="quality-finding-type">{formatTypeLabel(f.issue_type)}</div>
                        </div>
                        <div className="quality-finding-right">
                          <span className="quality-finding-amount">{f.affected_count || 0}</span>
                          <span className="quality-finding-label">affected</span>
                        </div>
                      </div>
                    ))}

                    {filteredFindingsByIssueType.length > 10 && (
                      <div className="quality-findings-more">Showing top 10 results.</div>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Column Quality Details */}
            <div className="quality-card">
              <div className="quality-card-head">
                <div>
                  <h2 className="quality-card-title">Column quality details</h2>
                  <p className="quality-card-sub">Search and drill into issues per column.</p>
                </div>
                <div className="quality-search">
                  <input
                    className="quality-input"
                    value={columnSearch}
                    onChange={(e) => setColumnSearch(e.target.value)}
                    placeholder="Search columns…"
                  />
                </div>
              </div>

              <div className="quality-columns-table">
                <div className="quality-col-head">
                  <div>Column</div>
                  <div>Type</div>
                  <div>Missing</div>
                  <div>Invalid</div>
                  <div>Quality</div>
                  <div>Issues</div>
                </div>

                {filteredColumns.map((col) => {
                  const isOpen = activeColumn === col.name;
                  const issuesCount = normalizeArray(col.issues).length;
                  return (
                    <div key={col.name} className="quality-col-block">
                      <div className="quality-col-row">
                        <div className="quality-col-name">
                          <div className="quality-col-name-main">{col.name}</div>
                        </div>
                        <div className="quality-col-type">{col.data_type}</div>
                        <div className="quality-col-metric">
                          <span className={`q-pill q-pill-small missing`}>
                            {col.missing_count} ({Number(col.missing_percentage || 0).toFixed(1)}%)
                          </span>
                        </div>
                        <div className="quality-col-metric">
                          <span className={`q-pill q-pill-small invalid`}>
                            {col.invalid_count} ({Number(col.invalid_percentage || 0).toFixed(1)}%)
                          </span>
                        </div>
                        <div className="quality-col-metric">
                          <span className={`q-pill q-pill-small ${qualityScoreVariant(col.quality_score)}`}>
                            {Number(col.quality_score || 0).toFixed(1)}%
                          </span>
                        </div>
                        <div className="quality-col-issues">
                          {issuesCount > 0 ? (
                            <button
                              type="button"
                              className="outline-button quality-view-btn"
                              onClick={() => setActiveColumn(isOpen ? null : col.name)}
                              disabled={running}
                            >
                              {isOpen ? 'Hide' : `View (${issuesCount})`}
                            </button>
                          ) : (
                            <span className="quality-none">None</span>
                          )}
                        </div>
                      </div>

                      {isOpen && (
                        <div className="quality-col-issues-panel">
                          <div className="quality-col-issues-head">Issues for {col.name}</div>
                          <div className="quality-col-issues-list">
                            {normalizeArray(col.issues).map((issue, idx) => (
                              <div key={`${issue.type}-${idx}`} className="quality-issue-detail">
                                <div className="quality-issue-detail-left">
                                  <span className={`q-sev ${severityToVariant(issue.severity)}`}>{issue.severity}</span>
                                  <span className="quality-issue-detail-type">{formatTypeLabel(issue.type)}</span>
                                </div>
                                <div className="quality-issue-detail-right">
                                  <span className="quality-issue-detail-count">{issue.count || 0}</span>
                                  <span className="quality-issue-detail-label">affected</span>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}

                {filteredColumns.length === 0 && (
                  <div className="quality-empty">
                    <div className="empty-sparkle-box">🔎</div>
                    <h3>No columns match your search</h3>
                    <p>Try a different search term.</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        </section>
      )}
    </div>
  );
};

export default DataQualityReportPage;
