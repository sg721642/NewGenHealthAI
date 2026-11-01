export default function Toast({ toast, onDismiss }) {
  if (!toast || !toast.show) return null;

  const iconMap = {
    success: 'fa-circle-check',
    error: 'fa-circle-exclamation',
    info: 'fa-circle-info',
  };

  const icon = iconMap[toast.type] || iconMap.info;

  return (
    <div
      className={`toast-notification toast-${toast.type || 'info'}`}
      role="status"
      aria-live="polite"
    >
      <div className="toast-icon">
        <i className={`fas ${icon}`} />
      </div>
      <div className="toast-content">
        <span className="toast-message">{toast.message}</span>
      </div>
      {onDismiss && (
        <button
          type="button"
          className="toast-close"
          onClick={onDismiss}
          aria-label="Dismiss notification"
        >
          <i className="fas fa-xmark" />
        </button>
      )}
    </div>
  );
}
