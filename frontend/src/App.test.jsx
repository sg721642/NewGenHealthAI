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

    it('renders general_recognition status cleanly as a universal understanding card without error banner', async () => {
        mockFetch.mockImplementation((url) => {
            if (url === '/api/v1/analyze-image') {
                return Promise.resolve({
                    json: () => Promise.resolve({
                        status: 'general_recognition',
                        success: true,
                        category: 'animal',
                        detected_subject: 'Golden Retriever Dog',
                        description: 'A golden retriever dog sitting on a lawn.',
                        is_person: false,
                        medical_applicable: false,
                        reason_not_applicable: 'This image depicts an animal. Veterinary images are outside the scope of human medical intake.',
                        safety_disclaimer: 'Veterinary images are outside the scope of human medical intake.',
                        vision_engine: 'groq_vision',
                    }),
                    status: 200,
                    ok: true,
                });
            }
            return Promise.resolve({ json: () => Promise.resolve({ success: true, sessions: [] }), ok: true });
        });

        render(<App />);

        const fileInput = document.querySelector('input[type="file"]');
        const file = new File(['fake-content'], 'golden_retriever.png', { type: 'image/png' });
        fireEvent.change(fileInput, { target: { files: [file] } });

        await waitFor(() => {
            expect(screen.getByText(/Universal Image Recognition/)).toBeInTheDocument();
            expect(screen.getByText(/Golden Retriever Dog/)).toBeInTheDocument();
            expect(screen.getByText(/A golden retriever dog sitting on a lawn/)).toBeInTheDocument();
            expect(screen.queryByText(/Error/i)).toBeNull();
            expect(screen.queryByText(/Unsupported Image/i)).toBeNull();
        });
    });

    it('renders recognition_unavailable status cleanly with notice about offline state and manual selection', async () => {
        mockFetch.mockImplementation((url) => {
            if (url === '/api/v1/analyze-image') {
                return Promise.resolve({
                    json: () => Promise.resolve({
                        status: 'recognition_unavailable',
                        success: false,
                        message: 'Visual recognition service is currently unavailable. Specialist medical models (Skin, X-ray, Retina) can still be selected manually.',
                        category: 'unknown',
                        vision_engine: 'heuristic_fallback',
                    }),
                    status: 200,
                    ok: true,
                });
            }
            return Promise.resolve({ json: () => Promise.resolve({ success: true, sessions: [] }), ok: true });
        });

        render(<App />);

        const fileInput = document.querySelector('input[type="file"]');
        const file = new File(['fake-content'], 'photo.png', { type: 'image/png' });
        fireEvent.change(fileInput, { target: { files: [file] } });

        await waitFor(() => {
            expect(screen.getByText(/Visual Recognition Unavailable/)).toBeInTheDocument();
            expect(screen.getByText(/Specialist medical models \(Skin, X-ray, Retina\) can still be selected manually/)).toBeInTheDocument();
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

    it('does not log sensitive patient data or medical phrases to console during chat', async () => {
        const sensitiveQuery = 'SYNTHETIC_DIAGNOSIS_CARDIAC_ARRHYTHMIA_12345';
        const sensitiveResponse = 'SYNTHETIC_PRESCRIPTION_METOPROLOL_67890';

        const logSpy = vi.spyOn(console, 'log');
        const warnSpy = vi.spyOn(console, 'warn');
        const errorSpy = vi.spyOn(console, 'error');

        mockFetch.mockImplementation((url) => {
            if (url === '/api/v1/chat') {
                return Promise.resolve({
                    json: () => Promise.resolve({
                        success: true,
                        response: sensitiveResponse,
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
        fireEvent.change(input, { target: { value: sensitiveQuery } });

        const sendBtn = screen.getByRole('button', { name: /Send message/i });
        fireEvent.click(sendBtn);

        await waitFor(() => {
            expect(screen.getByText(sensitiveResponse)).toBeInTheDocument();
        });

        const allSpies = [logSpy, warnSpy, errorSpy];
        for (const spy of allSpies) {
            for (const call of spy.mock.calls) {
                const callString = JSON.stringify(call);
                expect(callString).not.toContain(sensitiveQuery);
                expect(callString).not.toContain(sensitiveResponse);
            }
        }
    });

    it('performs immediate safe logout by wiping client state before server response resolves', async () => {
        let resolveLogout;
        const logoutPromise = new Promise((res) => {
            resolveLogout = res;
        });

        mockFetch.mockImplementation((url) => {
            if (url === '/api/v1/auth/logout') {
                return logoutPromise;
            }
            return Promise.resolve({ json: () => Promise.resolve({ success: true, sessions: [] }), ok: true });
        });

        render(<App />);

        expect(screen.getByText('Medical AI Assistant')).toBeInTheDocument();
        const logoutBtn = screen.getByRole('button', { name: /Log out/i });

        fireEvent.click(logoutBtn);

        // Immediate wipe verification:
        expect(localStorage.getItem('auth_token')).toBeNull();
        expect(localStorage.getItem('auth_user')).toBeNull();
        expect(screen.getByText('Welcome Back')).toBeInTheDocument();

        // Server eventually resolves
        resolveLogout({
            json: () => Promise.resolve({ success: true }),
            ok: true
        });
    });

    it('validates image size on client side and rejects files exceeding 5MB without sending network request', async () => {
        let imageFetchCalled = false;
        mockFetch.mockImplementation((url) => {
            if (url === '/api/v1/analyze-image') {
                imageFetchCalled = true;
                return Promise.resolve({ json: () => Promise.resolve({ success: true }), ok: true });
            }
            return Promise.resolve({ json: () => Promise.resolve({ success: true, sessions: [] }), ok: true });
        });

        render(<App />);

        const fileInput = document.querySelector('input[type="file"]');
        expect(fileInput).not.toBeNull();

        // Create an oversized file: 6MB
        const largeFile = new File(['x'.repeat(1024)], 'large_scan.png', { type: 'image/png' });
        Object.defineProperty(largeFile, 'size', { value: 6 * 1024 * 1024 });

        fireEvent.change(fileInput, { target: { files: [largeFile] } });

        await waitFor(() => {
            expect(screen.getByText(/Image size exceeds 5MB limit/i)).toBeInTheDocument();
        });

        expect(imageFetchCalled).toBe(false);
    });

    it('validates image format on client side and rejects unsupported formats without sending network request', async () => {
        let imageFetchCalled = false;
        mockFetch.mockImplementation((url) => {
            if (url === '/api/v1/analyze-image') {
                imageFetchCalled = true;
                return Promise.resolve({ json: () => Promise.resolve({ success: true }), ok: true });
            }
            return Promise.resolve({ json: () => Promise.resolve({ success: true, sessions: [] }), ok: true });
        });

        render(<App />);

        const fileInput = document.querySelector('input[type="file"]');
        expect(fileInput).not.toBeNull();

        const invalidFile = new File(['text content'], 'report.pdf', { type: 'application/pdf' });
        fireEvent.change(fileInput, { target: { files: [invalidFile] } });

        await waitFor(() => {
            expect(screen.getByText(/Unsupported image format/i)).toBeInTheDocument();
        });

        expect(imageFetchCalled).toBe(false);
    });

    it('ConfirmationModal traps keyboard focus between cancel and confirm', async () => {
        // Setup initial message so clearChat has something to clear
        mockFetch.mockImplementation((url) => {
            if (url === '/api/v1/sessions/active-session/history') {
                return Promise.resolve({
                    json: () => Promise.resolve({
                        success: true,
                        messages: [{ role: 'user', content: 'test message', timestamp: '12:00' }]
                    }),
                    ok: true
                });
            }
            return Promise.resolve({ json: () => Promise.resolve({ success: true, sessions: [] }), ok: true });
        });

        render(<App />);

        // Wait for active session or send a message to ensure messages.length > 0
        const input = screen.getByPlaceholderText('Describe your symptoms or ask a medical question…');
        fireEvent.change(input, { target: { value: 'test question' } });
        const sendBtn = screen.getByRole('button', { name: /Send message/i });
        fireEvent.click(sendBtn);

        const clearBtn = screen.getByRole('button', { name: /Clear current conversation/i });
        fireEvent.click(clearBtn);

        await waitFor(() => {
            expect(screen.getByText('Clear Conversation?')).toBeInTheDocument();
        });

        const cancelBtn = screen.getByRole('button', { name: 'Cancel' });
        const confirmBtn = screen.getByRole('button', { name: 'Clear Messages' });

        expect(confirmBtn).toBeInTheDocument();
        expect(document.activeElement).toBe(cancelBtn);

        // Tab to confirm button
        fireEvent.keyDown(window, { key: 'Tab' });
        // Shift+Tab wrap test
        fireEvent.keyDown(window, { key: 'Tab', shiftKey: true });

        // Close with escape
        fireEvent.keyDown(window, { key: 'Escape' });
        await waitFor(() => {
            expect(screen.queryByText('Clear Conversation?')).toBeNull();
        });
    });

    it('Sidebar session selection uses dedicated button and avoids nested interactive controls', async () => {
        const mockSessions = [{ session_id: 'sess-100', preview: 'Migraine notes', last_active: '2024' }];
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
            expect(screen.getByText('Migraine notes')).toBeInTheDocument();
        });

        const sessionBtn = document.querySelector('.session-select-btn');
        expect(sessionBtn).not.toBeNull();
        expect(sessionBtn.querySelector('button')).toBeNull();
        expect(sessionBtn.closest('.history-session-item').tagName.toLowerCase()).not.toBe('button');
    });

    it('renders general_recognition with top1 class and raw score without claiming medical analysis', async () => {
        mockFetch.mockImplementation((url) => {
            if (url === '/api/v1/analyze-image') {
                return Promise.resolve({
                    json: () => Promise.resolve({
                        status: 'general_recognition',
                        success: true,
                        type: 'general_image',
                        category: 'animal',
                        detected_category: 'animal',
                        detected_subject: 'Animal (Curly-Coated Retriever)',
                        description: 'Visual recognition identified a non-medical animal (curly-coated retriever).',
                        top1_class: 'curly-coated retriever',
                        top1_name: 'curly-coated retriever',
                        top1_prob: 0.8212,
                        raw_score: 0.8212,
                        score: 0.8212,
                        is_person: false,
                        medical_applicable: false,
                        reason_not_applicable: 'This image depicts an animal. Veterinary images are outside the scope of human medical intake.',
                        safety_disclaimer: 'Veterinary images are outside the scope of human medical intake.',
                        vision_engine: 'local_neural_vision',
                        routing_decision: 'NO AUTOMATIC MEDICAL ROUTE',
                    }),
                    ok: true,
                });
            }
            return Promise.resolve({ json: () => Promise.resolve({ success: true, sessions: [] }), ok: true });
        });

        render(<App />);
        const fileInput = document.querySelector('input[type="file"]');
        const file = new File(['dog-img'], 'dog.jpg', { type: 'image/jpeg' });
        fireEvent.change(fileInput, { target: { files: [file] } });

        await waitFor(() => {
            expect(screen.getByText(/Universal Image Recognition/)).toBeInTheDocument();
            expect(screen.getByText(/Curly-Coated Retriever/)).toBeInTheDocument();
            expect(screen.getByText(/0\.8212/)).toBeInTheDocument();
            expect(screen.getByText(/Medical Analysis:/)).toBeInTheDocument();
            expect(screen.queryByText(/Model Finding:/)).toBeNull();
        });
    });

    it('renders modality_selection_required guidance when automatic intake abstains from clinical routing', async () => {
        mockFetch.mockImplementation((url) => {
            if (url === '/api/v1/analyze-image') {
                return Promise.resolve({
                    json: () => Promise.resolve({
                        status: 'modality_selection_required',
                        success: false,
                        routing_decision: 'NO AUTOMATIC MEDICAL ROUTE',
                        message: 'Automatic clinical routing is disabled to ensure patient safety. If this is a medical image, please explicitly select the modality (Skin, X-ray, Retina) to proceed.',
                        category: 'ambiguous',
                        detected_subject: 'Unrecognized Visual Subject',
                        medical_applicable: false,
                    }),
                    ok: true,
                });
            }
            return Promise.resolve({ json: () => Promise.resolve({ success: true, sessions: [] }), ok: true });
        });

        render(<App />);
        const fileInput = document.querySelector('input[type="file"]');
        const file = new File(['clinical-img'], 'skin.jpg', { type: 'image/jpeg' });
        fireEvent.change(fileInput, { target: { files: [file] } });

        await waitFor(() => {
            expect(screen.getByText(/Medical Modality Selection Required/)).toBeInTheDocument();
            expect(screen.getByText(/explicitly select the modality/i)).toBeInTheDocument();
            expect(screen.getByText(/Autonomous routing using visual heuristics is disabled/i)).toBeInTheDocument();
        });
    });

    it('renders Person detection: Unsupported / Unknown when is_person is null', async () => {
        mockFetch.mockImplementation((url) => {
            if (url === '/api/v1/analyze-image') {
                return Promise.resolve({
                    json: () => Promise.resolve({
                        status: 'general_recognition',
                        success: true,
                        category: 'object',
                        detected_subject: 'Everyday Object (Suit)',
                        description: 'Visual recognition identified a non-medical object (suit).',
                        top1_class: 'suit',
                        top1_prob: 0.4459,
                        raw_score: 0.4459,
                        is_person: null,
                        person_detection_status: 'unsupported',
                        person_detection_note: 'Person presence could not be reliably determined. Closed-set ImageNet-1K does not support general person detection.',
                        medical_applicable: false,
                        routing_decision: 'NO AUTOMATIC MEDICAL ROUTE',
                    }),
                    ok: true,
                });
            }
            return Promise.resolve({ json: () => Promise.resolve({ success: true, sessions: [] }), ok: true });
        });

        render(<App />);
        const fileInput = document.querySelector('input[type="file"]');
        const file = new File(['portrait-img'], 'portrait.jpg', { type: 'image/jpeg' });
        fireEvent.change(fileInput, { target: { files: [file] } });

        await waitFor(() => {
            expect(screen.getByText(/Person detection: Unsupported \/ Unknown/i)).toBeInTheDocument();
            expect(screen.queryByText(/No person detected/i)).toBeNull();
        });
    });

    it('renders non-mandating biopsy disclaimer in medical analysis card', async () => {
        mockFetch.mockImplementation((url) => {
            if (url === '/api/v1/analyze-image') {
                return Promise.resolve({
                    json: () => Promise.resolve({
                        status: 'analysis_complete',
                        success: true,
                        category: 'skin',
                        disease: 'Melanoma',
                        finding_type: 'condition_detected',
                        score: 0.7140,
                        confidence: 0.7140,
                        clinical_warning: 'CRITICAL MEDICAL DISCLAIMER: Unvalidated prototype.',
                        predictions: [{ disease: 'Melanoma', score: 0.7140 }],
                    }),
                    ok: true,
                });
            }
            return Promise.resolve({ json: () => Promise.resolve({ success: true, sessions: [] }), ok: true });
        });

        render(<App />);
        const fileInput = document.querySelector('input[type="file"]');
        const file = new File(['skin-img'], 'skin.jpg', { type: 'image/jpeg' });
        fireEvent.change(fileInput, { target: { files: [file] } });

        await waitFor(() => {
            expect(screen.getByText(/CRITICAL MEDICAL DISCLAIMER — NOT A CLINICAL DIAGNOSIS/i)).toBeInTheDocument();
            expect(screen.getByText(/Any further investigation or biopsy should be determined by the treating clinician/i)).toBeInTheDocument();
            expect(screen.queryByText(/Formal clinical examination and dermatoscopic biopsy by a licensed healthcare provider are required/i)).toBeNull();
        });
    });
});
