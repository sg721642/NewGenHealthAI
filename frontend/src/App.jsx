import { useState, useEffect, useRef, useCallback } from 'react';
import Header from './components/Header';
import Sidebar from './components/Sidebar';
import ChatTimeline from './components/ChatTimeline';
import MessageComposer from './components/MessageComposer';
import ConfirmationModal from './components/ConfirmationModal';
import Toast from './components/Toast';
import AuthPage from './pages/AuthPage';
import { useIsMobile } from './hooks/useIsMobile';
import { buildDownloadText } from './utils/formatters';
import './index.css';

const API_BASE = '/api/v1';

export default function App() {
  const isMobile = useIsMobile();
  const [theme, setTheme] = useState(() => localStorage.getItem('theme') || 'light');
  const [sidebarOpen, setSidebarOpen] = useState(() => {
    if (typeof window !== 'undefined' && window.innerWidth <= 768) return false;
    return localStorage.getItem('sidebarOpen') !== 'false';
  });

  // Auth state
  const [user, setUser] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('auth_user'));
    } catch {
      return null;
    }
  });
  const [authToken, setAuthToken] = useState(() => localStorage.getItem('auth_token') || null);

  // Consultation state
  const [sessions, setSessions] = useState(null);
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [chatHistory, setChatHistory] = useState([]);
  const [showWelcome, setShowWelcome] = useState(true);
  const [isTyping, setIsTyping] = useState(false);
  const [inputValue, setInputValue] = useState('');

  // UI state
  const [toast, setToast] = useState({ show: false, message: '', type: 'success' });
  const [confirmModal, setConfirmModal] = useState({
    isOpen: false,
    title: '',
    message: '',
    confirmText: 'Confirm',
    confirmVariant: 'danger',
    onConfirm: () => {},
  });

  // References for race safety and cancellation
  const activeAbortRef = useRef(null);
  const currentSessionIdRef = useRef(null);
  const currentUserRef = useRef(user);
  const chatAreaRef = useRef(null);
  const inputRef = useRef(null);
  const fileInputRef = useRef(null);
  const toastTimerRef = useRef(null);

  useEffect(() => {
    currentUserRef.current = user;
  }, [user]);

  useEffect(() => {
    currentSessionIdRef.current = currentSessionId;
  }, [currentSessionId]);

  // Apply theme to document element
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  const toggleTheme = useCallback(() => {
    setTheme((prev) => (prev === 'light' ? 'dark' : 'light'));
  }, []);

  const toggleSidebar = useCallback(() => {
    setSidebarOpen((prev) => {
      const next = !prev;
      if (!isMobile) localStorage.setItem('sidebarOpen', String(next));
      return next;
    });
  }, [isMobile]);

  const closeSidebar = useCallback(() => {
    setSidebarOpen(false);
  }, []);

  // Show Toast
  const showToast = useCallback((message, type = 'success') => {
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    setToast({ show: true, message, type });
    toastTimerRef.current = setTimeout(() => {
      setToast((prev) => ({ ...prev, show: false }));
    }, 3200);
  }, []);

  const dismissToast = useCallback(() => {
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    setToast((prev) => ({ ...prev, show: false }));
  }, []);

  // Helper for auth headers
  const authHeaders = useCallback(
    (extra = {}) => {
      const headers = { ...extra };
      if (authToken) headers['Authorization'] = `Bearer ${authToken}`;
      return headers;
    },
    [authToken]
  );

  // Abort pending requests
  const abortPendingRequests = useCallback(() => {
    if (activeAbortRef.current) {
      activeAbortRef.current.abort();
      activeAbortRef.current = null;
    }
  }, []);

  // Handle successful login or registration
  const handleAuthSuccess = useCallback(
    (userData, token) => {
      abortPendingRequests();
      setUser(userData);
      setAuthToken(token);
      setMessages([]);
      setChatHistory([]);
      setSessions(null);
      setCurrentSessionId(null);
      currentSessionIdRef.current = null;
      setShowWelcome(true);
    },
    [abortPendingRequests]
  );

  // Handle Logout
  const handleLogout = useCallback(async () => {
    abortPendingRequests();
    try {
      if (authToken) {
        await fetch(`${API_BASE}/auth/logout`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${authToken}` },
        });
      }
    } catch {
      /* silent */
    }
    localStorage.removeItem('auth_token');
    localStorage.removeItem('auth_user');
    setUser(null);
    setAuthToken(null);
    setMessages([]);
    setChatHistory([]);
    setSessions(null);
    setCurrentSessionId(null);
    currentSessionIdRef.current = null;
    setShowWelcome(true);
  }, [authToken, abortPendingRequests]);

  // Verify token validity on initial mount
  useEffect(() => {
    if (!authToken) return;
    let isMounted = true;
    fetch(`${API_BASE}/auth/me`, {
      headers: { Authorization: `Bearer ${authToken}` },
    })
      .then((res) => {
        if (!res.ok) throw new Error('Session invalid');
        return res.json();
      })
      .then((data) => {
        if (isMounted && data && data.username) {
          setUser((prev) => prev || { username: data.username, user_id: data.user_id });
        }
      })
      .catch(() => {
        if (isMounted) {
          localStorage.removeItem('auth_token');
          localStorage.removeItem('auth_user');
          setUser(null);
          setAuthToken(null);
          setMessages([]);
          setChatHistory([]);
          setSessions(null);
          setCurrentSessionId(null);
          setShowWelcome(true);
          showToast('Session expired. Please log in again.', 'info');
        }
      });
    return () => {
      isMounted = false;
    };
  }, [authToken, showToast]);

  // Auto-scroll chat area
  const scrollToBottom = useCallback(() => {
    if (chatAreaRef.current) {
      chatAreaRef.current.scrollTo({
        top: chatAreaRef.current.scrollHeight,
        behavior: 'smooth',
      });
    }
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping, scrollToBottom]);

  // Load consultations list
  const loadSessions = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/sessions`, { headers: authHeaders() });
      const data = await res.json();
      if (data.success && data.sessions) {
        setSessions(data.sessions);
      } else {
        setSessions([]);
      }
    } catch {
      setSessions([]);
    }
  }, [authHeaders]);

  // Mount: load consultations and active history
  useEffect(() => {
    if (!user) return;
    loadSessions();

    (async () => {
      try {
        const res = await fetch(`${API_BASE}/history`, { headers: authHeaders() });
        const data = await res.json();
        if (data.success && data.messages && data.messages.length > 0) {
          const msgs = data.messages.map((m) => ({
            type: m.role === 'user' ? 'user' : 'assistant',
            content: m.content,
            timestamp: m.timestamp || '',
            source: m.source || null,
          }));
          setMessages(msgs);
          setChatHistory(msgs.map((m) => ({ ...m })));
          setShowWelcome(false);
        }
      } catch {
        /* silent */
      }
    })();
  }, [loadSessions, user, authHeaders]);

  // Load specific consultation session
  const loadSession = useCallback(
    async (sessionId) => {
      abortPendingRequests();
      try {
        const res = await fetch(`${API_BASE}/session/${sessionId}`, { headers: authHeaders() });
        const data = await res.json();
        if (data.success) {
          setCurrentSessionId(sessionId);
          currentSessionIdRef.current = sessionId;
          const msgs = (data.messages || []).map((m) => ({
            type: m.role === 'user' ? 'user' : 'assistant',
            content: m.content,
            timestamp: m.timestamp || '',
            source: m.source || null,
          }));
          setMessages(msgs);
          setChatHistory(msgs.map((m) => ({ ...m })));
          setShowWelcome(false);
          showToast('Consultation loaded', 'success');
          if (isMobile) setSidebarOpen(false);
        }
      } catch {
        showToast('Failed to load consultation', 'error');
      }
    },
    [showToast, authHeaders, abortPendingRequests, isMobile]
  );

  // Create new consultation
  const createNewChat = useCallback(async () => {
    abortPendingRequests();
    try {
      const res = await fetch(`${API_BASE}/new-chat`, { method: 'POST', headers: authHeaders() });
      if (res.ok) {
        const data = await res.json();
        setMessages([]);
        setChatHistory([]);
        setCurrentSessionId(data.session_id || null);
        currentSessionIdRef.current = data.session_id || null;
        setShowWelcome(true);
        await loadSessions();
        showToast('New conversation started', 'success');
        if (isMobile) setSidebarOpen(false);
      }
    } catch {
      showToast('Failed to create consultation', 'error');
    }
  }, [authHeaders, loadSessions, showToast, abortPendingRequests, isMobile]);

  // Delete consultation with confirmation
  const deleteSession = useCallback(
    (sessionId) => {
      setConfirmModal({
        isOpen: true,
        title: 'Delete Consultation?',
        message: 'This will permanently delete this consultation history from your account. This action cannot be undone.',
        confirmText: 'Delete Consultation',
        confirmVariant: 'danger',
        onConfirm: async () => {
          setConfirmModal((prev) => ({ ...prev, isOpen: false }));
          if (currentSessionIdRef.current === sessionId) abortPendingRequests();
          try {
            const res = await fetch(`${API_BASE}/session/${sessionId}`, {
              method: 'DELETE',
              headers: authHeaders(),
            });
            if (res.ok) {
              await loadSessions();
              if (currentSessionIdRef.current === sessionId) createNewChat();
              showToast('Conversation deleted', 'success');
            }
          } catch {
            showToast('Failed to delete consultation', 'error');
          }
        },
      });
    },
    [loadSessions, showToast, authHeaders, abortPendingRequests, createNewChat]
  );

  // Clear current conversation
  const clearChat = useCallback(() => {
    setConfirmModal({
      isOpen: true,
      title: 'Clear Conversation?',
      message: 'This will clear all messages in the active consultation while preserving your account history.',
      confirmText: 'Clear Messages',
      confirmVariant: 'danger',
      onConfirm: async () => {
        setConfirmModal((prev) => ({ ...prev, isOpen: false }));
        abortPendingRequests();
        try {
          const res = await fetch(`${API_BASE}/clear`, { method: 'POST', headers: authHeaders() });
          if (res.ok) {
            setMessages([]);
            setChatHistory([]);
            setShowWelcome(true);
            showToast('Conversation cleared', 'success');
          }
        } catch {
          showToast('Failed to clear conversation', 'error');
        }
      },
    });
  }, [showToast, authHeaders, abortPendingRequests]);

  // Export consultation transcript
  const downloadChat = useCallback(() => {
    if (chatHistory.length === 0) {
      showToast('No messages to download', 'error');
      return;
    }
    const content = buildDownloadText(chatHistory);
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `NewGenHealthAI-chat-${Date.now()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
    showToast('Chat exported', 'success');
  }, [chatHistory, showToast]);

  // Image upload handling with full Phase 2A/3A safety classification
  const handleImageUpload = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const imageURL = URL.createObjectURL(file);
    const userMsg = {
      type: 'user',
      content: 'Uploaded medical image for clinical analysis',
      image: imageURL,
      timestamp: time,
    };

    setMessages((prev) => [...prev, userMsg]);
    setChatHistory((prev) => [...prev, userMsg]);
    setIsTyping(true);
    setShowWelcome(false);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch(`${API_BASE}/analyze-image`, {
        method: 'POST',
        body: formData,
        headers: authHeaders(),
      });
      const data = await res.json().catch(() => ({
        status: 'inconclusive',
        message: 'Unable to parse server response.',
      }));
      console.log('Image API Response:', data);

      if (data.status === 'model_unavailable') {
        const catName = data.category || 'this modality';
        let result = `## Specialist Model Unavailable\n\n`;
        result += `The AI specialist model for **${catName}** is not loaded on this server.\n\n`;
        result += `*${data.message || 'Model weights are required to analyze this type of medical image.'}*`;
        const botMsg = {
          type: 'assistant',
          content: result,
          timestamp: new Date().toLocaleTimeString(),
          source: 'System',
        };
        setMessages((prev) => [...prev, botMsg]);
      } else if (data.status === 'unsupported_image') {
        let result = `## Unsupported Image\n\n`;
        if (data.description) {
          result += `**Observed Content:** ${data.description}\n\n`;
        }
        result += `*The uploaded image does not appear to be a supported medical image (skin photo, X-ray radiograph, or retinal fundus scan).\nPlease upload a supported clinical image for AI analysis.*`;
        const botMsg = {
          type: 'assistant',
          content: result,
          timestamp: new Date().toLocaleTimeString(),
          source: 'Vision Classifier',
        };
        setMessages((prev) => [...prev, botMsg]);
      } else if (data.status === 'inconclusive') {
        let result = `## Analysis Inconclusive\n\n`;
        result += `${data.message || 'The image could not be reliably classified or visual features were ambiguous.'}\n\n`;
        result += `*Please upload a clearer clinical image for analysis.*`;
        const botMsg = {
          type: 'assistant',
          content: result,
          timestamp: new Date().toLocaleTimeString(),
          source: 'Vision Classifier',
        };
        setMessages((prev) => [...prev, botMsg]);
      } else if (data.status === 'invalid_image') {
        let result = `## Invalid Image\n\n`;
        result += `${data.error || 'The uploaded file could not be decoded as a valid image format.'}\n`;
        const botMsg = {
          type: 'assistant',
          content: result,
          timestamp: new Date().toLocaleTimeString(),
          source: 'System',
        };
        setMessages((prev) => [...prev, botMsg]);
      } else if (data.status === 'analysis_complete' || data.type === 'medical_diagnosis') {
        const categoryLabels = {
          skin: 'Skin Imaging',
          xray: 'X-ray Radiography',
          retina: 'Retinal Fundus Scan',
          general: 'General Medical Imaging',
        };
        const catLabel = categoryLabels[data.category] || 'Medical Imaging';
        const scoreVal =
          typeof data.score === 'number'
            ? data.score
            : typeof data.confidence === 'number'
            ? data.confidence
            : 0;

        let result = `## Medical Image Analysis\n\n`;
        result += `**Modality:** ${catLabel}\n\n`;
        result += `### Model Finding: **${data.disease}**\n`;
        result += `**Model Output Score:** ${scoreVal.toFixed(4)} *(uncalibrated prototype score, not a clinical probability)*\n\n`;

        if (data.is_negative_finding) {
          result += `> **Normal/Negative Reference**: The classifier identified features consistent with normal reference imagery. This is an algorithmic observation and does not rule out underlying medical conditions.\n\n`;
        } else if (data.finding_type === 'anatomy_identified') {
          result += `> **Anatomical Classification**: The classifier identified the anatomical location. No disease pathology or fracture was detected or confirmed by the model.\n\n`;
        }

        if (data.clinical_note) {
          result += `*${data.clinical_note}*\n\n`;
        }

        if (data.predictions && data.predictions.length > 0) {
          result += `### Differential Model Outputs\n`;
          data.predictions.forEach((p, i) => {
            const pScore =
              typeof p.score === 'number'
                ? p.score
                : typeof p.confidence === 'number'
                ? p.confidence
                : 0;
            const filled = Math.min(20, Math.max(0, Math.round(pScore * 20)));
            const bar = '█'.repeat(filled) + '░'.repeat(20 - filled);
            result += `${i + 1}. **${p.disease}** — Score: ${pScore.toFixed(4)} \`${bar}\`\n`;
          });
          result += '\n';
        }

        result += `---\n*Educational Notice: Model findings are experimental and must not be used as clinical diagnoses. Consult a licensed healthcare provider for medical evaluation and care.*\n`;

        const botMsg = {
          type: 'assistant',
          content: result,
          timestamp: new Date().toLocaleTimeString(),
          source: `${data.category || 'medical'} model`,
        };
        setMessages((prev) => [...prev, botMsg]);

        if (data.medical_details) {
          const detailMsg = {
            type: 'assistant',
            content: `### Literature Reference: ${data.disease}\n\n${data.medical_details}`,
            timestamp: new Date().toLocaleTimeString(),
            source: 'Medical Reference',
          };
          setMessages((prev) => [...prev, detailMsg]);
        }
      } else {
        let result = `## Image Analysis\n\n`;
        if (data.description) {
          result += `**Description:** ${data.description}\n\n`;
        }
        result += `*This image does not appear to be a recognizable medical image.\nUpload a clear skin photo, X-ray, retina scan, or other medical image for AI analysis.*`;
        const botMsg = {
          type: 'assistant',
          content: result,
          timestamp: new Date().toLocaleTimeString(),
        };
        setMessages((prev) => [...prev, botMsg]);
      }
    } catch (err) {
      console.error('Image analysis error:', err);
      setMessages((prev) => [
        ...prev,
        {
          type: 'assistant',
          content: 'Image analysis failed. Please try again with a valid clinical image.',
          timestamp: time,
        },
      ]);
    }

    setIsTyping(false);
    event.target.value = '';
  };

  // Send message
  const sendMessage = useCallback(
    async (overrideText) => {
      const message = (overrideText ?? inputValue).trim();
      if (!message || isTyping) return;

      setShowWelcome(false);
      const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      const userMsg = { type: 'user', content: message, timestamp: time, source: null };
      setMessages((prev) => [...prev, userMsg]);
      setChatHistory((prev) => [...prev, userMsg]);
      setInputValue('');
      if (inputRef.current) inputRef.current.style.height = 'auto';
      setIsTyping(true);

      abortPendingRequests();
      const controller = new AbortController();
      activeAbortRef.current = controller;
      const targetSessionId = currentSessionId;
      const targetUserId = user?.user_id || user?.id;

      try {
        const res = await fetch(`${API_BASE}/chat`, {
          method: 'POST',
          headers: authHeaders({
            'Content-Type': 'application/json',
            ...(targetSessionId ? { 'X-Session-ID': targetSessionId } : {}),
          }),
          body: JSON.stringify({ message }),
          signal: controller.signal,
        });

        // Guard against race conditions and stale response injection
        if (controller.signal.aborted) return;
        if (currentSessionIdRef.current !== targetSessionId) return;
        const currentUid = currentUserRef.current?.user_id || currentUserRef.current?.id;
        if (currentUid !== targetUserId) return;

        if (res.status === 409) {
          showToast('Conversation was cleared or modified while message was generating.', 'info');
          return;
        }

        if (res.status === 404) {
          showToast('Conversation not found or expired. Starting a fresh consultation.', 'info');
          setCurrentSessionId(null);
          currentSessionIdRef.current = null;
          setMessages((prev) => [
            ...prev,
            {
              type: 'assistant',
              content: 'This conversation was not found or has expired. A fresh session has been started.',
              timestamp: new Date().toLocaleTimeString(),
            },
          ]);
          await loadSessions();
          return;
        }

        const data = await res.json();
        if (data.success) {
          if (currentSessionIdRef.current !== targetSessionId) return;
          const botMsg = {
            type: 'assistant',
            content: data.response,
            timestamp: new Date().toLocaleTimeString(),
            source: data.source || null,
            followUp: data.follow_up || null,
          };
          setMessages((prev) => [...prev, botMsg]);
          setChatHistory((prev) => [...prev, botMsg]);
          if (data.follow_up) {
            showToast('Additional health intake questions available', 'info');
          } else {
            showToast('Response received', 'success');
          }
          await loadSessions();
        } else {
          setMessages((prev) => [
            ...prev,
            {
              type: 'assistant',
              content: 'I encountered an error processing your inquiry. Please try again.',
              timestamp: new Date().toLocaleTimeString(),
            },
          ]);
          showToast('Error occurred', 'error');
        }
      } catch (err) {
        if (err && err.name === 'AbortError') return;
        setMessages((prev) => [
          ...prev,
          {
            type: 'assistant',
            content: 'Connection error. Please check your network connection and retry.',
            timestamp: new Date().toLocaleTimeString(),
          },
        ]);
        showToast('Connection error', 'error');
      } finally {
        if (activeAbortRef.current === controller) {
          activeAbortRef.current = null;
        }
        setIsTyping(false);
      }
    },
    [inputValue, isTyping, loadSessions, showToast, authHeaders, currentSessionId, user, abortPendingRequests]
  );

  const handleQuickQuestion = useCallback(
    (q) => {
      setTimeout(() => sendMessage(q), 150);
    },
    [sendMessage]
  );

  const handleFollowUpClick = useCallback(
    (optionText) => {
      setTimeout(() => sendMessage(optionText), 150);
    },
    [sendMessage]
  );

  const triggerImageUpload = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const triggerVoiceInput = useCallback(() => {
    const micBtn = document.querySelector('.composer-action-btn.voice-btn');
    micBtn?.click();
  }, []);

  // Show Auth Page if not authenticated
  if (!user || !authToken) {
    return <AuthPage onAuthSuccess={handleAuthSuccess} />;
  }

  // Active session title
  const currentSessionObj = sessions?.find((s) => s.session_id === currentSessionId);
  const currentSessionTitle = currentSessionObj?.preview || (messages.length > 0 ? 'Active Consultation' : null);

  return (
    <div className="app-layout">
      {/* Mobile Backdrop Veil */}
      {isMobile && sidebarOpen && (
        <div
          className="sidebar-backdrop"
          onClick={closeSidebar}
          aria-hidden="true"
        />
      )}

      {/* Sidebar */}
      <Sidebar
        sidebarOpen={sidebarOpen}
        sessions={sessions}
        currentSessionId={currentSessionId}
        onNewChat={createNewChat}
        onLoadSession={loadSession}
        onDeleteSession={deleteSession}
        onToggleTheme={toggleTheme}
        theme={theme}
        user={user}
        onLogout={handleLogout}
      />

      {/* Main Workspace */}
      <div className="workspace-main">
        <Header
          sidebarOpen={sidebarOpen}
          onToggleSidebar={toggleSidebar}
          currentSessionTitle={currentSessionTitle}
          theme={theme}
          onToggleTheme={toggleTheme}
          onClearChat={clearChat}
          onDownloadChat={downloadChat}
          user={user}
          onLogout={handleLogout}
        />

        <main className="workspace-body">
          <ChatTimeline
            messages={messages}
            isTyping={isTyping}
            showWelcome={showWelcome}
            onQuickQuestion={handleQuickQuestion}
            onFollowUpClick={handleFollowUpClick}
            onTriggerImageUpload={triggerImageUpload}
            onTriggerVoiceInput={triggerVoiceInput}
            chatAreaRef={chatAreaRef}
          />

          <MessageComposer
            inputValue={inputValue}
            setInputValue={setInputValue}
            onSend={() => sendMessage()}
            isTyping={isTyping}
            inputRef={inputRef}
            onImageUpload={handleImageUpload}
            fileInputRef={fileInputRef}
            currentSessionId={currentSessionId}
          />
        </main>
      </div>

      {/* Accessible Confirmation Modal */}
      <ConfirmationModal
        isOpen={confirmModal.isOpen}
        title={confirmModal.title}
        message={confirmModal.message}
        confirmText={confirmModal.confirmText}
        confirmVariant={confirmModal.confirmVariant}
        onConfirm={confirmModal.onConfirm}
        onCancel={() => setConfirmModal((prev) => ({ ...prev, isOpen: false }))}
      />

      {/* Floating Status Notification */}
      <Toast toast={toast} onDismiss={dismissToast} />
    </div>
  );
}
