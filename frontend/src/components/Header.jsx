import { useState, useEffect } from 'react';

export default function Header({
  sidebarOpen,
  onToggleSidebar,
  currentSessionTitle,
  theme,
  onToggleTheme,
  onClearChat,
  onDownloadChat,
  user,
  onLogout,
}) {
  const [isFullscreen, setIsFullscreen] = useState(false);

  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, []);

  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(() => {});
    } else {
      document.exitFullscreen().catch(() => {});
    }
  };

  return (
    <header className="app-header">
      <div className="header-left">
        <button
          type="button"
          className="btn-icon header-nav-toggle"
          onClick={onToggleSidebar}
          aria-label={sidebarOpen ? 'Close sidebar' : 'Open sidebar'}
          aria-expanded={sidebarOpen}
          title="Toggle sidebar"
        >
          <i className="fas fa-bars" />
        </button>

        <div className="header-title-block">
          <div className="header-title-row">
            <span className="header-main-title">Medical AI Assistant</span>
            <span className="clinical-status-badge" title="AI assistant is active for informational intake">
              <span className="status-dot online" />
              <span>AI Ready</span>
            </span>
          </div>
          {currentSessionTitle && (
            <span className="header-session-subtitle" title={currentSessionTitle}>
              {currentSessionTitle}
            </span>
          )}
        </div>
      </div>

      <div className="header-right">
        {/* Fullscreen Toggle */}
        <button
          type="button"
          className="btn-icon"
          onClick={toggleFullscreen}
          title={isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'}
          aria-label={isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'}
        >
          <i className={`fas ${isFullscreen ? 'fa-compress' : 'fa-expand'}`} />
        </button>

        {/* Clear Chat */}
        <button
          type="button"
          className="btn-icon btn-icon-danger"
          onClick={onClearChat}
          title="Clear current conversation"
          aria-label="Clear current conversation"
        >
          <i className="fas fa-trash-can" />
        </button>

        {/* Export Transcript */}
        <button
          type="button"
          className="btn-icon"
          onClick={onDownloadChat}
          title="Download consultation transcript"
          aria-label="Download consultation transcript"
        >
          <i className="fas fa-arrow-down-to-line" />
        </button>

        {/* Theme Toggle */}
        <button
          type="button"
          className="btn-icon theme-toggle-btn"
          onClick={onToggleTheme}
          title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
        >
          <i className={`fas ${theme === 'dark' ? 'fa-sun' : 'fa-moon'}`} />
        </button>

        {/* User Pill / Mobile Sign Out */}
        {user && (
          <div className="header-user-pill">
            <span className="user-avatar" aria-hidden="true">
              {user.username ? user.username[0].toUpperCase() : 'U'}
            </span>
            <span className="user-name">{user.username}</span>
            <button
              type="button"
              className="btn-text user-signout-btn"
              onClick={onLogout}
              title="Sign out of your account"
            >
              Log out
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
