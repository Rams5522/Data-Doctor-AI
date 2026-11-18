import React, { useEffect, useState } from 'react';
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

const LoginPage = () => {
  const navigate = useNavigate();
  const { user, login, booting, logout } = useAuth();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!booting && user) navigate('/');
  }, [booting, user, navigate]);

  const onSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    const emailNorm = normalizeEmail(email);
    if (!emailNorm) {
      setError('Please enter your email.');
      return;
    }
    if (!password) {
      setError('Please enter your password.');
      return;
    }

    setLoading(true);
    try {
      const accounts = loadAccounts();
      const account = accounts[emailNorm];
      if (!account) {
        setError('No account found for this email. Create one first.');
        return;
      }

      const passwordHash = await sha256Hex(password);
      if (account.passwordHash !== passwordHash) {
        setError('Incorrect password.');
        return;
      }

      login({
        email: account.email,
        name: account.name,
        picture: null
      });

      navigate('/');
    } catch (err) {
      setError(err?.message || 'Unable to sign in.');
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
              <div className="header-badge"><span>🔐</span> SIGN IN</div>
              <h1>DataDoctor AI</h1>
              <p>Sign in to save repair versions, validate changes, and download outputs.</p>
            </div>

            {user && (
              <div className="login-profile" style={{ marginTop: 10 }}>
                {user.picture ? <img src={user.picture} alt="User avatar" /> : <div className="login-avatar">👤</div>}
                <div className="login-profile-meta">
                  <div className="login-profile-name">{user.name || user.email || 'Signed in user'}</div>
                  <div className="login-profile-email">{user.email || '—'}</div>
                </div>
                <button className="outline-button" onClick={() => { logout(); navigate('/login'); }}>
                  Sign out
                </button>
              </div>
            )}

            {!user && (
              <form className="login-form" onSubmit={onSubmit}>
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
                    placeholder="••••••••"
                    disabled={loading}
                    required
                  />
                </div>

                {error && <div className="repair-alert error" style={{ marginTop: 6 }}><span>⚠️</span> {error}</div>}

                <button type="submit" className="primary-button" disabled={loading} style={{ marginTop: 16 }}>
                  {loading ? 'Signing in…' : 'Sign in'}
                </button>

                <div className="login-footer">
                  <span>New here?</span>
                  <button type="button" className="link-button" onClick={() => navigate('/signup')} disabled={loading}>
                    Create an account
                  </button>
                </div>

                <div className="muted" style={{ marginTop: 8 }}>
                  Demo auth is local to this browser (replace with backend auth later).
                </div>
              </form>
            )}
          </div>

          <aside className="login-aside">
            <div className="login-aside-inner">
              <div className="aside-badge">⚡ AI REPAIR LAB</div>
              <h2>Trusted repairs, every time.</h2>
              <p>
                DataDoctor detects defects, generates allowlisted strategies, validates safety, and exports repaired datasets without overwriting originals.
              </p>
              <ul className="aside-points">
                <li>Sandboxed execution</li>
                <li>Validation gates before apply</li>
                <li>Immutable version exports</li>
              </ul>
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
