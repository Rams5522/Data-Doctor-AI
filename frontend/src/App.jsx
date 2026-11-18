import React, { useState, useRef, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation, useNavigate } from 'react-router-dom';
import Sidebar from './layouts/Sidebar';
import HomeDashboard from './pages/HomeDashboard';
import DatasetsPage from './pages/DatasetsPage';
import DataQualityReportPage from './pages/DataQualityReportPage';
import RepairLabPage from './pages/RepairLabPage';
import VisualizationCenterPage from './pages/VisualizationCenterPage';
import KnowledgeBasePage from './pages/KnowledgeBasePage';
import AIInvestigationPage from './pages/AIInvestigationPage';
import HistoryAuditPage from './pages/HistoryAuditPage';
import SettingsPage from './pages/SettingsPage';
import LoginPage from './pages/LoginPage';
import SignupPage from './pages/SignupPage';
import { AuthProvider, useAuth } from './auth/AuthContext';

function ProtectedRoutes() {
  const { user, booting } = useAuth();
  const location = useLocation();

  if (booting) {
    return (
      <div className="repair-empty" style={{ margin: 0 }}>
        <div className="empty-sparkle-box">⏳</div>
        <h3>Loading session…</h3>
        <p>Preparing your authenticated workspace.</p>
      </div>
    );
  }

  const isAuthPage = location.pathname === '/login' || location.pathname === '/signup';
  const authed = !!user;

  if (!authed && !isAuthPage) return <Navigate to="/login" replace />;
  if (authed && isAuthPage) return <Navigate to="/" replace />;

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route path="/" element={<HomeDashboard />} />
      <Route path="/datasets" element={<DatasetsPage />} />
      <Route path="/quality-report" element={<DataQualityReportPage />} />
      <Route path="/repair-lab" element={<RepairLabPage />} />
      <Route path="/visualization-center" element={<VisualizationCenterPage />} />
      <Route path="/knowledge-base" element={<KnowledgeBasePage />} />
      <Route path="/ai-investigation" element={<AIInvestigationPage />} />
      <Route path="/history-audit" element={<HistoryAuditPage />} />
      <Route path="/settings" element={<SettingsPage />} />
    </Routes>
  );
}

// Header with user menu for authenticated pages
function Header({ user, logout, navigate }) {
  const [showUserMenu, setShowUserMenu] = useState(false);
  const userMenuRef = useRef(null);

  const handleLogout = () => {
    logout();
    navigate('/login');
    setShowUserMenu(false);
  };

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (userMenuRef.current && !userMenuRef.current.contains(event.target)) {
        setShowUserMenu(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  if (!user) return null;

  return (
    <header className="main-header">
      <div className="main-header-left">
        <h1 className="main-header-title">DataDoctor AI</h1>
      </div>
      <div className="main-header-right">
        <div className="header-user-menu" ref={userMenuRef}>
          <button
            className="header-user-button"
            onClick={() => setShowUserMenu(!showUserMenu)}
            aria-expanded={showUserMenu}
            aria-haspopup="true"
          >
            <span className="header-user-avatar">
              {user.picture ? <img src={user.picture} alt="" /> : '👤'}
            </span>
            <span className="header-user-name">{user.name || user.email || 'User'}</span>
            <span className="header-user-chevron">{showUserMenu ? '▲' : '▼'}</span>
          </button>
          {showUserMenu && (
            <div className="header-user-dropdown" role="menu">
              {user.email && <div className="header-user-email" role="menuitem">{user.email}</div>}
              <div className="header-user-divider" />
              <button className="header-user-signout" role="menuitem" onClick={handleLogout}>
                Sign out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}

function AppShell() {
  const location = useLocation();
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const hideSidebar = location.pathname === '/login' || location.pathname === '/signup';

  return (
    <div className="app-container">
      {!hideSidebar ? <Sidebar /> : null}
      <div className="main-content">
        {!hideSidebar && user && <Header user={user} logout={logout} navigate={navigate} />}
        <ProtectedRoutes />
      </div>
    </div>
  );
}

function App() {
  return (
    <AuthProvider>
      <Router>
        <AppShell />
      </Router>
    </AuthProvider>
  );
}

export default App;
