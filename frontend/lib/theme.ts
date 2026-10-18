'use client';

import { useCallback, useSyncExternalStore } from 'react';
import { THEME_STORAGE_KEY } from './theme-script';

export { THEME_STORAGE_KEY };

export type Theme = 'dark' | 'light';

const THEME_EVENT = 'ai-triage-theme';

export function getTheme(): Theme {
  if (typeof document === 'undefined') return 'dark';
  return document.documentElement.dataset.theme === 'light' ? 'light' : 'dark';
}

export function setTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch {
    // Sin almacenamiento (modo privado): el tema dura lo que la pestaña.
  }
  window.dispatchEvent(new Event(THEME_EVENT));
}

function subscribe(callback: () => void) {
  window.addEventListener(THEME_EVENT, callback);
  return () => window.removeEventListener(THEME_EVENT, callback);
}

export function useTheme(): { theme: Theme; toggleTheme: () => void } {
  const theme = useSyncExternalStore(subscribe, getTheme, () => 'dark' as Theme);
  const toggleTheme = useCallback(() => setTheme(getTheme() === 'light' ? 'dark' : 'light'), []);
  return { theme, toggleTheme };
}
