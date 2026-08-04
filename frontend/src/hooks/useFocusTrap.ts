import { useEffect, useRef } from 'react';

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function useFocusTrap(
  containerRef: React.RefObject<HTMLElement | null>,
  active: boolean,
  onEscape?: () => void
) {
  useEffect(() => {
    if (!active || !containerRef.current) return;
    const container = containerRef.current;
    const previouslyFocused = document.activeElement as HTMLElement | null;

    const focusables = () =>
      [...container.querySelectorAll<HTMLElement>(FOCUSABLE)].filter(el => el.offsetParent !== null);

    function keydown(e: KeyboardEvent) {
      if (e.key === 'Escape' && onEscape) { e.preventDefault(); onEscape(); return; }
      if (e.key !== 'Tab') return;
      const items = focusables();
      if (!items.length) return;
      const first = items[0], last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }

    container.addEventListener('keydown', keydown);
    focusables()[0]?.focus();

    return () => {
      container.removeEventListener('keydown', keydown);
      previouslyFocused?.focus();
    };
  }, [active, onEscape]);
}

export function useClickOutside(
  ref: React.RefObject<HTMLElement | null>,
  handler: () => void,
  active = true
) {
  const savedHandler = useRef(handler);
  savedHandler.current = handler;

  useEffect(() => {
    if (!active) return;
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        savedHandler.current();
      }
    }
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, [active, ref]);
}
