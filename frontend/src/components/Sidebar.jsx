import { useState, useMemo } from 'react';
import { formatTimeAgo } from '../utils/formatters';

export default function Sidebar({
  sidebarOpen,
  isOpen,
  sessions,
  currentSessionId,
  onNewChat,
  onLoadSession,
  onDeleteSession,
  onToggleTheme,
  theme,
  user,
  onLogout,
  onClearAllSessions,
}) {
  const isExpanded = sidebarOpen !== undefined ? sidebarOpen : (isOpen !== undefined ? isOpen : true);
  const [searchQuery, setSearchQuery] = useState('');

  const filteredSessions = useMemo(() => {
    if (!sessions) return null;
    if (!searchQuery.trim()) return sessions;
    const query = searchQuery.toLowerCase().trim();
    return sessions.filter((s) =>
      (s.preview || '').toLowerCase().includes(query)
    );
  }, [sessions, searchQuery]);

  return (
    <aside
      className={`app-sidebar ${isExpanded ? 'open' : 'collapsed'}`}
      aria-label="Consultation History and Controls"
    >
      {/* Brand Header */}
      <div className="sidebar-brand-section">
        <div className="sidebar-brand-row">
          <div className="sidebar-brand-badge" aria-hidden="true">
            <i className="fas fa-heart-pulse" />
          </div>
          <div className="sidebar-brand-text">
            <span className="sidebar-brand-name">NewGenHealthAI</span>
            <span className="sidebar-brand-version">Clinical AI Assistant v3.0</span>
          </div>
        </div>

        {/* New Conversation Button */}
        <button
          type="button"
          className="btn btn-primary new-chat-btn"
          onClick={onNewChat}
        >
          <i className="fas fa-plus" />
          <span>New Conversation</span>
        </button>
      </div>

      {/* Session Filter */}
      {sessions && sessions.length > 3 && (
        <div className="sidebar-search-box">
          <i className="fas fa-magnifying-glass search-icon" aria-hidden="true" />
          <input
            type="text"
            className="sidebar-search-input"
            placeholder="Filter consultations..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            aria-label="Filter consultation history"
          />
          {searchQuery && (
            <button
              type="button"
              className="search-clear-btn"
              onClick={() => setSearchQuery('')}
              aria-label="Clear filter"
            >
              <i className="fas fa-xmark" />
            </button>
          )}
        </div>
      )}

      {/* Consultations List */}
      <div className="sidebar-history-container">
        <div className="history-section-header">
          <span className="history-section-title">Consultation History</span>
          <div className="history-header-actions" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            {sessions && sessions.length > 0 && (
              <>
                <span className="history-count-badge">{sessions.length}</span>
                <button
                  type="button"
                  className="btn-clear-all-sessions"
                  onClick={onClearAllSessions}
                  title="Clear all consultation history"
                  aria-label="Clear all consultation history"
                  style={{
                    background: 'none',
                    border: 'none',
                    color: 'var(--color-danger, #ef4444)',
                    fontSize: '0.78rem',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    padding: '2px 6px',
                    borderRadius: '4px',
                  }}
                >
                  <i className="fas fa-trash-can" />
                  <span>Clear All</span>
                </button>
              </>
            )}
          </div>
        </div>

        <nav className="history-list" aria-label="Recent Consultations">
          {sessions === null ? (
            <div className="history-loading-state" role="status">
              <i className="fas fa-spinner fa-spin" />
              <span>Loading sessions…</span>
            </div>
          ) : filteredSessions.length === 0 ? (
            <div className="history-empty-state">
              <div className="empty-icon-wrap" aria-hidden="true">
                <i className="fas fa-comment-medical" />
              </div>
              <p className="empty-title">
                {searchQuery ? 'No matching consultations' : 'No conversations yet'}
              </p>
              <p className="empty-subtitle">
                {searchQuery ? 'Try a different search keyword' : 'Start your first chat.'}
              </p>
            </div>
          ) : (
            filteredSessions.map((session) => {
              const isActive = currentSessionId === session.session_id;
              return (
                <div
                  key={session.session_id}
                  className={`history-session-item ${isActive ? 'active' : ''}`}
                >
                  <button
                    type="button"
                    className="session-select-btn"
                    onClick={() => onLoadSession(session.session_id)}
                    aria-current={isActive ? 'true' : undefined}
                    title={session.title || session.preview || 'Open conversation'}
                  >
                    <div className="session-icon" aria-hidden="true">
                      <i className="fas fa-message" />
                    </div>
                    <div className="session-body">
                      <span className="session-title">
                        {session.title || session.preview || 'New conversation'}
                      </span>
                      <span className="session-time">
                        {formatTimeAgo(session.last_active)}
                      </span>
                    </div>
                  </button>
                  <button
                    type="button"
                    className="session-delete-btn"
                    title="Delete consultation"
                    aria-label={`Delete consultation: ${session.preview || 'New conversation'}`}
                    onClick={(e) => {
                      e.stopPropagation();
                      onDeleteSession(session.session_id);
                    }}
                  >
                    <i className="fas fa-trash" />
                  </button>
                </div>
              );
            })
          )}
        </nav>
      </div>

      {/* Sidebar Footer */}
      <div className="sidebar-footer">
        {/* Maintainer Info */}
        <div className="maintainer-card">
          <div className="maintainer-badge">
            <i className="fas fa-user-shield" />
            <span>Project Maintainer</span>
          </div>
          <span className="maintainer-name">Satyam Gupta</span>
          <span className="maintainer-org">NewGenHealthAI · Open Source</span>
        </div>

        {/* User Pill & Sign Out */}
        {user && (
          <div className="sidebar-user-block">
            <div className="sidebar-user-row">
              <div className="user-avatar-circle" aria-hidden="true">
                {user.username ? user.username[0].toUpperCase() : 'U'}
              </div>
              <div className="user-details">
                <span className="user-display-name">{user.username}</span>
                <span className="user-status-text">
                  <span className="status-indicator-dot" /> Authenticated
                </span>
              </div>
            </div>
            <button
              type="button"
              className="btn btn-secondary sidebar-logout-btn"
              onClick={onLogout}
            >
              <i className="fas fa-right-from-bracket" />
              <span>Sign Out</span>
            </button>
          </div>
        )}

        {/* Theme Toggle */}
        <button
          type="button"
          className="theme-switch-row"
          onClick={onToggleTheme}
        >
          <i className={`fas ${theme === 'dark' ? 'fa-sun' : 'fa-moon'}`} />
          <span>{theme === 'dark' ? 'Switch to Light' : 'Switch to Dark'}</span>
        </button>
      </div>
    </aside>
  );
}
