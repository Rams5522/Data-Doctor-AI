import React, { useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import { useAuth } from '../auth/AuthContext';

// Auth-gated pages show the signed-in user name in the UI via this context.
const noop = null; // keep bundlers from tree-shaking the import in some builds


// eslint-disable-next-line no-unused-vars
void noop;

const _unused = noop;
void _unused;

const formatNumber = num => {
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
  return num.toString();
};

const formatDate = value => {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleDateString();
};

const HomeDashboard = () => {
  const { user } = useAuth();
  const [datasets, setDatasets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [details, setDetails] = useState({});

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      const datasetsResponse = await axios.get('/api/datasets/');
      const loadedDatasets = Array.isArray(datasetsResponse.data) ? datasetsResponse.data : (datasetsResponse.data?.value || []);
      setDatasets(loadedDatasets);

      // Fetch details for each dataset
      const detailPromises = loadedDatasets.map(async dataset => {
        try {
          const versionsResponse = await axios.get(`/api/datasets/${dataset.id}/versions`);
          const version = versionsResponse.data[0];
          if (!version) return { datasetId: dataset.id, records: 0, issues: 0, repairs: 0 };

          const [profileResponse, findingsResponse, historyResponse] = await Promise.allSettled([
            axios.get(`/api/profiling/${dataset.id}/profile?version_id=${version.id}`),
            axios.get(`/api/quality/${dataset.id}/findings?version_id=${version.id}`),
            axios.get(`/api/repair/${dataset.id}/repair-history`)
          ]);

          return {
            datasetId: dataset.id,
            records: profileResponse.status === 'fulfilled'
              ? profileResponse.value.data.profile_summary?.total_records
                || profileResponse.value.data.profile_data?.dataset_info?.num_rows || 0
              : 0,
            issues: findingsResponse.status === 'fulfilled'
              ? (findingsResponse.value.data.findings || []).length : 0,
            repairs: historyResponse.status === 'fulfilled'
              ? (historyResponse.value.data.history || []).length : 0
          };
        } catch (err) {
          return { datasetId: dataset.id, records: 0, issues: 0, repairs: 0 };
        }
      });

      const loadedDetails = await Promise.all(detailPromises);
      setDetails(Object.fromEntries(loadedDetails.map(d => [d.datasetId, d])));
      setError(null);
    } catch (err) {
      console.error('Failed to fetch dashboard data:', err);
      setError('Failed to load dashboard data. Check that the backend is running.');
    } finally {
      setLoading(false);
    }
  };

  const stats = useMemo(() => {
    if (!datasets.length) {
      return { totalDatasets: 0, totalRecords: 0, totalIssues: 0, totalRepairs: 0 };
    }
    return {
      totalDatasets: datasets.length,
      totalRecords: datasets.reduce((sum, d) => sum + (details[d.id]?.records || 0), 0),
      totalIssues: datasets.reduce((sum, d) => sum + (details[d.id]?.issues || 0), 0),
      totalRepairs: datasets.reduce((sum, d) => sum + (details[d.id]?.repairs || 0), 0)
    };
  }, [datasets, details]);

  const recentDatasets = useMemo(() => datasets.slice(0, 5), [datasets]);

  if (loading) {
    return (
      <div className="home-dashboard">
        <div className="home-header">
          <div className="header-badge"><span>🏠</span> HOME DASHBOARD</div>
          <h1>Welcome to DataDoctor AI</h1>
          <p>Evidence-grounded, risk-aware data repair agent.</p>
        </div>
        <div className="repair-empty">
          <div className="empty-sparkle-box">⏳</div>
          <h3>Loading dashboard</h3>
          <p>Fetching your datasets and quality metrics.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="home-dashboard">
      <div className="home-header">
        <div>
          <div className="header-badge"><span>🏠</span> HOME DASHBOARD</div>
          <h1>Welcome to DataDoctor AI</h1>
          <p>Evidence-grounded, risk-aware data repair agent.</p>
        </div>
      </div>

      {error && <div className="repair-alert error"><span>⚠️</span> {error}</div>}

      {/* Hero */}
      <section className="home-hero">
        <div className="home-hero-copy">
          <div className="header-badge"><span>🛡️</span> EVIDENCE-GROUNDED REPAIR</div>
          <h2>Detect quality issues. Validate fixes. Preserve originals.</h2>
          <p>
            DataDoctor AI profiles your datasets, detects data-quality defects, generates allowlisted repair strategies,
            and requires validation before any change is applied. Every approved repair becomes a new immutable version
            so your source data is never overwritten.
          </p>
          <div className="home-hero-chips">
            <span className="chip">🔒 Sandboxed execution</span>
            <span className="chip">✅ Validation gates</span>
            <span className="chip">♻️ Immutable versions</span>
          </div>

          <div className="home-workflow">
            <div className="workflow-step">
              <div className="workflow-num">1</div>
              <div className="workflow-title">Upload</div>
              <div className="workflow-desc">Bring CSV / Excel / JSON</div>
            </div>
            <div className="workflow-step">
              <div className="workflow-num">2</div>
              <div className="workflow-title">Detect</div>
              <div className="workflow-desc">Find quality defects safely</div>
            </div>
            <div className="workflow-step">
              <div className="workflow-num">3</div>
              <div className="workflow-title">Validate</div>
              <div className="workflow-desc">Score & block unsafe repairs</div>
            </div>
            <div className="workflow-step">
              <div className="workflow-num">4</div>
              <div className="workflow-title">Export</div>
              <div className="workflow-desc">Download repaired versions</div>
            </div>
          </div>
        </div>

        <div className="home-hero-right">
          <div className="home-quick-stats">
            <div className="home-quick-stat">
              <span className="home-quick-stat-icon">🔒</span>
              <div>
                <div className="home-quick-stat-label">Session</div>
                <div className="home-quick-stat-value">Active</div>
              </div>
            </div>
            <div className="home-quick-stat">
              <span className="home-quick-stat-icon">🛡️</span>
              <div>
                <div className="home-quick-stat-label">Repairs</div>
                <div className="home-quick-stat-value">Validated only</div>
              </div>
            </div>
            <div className="home-quick-stat">
              <span className="home-quick-stat-icon">📦</span>
              <div>
                <div className="home-quick-stat-label">Exports</div>
                <div className="home-quick-stat-value">Original format</div>
              </div>
            </div>
          </div>

          <div className="home-hero-metric">
            <div className="home-hero-metric-card">
            <div className="home-hero-metric-top">
              <div className="home-hero-metric-icon">⚙️</div>
              <div>
                <div className="home-hero-metric-label">Repairs Completed</div>
                <div className="home-hero-metric-value">{formatNumber(stats.totalRepairs)}</div>
              </div>
            </div>
            <div className="home-hero-metric-note">Approved and applied repairs across your library</div>
          </div>
          </div>
        </div>
      </section>

      {/* Quick Actions */}
      <section className="home-section">
        <div className="section-heading">
          <div>
            <h2>Quick Actions</h2>
            <p>Jump straight to the most common workflows.</p>
          </div>
        </div>
        <div className="home-actions-grid">
          <a className="home-action-card" href="/datasets">
            <div className="home-action-icon">📤</div>
            <h3>Upload Dataset</h3>
            <p>Add new CSV, Excel, or JSON files to your library</p>
            <span className="home-action-arrow">→</span>
          </a>
          <a className="home-action-card" href="/quality-report">
            <div className="home-action-icon">🔍</div>
            <h3>Quality Report</h3>
            <p>Run profiling and detect issues on your data</p>
            <span className="home-action-arrow">→</span>
          </a>
          <a className="home-action-card" href="/repair-lab">
            <div className="home-action-icon">⚙️</div>
            <h3>Repair Lab</h3>
            <p>Generate, validate, and apply repair strategies</p>
            <span className="home-action-arrow">→</span>
          </a>
          <a className="home-action-card" href="/visualization-center">
            <div className="home-action-icon">📈</div>
            <h3>Visualization Center</h3>
            <p>Explore distributions, correlations, and patterns</p>
            <span className="home-action-arrow">→</span>
          </a>
          <a className="home-action-card" href="/ai-investigation">
            <div className="home-action-icon">🤖</div>
            <h3>AI Investigation</h3>
            <p>Root-cause analysis and evidence-grounded explanations</p>
            <span className="home-action-arrow">→</span>
          </a>
          <a className="home-action-card" href="/knowledge-base">
            <div className="home-action-icon">📚</div>
            <h3>Knowledge Base</h3>
            <p>Browse repair patterns and best practices</p>
            <span className="home-action-arrow">→</span>
          </a>
        </div>
      </section>

      {/* Recent Datasets */}
      <section className="home-section">
        <div className="section-heading">
          <div>
            <h2>Recent Datasets</h2>
            <p>Your {recentDatasets.length} most recently added datasets.</p>
          </div>
          <a className="outline-button" href="/datasets">View All</a>
        </div>

        {recentDatasets.length === 0 ? (
          <div className="repair-empty">
            <div className="empty-sparkle-box">📁</div>
            <h3>No datasets yet</h3>
            <p>Upload a CSV, Excel, or JSON file to start analyzing and repairing data.</p>
            <a className="primary-button" href="/datasets" style={{ marginTop: '16px', display: 'inline-flex' }}>
              <span>⬆</span> Upload Your First Dataset
            </a>
          </div>
        ) : (
          <div className="dataset-grid">
            {recentDatasets.map(dataset => {
              const d = details[dataset.id] || {};
              const version = dataset.latest_version;
              return (
                <article className="home-dataset-card" key={dataset.id}>
                  <div className="home-dataset-top">
                    <span className="version-pill">v{version?.version_number || 1}</span>
                    <span className="home-dataset-format">{version?.file_format ? version.file_format.toUpperCase() : 'FILE'}</span>
                  </div>
                  <h3>{dataset.name}</h3>
                  <p>{dataset.description || 'No description added.'}</p>
                  <div className="home-dataset-meta">
                    <span>Added {formatDate(dataset.created_at)}</span>
                    <span className="home-dataset-counts">
                      <span>📊 {formatNumber(d.records || 0)} rows</span>
                      <span>🔍 {d.issues || 0} issues</span>
                      <span>⚙️ {d.repairs || 0} repairs</span>
                    </span>
                  </div>
                  <div className="home-dataset-actions">
                    <a className="primary-button" href={`/repair-lab?dataset=${dataset.id}&version=${version?.id}`}>Repair</a>
                    <a className="outline-button" href={`/quality-report?dataset=${dataset.id}`}>Quality</a>
                    <a className="outline-button" href={`/visualization-center?dataset=${dataset.id}`}>Visualize</a>
                    <a className="outline-button" href={`/ai-investigation?dataset=${dataset.id}&version=${version?.id}`}>Investigate</a>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
};

function Metric({ icon, label, value, note, color }) {
  return (
    <div className={`metric-card ${color}`}>
      <div className="metric-glow"></div>
      <div className="metric-icon-wrap">
        <span className={`metric-icon ${color}`}>{icon}</span>
      </div>
      <div className="metric-info">
        <small>{label}</small>
        <strong>{value}</strong>
        <p>{note}</p>
      </div>
    </div>
  );
}

export default HomeDashboard;