import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';

const ACCOUNTS_KEY = 'datadoctor_accounts_v1';

function normalizeEmail(email) {
  return String(email || '').trim().toLowerCase();
}

async function sha256Hex(input) {
  const enc = new TextEncoder();
  const data = enc.encode(String(input));
  const hashBuffer = await crypto.subtle.digest('SHA-256', data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}

function loadAccounts() {
  try {
    const raw = localStorage.getItem(ACCOUNTS_KEY);
    if (!raw) return {};
    return JSON.parse(raw) || {};
  } catch {
    return {};
  }
}

function saveAccounts(accounts) {
  localStorage.setItem(ACCOUNTS_KEY, JSON.stringify(accounts));
}

const SignupPage = () => {
  const navigate = useNavigate();
  const { user, login, logout, booting } = useAuth();

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');

  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const emailNorm = useMemo(() => normalizeEmail(email), [email]);

  useEffect(() => {
    if (!booting && user) navigate('/');
  }, [booting, user, navigate]);

  const onSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    if (!emailNorm) {
      setError('Please enter your email.');
      return;
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }
    if (password !== confirm) {
      setError('Passwords do not match.');
      return;
    }

    setLoading(true);
    try {
      const accounts = loadAccounts();
      if (accounts[emailNorm]) {
        setError('An account with this email already exists.');
        return;
      }

      const passwordHash = await sha256Hex(password);
      accounts[emailNorm] = {
        email: emailNorm,
        name: name.trim() || emailNorm.split('@')[0],
        passwordHash,
        createdAt: new Date().toISOString()
      };
      saveAccounts(accounts);

      login({
        email: emailNorm,
        name: accounts[emailNorm].name,
        picture: null
      });

      navigate('/');
    } catch (err) {
      setError(err?.message || 'Unable to create account.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-shell">
        <div className="login-grid">
          <div className="login-card">
            <div className="login-brand">
              <div className="header-badge"><span>✨</span> CREATE ACCOUNT</div>
              <h1>DataDoctor AI</h1>
              <p>Create your account to save versions, validate repairs, and download outputs.</p>
            </div>

            <form className="login-form" onSubmit={onSubmit}>
              <div className="login-field">
                <label className="field-label">Full name</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Your name"
                  disabled={loading}
                />
              </div>

              <div className="login-field">
                <label className="field-label">Email</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  disabled={loading}
                  required
                />
              </div>

              <div className="login-field">
                <label className="field-label">Password</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="At least 8 characters"
                  disabled={loading}
                  required
                />
              </div>

              <div className="login-field">
                <label className="field-label">Confirm password</label>
                <input
                  type="password"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  placeholder="Re-enter password"
                  disabled={loading}
                  required
                />
              </div>

              {error && <div className="repair-alert error" style={{ marginTop: 6 }}><span>⚠️</span> {error}</div>}

              <button type="submit" className="primary-button" disabled={loading} style={{ marginTop: 16 }}>
                {loading ? 'Creating…' : 'Create account'}
              </button>

              <div className="login-footer">
                <span>Already have an account?</span>
                <button type="button" className="link-button" onClick={() => navigate('/login')} disabled={loading}>
                  Sign in
                </button>
              </div>

              <div className="muted" style={{ marginTop: 8 }}>
                Local demo accounts stored in this browser (replace with backend auth later).
              </div>
            </form>
          </div>

          <aside className="login-aside">
            <div className="login-aside-inner">
              <div className="aside-badge">🛡️ Secure-by-design</div>
              <h2>Versioned repairs.</h2>
              <p>
                DataDoctor never overwrites your originals. Every approved fix is validated and saved as a new immutable version.
              </p>
              <ul className="aside-points">
                <li>Deterministic, allowlisted repair operations</li>
                <li>Safety validation gates</li>
                <li>Export repaired datasets in original format</li>
              </ul>
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
};

export default SignupPage;
