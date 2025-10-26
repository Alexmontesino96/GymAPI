/**
 * useBranding - Hook para aplicar branding dinámico del workspace
 *
 * Este hook:
 * - Aplica colores personalizados como CSS variables
 * - Actualiza el título de la página
 * - Proporciona configuración de branding
 *
 * Uso:
 * ```typescript
 * function App() {
 *   const { branding, applyBranding } = useBranding();
 *
 *   // Los colores se aplican automáticamente al montar
 *   // También puedes acceder a branding.primary_color, etc.
 *
 *   return <div className="app">{...}</div>;
 * }
 * ```
 */

import { useEffect } from 'react';
import { useWorkspace } from './useWorkspace';
import { BrandingConfig } from '../services/contextService';

interface UseBrandingReturn {
  /**
   * Configuración de branding actual
   */
  branding: BrandingConfig | null;

  /**
   * Aplicar manualmente el branding
   */
  applyBranding: () => void;

  /**
   * Restablecer branding a valores por defecto
   */
  resetBranding: () => void;
}

const DEFAULT_COLORS = {
  primary: '#007bff',
  secondary: '#6c757d',
  accent: '#28a745'
};

export function useBranding(): UseBrandingReturn {
  const { context } = useWorkspace();

  const applyBranding = () => {
    if (!context?.branding) {
      console.warn('[useBranding] No branding config available');
      return;
    }

    const { primary_color, secondary_color, accent_color, app_title } = context.branding;

    // Aplicar CSS variables
    document.documentElement.style.setProperty(
      '--color-primary',
      primary_color || DEFAULT_COLORS.primary
    );
    document.documentElement.style.setProperty(
      '--color-secondary',
      secondary_color || DEFAULT_COLORS.secondary
    );
    document.documentElement.style.setProperty(
      '--color-accent',
      accent_color || DEFAULT_COLORS.accent
    );

    // Actualizar título de la página
    if (app_title) {
      document.title = app_title;
    }

    console.log('[useBranding] Branding applied:', {
      primary_color,
      secondary_color,
      accent_color,
      app_title
    });
  };

  const resetBranding = () => {
    // Restablecer a colores por defecto
    document.documentElement.style.setProperty('--color-primary', DEFAULT_COLORS.primary);
    document.documentElement.style.setProperty('--color-secondary', DEFAULT_COLORS.secondary);
    document.documentElement.style.setProperty('--color-accent', DEFAULT_COLORS.accent);

    console.log('[useBranding] Branding reset to defaults');
  };

  // Aplicar branding automáticamente cuando el contexto cambie
  useEffect(() => {
    if (context?.branding) {
      applyBranding();
    }

    // Cleanup: restablecer al desmontar
    return () => {
      // Opcional: descomentar si quieres resetear al desmontar
      // resetBranding();
    };
  }, [context]);

  return {
    branding: context?.branding || null,
    applyBranding,
    resetBranding
  };
}

/**
 * Hook para obtener solo los colores del branding
 */
export function useBrandingColors() {
  const { branding } = useBranding();

  if (!branding) {
    return {
      primary: DEFAULT_COLORS.primary,
      secondary: DEFAULT_COLORS.secondary,
      accent: DEFAULT_COLORS.accent
    };
  }

  return {
    primary: branding.primary_color,
    secondary: branding.secondary_color,
    accent: branding.accent_color
  };
}

/**
 * Hook para verificar el tema actual
 */
export function useTheme() {
  const { branding } = useBranding();

  const isTrainerTheme = branding?.theme === 'trainer';
  const isGymTheme = branding?.theme === 'gym';
  const isCompactMode = branding?.compact_mode === true;

  return {
    theme: branding?.theme || 'default',
    isTrainerTheme,
    isGymTheme,
    isCompactMode
  };
}
