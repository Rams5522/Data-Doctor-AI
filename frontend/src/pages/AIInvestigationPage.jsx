import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import {
  Search,
  Database,
  Zap,
  AlertTriangle,
  TrendingDown,
  Wrench,
  ChevronRight,
  ChevronDown,
  Copy,
  Check,
  Loader2,
  Brain,
  FileText,
  Lightbulb,
  Shield,
  ArrowRight,
  BookOpen,
  X
} from 'lucide-react';

const INVESTIGATION_TYPES = [
  {
    id: 'root_cause',
    name: 'Root Cause Analysis',
    description: 'Identify underlying causes of data quality issues',
    icon: Brain,
    color: '#3b82f6',
    bg: 'rgba(59, 130, 246, 0.1)'
  },
  {
    id: 'pattern_analysis',
    name: 'Pattern Analysis',
    description: 'Discover patterns in data quality issues across columns',
    icon: Search,
    color: '#22c55e',
    bg: 'rgba(34, 197, 94, 0.1)'
  },
  {
    id: 'anomaly_detection',
    name: 'Anomaly Detection',
    description: 'Identify unusual data patterns and outliers',
    icon: AlertTriangle,
    color: '#f59e0b',
    bg: 'rgba(245, 158, 11, 0.1)'
  },
  {
    id: 'impact_assessment',
    name: 'Impact Assessment',
    description: 'Analyze potential business impact of data issues',
    icon: TrendingDown,
    color: '#ef4444',
    bg: 'rgba(239, 68, 68, 0.1)'
  },
  {
    id: 'repair_recommendation',
    name: 'Repair Recommendation',
    description: 'Get AI-powered repair strategy recommendations',
    icon: Wrench,
    color: '#a855f7',
    bg: 'rgba(168, 85, 247, 0.1)'
  }
];

const AIInvestigationPage = () => {
  const [query, setQuery] = useState('');
  const [investigationType, setInvestigationType] = useState('root_cause');
  const [investigationTypes, setInvestigationTypes] = useState(INVESTIGATION_TYPES);
  const [isProcessing, setIsProcessing] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);
  const [datasets, setDatasets] = useState([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState(null);
  const [selectedVersionId, setSelectedVersionId] = useState(null);
  const [availableVersions, setAvailableVersions] = useState([]);
  const [findings, setFindings] = useState([]);
  const [llmStatus, setLlmStatus] = useState(null);
  const [showContext, setShowContext] = useState(true);
  const [copiedRecommendation, setCopiedRecommendation] = useState(null);
  const [loading, setLoading] = useState(true);

  const selectedTypeMeta = useMemo(
    () => investigationTypes.find(t => t.id === investigationType) || INVESTIGATION_TYPES[0],
    [investigationTypes, investigationType]
  );

  useEffect(() => {
    setLoading(true);
    const params = new URLSearchParams(window.location.search);
    const datasetParam = Number(params.get('dataset'));
    const versionParam = Number(params.get('version'));
    if (datasetParam) setSelectedDatasetId(datasetParam);
    if (versionParam) setSelectedVersionId(versionParam);

    fetchDatasets();
    axios.get('/api/ai-investigation/investigation-types')
      .then(res => {
        if (res.data.types?.length) setInvestigationTypes(res.data.types);
      })
      .catch(() => {});
    axios.get('/api/ai-investigation/llm/status')
      .then(res => setLlmStatus(res.data))
      .catch(() => setLlmStatus({ available: false, provider: 'unknown', model: '' }));
  }, []);

  const fetchDatasets = async () => {
    try {
      const response = await axios.get('/api/datasets/');
      const data = response.data.value || response.data;
      setDatasets(data);
      if (data.length > 0 && !selectedDatasetId) setSelectedDatasetId(data[0].id);
    } catch (err) {
      console.error('Failed to fetch datasets:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (selectedDatasetId) {
      axios.get(`/api/datasets/${selectedDatasetId}/versions`)
        .then(res => {
          setAvailableVersions(res.data);
          if (res.data.length > 0) setSelectedVersionId(res.data[0].id);
        })
        .catch(err => console.error('Failed to fetch versions:', err));
    }
  }, [selectedDatasetId]);

  useEffect(() => {
    if (selectedDatasetId && selectedVersionId) {
      axios.get(`/api/quality/${selectedDatasetId}/findings?version_id=${selectedVersionId}`)
        .then(res => setFindings(res.data.findings || []))
        .catch(err => console.error('Failed to fetch findings:', err));
    }
  }, [selectedDatasetId, selectedVersionId]);

  const handleInvestigation = async (e) => {
    e.preventDefault();
    if (!query.trim() || !selectedDatasetId || !selectedVersionId) return;

    setIsProcessing(true);
    setError(null);
    setResults(null);
    setCopiedRecommendation(null);

    try {
      const response = await axios.post('/api/ai-investigation/investigate', {
        dataset_id: selectedDatasetId,
        version_id: selectedVersionId,
        investigation_type: investigationType,
        user_query: query
      });
      setResults(response.data);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Investigation failed. Run a quality check on this version first.');
    } finally {
      setIsProcessing(false);
    }
  };

  const copyToClipboard = (text, index) => {
    navigator.clipboard.writeText(text);
    setCopiedRecommendation(index);
    setTimeout(() => setCopiedRecommendation(null), 2000);
  };

  const canInvestigate = query.trim() && selectedDatasetId && selectedVersionId && !isProcessing;

  if (loading && !datasets.length) {
    return (
      <div className="ai-page">
        <div className="ai-header">
          <div className="header-badge"><span>🤖</span> AI INVESTIGATION</div>
          <h1>AI Investigation</h1>
          <p>Root-cause, pattern, and repair analysis grounded in quality findings</p>
        </div>
        <div className="ai-loading">
          <div className="empty-sparkle-box">🤖</div>
          <h3>Loading AI Investigation…</h3>
          <p>Preparing datasets and checking LLM status.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="ai-page">
      <div className="ai-header">
        <div>
          <div className="header-badge"><span>🤖</span> AI INVESTIGATION</div>
          <h1>AI Investigation</h1>
          <p>Root-cause, pattern, and repair analysis grounded in quality findings</p>
        </div>
        <div className="ai-header-status">
          {llmStatus && (
            <div className={`ai-llm-status ${llmStatus.available ? 'available' : 'unavailable'}`}>
              <Brain size={16} />
              <span>
                {llmStatus.available ? 'LLM Connected' : 'LLM Unavailable'}
                {' — '}
                {llmStatus.provider} / {llmStatus.model || 'not set'}
              </span>
            </div>
          )}
        </div>
      </div>

      {error && (
        <div className="ai-alert error">
          <AlertTriangle size={20} /> {error}
          <button onClick={() => setError(null)}><X size={16} /></button>
        </div>
      )}

      {/* Dataset Context Card */}
      {datasets.length > 0 && (
        <section className="ai-context-card" style={{ display: showContext ? 'block' : 'none' }}>
          <div className="ai-card-header">
            <h2>
              <Database size={20} /> Dataset Context
            </h2>
            <button
              className="ai-toggle-context"
              onClick={() => setShowContext(!showContext)}
            >
              {showContext ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
            </button>
          </div>

          {showContext && (
            <div className="ai-context-grid">
              <div className="ai-context-field">
                <label>Dataset</label>
                <select
                  className="quality-select"
                  value={selectedDatasetId || ''}
                  onChange={(e) => setSelectedDatasetId(parseInt(e.target.value) || null)}
                >
                  <option value="">-- Select Dataset --</option>
                  {datasets.map(dataset => (
                    <option key={dataset.id} value={dataset.id}>{dataset.name}</option>
                  ))}
                </select>
              </div>

              <div className="ai-context-field">
                <label>Version</label>
                <select
                  className="quality-select"
                  value={selectedVersionId || ''}
                  onChange={(e) => setSelectedVersionId(parseInt(e.target.value) || null)}
                  disabled={availableVersions.length === 0}
                >
                  <option value="">-- Select Version --</option>
                  {availableVersions.map(version => (
                    <option key={version.id} value={version.id}>
                      Version {version.version_number} ({version.version_type})
                    </option>
                  ))}
                </select>
              </div>

              <div className="ai-context-field">
                <label>Quality Findings</label>
                <div className="ai-findings-summary">
                  <span className="ai-findings-count">{findings.length}</span>
                  <span className="ai-findings-label">issues detected</span>
                </div>
              </div>

              {findings.length > 0 && (
                <div className="ai-findings-preview">
                  <label>Issue Types Found</label>
                  <div className="ai-findings-tags">
                    {[...new Set(findings.map(f => f.issue_type))].map(type => (
                      <span key={type} className="ai-finding-tag">
                        {type.replace(/_/g, ' ')}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </section>
      )}

      {/* Investigation Type Selection */}
      <section className="ai-type-selection">
        <div className="ai-card-header">
          <h2>
            <Brain size={20} /> Select Investigation Type
          </h2>
        </div>
        <div className="ai-type-grid">
          {investigationTypes.map(type => {
            const Icon = type.icon || Brain;
            const isActive = investigationType === type.id;
            return (
              <button
                key={type.id}
                type="button"
                className={`ai-type-card ${isActive ? 'active' : ''}`}
                onClick={() => setInvestigationType(type.id)}
                style={{ borderColor: isActive ? type.color : undefined }}
              >
                <div className="ai-type-icon" style={{ background: type.bg, color: type.color }}>
                  <Icon size={24} />
                </div>
                <div className="ai-type-content">
                  <h3>{type.name}</h3>
                  <p>{type.description}</p>
                </div>
                {isActive && (
                  <div className="ai-type-check" style={{ background: type.color }}>
                    <Check size={16} />
                  </div>
                )}
              </button>
            );
          })}
        </div>
      </section>

      {/* Query Input */}
      <section className="ai-query-card">
        <div className="ai-card-header">
          <h2>
            <FileText size={20} /> Describe Your Investigation
          </h2>
        </div>
        <form onSubmit={handleInvestigation} className="ai-query-form">
          <div className="ai-query-input-wrapper">
            <textarea
              className="ai-query-input"
              rows={4}
              placeholder={selectedTypeMeta.id === 'repair_recommendation'
                ? 'Describe the repair challenge... e.g. "Best strategy to fix missing salary values while preserving department-level patterns"'
                : 'Describe what you want to investigate... e.g. "Why are there so many missing values in the salary column?"'}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            {findings.length > 0 && (
              <div className="ai-query-hint">
                <Lightbulb size={14} />
                <span>Available issue types: {[...new Set(findings.map(f => f.issue_type))].join(', ')}</span>
              </div>
            )}
          </div>
          <div className="ai-query-actions">
            <div className="ai-query-status">
              {llmStatus?.available ? (
                <span className="ai-status-ready">
                  <Shield size={14} /> LLM-powered analysis ready
                </span>
              ) : (
                <span className="ai-status-fallback">
                  <Shield size={14} /> Deterministic fallback mode (configure LLM in Settings)
                </span>
              )}
            </div>
            <button
              type="submit"
              className="primary-button ai-submit-btn"
              disabled={!canInvestigate}
            >
              {isProcessing ? (
                <>
                  <Loader2 size={20} className="ai-spinner" />
                  Investigating…
                </>
              ) : (
                <>
                  <Zap size={20} />
                  Start Investigation
                </>
              )}
            </button>
          </div>
        </form>
      </section>

      {/* Results */}
      {results && (
        <section className="ai-results">
          <div className="ai-results-header">
            <div>
              <h2>Investigation Results</h2>
              <p className="ai-results-subtitle">
                {selectedTypeMeta.name} for {datasets.find(d => d.id === selectedDatasetId)?.name || 'selected dataset'}
              </p>
            </div>
            <span className={`ai-status-badge ${results.status === 'completed' ? 'success' : 'warning'}`}>
              {results.status}
            </span>
          </div>

          {results.error && (
            <div className="ai-alert error">
              <AlertTriangle size={20} /> {results.error}
            </div>
          )}

          {/* Analysis */}
          <div className="ai-result-section">
            <div className="ai-result-header">
              <h3>
                <FileText size={18} /> Analysis
              </h3>
            </div>
            <div className="ai-analysis-content">
              {results.analysis ? (
                <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit' }}>{results.analysis}</pre>
              ) : (
                <div className="ai-empty-analysis">No analysis generated</div>
              )}
            </div>
          </div>

          {/* Recommendations */}
          {results.recommendations?.length > 0 && (
            <div className="ai-result-section">
              <div className="ai-result-header">
                <h3>
                  <Lightbulb size={18} /> Recommendations
                </h3>
              </div>
              <div className="ai-recommendations">
                {results.recommendations.map((rec, index) => (
                  <div key={index} className="ai-recommendation-card">
                    <div className="ai-rec-number">{index + 1}</div>
                    <div className="ai-rec-content">
                      <p>{rec}</p>
                    </div>
                    <button
                      className={`ai-copy-btn ${copiedRecommendation === index ? 'copied' : ''}`}
                      onClick={() => copyToClipboard(rec, index)}
                      title={copiedRecommendation === index ? 'Copied!' : 'Copy to clipboard'}
                    >
                      {copiedRecommendation === index ? <Check size={16} /> : <Copy size={16} />}
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Evidence */}
          {results.evidence?.length > 0 && (
            <div className="ai-result-section">
              <div className="ai-result-header">
                <h3>
                  <Shield size={18} /> Evidence ({results.evidence.length})
                </h3>
              </div>
              <div className="ai-evidence-list">
                {results.evidence.slice(0, 12).map((item, index) => (
                  <div key={index} className="ai-evidence-item">
                    <div className="ai-evidence-icon">
                      {item.type === 'quality_finding' && <AlertTriangle size={16} />}
                      {item.type === 'knowledge_base' && <BookOpen size={16} />}
                      {item.type === 'repair_memory' && <Wrench size={16} />}
                    </div>
                    <div className="ai-evidence-content">
                      <div className="ai-evidence-title">
                        {item.type === 'quality_finding' && (
                          <>
                            <span className="ai-evidence-type">{item.issue_type?.replace(/_/g, ' ')}</span>
                            {item.severity && (
                              <span className={`ai-severity-badge ${item.severity}`}>{item.severity}</span>
                            )}
                          </>
                        )}
                        {item.type === 'knowledge_base' && item.title && (
                          <span className="ai-evidence-type">{item.title}</span>
                        )}
                        {item.type === 'repair_memory' && (
                          <>
                            <span className="ai-evidence-type">{item.operation}</span>
                            <span className="ai-evidence-subtype">{item.finding_type}</span>
                          </>
                        )}
                      </div>
                      <div className="ai-evidence-meta">
                        {item.affected_count !== undefined && (
                          <span>{item.affected_count} rows affected ({item.affected_percent?.toFixed(1)}%)</span>
                        )}
                        {item.columns?.length && (
                          <span>Columns: {item.columns.join(', ')}</span>
                        )}
                        {item.similarity !== undefined && (
                          <span className="ai-similarity">
                            <Sparkles size={12} /> {(item.similarity * 100).toFixed(0)}% match
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
                {results.evidence.length > 12 && (
                  <div className="ai-evidence-more">
                    +{results.evidence.length - 12} more evidence items
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Knowledge Base Matches */}
          {results.knowledge_base_articles?.length > 0 && (
            <div className="ai-result-section">
              <div className="ai-result-header">
                <h3>
                  <BookOpen size={18} /> Knowledge Base Matches
                </h3>
              </div>
              <div className="ai-kb-matches">
                {results.knowledge_base_articles.map(article => (
                  <div key={article.id} className="ai-kb-match">
                    <div className="ai-kb-match-title">{article.title}</div>
                    <div className="ai-kb-match-meta">
                      <span className="ai-kb-category">{article.category}</span>
                      {article.similarity && (
                        <span className="ai-similarity">
                          <Sparkles size={12} /> {(article.similarity * 100).toFixed(0)}%
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Similar Repairs */}
          {results.similar_repairs?.length > 0 && (
            <div className="ai-result-section">
              <div className="ai-result-header">
                <h3>
                  <Wrench size={18} /> Similar Past Repairs
                </h3>
              </div>
              <div className="ai-repair-matches">
                {results.similar_repairs.map(repair => (
                  <div key={repair.id} className="ai-repair-match">
                    <div className="ai-repair-match-main">
                      <span className="ai-repair-operation">{repair.operation}</span>
                      <span className="ai-repair-finding">{repair.finding_type}</span>
                    </div>
                    <div className="ai-repair-match-meta">
                      {repair.parameters && (
                        <span className="ai-repair-params">{JSON.stringify(repair.parameters)}</span>
                      )}
                      {repair.outcome && (
                        <span className={`ai-repair-outcome ${repair.outcome}`}>{repair.outcome}</span>
                      )}
                      {repair.similarity && (
                        <span className="ai-similarity">
                          <Sparkles size={12} /> {(repair.similarity * 100).toFixed(0)}%
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>
      )}

      {/* Empty State */}
      {!results && !isProcessing && (
        <div className="ai-empty-state">
          <div className="empty-sparkle-box">🤖</div>
          <h3>Ready to investigate</h3>
          <p>Select a dataset, choose an investigation type, and describe what you want to analyze.</p>
          <div className="ai-empty-hint">
            <kbd>Tip</kbd> Run a Quality Check first to populate findings, then investigate root causes or get repair recommendations.
          </div>
        </div>
      )}
    </div>
  );
};

const ChevronUp = ({ size }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
    <path d="M18 15l-6-6-6 6" />
  </svg>
);

const Sparkles = ({ size }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
  </svg>
);

export default AIInvestigationPage;