/**
 * ContextService - Servicio para cargar y gestionar el contexto del workspace
 *
 * Este servicio proporciona métodos para:
 * - Cargar contexto completo del workspace
 * - Obtener estadísticas del workspace
 * - Cache automático de contexto
 *
 * Uso:
 * ```typescript
 * const service = new ContextService();
 * const context = await service.loadWorkspaceContext(token, gymId);
 * console.log(context.workspace.type); // "personal_trainer" o "gym"
 * ```
 */

import axios, { AxiosInstance } from 'axios';
import { CacheService } from './cacheService';

export interface MenuItem {
  id: string;
  label: string;
  icon: string;
  path: string;
}

export interface QuickAction {
  id: string;
  label: string;
  icon: string;
  color: string;
  action: string;
}

export interface BrandingConfig {
  logo_url: string | null;
  primary_color: string;
  secondary_color: string;
  accent_color: string;
  app_title: string;
  app_subtitle: string;
  theme: string;
  show_logo: boolean;
  compact_mode: boolean;
}

export interface UserContext {
  id: number;
  email: string;
  name: string;
  photo_url: string | null;
  role: string;
  role_label: string;
  permissions: string[];
}

export interface WorkspaceContext {
  workspace: {
    id: number;
    name: string;
    type: 'gym' | 'personal_trainer';
    is_personal_trainer: boolean;
    display_name: string;
    entity_label: string;
    timezone: string;
    email: string;
    phone?: string;
    address?: string;
    max_clients?: number;
    specialties?: string[];
  };
  terminology: Record<string, string>;
  features: Record<string, boolean>;
  navigation: MenuItem[];
  quick_actions: QuickAction[];
  branding: BrandingConfig;
  user_context: UserContext;
  api_version: string;
  environment: string;
}

export interface WorkspaceStats {
  type: 'trainer' | 'gym';
  metrics: {
    // Métricas de entrenador
    active_clients?: number;
    max_clients?: number;
    capacity_percentage?: number;
    sessions_this_week?: number;
    avg_sessions_per_client?: number;
    client_retention_rate?: number;
    revenue_this_month?: number;

    // Métricas de gimnasio
    total_members?: number;
    active_trainers?: number;
    active_classes?: number;
    occupancy_rate?: number;
    member_growth_rate?: number;
  };
}

export class ContextService {
  private client: AxiosInstance;
  private cache: CacheService;

  constructor(
    baseURL: string = 'http://localhost:8000/api/v1',
    cacheEnabled: boolean = true
  ) {
    this.client = axios.create({
      baseURL,
      headers: {
        'Content-Type': 'application/json'
      },
      timeout: 10000
    });

    this.cache = new CacheService(cacheEnabled);
  }

  /**
   * Cargar contexto completo del workspace
   *
   * @param token - Token JWT de autenticación
   * @param gymId - ID del workspace/gym
   * @param useCache - Usar cache (default: true)
   * @returns Contexto completo del workspace
   */
  async loadWorkspaceContext(
    token: string,
    gymId: number,
    useCache: boolean = true
  ): Promise<WorkspaceContext> {
    const cacheKey = `context:${gymId}`;

    // Intentar desde cache
    if (useCache) {
      const cached = this.cache.get<WorkspaceContext>(cacheKey);
      if (cached) {
        console.log('[ContextService] Using cached context');
        return cached;
      }
    }

    try {
      console.log('[ContextService] Loading context from API');

      const response = await this.client.get<WorkspaceContext>(
        '/context/workspace',
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'X-Gym-ID': gymId.toString()
          }
        }
      );

      const context = response.data;

      // Guardar en cache (5 minutos)
      this.cache.set(cacheKey, context, 300000);

      return context;

    } catch (error: any) {
      if (error.response?.status === 401) {
        throw new Error('Sesión expirada. Por favor inicia sesión nuevamente.');
      }

      if (error.response?.status === 403) {
        throw new Error('No tienes permisos para acceder a este workspace.');
      }

      throw new Error(
        error.response?.data?.detail?.message ||
        'Error al cargar el contexto del workspace'
      );
    }
  }

  /**
   * Obtener estadísticas del workspace
   *
   * @param token - Token JWT de autenticación
   * @param gymId - ID del workspace/gym
   * @param useCache - Usar cache (default: true)
   * @returns Estadísticas del workspace
   */
  async getWorkspaceStats(
    token: string,
    gymId: number,
    useCache: boolean = true
  ): Promise<WorkspaceStats> {
    const cacheKey = `stats:${gymId}`;

    // Intentar desde cache
    if (useCache) {
      const cached = this.cache.get<WorkspaceStats>(cacheKey);
      if (cached) {
        console.log('[ContextService] Using cached stats');
        return cached;
      }
    }

    try {
      console.log('[ContextService] Loading stats from API');

      const response = await this.client.get<WorkspaceStats>(
        '/context/workspace/stats',
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'X-Gym-ID': gymId.toString()
          }
        }
      );

      const stats = response.data;

      // Guardar en cache (5 minutos)
      this.cache.set(cacheKey, stats, 300000);

      return stats;

    } catch (error: any) {
      throw new Error(
        error.response?.data?.detail?.message ||
        'Error al cargar las estadísticas'
      );
    }
  }

  /**
   * Invalidar cache del contexto
   *
   * @param gymId - ID del workspace (opcional, si no se provee se limpia todo)
   */
  invalidateCache(gymId?: number) {
    if (gymId) {
      this.cache.delete(`context:${gymId}`);
      this.cache.delete(`stats:${gymId}`);
    } else {
      this.cache.clear();
    }
  }

  /**
   * Forzar recarga del contexto (sin cache)
   *
   * @param token - Token JWT de autenticación
   * @param gymId - ID del workspace/gym
   * @returns Contexto actualizado
   */
  async reloadContext(token: string, gymId: number): Promise<WorkspaceContext> {
    this.invalidateCache(gymId);
    return await this.loadWorkspaceContext(token, gymId, false);
  }
}

// Exportar instancia singleton si se desea
export const contextService = new ContextService();
