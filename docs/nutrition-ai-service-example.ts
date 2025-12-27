/**
 * Ejemplo de Servicio y Hooks para la API de Nutrición con IA
 *
 * Este archivo contiene implementaciones listas para usar en React
 * con manejo de errores, retry logic, y caching.
 */

import axios, { AxiosInstance, AxiosError } from 'axios';
import { useState, useCallback, useEffect, useRef } from 'react';
import type {
  GenerateIngredientsRequest,
  GenerateIngredientsResponse,
  Meal,
  ErrorResponse,
  NutritionAPIConfig,
  UseAIGenerationReturn,
  AIUsageStats,
  NUTRITION_CONSTANTS
} from './nutrition-ai-types';

// ============================================
// API Service Class
// ============================================

class NutritionAIService {
  private client: AxiosInstance;
  private gymId: number;
  private retryAttempts: number;
  private abortControllers: Map<string, AbortController>;

  constructor(config: NutritionAPIConfig) {
    this.gymId = config.gymId;
    this.retryAttempts = config.retryAttempts || 3;
    this.abortControllers = new Map();

    this.client = axios.create({
      baseURL: config.baseURL,
      timeout: config.timeout || 30000,
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${config.token}`,
        'X-Gym-ID': config.gymId.toString()
      }
    });

    // Response interceptor para manejo de errores
    this.client.interceptors.response.use(
      response => response,
      this.handleError.bind(this)
    );

    // Request interceptor para logging
    this.client.interceptors.request.use(
      request => {
        console.log('[NutritionAI] Request:', request.method?.toUpperCase(), request.url);
        return request;
      },
      error => Promise.reject(error)
    );
  }

  /**
   * Genera ingredientes con IA para una comida
   */
  async generateIngredients(
    mealId: number,
    options: GenerateIngredientsRequest
  ): Promise<GenerateIngredientsResponse> {
    const key = `generate-${mealId}`;

    // Cancelar request anterior si existe
    this.cancelRequest(key);

    // Crear nuevo AbortController
    const controller = new AbortController();
    this.abortControllers.set(key, controller);

    try {
      const response = await this.client.post<GenerateIngredientsResponse>(
        `/api/v1/nutrition/meals/${mealId}/generate-ingredients`,
        options,
        { signal: controller.signal }
      );

      // Cache la respuesta localmente
      this.cacheResponse(mealId, response.data);

      return response.data;
    } finally {
      this.abortControllers.delete(key);
    }
  }

  /**
   * Obtiene una comida con sus ingredientes
   */
  async getMeal(mealId: number): Promise<Meal> {
    const cached = this.getCachedMeal(mealId);
    if (cached) {
      console.log('[NutritionAI] Returning cached meal:', mealId);
      return cached;
    }

    const response = await this.client.get<Meal>(`/api/v1/nutrition/meals/${mealId}`);
    return response.data;
  }

  /**
   * Elimina todos los ingredientes de una comida
   */
  async deleteIngredients(mealId: number): Promise<void> {
    await this.client.delete(`/api/v1/nutrition/meals/${mealId}/ingredients`);
    this.clearCache(mealId);
  }

  /**
   * Cancela una request en progreso
   */
  cancelRequest(key: string): void {
    const controller = this.abortControllers.get(key);
    if (controller) {
      controller.abort();
      this.abortControllers.delete(key);
    }
  }

  /**
   * Cancela todas las requests en progreso
   */
  cancelAllRequests(): void {
    this.abortControllers.forEach(controller => controller.abort());
    this.abortControllers.clear();
  }

  /**
   * Manejo centralizado de errores
   */
  private async handleError(error: AxiosError): Promise<never> {
    if (error.response) {
      const status = error.response.status;
      const data = error.response.data as ErrorResponse;

      console.error('[NutritionAI] Error Response:', status, data);

      // Manejo específico por código de estado
      switch (status) {
        case 429: // Rate limit
          // Implementar retry automático con backoff
          if (this.shouldRetry(error)) {
            await this.delay(this.getRetryDelay(error));
            return this.client.request(error.config!);
          }
          break;

        case 500: // Error del servidor
        case 502: // Bad Gateway
        case 503: // Service Unavailable
        case 504: // Gateway Timeout
          // Reintentar automáticamente para errores del servidor
          if (this.shouldRetry(error)) {
            await this.delay(1000);
            return this.client.request(error.config!);
          }
          break;
      }

      throw {
        status,
        detail: data.detail || 'Error desconocido',
        type: 'api_error'
      } as ErrorResponse;
    } else if (error.request) {
      // Request fue enviada pero no hay respuesta
      throw {
        status: 0,
        detail: 'No se pudo conectar con el servidor',
        type: 'network_error'
      } as ErrorResponse;
    } else {
      // Error configurando la request
      throw {
        status: 0,
        detail: error.message,
        type: 'request_error'
      } as ErrorResponse;
    }
  }

  /**
   * Determina si se debe reintentar la request
   */
  private shouldRetry(error: AxiosError): boolean {
    const config = error.config as any;
    const retryCount = config._retryCount || 0;
    return retryCount < this.retryAttempts;
  }

  /**
   * Calcula el delay para el retry con exponential backoff
   */
  private getRetryDelay(error: AxiosError): number {
    const config = error.config as any;
    const retryCount = config._retryCount || 0;
    config._retryCount = retryCount + 1;
    return Math.min(1000 * Math.pow(2, retryCount), 10000);
  }

  /**
   * Delay utility
   */
  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Cache de respuestas
   */
  private cacheResponse(mealId: number, response: GenerateIngredientsResponse): void {
    const cacheKey = `ai_meal_${mealId}`;
    const cacheData = {
      response,
      timestamp: Date.now()
    };

    try {
      localStorage.setItem(cacheKey, JSON.stringify(cacheData));
    } catch (e) {
      console.warn('[NutritionAI] Failed to cache response:', e);
    }
  }

  /**
   * Obtiene una comida cacheada
   */
  private getCachedMeal(mealId: number): Meal | null {
    const cacheKey = `ai_meal_${mealId}`;

    try {
      const cached = localStorage.getItem(cacheKey);
      if (!cached) return null;

      const data = JSON.parse(cached);
      const age = Date.now() - data.timestamp;

      // Cache válido por 5 minutos
      if (age > NUTRITION_CONSTANTS.CACHE_DURATION_MINUTES * 60 * 1000) {
        localStorage.removeItem(cacheKey);
        return null;
      }

      return data.response.data;
    } catch {
      return null;
    }
  }

  /**
   * Limpia el cache de una comida
   */
  private clearCache(mealId: number): void {
    const cacheKey = `ai_meal_${mealId}`;
    localStorage.removeItem(cacheKey);
  }
}

// ============================================
// React Hook: useAIGeneration
// ============================================

export function useAIGeneration(config: NutritionAPIConfig): UseAIGenerationReturn {
  const [isGenerating, setIsGenerating] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<ErrorResponse | null>(null);
  const [usageStats, setUsageStats] = useState<AIUsageStats>({
    dailyUsage: 0,
    dailyLimit: NUTRITION_CONSTANTS.DAILY_GENERATION_LIMIT,
    monthlyUsage: 0,
    monthlyLimit: NUTRITION_CONSTANTS.GYM_DAILY_LIMIT * 30,
    lastResetDate: new Date().toISOString()
  });

  const serviceRef = useRef<NutritionAIService | null>(null);
  const progressIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Inicializar servicio
  useEffect(() => {
    serviceRef.current = new NutritionAIService(config);

    // Cargar estadísticas de uso desde localStorage
    const savedStats = localStorage.getItem('ai_usage_stats');
    if (savedStats) {
      const stats = JSON.parse(savedStats);
      // Reset diario si es necesario
      const lastReset = new Date(stats.lastResetDate);
      const today = new Date();
      if (lastReset.getDate() !== today.getDate()) {
        stats.dailyUsage = 0;
        stats.lastResetDate = today.toISOString();
      }
      setUsageStats(stats);
    }

    return () => {
      serviceRef.current?.cancelAllRequests();
      if (progressIntervalRef.current) {
        clearInterval(progressIntervalRef.current);
      }
    };
  }, [config]);

  /**
   * Simula progreso para mejor UX
   */
  const simulateProgress = useCallback(() => {
    setProgress(0);
    let currentProgress = 0;

    progressIntervalRef.current = setInterval(() => {
      currentProgress += Math.random() * 15;
      if (currentProgress > 90) currentProgress = 90;
      setProgress(currentProgress);
    }, 1000);
  }, []);

  /**
   * Genera ingredientes con IA
   */
  const generate = useCallback(async (
    mealId: number,
    options: GenerateIngredientsRequest
  ): Promise<GenerateIngredientsResponse> => {
    if (!serviceRef.current) {
      throw new Error('Service not initialized');
    }

    // Verificar límites
    if (usageStats.dailyUsage >= usageStats.dailyLimit) {
      const error: ErrorResponse = {
        status: 429,
        detail: 'Has alcanzado el límite diario de generaciones con IA',
        type: 'rate_limit'
      };
      setError(error);
      throw error;
    }

    setIsGenerating(true);
    setError(null);
    simulateProgress();

    try {
      // Verificar si la comida ya tiene ingredientes
      const meal = await serviceRef.current.getMeal(mealId);

      if (meal.has_ingredients) {
        // Preguntar confirmación al usuario (esto debería manejarse en el UI)
        console.warn('Meal already has ingredients. Should delete first.');
      }

      // Generar con IA
      const response = await serviceRef.current.generateIngredients(mealId, {
        ...options,
        language: options.language || NUTRITION_CONSTANTS.DEFAULT_LANGUAGE,
        servings: options.servings || NUTRITION_CONSTANTS.DEFAULT_SERVINGS
      });

      // Actualizar estadísticas
      const newStats = {
        ...usageStats,
        dailyUsage: usageStats.dailyUsage + 1,
        monthlyUsage: usageStats.monthlyUsage + 1
      };
      setUsageStats(newStats);
      localStorage.setItem('ai_usage_stats', JSON.stringify(newStats));

      setProgress(100);
      return response;
    } catch (err) {
      const error = err as ErrorResponse;
      setError(error);
      throw error;
    } finally {
      setIsGenerating(false);
      if (progressIntervalRef.current) {
        clearInterval(progressIntervalRef.current);
        progressIntervalRef.current = null;
      }
      // Reset progress después de un delay
      setTimeout(() => setProgress(0), 500);
    }
  }, [usageStats]);

  /**
   * Reset del estado de error
   */
  const reset = useCallback(() => {
    setError(null);
    setProgress(0);
    setIsGenerating(false);
  }, []);

  /**
   * Determina si se puede generar
   */
  const canGenerate = usageStats.dailyUsage < usageStats.dailyLimit && !isGenerating;

  return {
    generate,
    isGenerating,
    progress,
    error,
    reset,
    canGenerate,
    usageStats
  };
}

// ============================================
// React Hook: useNutritionAI (Simplificado)
// ============================================

export function useNutritionAI(
  baseURL: string,
  token: string,
  gymId: number
) {
  const config: NutritionAPIConfig = {
    baseURL,
    token,
    gymId,
    timeout: NUTRITION_CONSTANTS.AI_TIMEOUT_SECONDS * 1000,
    retryAttempts: NUTRITION_CONSTANTS.MAX_RETRY_ATTEMPTS
  };

  const {
    generate,
    isGenerating,
    progress,
    error,
    reset,
    canGenerate,
    usageStats
  } = useAIGeneration(config);

  /**
   * Wrapper con mejor manejo de errores
   */
  const generateWithFeedback = async (
    mealId: number,
    options: GenerateIngredientsRequest
  ) => {
    try {
      const result = await generate(mealId, options);

      // Mostrar notificación de éxito (esto debe conectarse con tu sistema de notificaciones)
      console.log('✅ Ingredientes generados exitosamente');

      return result;
    } catch (error) {
      const err = error as ErrorResponse;

      // Manejo específico de errores
      switch (err.status) {
        case 400:
          if (err.detail.includes('ya tiene ingredientes')) {
            console.error('⚠️ Elimina los ingredientes actuales primero');
          }
          break;
        case 429:
          console.error('⏰ Límite de solicitudes excedido. Intenta más tarde.');
          break;
        case 500:
          console.error('❌ Error del servidor. Por favor intenta nuevamente.');
          break;
        default:
          console.error('❌ Error inesperado:', err.detail);
      }

      throw error;
    }
  };

  return {
    generateIngredients: generateWithFeedback,
    isGenerating,
    progress,
    error,
    reset,
    canGenerate,
    usageStats,
    remainingGenerations: usageStats.dailyLimit - usageStats.dailyUsage
  };
}

// ============================================
// Exportaciones
// ============================================

export default NutritionAIService;
export { NutritionAIService };