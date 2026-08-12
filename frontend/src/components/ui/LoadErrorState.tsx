interface LoadErrorStateProps {
  title: string;
  description?: string;
  onRetry: () => void;
  icon?: string;
  className?: string;
}

export function LoadErrorState({
  title,
  description = 'Something went wrong reaching the server.',
  onRetry,
  icon = '⚠️',
  className,
}: LoadErrorStateProps) {
  return (
    <div className={`empty-state${className ? ` ${className}` : ''}`} role="alert">
      <div className="empty-state-icon">{icon}</div>
      <div className="empty-state-title">{title}</div>
      <div className="empty-state-desc">{description}</div>
      <button className="btn btn-primary" style={{ marginTop: 'var(--space-2)' }} onClick={onRetry}>
        Retry
      </button>
    </div>
  );
}
