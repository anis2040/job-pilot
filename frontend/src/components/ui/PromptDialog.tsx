import { useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useFocusTrap } from '../../hooks/useFocusTrap';

interface PromptDialogProps {
  open: boolean;
  title: string;
  message?: string;
  defaultValue?: string;
  placeholder?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: (value: string) => void;
  onCancel: () => void;
}

export function PromptDialog({
  open, title, message, defaultValue = '', placeholder = '',
  confirmLabel = 'Save', cancelLabel = 'Cancel', onConfirm, onCancel,
}: PromptDialogProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [value, setValue] = useState(defaultValue);
  useFocusTrap(ref, open, onCancel);

  if (!open) return null;

  const submit = () => { const v = value.trim(); if (v) onConfirm(v); };

  return createPortal(
    <div
      className="confirm-backdrop open"
      role="dialog"
      aria-modal="true"
      aria-labelledby="prompt-title"
      onClick={e => { if (e.target === e.currentTarget) onCancel(); }}
    >
      <div className="confirm-box" ref={ref}>
        <div className="confirm-head">
          <h2 id="prompt-title">{title}</h2>
        </div>
        {message && <p className="confirm-msg">{message}</p>}
        <input
          className="prompt-input"
          type="text"
          value={value}
          placeholder={placeholder}
          autoFocus
          onChange={e => setValue(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); submit(); } }}
        />
        <div className="confirm-actions">
          <button className="btn btn-ghost" onClick={onCancel}>{cancelLabel}</button>
          <button className="btn btn-primary" onClick={submit}>{confirmLabel}</button>
        </div>
      </div>
    </div>,
    document.body
  );
}
