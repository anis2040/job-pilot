import { createContext } from 'react';

export interface ToastContextValue {
  showToast: (msg: string, type?: 'ok' | 'err') => void;
}

export const ToastContext = createContext<ToastContextValue>({ showToast: () => {} });
