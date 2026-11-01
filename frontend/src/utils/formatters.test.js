import { describe, it, expect } from 'vitest';
import { formatMessageTimestamp, buildDownloadText } from './formatters';

describe('formatMessageTimestamp', () => {
  it('formats raw ISO UTC strings to localized time', () => {
    const iso = '2026-11-01T22:59:24.148046Z';
    const formatted = formatMessageTimestamp(iso);
    expect(formatted).toMatch(/^\d{1,2}:\d{2}\s*(?:AM|PM)$/i);
    expect(formatted).not.toContain('2026-11');
    expect(formatted).not.toContain('Z');
  });

  it('preserves already localized time strings', () => {
    expect(formatMessageTimestamp('10:30 PM')).toBe('10:30 PM');
    expect(formatMessageTimestamp('04:31 AM')).toBe('04:31 AM');
    expect(formatMessageTimestamp('04:31 am')).toBe('04:31 am');
  });

  it('handles empty and null timestamps gracefully', () => {
    expect(formatMessageTimestamp('')).toBe('');
    expect(formatMessageTimestamp(null)).toBe('');
    expect(formatMessageTimestamp(undefined)).toBe('');
  });

  it('formats ISO without timezone designator as UTC', () => {
    const raw = '2026-11-01 22:59:24';
    const formatted = formatMessageTimestamp(raw);
    expect(formatted).toMatch(/^\d{1,2}:\d{2}\s*(?:AM|PM)$/i);
  });
});

describe('buildDownloadText', () => {
  it('uses formatMessageTimestamp for export entries', () => {
    const history = [
      {
        type: 'user',
        content: 'I have a fever',
        timestamp: '2026-11-01T22:59:24.148046Z',
      },
      {
        type: 'assistant',
        content: 'How high is your temperature?',
        timestamp: '10:30 PM',
        source: 'Clinical Triage',
      },
    ];
    const text = buildDownloadText(history);
    expect(text).toContain('Patient / User');
    expect(text).toContain('NewGenHealthAI Assistant');
    expect(text).not.toContain('2026-11-01T22:59');
  });
});
