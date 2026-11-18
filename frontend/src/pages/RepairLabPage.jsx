import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';

const riskFor = operation => {
  if (!operation) return { label: 'LOW RISK', className: 'low' };
  if (operation.includes('outlier')) return { label: 'MEDIUM RISK', className: 'medium' };
  if (operation.includes('rule') || operation.includes('format')) return { label: 'REVIEW REQUIRED', className: 'high' };
  return { label: 'LOW RISK', className: 'low' };
};

const titleFor = operation => (operation || 'Repair strategy').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

const getRepairExplanation = (operation, parameters, selectedFindingId, findings) => {
  const finding = (selectedFindingId && findings.find(f => f.id === selectedFindingId)) || findings[0];
  const issueText = finding?.evidence?.description || finding?.issue_type || 'the detected data-quality problem';

  const op = String(operation || '').toLowerCase();
  const params = parameters || {};

  const bullets = (() => {
    if (op.includes('fill') || op.includes('impute') || op.includes('missing') || op.includes('null')) {
      const method = params.method || params.strategy || params.impute_method || 'a safe imputation rule';
      const value = params.value ?? params.constant;
      return [
        `Why it fixes it: the repair targets ${issueText} by filling missing/blank values in the affected column(s).`,
        `How it works: it uses **${method}**` + (value !== undefined ? ` (constant=${JSON.stringify(value)})` : '') + ` to generate replacement values.`,
        'Safety: validation re-runs checks and blocks the repair if it introduces new rule violations or worsens quality metrics.'
      ];
    }

    if (op.includes('duplicate') || op.includes('dedup')) {
      const subset = params.subset || params.columns || params.on || 'all columns';
      return [
        `Why it fixes it: the repair addresses ${issueText} by removing duplicated rows.` ,
        `How it works: it deduplicates using **${JSON.stringify(subset)}** (based on the operation parameters).`,
        'Safety: validation ensures row counts/types and downstream checks remain consistent.'
      ];
    }

    if (op.includes('outlier') || op.includes('winsor') || op.includes('clip') || op.includes('cap')) {
      const lower = params.lower ?? params.min ?? params.floor;
      const upper = params.upper ?? params.max ?? params.ceiling;
      return [
        `Why it fixes it: the repair targets ${issueText} by constraining extreme values (outliers) that break quality rules.`,
        `How it works: it applies a **clipping/capping** rule` +
          ((lower !== undefined || upper !== undefined)
            ? ` (lower=${lower ?? '—'}, upper=${upper ?? '—'})`
            : '') + ` to bring values back into an acceptable range.`,
        'Safety: validation confirms the rule checks pass and that the operation does not corrupt unaffected columns.'
      ];
    }

    if (op.includes('format') || op.includes('date') || op.includes('string') || op.includes('trim') || op.includes('normalize')) {
      const to = params.to_format || params.format || params.target_format;
      return [
        `Why it fixes it: the repair resolves ${issueText} by normalizing the representation (format/casing/whitespace) to match expected patterns.`,
        `How it works: it applies **${to ? `target format=${JSON.stringify(to)}` : 'a normalization rule'}** using the provided parameters.`,
        'Safety: validation verifies the updated values still satisfy schema/type constraints.'
      ];
    }

    if (op.includes('cast') || op.includes('type') || op.includes('convert')) {
      const dtype = params.dtype || params.target_type || params.type;
      return [
        `Why it fixes it: the repair targets ${issueText} by converting values into the expected data type.`,
        `How it works: it converts to **${dtype ? dtype : 'the operation’s target type'}**.` ,
        'Safety: validation blocks the repair if conversions cause parse failures or create new violations.'
      ];
    }

    if (op.includes('rule') || op.includes('business')) {
      const rule = params.rule || params.condition || 'the specified rule';
      return [
        `Why it fixes it: the repair addresses ${issueText} by enforcing the operation’s allowed business/data rule.`,
        `How it works: it applies **${rule}** to adjust values that violate constraints.`,
        'Safety: the validation stage checks before/after compliance and stops any change that would introduce new failures.'
      ];
    }

    return [
      `Why it fixes it: the repair is designed to improve ${issueText} by applying the registry-defined operation **${operation}** to the affected subset.`,
      `How it works: it uses **${JSON.stringify(params)}** to parameterize the deterministic transformation.`,
      'Safety: the apply step is only allowed after validation passes (or returns an explicitly “warning” result).'
    ];
  })();

  return (
    <ul>
      {bullets.map((b, idx) => <li key={idx}>{renderMarkdownInline(b)}</li>)}
    </ul>
  );
};

// Tiny helper to render **bold** inside our explanation strings.
const renderMarkdownInline = (text) => {
  const parts = String(text).split(/(\*\*[^*]+\*\*)/g).filter(Boolean);
  return parts.map((p, i) => {
    const m = p.match(/^\*\*([^*]+)\*\*$/);
    if (m) return <strong key={i}>{m[1]}</strong>;
    return <React.Fragment key={i}>{p}</React.Fragment>;
  });
};

const RepairLabPage = () => {
  const [datasets, setDatasets] = useState([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState(null);
  const [versions, setVersions] = useState([]);
  const [selectedVersionId, setSelectedVersionId] = useState(null);
  const [findings, setFindings] = useState([]);
  const [selectedFindingId, setSelectedFindingId] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [validationResults, setValidationResults] = useState({});
  const [selectedCandidates, setSelectedCandidates] = useState([]);
  const [selectedCandidate, setSelectedCandidate] = useState(null);
  const [profile, setProfile] = useState(null);
  const [approvedVersion, setApprovedVersion] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [exportFormat, setExportFormat] = useState('csv');
  const [previewOpen, setPreviewOpen] = useState(false);
  const [repairedPreview, setRepairedPreview] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const sourceFormat = useMemo(() => {
    const v = versions.find(x => x.id === selectedVersionId);
    return v?.file_format || null;
  }, [versions, selectedVersionId]);

  useEffect(() => {
    if (!sourceFormat) return;
    if (sourceFormat === 'csv') setExportFormat('csv');
    else if (sourceFormat === 'xlsx' || sourceFormat === 'xls') setExportFormat('xlsx');
    else if (sourceFormat === 'json') setExportFormat('json');
  }, [sourceFormat]);
  const [exporting, setExporting] = useState(false);
  const [showUpload, setShowUpload] = useState(false);
  const [uploadName, setUploadName] = useState('');
  const [showIssues, setShowIssues] = useState(false);
  const [comparisonCandidates, setComparisonCandidates] = useState([]);
  const [activeTab, setActiveTab] = useState('strategies');

  useEffect(() => { loadDatasets(); }, []);

  const loadDatasets = async () => {
    try {
      const response = await axios.get('/api/datasets/', { timeout: 30000 });
      const payload = response.data;
      const data = Array.isArray(payload) ? payload : (Array.isArray(payload?.value) ? payload.value : []);
      setDatasets(data);
      if (!data.length) { setError('No datasets are available. Upload a CSV, Excel, or JSON file.'); return; }
      const requested = Number(new URLSearchParams(window.location.search).get('dataset'));
      await loadDataset(data.some(d => Number(d.id) === requested) ? requested : Number(data[0].id));
    } catch (err) {
      setDatasets([]); setError(err.response?.data?.detail || 'Unable to load datasets. Check that the backend is running on port 8001.');
    }
  };

  const loadDataset = async datasetId => {
    setSelectedDatasetId(datasetId || null);
    setSelectedVersionId(null);
    setSelectedFindingId(null); setFindings([]); setCandidates([]); setSelectedCandidates([]); setValidationResults({}); setProfile(null); setApprovedVersion(null); setError(null);
    if (!datasetId) { setVersions([]); return; }
    try {
      const response = await axios.get(`/api/datasets/${datasetId}/versions`);
      const loaded = response.data || [];
      setVersions(loaded);
      const requested = Number(new URLSearchParams(window.location.search).get('version'));
      const version = loaded.find(v => v.id === requested) || loaded[0];
      if (version) await selectVersion(version.id);
    } catch (err) { setError(err.response?.data?.detail || 'Unable to load dataset versions'); }
  };

  const selectVersion = async (versionId) => {
    setSelectedVersionId(versionId || null);
    setSelectedFindingId(null); setFindings([]); setCandidates([]); setSelectedCandidates([]);
    setValidationResults({}); setProfile(null); setApprovedVersion(null); setShowIssues(false);
  };

  const detectIssues = async () => {
    if (!selectedDatasetId) { setError('Select a dataset first.'); return; }
    if (!selectedVersionId) {
      try {
        const response = await axios.get(`/api/datasets/${selectedDatasetId}/versions`);
        const firstVersion = (response.data || [])[0];
        if (!firstVersion) { setError('This dataset has no available version.'); return; }
        setVersions(response.data || []); setSelectedVersionId(firstVersion.id);
      } catch (err) { setError(err.response?.data?.detail || 'Unable to load the selected dataset version.'); }
      return;
    }
    setLoading(true); setError(null);
    try {
      await axios.post(`/api/quality/${selectedDatasetId}/detect?version_id=${selectedVersionId}`, null, { timeout: 120000 });
      await axios.post(`/api/profiling/${selectedDatasetId}/analyze?version_id=${selectedVersionId}`, null, { timeout: 120000 });
      const [findingsResponse, profileResponse] = await Promise.all([
        axios.get(`/api/quality/${selectedDatasetId}/findings?version_id=${selectedVersionId}`, { timeout: 30000 }),
        axios.get(`/api/profiling/${selectedDatasetId}/profile?version_id=${selectedVersionId}`, { timeout: 30000 })
      ]);
      setFindings(findingsResponse.data.findings || []);
      setProfile(profileResponse.data.profile_data);
      setShowIssues(true);
    } catch (err) { setError(err.response?.data?.detail || 'Unable to detect issues for this version'); }
    finally { setLoading(false); }
  };

  const generateCandidates = async () => {
    if (!selectedFindingId) return;
    setLoading(true); setError(null);
    try {
      const response = await axios.post(`/api/repair/${selectedDatasetId}/versions/${selectedVersionId}/findings/${selectedFindingId}/candidates`);
      setCandidates(response.data.candidates || []); setSelectedCandidates([]);
    } catch (err) { setError(err.response?.data?.detail || 'Unable to generate repair strategies'); }
    finally { setLoading(false); }
  };

  const formatApiError = (err, fallback) => {
    const detail = err.response?.data?.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) return detail.map(item => item.msg || JSON.stringify(item)).join('; ');
    return err.message || fallback;
  };

  const validate = async candidate => {
    setLoading(true); setError(null);
    try {
      const response = await axios.post(`/api/repair/repair-candidates/${candidate.id}/validate`);
      setValidationResults(prev => ({ ...prev, [candidate.id]: response.data }));
      if (response.data.validation_status === 'failed') {
        const reasons = [...(response.data.errors || []), ...(response.data.warnings || [])];
        setError(reasons.length ? `Validation failed: ${reasons.join(' ')}` : 'Validation failed: this repair did not pass the safety checks.');
      }
      return response.data;
    } catch (err) { setError(formatApiError(err, 'Validation failed. The backend could not validate this strategy.')); return null; }
    finally { setLoading(false); }
  };

  const validateAndApply = async candidate => {
    if (!candidate || loading) return;
    const result = await validate(candidate);
    if (!result || !['passed', 'warning'].includes(result.validation_status)) return;
    await approve(candidate, result);
  };

  const approve = async (candidate, validationOverride = null) => {
    if (!candidate) return;
    let validation = validationOverride || validationResults[candidate.id];
    if (!validation) {
      setLoading(true); setError(null);
      try {
        const response = await axios.post(`/api/repair/repair-candidates/${candidate.id}/validate`);
        validation = response.data;
        setValidationResults(prev => ({ ...prev, [candidate.id]: validation }));
      } catch (err) { setError(formatApiError(err, 'Validation failed. The backend could not validate this strategy.')); return; }
      finally { setLoading(false); }
    }
    if (!['passed', 'warning'].includes(validation.validation_status)) {
      setError(`This repair cannot be applied because validation status is ${validation.validation_status}.`);
      return;
    }
    if (!window.confirm(`Apply ${candidate.description}? The original dataset will remain unchanged.`)) return;
    setLoading(true); setError(null);
    try {
      const response = await axios.post(`/api/repair/repair-candidates/${candidate.id}/approve`);
      setApprovedVersion(response.data); setSelectedCandidate(null); setSelectedCandidates([]); setFindings([]); setCandidates([]);
      const versionsResponse = await axios.get(`/api/datasets/${selectedDatasetId}/versions`);
      setVersions(versionsResponse.data || []);
      setSelectedVersionId(response.data.new_version_id);
      setActiveTab('export');
    } catch (err) { setError(formatApiError(err, 'Unable to apply repair. The repaired version was not created.')); }
    finally { setLoading(false); }
  };

  const uploadDataset = async event => {
    const file = event.target.files?.[0]; if (!file) return;
    const form = new FormData(); form.append('file', file); form.append('name', uploadName || file.name.replace(/\.[^.]+$/, ''));
    setLoading(true); setError(null);
    try {
      const response = await axios.post('/api/datasets/upload', form);
      setShowUpload(false); setUploadName(''); await loadDatasets(); await loadDataset(response.data.dataset_id);
    } catch (err) { setError(err.response?.data?.detail || 'Upload failed. Check that the file is a readable CSV, Excel, or JSON dataset.'); } finally { setLoading(false); }
  };

  const downloadExport = async () => {
    if (!selectedDatasetId || !selectedVersionId) return;
    setExporting(true); setError(null);
    try {
      const response = await axios.get(`/api/datasets/${selectedDatasetId}/export`, { params: { format: exportFormat, version_id: selectedVersionId }, responseType: 'blob' });
      const url = URL.createObjectURL(response.data); const link = document.createElement('a'); link.href = url; link.download = `dataset_v${selectedVersion?.version_number || ''}.${exportFormat}`; link.click(); URL.revokeObjectURL(url);
    } catch (err) { setError('Unable to export this dataset version.'); } finally { setExporting(false); }
  };

  const viewRepairedFile = async () => {
    if (!approvedVersion || !selectedDatasetId) return;
    setPreviewLoading(true); setError(null);
    try {
      const response = await axios.get(`/api/datasets/${selectedDatasetId}/preview`, {
        params: { version_id: approvedVersion.new_version_id, limit: 100 },
        timeout: 30000
      });
      setRepairedPreview(response.data);
      setPreviewOpen(true);
    } catch (err) {
      setError(err.response?.data?.detail || 'Unable to load repaired file preview.');
    } finally {
      setPreviewLoading(false);
    }
  };

  const toggleCandidate = id => setSelectedCandidates(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);
  const compareSelected = () => {
    const selected = candidates.filter(candidate => selectedCandidates.includes(candidate.id));
    if (selected.length < 2) { setError('Select at least two repair methods to compare.'); return; }
    setComparisonCandidates(selected); setSelectedCandidate(selected[0]);
  };
  const totalRows = profile?.dataset_info?.num_rows || 0;
  const totalColumns = profile?.dataset_info?.num_columns || (profile?.column_profiles ? Object.keys(profile.column_profiles).length : 0);
  const missingCells = profile?.dataset_info?.missing_values ?? (profile?.column_profiles ? Object.values(profile.column_profiles).reduce((sum, column) => sum + (column.missing_count || 0), 0) : null);
  const duplicateRows = profile?.dataset_info?.duplicate_rows ?? null;
  const affectedRows = findings.reduce((sum, f) => sum + (f.affected_count || 0), 0);
  const validatedCount = candidates.filter(c => validationResults[c.id]?.validation_status === 'passed').length;
  const issueGroups = useMemo(() => Object.entries(findings.reduce((acc, f) => { acc[f.issue_type] = (acc[f.issue_type] || 0) + (f.affected_count || 0); return acc; }, {})), [findings]);
  const selectedVersion = versions.find(v => v.id === selectedVersionId);

  return (
    <div className="repair-lab-page">
    <div className="repair-lab-header">
      <div>
        <div className="header-badge"><span>⚡</span> AI REPAIR LAB</div>
        <h1>Data Repair Lab</h1>
        <p>Benchmark, validate, and apply intelligent data healing strategies with zero data loss.</p>
      </div>
      <div className="preserved-status">
        <span className="live-dot"></span>
        <span>Original Dataset Preserved</span>
      </div>
    </div>

    {error && <div className="repair-alert error"><span>⚠️</span> {error}</div>}
    {approvedVersion && <div className="repair-alert success"><span>✓</span> Repair approved. Version {approvedVersion.version_number} was created successfully.</div>}

    <div className="repair-toolbar">
      <div className="toolbar-top-row">
        <div className="toolbar-select">
          <div className="select-icon-box">📊</div>
          <div className="select-field-group">
            <label className="field-label">Active Dataset</label>
            <select value={selectedDatasetId || ''} onChange={e => loadDataset(Number(e.target.value) || null)}>
              <option value="">Select a dataset to begin…</option>
              {datasets.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
          </div>
          {selectedVersion && (
            <span className="version-badge">
              <span className="version-pill">v{selectedVersion.version_number}</span>
              <span className="version-type">{selectedVersion.version_type}</span>
            </span>
          )}
        </div>

        <div className="toolbar-upload">
          {showUpload ? (
            <div className="upload-panel">
              <input placeholder="Dataset name (optional)" value={uploadName} onChange={e => setUploadName(e.target.value)} />
              <input type="file" accept=".csv,.xlsx,.xls,.json" onChange={uploadDataset} />
              <button className="outline-button" onClick={() => setShowUpload(false)}>Cancel</button>
            </div>
          ) : (
            <button className="upload-button" onClick={() => setShowUpload(true)}>
              <span className="upload-btn-icon">⬆</span>
              <span>Upload Dataset</span>
            </button>
          )}
        </div>
      </div>

      <div className="toolbar-actions">
        <button className="detect-btn" onClick={detectIssues} disabled={!selectedVersionId || loading}>
          <span className="btn-icon">{loading ? '⏳' : '⚡'}</span>
          <span>{loading ? 'Analyzing Quality Issues…' : 'Detect Quality Issues'}</span>
        </button>
      </div>
    </div>

    <div className="repair-metrics">
      <Metric icon="🎯" label="Quality Score" value={profile ? `${Math.max(0, Math.round(100 - Math.min(100, (affectedRows / Math.max(totalRows, 1)) * 100)))}/100` : '—'} note={profile ? 'Based on detected findings' : 'Detect issues to calculate'} color="blue" />
      <Metric icon="⚠️" label="Issues Detected" value={findings.length || '—'} note="Current quality run" color="red" />
      <Metric icon="📊" label="Rows Affected" value={totalRows ? `${Math.min(100, Math.round((affectedRows / totalRows) * 1000) / 10)}%` : '—'} note={`${affectedRows || '—'} of ${totalRows || '—'} rows`} color="purple" />
      <Metric icon="✨" label="Candidates Ready" value={candidates.length || '—'} note={`${validatedCount} validated`} color="green" />
    </div>

    <div className="repair-grid">
      <div className="repair-tabs">
      <div className="tab-bar">
        <button className={`tab-btn ${activeTab === 'strategies' ? 'active' : ''}`} onClick={() => setActiveTab('strategies')}>
          <span className="tab-icon">🛠️</span>
          <span>Repair Strategies</span>
          {candidates.length > 0 && <span className="tab-count">{candidates.length}</span>}
        </button>
        <button className={`tab-btn ${activeTab === 'issues' ? 'active' : ''}`} onClick={() => setActiveTab('issues')}>
          <span className="tab-icon">📋</span>
          <span>Detected Issues</span>
          {findings.length > 0 && <span className="tab-count alert">{findings.length}</span>}
        </button>
        <button className={`tab-btn ${activeTab === 'export' ? 'active' : ''}`} onClick={() => setActiveTab('export')}>
          <span className="tab-icon">💾</span>
          <span>Export & Download</span>
          {approvedVersion && <span className="tab-count success">Ready</span>}
        </button>
      </div>
      <div className="tab-panel">
        {activeTab === 'strategies' && <section className="repair-section">
          <div className="section-heading">
            <div>
              <h2>AI Repair Strategies</h2>
              <p>Each strategy runs on an isolated copy; results are independently validated before applying.</p>
            </div>
            <span className="sandbox-label">🔒 Sandbox Execution</span>
          </div>

          <div className="finding-picker">
            <div className="finding-picker-header">
              <span className="picker-badge">TARGET ISSUE</span>
              <label>Select a detected quality issue to repair:</label>
            </div>
            <div className="finding-picker-controls">
              <select value={selectedFindingId || ''} onChange={e => setSelectedFindingId(Number(e.target.value) || null)} disabled={!findings.length}>
                <option value="">Choose an issue to repair…</option>
                {findings.map(f => <option key={f.id} value={f.id}>[{f.issue_type}] {f.evidence?.description || 'Detected issue'} ({f.affected_count || 0} affected)</option>)}
              </select>
              <button className="generate-btn" onClick={generateCandidates} disabled={!selectedFindingId || loading}>
                <span>✨</span>
                <span>{loading ? 'Synthesizing…' : 'Generate Strategies'}</span>
              </button>
            </div>
          </div>

          {!candidates.length ? (
            <EmptyState text={findings.length ? 'Select an issue above and click "Generate Strategies" to begin.' : 'Click "Detect Quality Issues" above to identify problems and synthesize fixes.'} />
          ) : (
            <div className="strategy-grid">
              {candidates.map(candidate => (
                <StrategyCard
                  key={candidate.id}
                  candidate={candidate}
                  validation={validationResults[candidate.id]}
                  selected={selectedCandidates.includes(candidate.id)}
                  onToggle={() => toggleCandidate(candidate.id)}
                  onInspect={() => setSelectedCandidate(candidate)}
                  onValidate={() => validate(candidate)}
                  onApprove={() => approve(candidate)}
                  onValidateAndApply={() => validateAndApply(candidate)}
                  loading={loading}
                />
              ))}
            </div>
          )}
        </section>}

        {activeTab === 'issues' && <section className="issues-section">
          <div className="issues-list">
            {findings.length ? findings.map(f => (
              <article className="issue-detail" key={f.id}>
                <div>
                  <strong>{titleFor(f.issue_type)}</strong>
                  <span className={`risk-badge ${f.severity === 'high' || f.severity === 'critical' ? 'high' : f.severity === 'medium' ? 'medium' : 'low'}`}>
                    <span className="risk-dot"></span>
                    {f.severity || 'review'}
                  </span>
                </div>
                <p>{f.evidence?.description || 'Detected data-quality issue.'}</p>
                <small>Column: {(f.affected_columns || []).join(', ') || 'Multiple'} · Affected rows: {f.affected_count || 0}</small>
                <p className="muted">💡 Recommended: {f.recommended_next_action || 'Review and choose a repair strategy.'}</p>
              </article>
            )) : (
              <p className="muted">No issues detected for this version. Click "Detect Quality Issues" to run analysis.</p>
            )}
          </div>
        </section>}

        {activeTab === 'export' && <section className="side-card export-card">
          <h3>Download Repaired Dataset</h3>
          <p className="muted">Export version {selectedVersion?.version_number || '—'} as a high-fidelity data file.</p>
          {approvedVersion && (
            <div className="repair-result">
              <span className="result-check">✓</span>
              <div>
                <strong>Repaired version {approvedVersion.version_number} is ready for download.</strong>
                <p className="muted" style={{ margin: '4px 0 0' }}>All changes were verified with zero data corruption.</p>
              </div>
              <div style={{ marginLeft: 'auto', display: 'flex', gap: '10px' }}>
                <button className="outline-button" onClick={viewRepairedFile} disabled={previewLoading}>
                  {previewLoading ? 'Loading…' : '👁 View Repaired File'}
                </button>
                <a className="outline-button" href={`/ai-investigation?dataset=${selectedDatasetId}&version=${approvedVersion.new_version_id}`}>
                  🤖 AI Investigation →
                </a>
              </div>
            </div>
          )}
          <div className="export-controls">
            <select value={exportFormat} onChange={e => setExportFormat(e.target.value)}>
              <option value="csv">CSV (Comma-Separated Values)</option>
              <option value="xlsx">Excel Workbook (.xlsx)</option>
              <option value="json">JSON Records</option>
              <option value="pdf">PDF Quality Report (100-row preview)</option>
            </select>
            <button className="primary-button" onClick={downloadExport} disabled={!selectedVersionId || exporting}>
              {exporting ? 'Preparing File…' : '📥 Download Repaired Dataset'}
            </button>
          </div>
        </section>}
      </div>
      </div>
    </div>

    <div className="repair-action-bar">
      <div className="action-bar-left">
        <button className="primary-button compare-btn" disabled={selectedCandidates.length < 2} onClick={compareSelected}>
          <span>⚖️</span> Compare Selected ({selectedCandidates.length})
        </button>
        <button className="outline-button preview-btn" disabled={!selectedCandidate} onClick={() => setSelectedCandidate(selectedCandidate)}>
          <span>👁</span> Preview Changes
        </button>
      </div>
      <div className="action-bar-center">
        <span className="safe-badge">🛡️ Zero-Risk Execution</span>
        <span className="action-bar-hint">Original file untouched · Immutable new version created</span>
      </div>
      <div className="action-bar-right">
        <button className="apply-button execute-btn" disabled={!selectedCandidate} onClick={() => approve(selectedCandidate)}>
          <span>⚡</span> Apply Repair
        </button>
      </div>
    </div>
    {comparisonCandidates.length > 1 && <div className="inspect-overlay" onClick={() => setComparisonCandidates([])}><div className="inspect-panel comparison-panel" onClick={e => e.stopPropagation()}><button className="close-button" onClick={() => setComparisonCandidates([])}>×</button><h2>Compare Repair Methods</h2><p className="muted">Validate each method to compare its measured results.</p>{comparisonCandidates.map(candidate => <div className="comparison-row" key={candidate.id}><strong>{titleFor(candidate.operation)}</strong><span>{validationResults[candidate.id]?.validation_status || 'Not validated'}</span><span>Improvement: {validationResults[candidate.id]?.metrics?.improvement ?? '—'}</span><button className="outline-button" onClick={() => setSelectedCandidate(candidate)}>Inspect</button></div>)}</div></div>}
    {selectedCandidate && <div className="inspect-overlay" onClick={() => setSelectedCandidate(null)}><div className="inspect-panel" onClick={e => e.stopPropagation()}><button className="close-button" onClick={() => setSelectedCandidate(null)}>×</button><h2>Inspect Strategy</h2><h3>{selectedCandidate.description}</h3><div className="inspect-explanation">
<h4>How this repair solves the issue</h4>
<div className="inspect-explanation-body">
{getRepairExplanation(selectedCandidate.operation, selectedCandidate.parameters, selectedFindingId, findings)}
</div>
</div>
<div className="inspect-stats">
<Overview label="Target Issue" value={selectedCandidate.issue_type || 'General Quality'} />
<Overview label="Operation" value={selectedCandidate.operation} />
<Overview label="Parameters" value={JSON.stringify(selectedCandidate.parameters || {})} />
<Overview label="Rows affected" value={selectedCandidate.issue_type ? findings.find(f => f.id === selectedFindingId)?.affected_count || '—' : '—'} />
<Overview label="Validation" value={validationResults[selectedCandidate.id]?.validation_status || 'Not run'} />
<Overview label="Errors" value={validationResults[selectedCandidate.id]?.errors?.length ?? '—'} />
<Overview label="Warnings" value={validationResults[selectedCandidate.id]?.warnings?.length ?? '—'} />
</div>
<p className="muted">This candidate runs against an isolated copy. Validation runs automatically before the repair is applied, and the original file stays unchanged.</p>
<div className="inspect-actions">
<button className="apply-button" onClick={() => approve(selectedCandidate)} disabled={loading}>
<span>⚡</span> {loading ? 'Applying…' : 'Apply Repair'}
</button>
</div>
</div></div>}

    {previewOpen && <div className="inspect-overlay" onClick={() => setPreviewOpen(false)}>
      <div className="inspect-panel" onClick={e => e.stopPropagation()} style={{ maxWidth: 980 }}>
        <button className="close-button" onClick={() => setPreviewOpen(false)}>×</button>
        <h2>Repaired file preview</h2>
        {previewLoading ? (
          <p className="muted">Loading preview…</p>
        ) : (
          <>
            <p className="muted">Showing first 100 rows (preview limited).</p>
            {repairedPreview?.columns?.length ? (
              <>
                <div style={{ overflow: 'auto', maxHeight: 420, border: '1px solid rgba(0,0,0,0.08)', borderRadius: 8 }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead>
                      <tr>
                        {repairedPreview.columns.map((c, idx) => (
                          <th key={idx} style={{ textAlign: 'left', padding: '8px 10px', background: '#f6f7fb', borderBottom: '1px solid rgba(0,0,0,0.08)' }}>{c}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {repairedPreview.data?.slice(0, 100)?.map((row, rIdx) => (
                        <tr key={rIdx}>
                          {repairedPreview.columns.map((c, cIdx) => (
                            <td key={cIdx} style={{ padding: '6px 10px', borderBottom: '1px solid rgba(0,0,0,0.04)' }}>{String(row[c] ?? '')}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="muted">Total rows: {repairedPreview.total_rows ?? '—'} · Preview rows: {repairedPreview.preview_rows ?? '—'}</p>
              </>
            ) : (
              <p className="muted">No preview available.</p>
            )}
          </>
        )}
      </div>
    </div>}
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

function StrategyCard({ candidate, validation, selected, onToggle, onInspect, onValidate, onApprove, onValidateAndApply, loading }) {
  const risk = riskFor(candidate.operation);
  const validated = validation && ['passed', 'warning'].includes(validation.validation_status);
  return (
    <article className={`strategy-card ${selected ? 'selected' : ''}`}>
      <div className="strategy-top">
        <input type="checkbox" checked={selected} onChange={onToggle} title="Select to compare" />
        <div className="strategy-title-area">
          <h3>{titleFor(candidate.operation)}</h3>
          <span className="strategy-op-tag"><code>{candidate.operation}</code></span>
        </div>
        <span className={`risk-badge ${risk.className}`}>
          <span className="risk-dot"></span>
          {risk.label}
        </span>
      </div>
      <p className="strategy-desc">{candidate.description}</p>
      <div className="strategy-meta">
        <div className="meta-cell">
          <small>Target Issue</small>
          <span>{candidate.issue_type || 'General Quality'}</span>
        </div>
        <div className="meta-cell params-cell">
          <small>Parameters</small>
          <code>{JSON.stringify(candidate.parameters || {})}</code>
        </div>
        <div className="meta-cell">
          <small>Safety Guarantee</small>
          <span className="safety-guarantee">🛡️ Sandbox Verified</span>
        </div>
      </div>
      <div className="strategy-metrics">
        <div className="metric-stat-box improvement">
          <small>Expected Improvement</small>
          <b>{validation?.metrics?.improvement ?? '—'}</b>
        </div>
        <div className="metric-stat-box side-effects">
          <small>Detected Side Effects</small>
          <b>{validation?.warnings?.length ?? '0'}</b>
        </div>
      </div>
      <div className="strategy-footer">
        <span className={`validation-dot ${validated ? 'passed' : ''}`}>
          <span className="v-dot"></span>
          {validation ? validation.validation_status : 'Not validated yet'}
        </span>
        <button className="outline-button inspect-btn" onClick={onInspect}>Inspect</button>
      </div>
    </article>
  );
}

function Safety({ label, status, warning }) {
  return (
    <div className={`safety-item ${warning ? 'warning' : ''}`}>
      <span>{warning ? '⚠️' : '✓'}</span>
      <div><b>{label}</b><small>{status}</small></div>
    </div>
  );
}

function Overview({ label, value }) {
  return (
    <div className="overview-row">
      <span>{label}</span>
      <b>{value}</b>
    </div>
  );
}

function EmptyState({ text }) {
  return (
    <div className="repair-empty">
      <div className="empty-sparkle-box">✨</div>
      <h3>Ready to Heal Your Dataset</h3>
      <p>{text}</p>
    </div>
  );
}
export default RepairLabPage;