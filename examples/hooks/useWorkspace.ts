/**
 * useWorkspace - Hook para gestionar el contexto del workspace
 *
 * Este hook proporciona:
 * - Estado del contexto del workspace
 * - Loading y error states
 * - Función para recargar el contexto
 *
 * Uso:
 * ```typescript
 * function MyComponent() {
 *   const { context, isLoading, error, reload } = useWorkspace();
 *
 *   if (isLoading) return <Spinner />;
 *   if (error) return <Error message={error} />;
 *
 *   return <div>{context.workspace.name}</div>;
 * }
 * ```
 */

import { useState, useEffect, useCallback } from 'react';
import { ContextService, WorkspaceContext } from '../services/contextService';

interface UseWorkspaceReturn {
  context: WorkspaceContext | null;
  isLoading: boolean;
  error: string | null;
  reload: () => Promise<void>;
}

export function useWorkspace(): UseWorkspaceReturn {
  const [context, setContext] = useState<WorkspaceContext | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadContext = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      // Obtener credenciales del localStorage
      const token = localStorage.getItem('auth_token');
      const gymId = parseInt(localStorage.getItem('gym_id') || '0');

      if (!token || !gymId) {
        throw new Error('No hay sesión activa');
      }

      // Cargar contexto
      const service = new ContextService();
      const data = await service.loadWorkspaceContext(token, gymId);

      setContext(data);

    } catch (err: any) {
      console.error('[useWorkspace] Error loading context:', err);
      setError(err.message || 'Error al cargar el contexto');
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Cargar al montar el componente
  useEffect(() => {
    loadContext();
  }, [loadContext]);

  return {
    context,
    isLoading,
    error,
    reload: loadContext
  };
}
