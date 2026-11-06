import { useState, useEffect, useRef } from 'react';

export default function AuthPage({ onAuthSuccess }) {
  const [tab, setTab] = useState('login'); // 'login' | 'register'
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const timeoutRef = useRef(null);

  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
    };
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMessage('');
    setSuccessMessage('');

    const trimmedUsername = username.trim();
    if (!trimmedUsername || !password) {
      setErrorMessage('Please enter both your username and password.');
      return;
    }

    if (tab === 'register' && password.length < 8) {
      setErrorMessage('Password must be at least 8 characters long.');
      return;
    }

    setLoading(true);
    try {
      const endpoint = tab === 'login' ? '/api/v1/auth/login' : '/api/v1/auth/register';
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: trimmedUsername, password }),
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        if (res.status === 429) {
          setErrorMessage(data.detail || 'Too many attempts. Please wait 60 seconds before retrying.');
        } else {
          setErrorMessage(data.detail || 'Authentication failed. Please verify your credentials.');
        }
      } else {
        const welcomeText = tab === 'login'
          ? `Welcome back, ${data.username}!`
          : `Account created successfully. Welcome, ${data.username}!`;
        setSuccessMessage(welcomeText);

        localStorage.setItem('auth_token', data.token);
        localStorage.setItem(
          'auth_user',
          JSON.stringify({ username: data.username, user_id: data.user_id })
        );

        timeoutRef.current = setTimeout(() => {
          onAuthSuccess({ username: data.username, user_id: data.user_id }, data.token);
        }, 400);
      }
    } catch {
      setErrorMessage('Unable to connect to the authentication service. Please check your network connection.');
    } finally {
      setLoading(false);
    }
  };

  const handleTabChange = (newTab) => {
    setTab(newTab);
    setErrorMessage('');
    setSuccessMessage('');
  };

  const handleTabKeyDown = (e) => {
    if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
      e.preventDefault();
      handleTabChange(tab === 'login' ? 'register' : 'login');
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-surface">
        {/* Brand Header */}
        <div className="auth-brand">
          <div className="auth-brand-badge">
            <i className="fas fa-heart-pulse" />
          </div>
          <h1 className="auth-brand-title">NewGenHealthAI</h1>
          <p className="auth-brand-subtitle">AI-Powered Healthcare Intake & Clinical Education</p>
        </div>

        {/* Tab Controls */}
        <div className="auth-tabs" role="tablist" aria-label="Authentication Options">
          <button
            id="tab-login"
            type="button"
            role="tab"
            aria-selected={tab === 'login'}
            aria-controls="auth-panel"
            tabIndex={tab === 'login' ? 0 : -1}
            className={`auth-tab ${tab === 'login' ? 'active' : ''}`}
            onClick={() => handleTabChange('login')}
            onKeyDown={handleTabKeyDown}
          >
            Sign In
          </button>
          <button
            id="tab-register"
            type="button"
            role="tab"
            aria-selected={tab === 'register'}
            aria-controls="auth-panel"
            tabIndex={tab === 'register' ? 0 : -1}
            className={`auth-tab ${tab === 'register' ? 'active' : ''}`}
            onClick={() => handleTabChange('register')}
            onKeyDown={handleTabKeyDown}
          >
            Register
          </button>
        </div>

        {/* Greeting & Scope Notice */}
        <div className="auth-greeting">
          <h2 className="auth-greeting-title">
            {tab === 'login' ? 'Welcome Back' : 'Create an Account'}
          </h2>
          <p className="auth-greeting-desc">
            {tab === 'login'
              ? 'Access your private consultation history and AI health intake assistant.'
              : 'Sign up for private, isolated healthcare intake and clinical education.'}
          </p>
        </div>

        <div id="auth-panel" role="tabpanel" aria-labelledby={tab === 'login' ? 'tab-login' : 'tab-register'}>

        {/* Form */}
        <form onSubmit={handleSubmit} className="auth-form" noValidate>
          <div className="form-group">
            <label htmlFor="auth-username" className="form-label">
              Username
            </label>
            <div className="input-affix-wrapper">
              <span className="input-icon">
                <i className="fas fa-user" />
              </span>
              <input
                id="auth-username"
                type="text"
                className="form-input with-icon"
                placeholder="Enter your username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                autoFocus
                required
              />
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="auth-password" className="form-label">
              Password
            </label>
            <div className="input-affix-wrapper">
              <span className="input-icon">
                <i className="fas fa-lock" />
              </span>
              <input
                id="auth-password"
                type={showPassword ? 'text' : 'password'}
                className="form-input with-icon with-action"
                placeholder={tab === 'register' ? 'Minimum 8 characters' : 'Enter your password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete={tab === 'login' ? 'current-password' : 'new-password'}
                required
              />
              <button
                type="button"
                className="input-action-btn"
                onClick={() => setShowPassword((prev) => !prev)}
                title={showPassword ? 'Hide password' : 'Show password'}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
                tabIndex={-1}
              >
                <i className={`fas ${showPassword ? 'fa-eye-slash' : 'fa-eye'}`} />
              </button>
            </div>
          </div>

          {/* Feedback Messages */}
          {errorMessage && (
            <div className="auth-alert error" role="alert">
              <i className="fas fa-circle-exclamation" />
              <span>{errorMessage}</span>
            </div>
          )}

          {successMessage && (
            <div className="auth-alert success" role="status">
              <i className="fas fa-circle-check" />
              <span>{successMessage}</span>
            </div>
          )}

          <button
            type="submit"
            id="auth-submit"
            className="btn btn-primary auth-submit-btn"
            disabled={loading}
          >
            {loading ? (
              <>
                <i className="fas fa-spinner fa-spin" />
                <span>Processing...</span>
              </>
            ) : tab === 'login' ? (
              <>
                <i className="fas fa-right-to-bracket" />
                <span>Sign In</span>
              </>
            ) : (
              <>
                <i className="fas fa-user-plus" />
                <span>Create Free Account</span>
              </>
            )}
          </button>
        </form>
        </div>

        {/* Clinical Transparency & Privacy Note */}
        <div className="auth-disclaimer">
          <p className="disclaimer-text">
            <i className="fas fa-shield-heart" />
            <strong>Educational & Informational System:</strong> Consultations are private, isolated, and intended for symptom education. AI does not replace clinical evaluation by a licensed healthcare professional.
          </p>
        </div>
      </div>
    </div>
  );
}
