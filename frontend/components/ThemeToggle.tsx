'use client';

import { Moon, Sun } from 'lucide-react';
import { useTheme } from '@/lib/theme';

/** Alterna entre el tema oscuro (predeterminado) y el claro. */
export default function ThemeToggle({ showLabel = true, className = '' }: { showLabel?: boolean; className?: string }) {
  const { theme, toggleTheme } = useTheme();
  const isLight = theme === 'light';
  const label = isLight ? 'Tema oscuro' : 'Tema claro';
  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={`Cambiar a ${label.toLowerCase()}`}
      title={`Cambiar a ${label.toLowerCase()}`}
      className={`flex items-center gap-2.5 rounded-lg text-slate-400 hover:bg-slate-800/50 hover:text-slate-200 transition-all text-xs ${className}`}
    >
      <span className="shrink-0">{isLight ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}</span>
      {showLabel && <span className="truncate">{label}</span>}
    </button>
  );
}
