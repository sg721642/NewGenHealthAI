import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import App from './App';

describe('App Integration', () => {
    // Mock fetch
    const mockFetch = vi.fn();
    global.fetch = mockFetch;

    beforeEach(() => {
        mockFetch.mockClear();
        // Default mocks
        mockFetch.mockResolvedValue({
            json: () => Promise.resolve({ success: true, messages: [], sessions: [] }),
            ok: true
        });

        // Use native localStorage of happy-dom
        localStorage.setItem('auth_user', JSON.stringify({ username: 'testuser' }));
        localStorage.setItem('auth_token', 'mock-token');
        localStorage.setItem('sidebarOpen', 'true');
        localStorage.setItem('theme', 'dark');
    });

    afterEach(() => {
        localStorage.clear();
        vi.restoreAllMocks();
    });

    it('renders app structure', async () => {
        render(<App />);
        expect(screen.getByText('Medical AI Assistant')).toBeInTheDocument();
        expect(screen.getAllByText('NewGenHealthAI').length).toBeGreaterThan(0);
        expect(screen.getByPlaceholderText('Describe your symptoms or ask a medical question…')).toBeInTheDocument();
    });

    it('loads sessions on mount', async () => {
        const mockSessions = [{ session_id: '1', preview: 'Flu symptoms', last_active: '2023' }];
        mockFetch.mockImplementation((url) => {
            if (url === '/api/v1/sessions') {
                return Promise.resolve({
                    json: () => Promise.resolve({ success: true, sessions: mockSessions }),
                    ok: true
                });
            }
            return Promise.resolve({ json: () => Promise.resolve({ success: true }), ok: true });
        });

        render(<App />);

        await waitFor(() => {
            expect(screen.getByText('Flu symptoms')).toBeInTheDocument();
        });
    });

    it('sends a message and displays response', async () => {
        // Setup mocks
        mockFetch.mockImplementation((url, _options) => {
            if (url === '/api/v1/chat') {
                return Promise.resolve({
                    json: () => Promise.resolve({
                        success: true,
                        response: 'I can help with that.',
                        source: 'test-source',
                        timestamp: 'now'
                    }),
                    ok: true
                });
            }
            return Promise.resolve({ json: () => Promise.resolve({ success: true, sessions: [] }), ok: true });
        });

        render(<App />);

        const input = screen.getByPlaceholderText('Describe your symptoms or ask a medical question…');
        fireEvent.change(input, { target: { value: 'Headache' } });

        const sendBtn = screen.getByRole('button', { name: /Send message/i });
        fireEvent.click(sendBtn);

        expect(screen.getByText('Headache')).toBeInTheDocument(); // Optimistic UI

        await waitFor(() => {
            expect(screen.getByText('I can help with that.')).toBeInTheDocument();
        });
    });

    it('creates new chat', async () => {
        mockFetch.mockImplementation((url) => {
            if (url === '/api/v1/new-chat') {
                return Promise.resolve({
                    json: () => Promise.resolve({ success: true, session_id: 'new-session' }),
                    ok: true
                });
            }
            return Promise.resolve({ json: () => Promise.resolve({ success: true, sessions: [] }), ok: true });
        });

        render(<App />);

        const newChatBtn = screen.getByText('New Conversation');
        fireEvent.click(newChatBtn);

        await waitFor(() => {
            // Check if new chat API was called
            expect(mockFetch).toHaveBeenCalledWith('/api/v1/new-chat', expect.any(Object));
        });
    });

    it('clears state and aborts pending requests on logout', async () => {
        render(<App />);

        const logoutBtn = screen.getByText('Sign Out');
        fireEvent.click(logoutBtn);

        await waitFor(() => {
            expect(localStorage.getItem('auth_token')).toBeNull();
            expect(localStorage.getItem('auth_user')).toBeNull();
            expect(screen.getByText('Welcome Back')).toBeInTheDocument();
        });
    });

    it('suppresses stale response if session changes before response arrives', async () => {
        let resolveChat;
        const chatPromise = new Promise((resolve) => {
            resolveChat = resolve;
        });

        mockFetch.mockImplementation((url) => {
            if (url === '/api/v1/chat') {
                return chatPromise;
            }
            if (url === '/api/v1/new-chat') {
                return Promise.resolve({
                    json: () => Promise.resolve({ success: true, session_id: 'session-2' }),
                    ok: true,
                });
            }
            return Promise.resolve({ json: () => Promise.resolve({ success: true, sessions: [] }), ok: true });
        });

        render(<App />);

        const input = screen.getByPlaceholderText('Describe your symptoms or ask a medical question…');
        fireEvent.change(input, { target: { value: 'Query for session 1' } });
        const sendBtn = screen.getByRole('button', { name: /Send message/i });
        fireEvent.click(sendBtn);

        expect(screen.getByText('Query for session 1')).toBeInTheDocument();

        // Switch session by clicking New Conversation
        const newChatBtn = screen.getByText('New Conversation');
        fireEvent.click(newChatBtn);

        await waitFor(() => {
            expect(mockFetch).toHaveBeenCalledWith('/api/v1/new-chat', expect.any(Object));
        });

        // Resolve delayed response from session 1
        resolveChat({
            json: () => Promise.resolve({
                success: true,
                response: 'Delayed Response from Session 1',
                source: 'test',
                timestamp: 'now',
            }),
            ok: true,
        });

        // Delayed response should NOT appear in current session
        await new Promise((r) => setTimeout(r, 50));
        expect(screen.queryByText('Delayed Response from Session 1')).toBeNull();
    });

    it('renders analysis_complete with uncalibrated score and without primary diagnosis or percentage certainty', async () => {
        mockFetch.mockImplementation((url) => {
            if (url === '/api/v1/analyze-image') {
                return Promise.resolve({
                    json: () => Promise.resolve({
                        status: 'analysis_complete',
                        success: true,
                        category: 'skin',
                        disease: 'Actinic Keratosis',
                        finding_type: 'condition_detected',
                        is_negative_finding: false,
                        score: 0.8543,
                        confidence: 0.8543,
                        calibrated_confidence: null,
                        predictions: [
                            { disease: 'Actinic Keratosis', score: 0.8543 },
                            { disease: 'Squamous Cell Carcinoma', score: 0.1021 },
                        ],
                        medical_details: 'Precancerous scaly lesion caused by sun damage.',
                    }),
                    ok: true,
                });
            }
            return Promise.resolve({ json: () => Promise.resolve({ success: true, sessions: [] }), ok: true });
        });

        render(<App />);

        const fileInput = document.querySelector('input[type="file"]');
        expect(fileInput).not.toBeNull();

        const file = new File(['fake-content'], 'lesion.png', { type: 'image/png' });
        fireEvent.change(fileInput, { target: { files: [file] } });

        await waitFor(() => {
            expect(screen.getByText(/Model Finding:/)).toBeInTheDocument();
            expect(screen.getAllByText('Actinic Keratosis').length).toBeGreaterThan(0);
            expect(screen.getByText(/Model Output Score:/)).toBeInTheDocument();
            expect(screen.getAllByText(/0\.8543/).length).toBeGreaterThan(0);
            // Verify absence of misleading claims
            expect(screen.queryByText(/Primary Diagnosis/)).toBeNull();
            expect(screen.queryByText(/85.4%/)).toBeNull();
        });
    });

    it('renders normal/negative reference finding notice without diagnosing disease', async () => {
        mockFetch.mockImplementation((url) => {
            if (url === '/api/v1/analyze-image') {
                return Promise.resolve({
                    json: () => Promise.resolve({
                        status: 'analysis_complete',
                        success: true,
                        category: 'general',
                        disease: 'Normal Reference Finding',
                        finding_type: 'normal_or_negative',
                        is_negative_finding: true,
                        score: 0.9600,
                        confidence: 0.9600,
                        calibrated_confidence: null,
                        predictions: [
                            { disease: 'Normal Reference Finding', score: 0.9600 },
                            { disease: 'Pneumonia', score: 0.0400 },
                        ],
                    }),
                    ok: true,
                });
            }
            return Promise.resolve({ json: () => Promise.resolve({ success: true, sessions: [] }), ok: true });
        });

        render(<App />);

        const fileInput = document.querySelector('input[type="file"]');
        const file = new File(['fake-content'], 'scan.png', { type: 'image/png' });
        fireEvent.change(fileInput, { target: { files: [file] } });

        await waitFor(() => {
            expect(screen.getAllByText('Normal Reference Finding').length).toBeGreaterThan(0);
            expect(screen.getByText(/Normal\/Negative Reference/)).toBeInTheDocument();
            // Verify pneumonia is NOT diagnosed
            expect(screen.queryByText(/Primary Diagnosis: Pneumonia/)).toBeNull();
        });
    });

    it('renders model_unavailable status cleanly', async () => {
        mockFetch.mockImplementation((url) => {
            if (url === '/api/v1/analyze-image') {
                return Promise.resolve({
                    json: () => Promise.resolve({
                        status: 'model_unavailable',
                        success: false,
                        category: 'skin',
                        message: 'Specialist AI model for skin is not loaded on this server.',
                    }),
                    status: 503,
                    ok: false,
                });
            }
            return Promise.resolve({ json: () => Promise.resolve({ success: true, sessions: [] }), ok: true });
        });

        render(<App />);

        const fileInput = document.querySelector('input[type="file"]');
        const file = new File(['fake-content'], 'skin.png', { type: 'image/png' });
        fireEvent.change(fileInput, { target: { files: [file] } });

        await waitFor(() => {
            expect(screen.getByText(/Specialist Model Unavailable/)).toBeInTheDocument();
            expect(screen.getByText(/The AI specialist model for/)).toBeInTheDocument();
        });
    });

    it('renders unsupported_image status cleanly', async () => {
        mockFetch.mockImplementation((url) => {
            if (url === '/api/v1/analyze-image') {
                return Promise.resolve({
                    json: () => Promise.resolve({
                        status: 'unsupported_image',
                        success: false,
                        description: 'a brown dog running in the park',
                    }),
                    status: 422,
                    ok: false,
                });
            }
            return Promise.resolve({ json: () => Promise.resolve({ success: true, sessions: [] }), ok: true });
        });

        render(<App />);

        const fileInput = document.querySelector('input[type="file"]');
        const file = new File(['fake-content'], 'dog.png', { type: 'image/png' });
        fireEvent.change(fileInput, { target: { files: [file] } });

        await waitFor(() => {
            expect(screen.getByText(/Unsupported Image/)).toBeInTheDocument();
            expect(screen.getByText(/a brown dog running in the park/)).toBeInTheDocument();
        });
    });

    it('renders inconclusive status cleanly', async () => {
        mockFetch.mockImplementation((url) => {
            if (url === '/api/v1/analyze-image') {
                return Promise.resolve({
                    json: () => Promise.resolve({
                        status: 'inconclusive',
                        success: false,
                        message: 'Image modality could not be reliably determined.',
                    }),
                    ok: true,
                });
            }
            return Promise.resolve({ json: () => Promise.resolve({ success: true, sessions: [] }), ok: true });
        });

        render(<App />);

        const fileInput = document.querySelector('input[type="file"]');
        const file = new File(['fake-content'], 'blur.png', { type: 'image/png' });
        fireEvent.change(fileInput, { target: { files: [file] } });

        await waitFor(() => {
            expect(screen.getByText(/Analysis Inconclusive/)).toBeInTheDocument();
            expect(screen.getByText(/Image modality could not be reliably determined/)).toBeInTheDocument();
        });
    });

    it('handles microphone permission denial gracefully', async () => {
        const originalAlert = window.alert;
        const mockAlert = vi.fn();
        window.alert = mockAlert;

        const originalMediaDevices = navigator.mediaDevices;
        Object.defineProperty(navigator, 'mediaDevices', {
            value: {
                getUserMedia: vi.fn().mockRejectedValue({ name: 'NotAllowedError', message: 'Permission denied' }),
            },
            configurable: true,
        });

        render(<App />);

        const micButton = screen.getByTitle('Voice input — click to speak');
        fireEvent.click(micButton);

        await waitFor(() => {
            expect(mockAlert).toHaveBeenCalledWith(expect.stringContaining('Microphone access denied'));
        });

        window.alert = originalAlert;
        Object.defineProperty(navigator, 'mediaDevices', {
            value: originalMediaDevices,
            configurable: true,
        });
    });

    it('handles unsupported browser media devices gracefully', async () => {
        const originalAlert = window.alert;
        const mockAlert = vi.fn();
        window.alert = mockAlert;

        const originalMediaDevices = navigator.mediaDevices;
        Object.defineProperty(navigator, 'mediaDevices', {
            value: undefined,
            configurable: true,
        });

        render(<App />);

        const micButton = screen.getByTitle('Voice input — click to speak');
        fireEvent.click(micButton);

        await waitFor(() => {
            expect(mockAlert).toHaveBeenCalledWith(expect.stringContaining('not supported by your browser'));
        });

        window.alert = originalAlert;
        Object.defineProperty(navigator, 'mediaDevices', {
            value: originalMediaDevices,
            configurable: true,
        });
    });

    it('toggles light and dark themes and updates document attributes', async () => {
        render(<App />);

        const themeToggle = screen.getByTitle(/Switch to (light|dark) mode/i);
        expect(themeToggle).toBeInTheDocument();

        // Initial theme is dark from beforeEach
        expect(document.documentElement.getAttribute('data-theme')).toBe('dark');

        fireEvent.click(themeToggle);
        expect(document.documentElement.getAttribute('data-theme')).toBe('light');
        expect(localStorage.getItem('theme')).toBe('light');

        fireEvent.click(themeToggle);
        expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
        expect(localStorage.getItem('theme')).toBe('dark');
    });

    it('filters session list based on search term', async () => {
        const mockSessions = [
            { session_id: '1', preview: 'Flu symptoms and fever', last_active: '2023' },
            { session_id: '2', preview: 'Cardiology palpitations', last_active: '2023' },
            { session_id: '3', preview: 'Headache migraine advice', last_active: '2023' },
            { session_id: '4', preview: 'Skin rash inspection', last_active: '2023' }
        ];

        mockFetch.mockImplementation((url) => {
            if (url === '/api/v1/sessions') {
                return Promise.resolve({
                    json: () => Promise.resolve({ success: true, sessions: mockSessions }),
                    ok: true
                });
            }
            return Promise.resolve({ json: () => Promise.resolve({ success: true }), ok: true });
        });

        render(<App />);

        await waitFor(() => {
            expect(screen.getByText('Flu symptoms and fever')).toBeInTheDocument();
            expect(screen.getByText('Cardiology palpitations')).toBeInTheDocument();
        });

        const searchInput = screen.getByPlaceholderText('Filter consultations...');
        fireEvent.change(searchInput, { target: { value: 'Cardio' } });

        expect(screen.getByText('Cardiology palpitations')).toBeInTheDocument();
        expect(screen.queryByText('Flu symptoms and fever')).not.toBeInTheDocument();
    });

    it('opens confirmation modal on delete session and cancels cleanly', async () => {
        const mockSessions = [
            { session_id: 'sess-delete-1', preview: 'Routine checkup consult', last_active: '2023' }
        ];

        mockFetch.mockImplementation((url) => {
            if (url === '/api/v1/sessions') {
                return Promise.resolve({
                    json: () => Promise.resolve({ success: true, sessions: mockSessions }),
                    ok: true
                });
            }
            return Promise.resolve({ json: () => Promise.resolve({ success: true }), ok: true });
        });

        render(<App />);

        await waitFor(() => {
            expect(screen.getByText('Routine checkup consult')).toBeInTheDocument();
        });

        const deleteBtn = screen.getByTitle('Delete consultation');
        fireEvent.click(deleteBtn);

        // Confirmation modal is visible
        expect(screen.getByText('Delete Consultation?')).toBeInTheDocument();
        expect(screen.getByText(/permanently delete this consultation history/i)).toBeInTheDocument();

        // Cancel modal
        const cancelBtn = screen.getByText('Cancel');
        fireEvent.click(cancelBtn);

        await waitFor(() => {
            expect(screen.queryByText('Delete Consultation?')).not.toBeInTheDocument();
            expect(screen.getByText('Routine checkup consult')).toBeInTheDocument();
        });
    });

    it('submits query when clicking quick question starter card', async () => {
        mockFetch.mockImplementation((url) => {
            if (url === '/api/v1/chat') {
                return Promise.resolve({
                    json: () => Promise.resolve({
                        success: true,
                        response: 'Tension headaches can often be managed with rest and hydration.',
                        source: 'clinical-kb',
                        timestamp: 'now'
                    }),
                    ok: true
                });
            }
            return Promise.resolve({ json: () => Promise.resolve({ success: true, sessions: [] }), ok: true });
        });

        render(<App />);

        const starterCard = screen.getByText('How can I safely manage a tension headache at home?');
        expect(starterCard).toBeInTheDocument();

        fireEvent.click(starterCard);

        await waitFor(() => {
            expect(mockFetch).toHaveBeenCalledWith(
                '/api/v1/chat',
                expect.objectContaining({
                    body: expect.stringContaining('How can I safely manage a tension headache at home?')
                })
            );
            expect(screen.getByText(/managed with rest and hydration/)).toBeInTheDocument();
        });
    });

    it('toggles password visibility on AuthPage', async () => {
        localStorage.clear();
        render(<App />);

        expect(screen.getByText('Welcome Back')).toBeInTheDocument();
        const passwordInput = screen.getByPlaceholderText('Enter your password');
        expect(passwordInput).toHaveAttribute('type', 'password');

        const eyeToggleBtn = screen.getByTitle('Show password');
        fireEvent.click(eyeToggleBtn);

        expect(passwordInput).toHaveAttribute('type', 'text');

        const hideToggleBtn = screen.getByTitle('Hide password');
        fireEvent.click(hideToggleBtn);

        expect(passwordInput).toHaveAttribute('type', 'password');
    });

    it('dispatches message when follow-up choice chip is clicked', async () => {
        let chatCallCount = 0;
        mockFetch.mockImplementation((url) => {
            if (url === '/api/v1/chat') {
                chatCallCount++;
                if (chatCallCount === 1) {
                    return Promise.resolve({
                        json: () => Promise.resolve({
                            success: true,
                            response: 'How long have you had this cough?',
                            follow_up: {
                                round: 1,
                                questions: [
                                    {
                                        text: 'Duration of cough',
                                        options: ['Less than 3 days', 'More than 2 weeks']
                                    }
                                ]
                            },
                            source: 'clinical-triage',
                            timestamp: 'now'
                        }),
                        ok: true
                    });
                }
                return Promise.resolve({
                    json: () => Promise.resolve({
                        success: true,
                        response: 'Noted. For a cough lasting over 2 weeks, clinical evaluation is advised.',
                        source: 'clinical-triage',
                        timestamp: 'now'
                    }),
                    ok: true
                });
            }
            return Promise.resolve({ json: () => Promise.resolve({ success: true, sessions: [] }), ok: true });
        });

        render(<App />);

        const input = screen.getByPlaceholderText('Describe your symptoms or ask a medical question…');
        const sendBtn = screen.getByRole('button', { name: /Send message/i });

        fireEvent.change(input, { target: { value: 'I have a dry cough' } });
        fireEvent.click(sendBtn);

        await waitFor(() => {
            expect(screen.getByText('Less than 3 days')).toBeInTheDocument();
            expect(screen.getByText('More than 2 weeks')).toBeInTheDocument();
        });

        const chipBtn = screen.getByText('More than 2 weeks');
        fireEvent.click(chipBtn);

        await waitFor(() => {
            expect(chatCallCount).toBe(2);
            expect(screen.getByText(/cough lasting over 2 weeks/)).toBeInTheDocument();
        });
    });
});
