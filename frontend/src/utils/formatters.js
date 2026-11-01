/**
 * NewGenHealthAI — Text & Date Formatters
 */

export function formatTimeAgo(timestamp) {
  if (!timestamp) return '';
  const now = new Date();
  const past = new Date(timestamp);
  if (isNaN(past.getTime())) return String(timestamp);
  const diffMs = now - past;
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);
  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return past.toLocaleDateString();
}

export function buildDownloadText(chatHistory) {
  let content = 'NewGenHealthAI Consultation Export\n';
  content += '='.repeat(50) + '\n';
  content += 'Educational & Informational Healthcare AI Assistant\n';
  content += `Export Date: ${new Date().toLocaleString()}\n`;
  content += '='.repeat(50) + '\n\n';
  (chatHistory || []).forEach((msg) => {
    const sender = msg.type === 'user' ? 'Patient / User' : 'NewGenHealthAI Assistant';
    content += `[${msg.timestamp || 'No time'}] ${sender}:\n`;
    content += (msg.content || '') + '\n';
    if (msg.source) content += `Clinical Source: ${msg.source}\n`;
    content += '\n';
  });
  content += '---\n';
  content += 'DISCLAIMER: AI-generated information is for educational purposes only and does not constitute a certified medical diagnosis or treatment plan. Always consult a qualified physician for clinical care.\n';
  return content;
}
