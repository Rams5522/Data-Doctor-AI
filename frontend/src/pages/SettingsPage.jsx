import React, { useState, useEffect } from 'react';
import axios from 'axios';

const SettingsPage = () => {
  const [settings, setSettings] = useState({
    llmProvider: 'ollama',
    ollamaEndpoint: 'http://localhost:11434',
    openaiApiKey: '',
    ragEnabled: true,
    chromaDbPath: './storage/chroma',
    notificationsEnabled: true,
    dataRetentionDays: 90,
    autoBackup: true,
    backupInterval: 24
  });
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [llmStatus, setLlmStatus] = useState(null);
  const [llmTest, setLlmTest] = useState(null);
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    fetchSettings();
    fetchLlmStatus();
  }, []);

  const fetchLlmStatus = async () => {
    try {
      const response = await axios.get('/api/ai-investigation/llm/status');
      setLlmStatus(response.data);
      if (response.data?.provider) {
        setSettings(prev => ({ ...prev, llmProvider: response.data.provider }));
      }
    } catch (err) {
      setLlmStatus({ available: false, provider: 'unknown', model: '', available_models: [] });
    }
  };

  const testLlm = async () => {
    setTesting(true);
    setLlmTest(null);
    setError(null);
    try {
      const response = await axios.post('/api/ai-investigation/llm/test', null, {
        params: { prompt: 'Reply with the single word: ready' }
      });
      setLlmTest(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'LLM test failed. Check that Ollama is running or an OpenAI key is set in backend/.env');
    } finally {
      setTesting(false);
    }
  };

  const fetchSettings = async () => {
    // General settings are currently local UI preferences. LLM status is loaded separately.
  };

  const handleChange = (key, value) => {
    setSettings(prev => ({
      ...prev,
      [key]: value
    }));
    setSaved(false);
  };

  const handleSave = async () => {
    setLoading(true);
    setError(null);

    try {
      if (settings.llmProvider !== llmStatus?.provider) {
        throw new Error('Change LLM_PROVIDER in backend/.env and restart or reload the backend.');
      }
      await axios.post('/api/ai-investigation/llm/reload');
      await fetchLlmStatus();
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      setError('Failed to save settings. Settings endpoint not yet implemented.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <h1>Settings</h1>
        <p className="lead mb-0">Configure DataDoctor AI system settings</p>
      </div>
      <div className="page-content">
        {saved && (
          <div className="alert alert-success alert-dismissible fade show" role="alert">
            Settings saved successfully!
            <button type="button" className="btn-close" onClick={() => setSaved(false)}></button>
          </div>
        )}
        {error && (
          <div className="alert alert-warning alert-dismissible fade show" role="alert">
            {error}
            <button type="button" className="btn-close" onClick={() => setError(null)}></button>
          </div>
        )}

        {/* LLM Configuration */}
        <div className="card mb-4">
          <div className="card-header">
            <h2>LLM Configuration</h2>
            {llmStatus && (
              <span className={`badge ms-2 ${llmStatus.available ? 'bg-success' : 'bg-warning text-dark'}`}>
                {llmStatus.available ? 'Available' : 'Unavailable'} — {llmStatus.provider} / {llmStatus.model || 'unset'}
              </span>
            )}
          </div>
          <div className="card-body">
            <div className="row g-3">
              <div className="col-md-6">
                <label className="form-label">LLM Provider</label>
                <select
                  className="form-control"
                  value={settings.llmProvider}
                  onChange={(e) => handleChange('llmProvider', e.target.value)}
                  disabled={loading}
                >
                  <option value="ollama">Ollama (Local)</option>
                  <option value="openai">OpenAI (Cloud)</option>
                  <option value="groq">Groq (Cloud)</option>
                </select>
                <small className="form-text text-muted">
                  Provider is configured in backend/.env (LLM_PROVIDER, LLM_MODEL). This page reports live status.
                </small>
              </div>

              {settings.llmProvider === 'ollama' && (
                <div className="col-md-6">
                  <label className="form-label">Ollama Endpoint</label>
                  <input
                    type="text"
                    className="form-control"
                    value={settings.ollamaEndpoint}
                    onChange={(e) => handleChange('ollamaEndpoint', e.target.value)}
                    placeholder="http://localhost:11434"
                    disabled={loading}
                  />
                  <small className="form-text text-muted">
                    Ollama must be running locally with the model pulled.
                  </small>
                </div>
              )}

              {settings.llmProvider === 'groq' && (
                <div className="col-md-6">
                  <label className="form-label">Groq API Key</label>
                  <input
                    type="password"
                    className="form-control"
                    placeholder="gsk_..."
                    disabled={loading}
                  />
                  <small className="form-text text-muted">
                    Set GROQ_API_KEY in backend/.env, then restart the backend.
                  </small>
                </div>
              )}

              {settings.llmProvider === 'openai' && (
                <div className="col-md-6">
                  <label className="form-label">OpenAI API Key</label>
                  <input
                    type="password"
                    className="form-control"
                    value={settings.openaiApiKey}
                    onChange={(e) => handleChange('openaiApiKey', e.target.value)}
                    placeholder="sk-..."
                    disabled={loading}
                  />
                  <small className="form-text text-muted">
                    Your API key is stored securely (Stage 3)
                  </small>
                </div>
              )}
            </div>
            {llmStatus?.available_models?.length > 0 && (
              <p className="mt-3 mb-2"><small>Models: {llmStatus.available_models.join(', ')}</small></p>
            )}
            <div className="mt-3">
              <button className="btn btn-outline-primary" onClick={testLlm} disabled={testing}>
                {testing ? 'Testing...' : 'Test LLM connection'}
              </button>
            </div>
            {llmTest && (
              <div className="alert alert-success mt-3 mb-0">
                <strong>{llmTest.provider} / {llmTest.model}:</strong> {llmTest.response}
              </div>
            )}
          </div>
        </div>

        {/* RAG Configuration */}
        <div className="card mb-4">
          <div className="card-header">
            <h2>RAG System Configuration</h2>
            <span className="badge bg-warning text-dark ms-2">Stage 3 Feature</span>
          </div>
          <div className="card-body">
            <div className="row g-3">
              <div className="col-12">
                <div className="form-check form-switch">
                  <input
                    className="form-check-input"
                    type="checkbox"
                    id="ragEnabled"
                    checked={settings.ragEnabled}
                    onChange={(e) => handleChange('ragEnabled', e.target.checked)}
                    disabled={loading}
                  />
                  <label className="form-check-label" htmlFor="ragEnabled">
                    Enable RAG-powered knowledge base
                  </label>
                </div>
              </div>

              {settings.ragEnabled && (
                <div className="col-md-6">
                  <label className="form-label">ChromaDB Path</label>
                  <input
                    type="text"
                    className="form-control"
                    value={settings.chromaDbPath}
                    onChange={(e) => handleChange('chromaDbPath', e.target.value)}
                    placeholder="./storage/chroma"
                    disabled={loading}
                  />
                  <small className="form-text text-muted">
                    Local storage path for vector database (Stage 3)
                  </small>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Notifications */}
        <div className="card mb-4">
          <div className="card-header">
            <h2>Notifications</h2>
          </div>
          <div className="card-body">
            <div className="form-check form-switch mb-3">
              <input
                className="form-check-input"
                type="checkbox"
                id="notificationsEnabled"
                checked={settings.notificationsEnabled}
                onChange={(e) => handleChange('notificationsEnabled', e.target.checked)}
                disabled={loading}
              />
              <label className="form-check-label" htmlFor="notificationsEnabled">
                Enable notifications for repair operations
              </label>
            </div>
            <small className="text-muted">
              Get notified when repairs complete, fail, or require approval
            </small>
          </div>
        </div>

        {/* Data Management */}
        <div className="card mb-4">
          <div className="card-header">
            <h2>Data Management</h2>
          </div>
          <div className="card-body">
            <div className="row g-3">
              <div className="col-md-6">
                <label className="form-label">Data Retention Period</label>
                <select
                  className="form-control"
                  value={settings.dataRetentionDays}
                  onChange={(e) => handleChange('dataRetentionDays', parseInt(e.target.value))}
                  disabled={loading}
                >
                  <option value={30}>30 days</option>
                  <option value={60}>60 days</option>
                  <option value={90}>90 days</option>
                  <option value={180}>180 days</option>
                  <option value={365}>1 year</option>
                </select>
                <small className="form-text text-muted">
                  Automatically delete old datasets and versions
                </small>
              </div>

              <div className="col-12">
                <div className="form-check form-switch mb-3">
                  <input
                    className="form-check-input"
                    type="checkbox"
                    id="autoBackup"
                    checked={settings.autoBackup}
                    onChange={(e) => handleChange('autoBackup', e.target.checked)}
                    disabled={loading}
                  />
                  <label className="form-check-label" htmlFor="autoBackup">
                    Enable automatic backups
                  </label>
                </div>

                {settings.autoBackup && (
                  <div className="ms-4">
                    <label className="form-label">Backup Interval (hours)</label>
                    <input
                      type="number"
                      className="form-control"
                      style={{ maxWidth: '200px' }}
                      value={settings.backupInterval}
                      onChange={(e) => handleChange('backupInterval', parseInt(e.target.value))}
                      min="1"
                      max="168"
                      disabled={loading}
                    />
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Stage 2 Status */}
        <div className="card mb-4">
          <div className="card-header">
            <h2>Current Stage Status</h2>
          </div>
          <div className="card-body">
            <div className="row g-3">
              <div className="col-md-4">
                <div className="p-3 bg-success bg-opacity-10 rounded">
                  <h6 className="text-success mb-2">✅ Stage 1: Data Profiling</h6>
                  <small className="text-muted">Upload, profile, and analyze datasets</small>
                </div>
              </div>
              <div className="col-md-4">
                <div className="p-3 bg-success bg-opacity-10 rounded">
                  <h6 className="text-success mb-2">✅ Stage 2: Repair Engine</h6>
                  <small className="text-muted">Quality checks, repair candidates, validation, approval</small>
                </div>
              </div>
              <div className="col-md-4">
                <div className="p-3 bg-warning bg-opacity-10 rounded">
                  <h6 className="text-success mb-2">Stage 3: AI Intelligence</h6>
                  <small className="text-muted">Knowledge base, LLM investigations, repair memory</small>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Save Button */}
        <div className="d-flex justify-content-end mb-4">
          <button className="btn btn-primary btn-lg" onClick={handleSave} disabled={loading}>
            {loading ? 'Saving...' : 'Save Settings'}
          </button>
        </div>

        {/* System Information */}
        <div className="card">
          <div className="card-header">
            <h2>System Information</h2>
          </div>
          <div className="card-body">
            <div className="row g-3">
              <div className="col-md-6">
                <div className="p-3 bg-light rounded">
                  <h6 className="mb-2">Version</h6>
                  <p className="mb-0">DataDoctor AI v0.1.0 (Stage 3)</p>
                </div>
              </div>
              <div className="col-md-6">
                <div className="p-3 bg-light rounded">
                  <h6 className="mb-2">Database</h6>
                  <p className="mb-0">SQLite (local)</p>
                </div>
              </div>
              <div className="col-md-6">
                <div className="p-3 bg-light rounded">
                  <h6 className="mb-2">Storage Location</h6>
                  <p className="mb-0 small">./storage/</p>
                </div>
              </div>
              <div className="col-md-6">
                <div className="p-3 bg-light rounded">
                  <h6 className="mb-2">Backend API</h6>
                  <p className="mb-0">http://localhost:8000</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SettingsPage;