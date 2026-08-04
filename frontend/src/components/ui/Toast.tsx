import { createContext, useContext, useState, useCallback, useRef, type ReactNode } from 'react';

interface ToastMessage {
  id: number;
  text: string;
  type: 'ok' | 'err';
}

interface ToastContextValue {
  showToast: (msg: string, type?: 'ok' | 'err') => void;
}

const ToastContext = createContext<ToastContextValue>({ showToast: () => {} });

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<ToastMessage | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const showToast = useCallback((text: string, type: 'ok' | 'err' = 'ok') => {
    if (timerRef.current) clearTimeout(timerRef.current);
    setToast({ id: Date.now(), text, type });
    timerRef.current = setTimeout(() => setToast(null), 2600);
  }, []);

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      {toast && (
        <div
          key={toast.id}
          className={`toast ${toast.type} show`}
          role="status"
          aria-live="polite"
        >
          {toast.text}
        </div>
      )}
    </ToastContext.Provider>
  );
}

export function useToast() {
  return useContext(ToastContext);
}
