/**
 * useTerminology - Hook para textos adaptativos según tipo de workspace
 *
 * Este hook proporciona una función `t` (terminology) que retorna
 * el texto apropiado según si es un gym o entrenador personal.
 *
 * Ejemplos:
 * - "members" → "clientes" (trainer) o "miembros" (gym)
 * - "class" → "sesión" (trainer) o "clase" (gym)
 * - "gym" → "espacio de trabajo" (trainer) o "gimnasio" (gym)
 *
 * Uso:
 * ```typescript
 * function MyComponent() {
 *   const { t } = useTerminology();
 *
 *   return (
 *     <div>
 *       <h1>Lista de {t('members')}</h1>
 *       <button>Agregar {t('member')}</button>
 *     </div>
 *   );
 * }
 * ```
 */

import { useWorkspace } from './useWorkspace';

interface UseTerminologyReturn {
  /**
   * Obtener término adaptado al tipo de workspace
   *
   * @param key - Clave del término (ej: 'members', 'class', 'gym')
   * @param fallback - Valor por defecto si no se encuentra el término
   * @returns Término traducido o fallback
   */
  t: (key: string, fallback?: string) => string;

  /**
   * Obtener todos los términos
   */
  terminology: Record<string, string> | null;
}

export function useTerminology(): UseTerminologyReturn {
  const { context } = useWorkspace();

  const t = (key: string, fallback?: string): string => {
    if (!context?.terminology) {
      return fallback || key;
    }

    return context.terminology[key] || fallback || key;
  };

  return {
    t,
    terminology: context?.terminology || null
  };
}

/**
 * Variante del hook que retorna undefined si el contexto no está cargado
 * Útil para mostrar loaders mientras se carga
 */
export function useTerminologyStrict(): UseTerminologyReturn | undefined {
  const { context, isLoading } = useWorkspace();

  if (isLoading || !context) {
    return undefined;
  }

  const t = (key: string, fallback?: string): string => {
    return context.terminology[key] || fallback || key;
  };

  return {
    t,
    terminology: context.terminology
  };
}
