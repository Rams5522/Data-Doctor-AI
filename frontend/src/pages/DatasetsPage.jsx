import React, { useState, useEffect, useMemo } from 'react';
import axios from 'axios';

const formatLabel = format => {
  const map = { csv: 'CSV', xlsx: 'XLSX', xls: 'XLS', json: 'JSON' };
  return map[String(format || '').toLowerCase()] || 'FILE';
};

const formatDate = value => {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString();
};

const DatasetsPage = () => {
  const [datasets, setDatasets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const [deletingId, setDeletingId] = useState(null);
  const [query, setQuery] = useState('');

  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [file, setFile] = useState(null);

  useEffect(() => {
    fetchDatasets();
  }, []);

  const fetchDatasets = async () => {
    setLoading(true);
    try {
      const response = await axios.get('/api/datasets/');
      const payload = response.data;
      setDatasets(Array.isArray(payload) ? payload : (payload?.value || []));
      setError(null);
    } catch (err) {
      setError('Failed to fetch datasets. Check that the backend is running.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (datasetId) => {
    if (!window.confirm('Delete this dataset? This cannot be undone.')) return;
    try {
      setDeletingId(datasetId);
      await axios.delete(`/api/datasets/${datasetId}`);
      await fetchDatasets();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to delete dataset');
      console.error(err);
    } finally {
      setDeletingId(null);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setUploadError(null);

    if (!file) {
      setUploadError('Please select a file to upload');
      return;
    }

    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('name', name || file.name.replace(/\.[^.]+$/, ''));
      formData.append('description', description || '');

      await axios.post('/api/datasets/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      setName('');
      setDescription('');
      setFile(null);
      e.target.reset();
      await fetchDatasets();
    } catch (err) {
      setUploadError(err.response?.data?.detail || 'Upload failed. Check that the file is a readable CSV, Excel, or JSON dataset.');
      console.error(err);
    } finally {
      setUploading(false);
    }
  };

  const visibleDatasets = useMemo(() => {
    const term = query.trim().toLowerCase();
    if (!term) return datasets;
    return datasets.filter(dataset =>
      [dataset.name, dataset.description, dataset.latest_version?.file_format]
        .filter(Boolean)
        .some(value => String(value).toLowerCase().includes(term))
    );
  }, [datasets, query]);

  const formatCounts = useMemo(() => (
    datasets.reduce((counts, dataset) => {
      const format = String(dataset.latest_version?.file_format || 'other').toLowerCase();
      counts[format] = (counts[format] || 0) + 1;
      return counts;
    }, {})
  ), [datasets]);

  return (
    <div className="datasets-page">
      <div className="datasets-header">
        <div>
          <div className="header-badge"><span>📁</span> DATA LIBRARY</div>
          <h1>Datasets</h1>
          <p>Upload source files, keep every version, and send them straight to repair.</p>
        </div>
        <div className="datasets-summary">
          <span><b>{datasets.length}</b> datasets</span>
          <span><b>{formatCounts.csv || 0}</b> CSV</span>
          <span><b>{(formatCounts.xlsx || 0) + (formatCounts.xls || 0)}</b> Excel</span>
          <span><b>{formatCounts.json || 0}</b> JSON</span>
        </div>
      </div>

      {error && <div className="repair-alert error"><span>⚠️</span> {error}</div>}

      <section className="datasets-upload-card">
        <div className="datasets-upload-copy">
          <span className="picker-badge">NEW DATASET</span>
          <h2>Upload a dataset</h2>
          <p>CSV, Excel, and JSON are accepted. The original file is stored unchanged and every repair becomes a new version.</p>
        </div>
        <form className="datasets-upload-form" onSubmit={handleSubmit}>
          <label>
            <span className="field-label">Dataset name</span>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Optional — defaults to the file name"
              disabled={uploading}
            />
          </label>
          <label>
            <span className="field-label">Description</span>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What is this dataset for?"
              rows="3"
              disabled={uploading}
            />
          </label>
          <label className="datasets-file-field">
            <span className="field-label">Source file</span>
            <input
              type="file"
              accept=".csv,.xlsx,.xls,.json"
              disabled={uploading}
              onChange={(e) => setFile(e.target.files[0])}
            />
            <small>{file ? file.name : 'CSV, XLSX, XLS, or JSON'}</small>
          </label>
          <div className="datasets-upload-actions">
            <button type="submit" className="primary-button" disabled={uploading}>
              <span>⬆</span> {uploading ? 'Uploading…' : 'Upload Dataset'}
            </button>
            {uploadError && <span className="datasets-upload-error">{uploadError}</span>}
          </div>
        </form>
      </section>

      <section className="datasets-library">
        <div className="datasets-library-head">
          <div>
            <h2>Your datasets</h2>
            <p>{visibleDatasets.length} of {datasets.length} shown</p>
          </div>
          <input
            className="datasets-search"
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by name, description, or format"
          />
        </div>

        {loading ? (
          <div className="repair-empty">
            <div className="empty-sparkle-box">⏳</div>
            <h3>Loading datasets</h3>
            <p>Fetching the library from the backend.</p>
          </div>
        ) : visibleDatasets.length === 0 ? (
          <div className="repair-empty">
            <div className="empty-sparkle-box">📁</div>
            <h3>{datasets.length ? 'No datasets match your search' : 'No datasets yet'}</h3>
            <p>{datasets.length ? 'Try a different name, description, or file format.' : 'Upload a CSV, Excel, or JSON file to start analyzing and repairing data.'}</p>
          </div>
        ) : (
          <div className="dataset-grid">
            {visibleDatasets.map(dataset => {
              const version = dataset.latest_version;
              const format = formatLabel(version?.file_format);
              return (
                <article className="dataset-card" key={dataset.id}>
                  <div className="dataset-card-top">
                    <span className={`dataset-format format-${format.toLowerCase()}`}>{format}</span>
                    {version && <span className="version-pill">v{version.version_number}</span>}
                  </div>
                  <h3>{dataset.name}</h3>
                  <p>{dataset.description || 'No description added.'}</p>
                  <div className="dataset-meta">
                    <span>Added {formatDate(dataset.created_at)}</span>
                    <span>{version?.version_type || 'original'}</span>
                  </div>
                  <div className="dataset-actions">
                    {version ? (
                      <>
                        <a className="primary-button" href={`/repair-lab?dataset=${dataset.id}&version=${version.id}`}>Repair</a>
                        <a className="outline-button" href={`/ai-investigation?dataset=${dataset.id}&version=${version.id}`}>Investigate</a>
                        <a className="outline-button" href={`/api/datasets/${dataset.id}/versions/${version.id}/download`} download>Download</a>
                      </>
                    ) : (
                      <span className="muted">No version available</span>
                    )}
                    <button
                      className="outline-button dataset-delete"
                      onClick={() => handleDelete(dataset.id)}
                      disabled={deletingId === dataset.id}
                    >
                      {deletingId === dataset.id ? 'Deleting…' : 'Delete'}
                    </button>
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

export default DatasetsPage;
