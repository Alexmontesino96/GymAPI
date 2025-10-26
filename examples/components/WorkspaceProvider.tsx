/**
 * WorkspaceProvider - Context Provider para el workspace
 *
 * Este componente proporciona el contexto del workspace a toda la aplicación.
 * Debe envolver la aplicación en el nivel más alto posible.
 *
 * Uso:
 * ```typescript
 * function App() {
 *   return (
 *     <WorkspaceProvider>
 *       <Router>
 *         <Routes />
 *       </Router>
 *     </WorkspaceProvider>
 *   );
 * }
 * ```
 */

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { ContextService, WorkspaceContext } from '../services/contextService';

interface WorkspaceContextValue {
  context: WorkspaceContext | null;
  isLoading: boolean;
  error: string | null;
  reload: () => Promise<void>;
}

const WorkspaceContext = createContext<WorkspaceContextValue>({
  context: null,
  isLoading: true,
  error: null,
  reload: async () => {}
});

export const useWorkspaceContext = () => useContext(WorkspaceContext);

interface WorkspaceProviderProps {
  children: React.ReactNode;
  /**
   * Componente a mostrar mientras se carga el contexto
   */
  loadingComponent?: React.ReactNode;
  /**
   * Componente a mostrar en caso de error
   */
  errorComponent?: (error: string, reload: () => Promise<void>) => React.ReactNode;
  /**
   * Callback cuando el contexto se carga exitosamente
   */
  onContextLoaded?: (context: WorkspaceContext) => void;
  /**
   * Callback cuando ocurre un error
   */
  onError?: (error: string) => void;
}

export function WorkspaceProvider({
  children,
  loadingComponent,
  errorComponent,
  onContextLoaded,
  onError
}: WorkspaceProviderProps) {
  const [context, setContext] = useState<WorkspaceContext | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadContext = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      // Obtener credenciales
      const token = localStorage.getItem('auth_token');
      const gymId = parseInt(localStorage.getItem('gym_id') || '0');

      if (!token || !gymId) {
        throw new Error('No hay sesión activa. Por favor inicia sesión.');
      }

      // Cargar contexto
      const service = new ContextService();
      const data = await service.loadWorkspaceContext(token, gymId);

      setContext(data);

      // Callback de éxito
      if (onContextLoaded) {
        onContextLoaded(data);
      }

    } catch (err: any) {
      const errorMessage = err.message || 'Error al cargar el contexto';
      console.error('[WorkspaceProvider] Error:', err);

      setError(errorMessage);

      // Callback de error
      if (onError) {
        onError(errorMessage);
      }

    } finally {
      setIsLoading(false);
    }
  }, [onContextLoaded, onError]);

  // Cargar al montar
  useEffect(() => {
    loadContext();
  }, [loadContext]);

  // Mostrar componente de loading
  if (isLoading) {
    return (
      <>
        {loadingComponent || (
          <div style={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            height: '100vh'
          }}>
            <div>Cargando...</div>
          </div>
        )}
      </>
    );
  }

  // Mostrar componente de error
  if (error) {
    return (
      <>
        {errorComponent ? errorComponent(error, loadContext) : (
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            alignItems: 'center',
            height: '100vh',
            gap: '1rem'
          }}>
            <div style={{ color: 'red' }}>Error: {error}</div>
            <button onClick={loadContext}>Reintentar</button>
          </div>
        )}
      </>
    );
  }

  return (
    <WorkspaceContext.Provider
      value={{
        context,
        isLoading,
        error,
        reload: loadContext
      }}
    >
      {children}
    </WorkspaceContext.Provider>
  );
}

/**
 * Custom hook para usar el contexto (alias del hook principal)
 */
export { useWorkspaceContext as useWorkspace };
