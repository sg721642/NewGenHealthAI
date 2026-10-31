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
});
