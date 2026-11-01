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
import { requestManager } from './utils/requestManager';
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
  const [aiReady, setAiReady] = useState(true);
  const [selectedModality, setSelectedModality] = useState('auto');

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
  const currentSessionIdRef = useRef(null);
  const currentUserRef = useRef(user);
  const createdObjectURLsRef = useRef(new Set());
  const chatAreaRef = useRef(null);
  const inputRef = useRef(null);
  const fileInputRef = useRef(null);
  const toastTimerRef = useRef(null);

  useEffect(() => {
    currentUserRef.current = user;
    if (user) {
      requestManager.setCurrentUser(user.user_id || user.id);
    }
  }, [user]);

  useEffect(() => {
    currentSessionIdRef.current = currentSessionId;
  }, [currentSessionId]);

  // Clean up object URLs
  const revokeAllObjectURLs = useCallback(() => {
    createdObjectURLsRef.current.forEach((url) => {
      try {
        URL.revokeObjectURL(url);
      } catch {
        /* ignore */
      }
    });
    createdObjectURLsRef.current.clear();
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      revokeAllObjectURLs();
      requestManager.abortAll();
      if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    };
  }, [revokeAllObjectURLs]);

  // Apply theme to document element
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  // Check backend AI readiness
  useEffect(() => {
    let mounted = true;
    fetch('/api/v1/health')
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (mounted && data) {
          setAiReady(Boolean(data.ai_ready));
        }
      })
      .catch(() => {
        /* ignore network failure */
      });
    return () => {
      mounted = false;
    };
  }, []);

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



  // Handle successful login or registration
  const handleAuthSuccess = useCallback(
    (userData, token) => {
      requestManager.nextAuthGeneration(userData?.user_id || userData?.id);
      revokeAllObjectURLs();
      setUser(userData);
      setAuthToken(token);
      setMessages([]);
      setChatHistory([]);
      setSessions(null);
      setCurrentSessionId(null);
      currentSessionIdRef.current = null;
      setShowWelcome(true);
      setIsTyping(false);
    },
    [revokeAllObjectURLs]
  );

  // Handle Logout - Immediately Safe
  const handleLogout = useCallback(() => {
    // 1. Immediately invalidate auth generation & abort all in-flight requests
    requestManager.nextAuthGeneration(null);

    // 2. Immediately revoke object URLs to prevent memory leaks
    revokeAllObjectURLs();

    // 3. Immediately capture and remove credentials from localStorage
    const tokenToRevoke = authToken || localStorage.getItem('auth_token');
    localStorage.removeItem('auth_token');
    localStorage.removeItem('auth_user');

    // 4. Immediately clear all private UI state
    setUser(null);
    setAuthToken(null);
    setMessages([]);
    setChatHistory([]);
    setSessions(null);
    setCurrentSessionId(null);
    currentSessionIdRef.current = null;
    setShowWelcome(true);
    setIsTyping(false);

    // 5. Fire server-side revocation in background (non-blocking, doesn't delay privacy wipe)
    if (tokenToRevoke) {
      fetch(`${API_BASE}/auth/logout`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${tokenToRevoke}` },
      }).catch(() => {
        /* silent - local state is already safely wiped */
      });
    }
  }, [authToken, revokeAllObjectURLs]);

  // Verify token validity on initial mount
  useEffect(() => {
    if (!authToken) return;
    const request = requestManager.createRequest('auth', {
      userId: user?.user_id || user?.id,
    });

    fetch(`${API_BASE}/auth/me`, {
      headers: { Authorization: `Bearer ${authToken}` },
      signal: request.signal,
    })
      .then((res) => {
        if (!res.ok) throw new Error('Session invalid');
        return res.json();
      })
      .then((data) => {
        if (request.isValid() && data && data.username) {
          setUser((prev) => prev || { username: data.username, user_id: data.user_id });
          requestManager.setCurrentUser(data.user_id);
        }
      })
      .catch((err) => {
        if (err?.name === 'AbortError') return;
        if (request.isValid()) {
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
      })
      .finally(() => {
        request.complete();
      });

    return () => {
      request.abort();
    };
  }, [authToken, showToast, user]);

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
    if (!authToken) return;
    const request = requestManager.createRequest('sessions', {
      userId: user?.user_id || user?.id,
    });

    try {
      const res = await fetch(`${API_BASE}/sessions`, {
        headers: authHeaders(),
        signal: request.signal,
      });
      if (!request.isValid()) return;
      const data = await res.json();
      if (!request.isValid()) return;

      if (data.success && data.sessions) {
        setSessions(data.sessions);
      } else {
        setSessions((prev) => prev || []);
      }
    } catch (err) {
      if (err?.name === 'AbortError') return;
      // Preserve existing valid sessions on transient failure
      setSessions((prev) => prev || []);
    } finally {
      request.complete();
    }
  }, [authHeaders, authToken, user]);

  // Mount: load consultations and active history
  useEffect(() => {
    if (!user || !authToken) return;
    loadSessions();

    const request = requestManager.createRequest('history', {
      userId: user?.user_id || user?.id,
      sessionId: currentSessionIdRef.current,
    });

    fetch(`${API_BASE}/history`, {
      headers: authHeaders(),
      signal: request.signal,
    })
      .then((res) => res.json())
      .then((data) => {
        if (!request.isValid(currentSessionIdRef.current)) return;
        if (data.success && data.messages && data.messages.length > 0) {
          const msgs = data.messages.map((m) => ({
            type: m.role === 'user' ? 'user' : 'assistant',
            content: m.content,
            timestamp: m.timestamp || '',
            source: m.source || null,
            followUp: m.follow_up || m.followUp || null,
          }));
          setMessages(msgs);
          setChatHistory(msgs.map((m) => ({ ...m })));
          setShowWelcome(false);
        }
      })
      .catch((err) => {
        if (err?.name === 'AbortError') return;
      })
      .finally(() => {
        request.complete();
      });

    return () => {
      request.abort();
    };
  }, [loadSessions, user, authToken, authHeaders]);

  // Load specific consultation session
  const loadSession = useCallback(
    async (sessionId) => {
      const targetUserId = user?.user_id || user?.id;
      const request = requestManager.createRequest('history', {
        userId: targetUserId,
        sessionId,
      });

      try {
        const res = await fetch(`${API_BASE}/session/${sessionId}`, {
          headers: authHeaders(),
          signal: request.signal,
        });
        if (!request.isValid()) return;
        const data = await res.json();
        if (!request.isValid()) return;

        if (data.success) {
          revokeAllObjectURLs();
          setCurrentSessionId(sessionId);
          currentSessionIdRef.current = sessionId;
          const msgs = (data.messages || []).map((m, idx, arr) => {
            let followUp = m.follow_up || m.followUp || null;
            if (!followUp && data.follow_up && idx === arr.length - 1 && m.role === 'assistant') {
              followUp = data.follow_up;
            }
            return {
              type: m.role === 'user' ? 'user' : 'assistant',
              content: m.content,
              timestamp: m.timestamp || '',
              source: m.source || null,
              followUp,
            };
          });
          setMessages(msgs);
          setChatHistory(msgs.map((m) => ({ ...m })));
          setShowWelcome(false);
          showToast('Consultation loaded', 'success');
          if (isMobile) setSidebarOpen(false);
        }
      } catch (err) {
        if (err?.name === 'AbortError') return;
        if (request.isValid()) {
          showToast('Failed to load consultation', 'error');
        }
      } finally {
        request.complete();
      }
    },
    [showToast, authHeaders, isMobile, user, revokeAllObjectURLs]
  );

  // Create new consultation
  const createNewChat = useCallback(async () => {
    const targetUserId = user?.user_id || user?.id;
    const request = requestManager.createRequest('chat', {
      userId: targetUserId,
    });

    try {
      const res = await fetch(`${API_BASE}/new-chat`, {
        method: 'POST',
        headers: authHeaders(),
        signal: request.signal,
      });
      if (!request.isValid()) return;
      if (res.ok) {
        const data = await res.json();
        if (!request.isValid()) return;
        revokeAllObjectURLs();
        setMessages([]);
        setChatHistory([]);
        setCurrentSessionId(data.session_id || null);
        currentSessionIdRef.current = data.session_id || null;
        setShowWelcome(true);
        await loadSessions();
        showToast('New conversation started', 'success');
        if (isMobile) setSidebarOpen(false);
      }
    } catch (err) {
      if (err?.name === 'AbortError') return;
      if (request.isValid()) {
        showToast('Failed to create consultation', 'error');
      }
    } finally {
      request.complete();
    }
  }, [authHeaders, loadSessions, showToast, isMobile, user, revokeAllObjectURLs]);

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
          if (currentSessionIdRef.current === sessionId) {
            requestManager.abortCategory('chat');
            requestManager.abortCategory('image');
            revokeAllObjectURLs();
          }
          try {
            const res = await fetch(`${API_BASE}/session/${sessionId}`, {
              method: 'DELETE',
              headers: authHeaders(),
            });
            if (res.ok) {
              await loadSessions();
              if (currentSessionIdRef.current === sessionId) {
                createNewChat();
              }
              showToast('Conversation deleted', 'success');
            }
          } catch {
            showToast('Failed to delete consultation', 'error');
          }
        },
      });
    },
    [loadSessions, showToast, authHeaders, createNewChat, revokeAllObjectURLs]
  );

  // Clear all conversations with confirmation
  const handleClearAllSessions = useCallback(() => {
    if (!sessions || sessions.length === 0) {
      showToast('No consultations to clear', 'info');
      return;
    }

    setConfirmModal({
      isOpen: true,
      title: 'Clear All Consultations?',
      message: 'This will permanently delete all consultation histories from your account. This action cannot be undone.',
      confirmText: 'Delete All',
      confirmVariant: 'danger',
      onConfirm: async () => {
        setConfirmModal((prev) => ({ ...prev, isOpen: false }));
        requestManager.abortCategory('chat');
        requestManager.abortCategory('image');
        revokeAllObjectURLs();

        try {
          const res = await fetch(`${API_BASE}/sessions`, {
            method: 'DELETE',
            headers: authHeaders(),
          });
          if (res.ok) {
            setCurrentSessionId(null);
            currentSessionIdRef.current = null;
            setMessages([]);
            setChatHistory([]);
            setSessions([]);
            setShowWelcome(true);
            showToast('All consultations cleared', 'success');
          } else {
            showToast('Failed to clear consultations', 'error');
          }
        } catch {
          showToast('Failed to clear consultations', 'error');
        }
      },
    });
  }, [sessions, authHeaders, loadSessions, createNewChat, revokeAllObjectURLs, showToast]);

  // Clear current conversation
  const clearChat = useCallback(() => {
    const targetSessionId = currentSessionIdRef.current;
    if (!targetSessionId && messages.length === 0) {
      showToast('No active conversation to clear', 'info');
      return;
    }

    setConfirmModal({
      isOpen: true,
      title: 'Clear Conversation?',
      message: 'This will clear all messages in the active consultation while preserving your account history.',
      confirmText: 'Clear Messages',
      confirmVariant: 'danger',
      onConfirm: async () => {
        setConfirmModal((prev) => ({ ...prev, isOpen: false }));
        requestManager.abortCategory('chat');
        requestManager.abortCategory('image');
        revokeAllObjectURLs();

        try {
          const headers = authHeaders();
          if (targetSessionId) {
            headers['X-Session-ID'] = targetSessionId;
          }
          const res = await fetch(`${API_BASE}/clear`, {
            method: 'POST',
            headers,
          });
          if (res.ok) {
            setMessages([]);
            setChatHistory([]);
            setShowWelcome(true);
            showToast('Conversation cleared', 'success');
          } else {
            showToast('Failed to clear conversation', 'error');
          }
        } catch {
          showToast('Failed to clear conversation', 'error');
        }
      },
    });
  }, [showToast, authHeaders, messages.length, revokeAllObjectURLs]);

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

  // Image upload handling with full Phase 2A/3A/6 safety classification & validation
  const handleImageUpload = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    // Client-side format and size pre-validation
    const MAX_IMAGE_BYTES = 5 * 1024 * 1024; // 5MB
    const ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp'];

    if (!ALLOWED_IMAGE_TYPES.includes(file.type)) {
      showToast('Unsupported image format. Please select a JPEG, PNG, or WebP image.', 'error');
      if (event.target) event.target.value = '';
      return;
    }
    if (file.size > MAX_IMAGE_BYTES) {
      showToast('Image size exceeds 5MB limit. Please upload a smaller image.', 'error');
      if (event.target) event.target.value = '';
      return;
    }

    const targetSessionId = currentSessionIdRef.current;
    const targetUserId = user?.user_id || user?.id;

    const request = requestManager.createRequest('image', {
      userId: targetUserId,
      sessionId: targetSessionId,
    });

    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const imageURL = URL.createObjectURL(file);
    createdObjectURLsRef.current.add(imageURL);

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
    if (selectedModality && selectedModality !== 'auto') {
      formData.append('modality', selectedModality);
    }

    try {
      const headers = authHeaders();
      if (targetSessionId) {
        headers['X-Session-ID'] = targetSessionId;
      }

      const res = await fetch(`${API_BASE}/analyze-image`, {
        method: 'POST',
        body: formData,
        headers,
        signal: request.signal,
      });

      if (!request.isValid(currentSessionIdRef.current)) return;

      const data = await res.json().catch(() => ({
        status: res.status === 503 ? 'model_unavailable' : 'inconclusive',
        message: 'Unable to parse server response.',
      }));

      if (!request.isValid(currentSessionIdRef.current)) return;

      if (data.status === 'model_unavailable' || res.status === 503) {
        const catName = data.category ? data.category.charAt(0).toUpperCase() + data.category.slice(1) : 'Requested';
        let result = `## Specialist Model Unavailable\n\n`;
        result += `The AI specialist model for **${catName}** is not loaded on this server. The category was recognized, but the specialist deep learning analysis model is currently unavailable on this server.\n\n`;
        result += `*${data.message || 'No disease classification was performed.'}*`;
        const botMsg = {
          type: 'assistant',
          content: result,
          timestamp: new Date().toLocaleTimeString(),
          source: 'Vision Service',
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
      if (err?.name === 'AbortError') return;
      if (!request.isValid(currentSessionIdRef.current)) return;
      setMessages((prev) => [
        ...prev,
        {
          type: 'assistant',
          content: 'Image analysis failed. Please try again with a valid clinical image.',
          timestamp: time,
        },
      ]);
    } finally {
      request.complete();
      setIsTyping(false);
      if (event.target) event.target.value = '';
    }
  };

  // Chat message sending with request lifecycle protection and race guards
  const handleSendMessage = useCallback(
    async (textToSend) => {
      const message = (textToSend || inputValue).trim();
      if (!message || isTyping) return;

      const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      const userMsg = { type: 'user', content: message, timestamp: time };

      setMessages((prev) => [...prev, userMsg]);
      setChatHistory((prev) => [...prev, userMsg]);
      setInputValue('');
      setIsTyping(true);
      setShowWelcome(false);

      const targetSessionId = currentSessionIdRef.current;
      const targetUserId = user?.user_id || user?.id;

      const request = requestManager.createRequest('chat', {
        userId: targetUserId,
        sessionId: targetSessionId,
      });

      try {
        const res = await fetch(`${API_BASE}/chat`, {
          method: 'POST',
          headers: authHeaders({
            'Content-Type': 'application/json',
            ...(targetSessionId ? { 'X-Session-ID': targetSessionId } : {}),
          }),
          body: JSON.stringify({ message }),
          signal: request.signal,
        });

        // Guard against race conditions and stale response injection
        if (!request.isValid(currentSessionIdRef.current)) return;

        if (res.status === 409) {
          showToast('Conversation was cleared or modified while message was generating.', 'info');
          return;
        }

        if (res.status === 404) {
          showToast('Consultation not found or expired. Please start a new conversation.', 'info');
          setCurrentSessionId(null);
          currentSessionIdRef.current = null;
          setMessages((prev) => [
            ...prev,
            {
              type: 'assistant',
              content: 'This consultation was not found or has expired. Please click **New Conversation** to begin a fresh consultation.',
              timestamp: new Date().toLocaleTimeString(),
            },
          ]);
          await loadSessions();
          return;
        }

        const data = await res.json();
        if (!request.isValid(currentSessionIdRef.current)) return;

        if (data.success) {
          if (data.session_id && currentSessionIdRef.current !== data.session_id) {
            setCurrentSessionId(data.session_id);
            currentSessionIdRef.current = data.session_id;
          }
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
        if (request.signal.aborted || (err && (err.name === 'AbortError' || err.message?.includes('aborted')))) return;
        if (!request.isValid(currentSessionIdRef.current)) return;
        setMessages((prev) => [
          ...prev,
          {
            type: 'assistant',
            content: 'Unable to reach the clinical AI assistant. Please check your connection and retry.',
            timestamp: time,
          },
        ]);
        showToast('Connection error', 'error');
      } finally {
        request.complete();
        setIsTyping(false);
      }
    },
    [inputValue, isTyping, authHeaders, loadSessions, showToast, user]
  );

  const handleQuickQuestion = useCallback(
    (question) => {
      handleSendMessage(question);
    },
    [handleSendMessage]
  );

  const handleFollowUpClick = useCallback(
    (optionText) => {
      handleSendMessage(optionText);
    },
    [handleSendMessage]
  );

  const triggerImageUpload = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const triggerVoiceInput = useCallback(() => {
    // Focus the input area
    inputRef.current?.focus();
  }, []);

  // Not authenticated: render AuthPage
  if (!user) {
    return <AuthPage onAuthSuccess={handleAuthSuccess} />;
  }

  return (
    <div className="app-shell" data-theme={theme}>
      {/* Toast Alert */}
      <Toast toast={toast} onDismiss={dismissToast} />

      {/* Confirmation Modal */}
      <ConfirmationModal
        isOpen={confirmModal.isOpen}
        title={confirmModal.title}
        message={confirmModal.message}
        confirmText={confirmModal.confirmText}
        confirmVariant={confirmModal.confirmVariant}
        onConfirm={confirmModal.onConfirm}
        onCancel={() => setConfirmModal((prev) => ({ ...prev, isOpen: false }))}
      />

      <div className="app-layout">
        {/* Sidebar Drawer Backdrop for Mobile */}
        {sidebarOpen && isMobile && (
          <div
            className="sidebar-backdrop"
            onClick={closeSidebar}
            aria-hidden="true"
          />
        )}

        {/* Sidebar Navigation */}
        <Sidebar
          sidebarOpen={sidebarOpen}
          isOpen={sidebarOpen}
          sessions={sessions}
          currentSessionId={currentSessionId}
          user={user}
          theme={theme}
          onNewChat={createNewChat}
          onLoadSession={loadSession}
          onDeleteSession={deleteSession}
          onClearAllSessions={handleClearAllSessions}
          onLogout={handleLogout}
          onToggleTheme={toggleTheme}
        />

        {/* Workspace Main View */}
        <div className="workspace-main">
          {/* Header */}
          <Header
            sidebarOpen={sidebarOpen}
            onToggleSidebar={toggleSidebar}
            onClearChat={clearChat}
            onDownloadChat={downloadChat}
            theme={theme}
            onToggleTheme={toggleTheme}
            user={user}
            onLogout={handleLogout}
            aiReady={aiReady}
          />

          {/* Main Clinical Workspace */}
          <main className="chat-container">
            {/* Timeline */}
            <ChatTimeline
              messages={messages}
              isTyping={isTyping}
              showWelcome={showWelcome}
              chatAreaRef={chatAreaRef}
              onQuickQuestion={handleQuickQuestion}
              onTriggerImageUpload={triggerImageUpload}
              onTriggerVoiceInput={triggerVoiceInput}
              onFollowUpClick={handleFollowUpClick}
            />

            {/* Bottom Message Composer */}
            <MessageComposer
              inputValue={inputValue}
              setInputValue={setInputValue}
              isTyping={isTyping}
              onSend={() => handleSendMessage()}
              onImageUpload={handleImageUpload}
              fileInputRef={fileInputRef}
              inputRef={inputRef}
              currentSessionId={currentSessionId}
              selectedModality={selectedModality}
              setSelectedModality={setSelectedModality}
            />
          </main>
        </div>
      </div>
    </div>
  );
}
