/**
 * NewGenHealthAI — Text & Date Formatters
 */

export function formatTimeAgo(timestamp) {
  if (!timestamp) return '';
  const now = new Date();
  let pastStr = String(timestamp).trim();
  // If the ISO string lacks timezone offset and lacks Z, append Z so it is treated as UTC
  if (/^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?$/.test(pastStr)) {
    pastStr = pastStr.replace(' ', 'T') + 'Z';
  }
  const past = new Date(pastStr);
  if (isNaN(past.getTime())) return String(timestamp);
  const diffMs = now - past;
  if (diffMs < 0) return 'Just now';
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);
  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return past.toLocaleDateString();
}

/**
 * Format message timestamp into a clean localized time string (e.g. "04:31 AM" or "10:15 PM").
 * Safely parses ISO UTC timestamps (e.g. "2026-11-01T22:59:24.148046Z"), date strings,
 * or returns existing localized time strings untouched.
 */
export function formatMessageTimestamp(timestamp) {
  if (!timestamp) return '';
  const str = String(timestamp).trim();
  // If already formatted like '10:30 PM' or '04:31 AM', return as-is
  if (/^\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM|am|pm)$/i.test(str)) {
    return str;
  }
  // Normalize ISO timestamp without timezone designator to UTC
  let isoStr = str;
  if (/^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?$/.test(isoStr)) {
    isoStr = isoStr.replace(' ', 'T') + 'Z';
  }
  const date = new Date(isoStr);
  if (!isNaN(date.getTime())) {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }
  return str;
}

export function buildDownloadText(chatHistory) {
  let content = 'NewGenHealthAI Consultation Export\n';
  content += '='.repeat(50) + '\n';
  content += 'Educational & Informational Healthcare AI Assistant\n';
  content += `Export Date: ${new Date().toLocaleString()}\n`;
  content += '='.repeat(50) + '\n\n';
  (chatHistory || []).forEach((msg) => {
    const sender = msg.type === 'user' ? 'Patient / User' : 'NewGenHealthAI Assistant';
    content += `[${formatMessageTimestamp(msg.timestamp) || 'No time'}] ${sender}:\n`;
    content += (msg.content || '') + '\n';
    if (msg.source) content += `Clinical Source: ${msg.source}\n`;
    content += '\n';
  });
  content += '---\n';
  content += 'DISCLAIMER: AI-generated information is for educational purposes only and does not constitute a certified medical diagnosis or treatment plan. Always consult a qualified physician for clinical care.\n';
  return content;
}
