import React from 'react';
import { NavLink } from 'react-router-dom';

const Sidebar = () => {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <h2>DataDoctor AI</h2>
      </div>

      <nav className="sidebar-nav">
        <ul>
          <li>
            <NavLink to="/" className={({ isActive }) => (isActive ? 'active' : undefined)}>
              <span>🏠</span>
              <span>Home Dashboard</span>
            </NavLink>
          </li>
          <li>
            <NavLink to="/datasets" className={({ isActive }) => (isActive ? 'active' : undefined)}>
              <span>📊</span>
              <span>Datasets</span>
            </NavLink>
          </li>
          <li>
            <NavLink to="/quality-report" className={({ isActive }) => (isActive ? 'active' : undefined)}>
              <span>📋</span>
              <span>Data Quality Report</span>
            </NavLink>
          </li>
          <li>
            <NavLink to="/repair-lab" className={({ isActive }) => (isActive ? 'active' : undefined)}>
              <span>🔧</span>
              <span>Repair Lab</span>
            </NavLink>
          </li>
          <li>
            <NavLink to="/visualization-center" className={({ isActive }) => (isActive ? 'active' : undefined)}>
              <span>📈</span>
              <span>Visualization Center</span>
            </NavLink>
          </li>
          <li>
            <NavLink to="/knowledge-base" className={({ isActive }) => (isActive ? 'active' : undefined)}>
              <span>📚</span>
              <span>Knowledge Base</span>
            </NavLink>
          </li>
          <li>
            <NavLink to="/ai-investigation" className={({ isActive }) => (isActive ? 'active' : undefined)}>
              <span>🤖</span>
              <span>AI Investigation</span>
            </NavLink>
          </li>
          <li>
            <NavLink to="/history-audit" className={({ isActive }) => (isActive ? 'active' : undefined)}>
              <span>🕒</span>
              <span>History & Audit</span>
            </NavLink>
          </li>
          <li>
            <NavLink to="/settings" className={({ isActive }) => (isActive ? 'active' : undefined)}>
              <span>⚙️</span>
              <span>Settings</span>
            </NavLink>
          </li>
        </ul>
      </nav>
    </aside>
  );
};

export default Sidebar;
