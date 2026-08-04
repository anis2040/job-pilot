import { useRef, type ReactNode } from 'react';
import { useFocusTrap } from '../../hooks/useFocusTrap';
import { Icon } from './Icon';

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  children?: ReactNode;
}

export function ConfirmDialog({
  open, title, message, confirmLabel = 'Confirm', cancelLabel = 'Cancel',
  danger = false, onConfirm, onCancel, children,
}: ConfirmDialogProps) {
  const ref = useRef<HTMLDivElement>(null);
  useFocusTrap(ref, open, onCancel);

  if (!open) return null;

  return (
    <div
      className="confirm-backdrop open"
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-title"
      onClick={e => { if (e.target === e.currentTarget) onCancel(); }}
    >
      <div className="confirm-box" ref={ref}>
        <div className="confirm-head">
          {danger && <span className="confirm-icon danger"><Icon name="alert" size={20} /></span>}
          <h2 id="confirm-title">{title}</h2>
        </div>
        {message && <p className="confirm-msg">{message}</p>}
        {children}
        <div className="confirm-actions">
          <button className="btn btn-ghost" onClick={onCancel}>{cancelLabel}</button>
          <button
            className={`btn ${danger ? 'btn-danger' : 'btn-primary'}`}
            onClick={onConfirm}
            autoFocus
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
