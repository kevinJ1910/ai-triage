// Sin React: lo importa el layout (componente de servidor) y lib/theme.ts.

// Preferencia del usuario en este navegador (no es un dato clinico ni una credencial).
export const THEME_STORAGE_KEY = 'ai_triage_theme';

/**
 * Script que se ejecuta en <head> antes de pintar, para que el tema guardado se aplique sin parpadeo.
 * El tema oscuro es el predeterminado.
 */
export const THEME_INIT_SCRIPT = `try{var t=localStorage.getItem('${THEME_STORAGE_KEY}');if(t==='light'||t==='dark'){document.documentElement.dataset.theme=t}}catch(e){}`;
