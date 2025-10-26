/**
 * CacheService - Servicio de cache en memoria con TTL
 *
 * Proporciona cache simple en memoria para reducir llamadas a la API.
 * Útil para:
 * - Contexto del workspace (no cambia frecuentemente)
 * - Estadísticas (actualización cada 5 minutos)
 * - Respuestas de validación (evitar rate limiting)
 *
 * Uso:
 * ```typescript
 * const cache = new CacheService();
 * cache.set('key', data, 300000); // 5 minutos
 * const data = cache.get('key');
 * ```
 */

interface CacheItem<T> {
  data: T;
  timestamp: number;
  ttl: number;
}

export class CacheService {
  private cache: Map<string, CacheItem<any>> = new Map();
  private enabled: boolean;

  constructor(enabled: boolean = true) {
    this.enabled = enabled;

    // Limpieza periódica de items expirados (cada 5 minutos)
    if (enabled) {
      setInterval(() => this.cleanup(), 300000);
    }
  }

  /**
   * Guardar un item en cache
   *
   * @param key - Clave única del item
   * @param data - Datos a cachear
   * @param ttl - Tiempo de vida en milisegundos (default: 5 minutos)
   */
  set<T>(key: string, data: T, ttl: number = 300000): void {
    if (!this.enabled) return;

    this.cache.set(key, {
      data,
      timestamp: Date.now(),
      ttl
    });

    console.log(`[Cache] Set: ${key} (TTL: ${ttl}ms)`);
  }

  /**
   * Obtener un item del cache
   *
   * @param key - Clave del item
   * @returns Datos cacheados o null si no existe o expiró
   */
  get<T>(key: string): T | null {
    if (!this.enabled) return null;

    const item = this.cache.get(key);

    if (!item) {
      console.log(`[Cache] Miss: ${key}`);
      return null;
    }

    const now = Date.now();
    const age = now - item.timestamp;

    // Verificar si expiró
    if (age > item.ttl) {
      console.log(`[Cache] Expired: ${key} (age: ${age}ms, ttl: ${item.ttl}ms)`);
      this.cache.delete(key);
      return null;
    }

    console.log(`[Cache] Hit: ${key} (age: ${age}ms)`);
    return item.data as T;
  }

  /**
   * Verificar si un item existe y no ha expirado
   *
   * @param key - Clave del item
   * @returns true si existe y es válido
   */
  has(key: string): boolean {
    return this.get(key) !== null;
  }

  /**
   * Eliminar un item específico del cache
   *
   * @param key - Clave del item
   */
  delete(key: string): void {
    const deleted = this.cache.delete(key);
    if (deleted) {
      console.log(`[Cache] Deleted: ${key}`);
    }
  }

  /**
   * Limpiar todo el cache
   */
  clear(): void {
    const size = this.cache.size;
    this.cache.clear();
    console.log(`[Cache] Cleared: ${size} items`);
  }

  /**
   * Limpiar items expirados
   */
  private cleanup(): void {
    const now = Date.now();
    let cleaned = 0;

    for (const [key, item] of this.cache.entries()) {
      const age = now - item.timestamp;

      if (age > item.ttl) {
        this.cache.delete(key);
        cleaned++;
      }
    }

    if (cleaned > 0) {
      console.log(`[Cache] Cleanup: removed ${cleaned} expired items`);
    }
  }

  /**
   * Obtener estadísticas del cache
   *
   * @returns Información sobre el estado del cache
   */
  stats() {
    const now = Date.now();
    let valid = 0;
    let expired = 0;

    for (const [_, item] of this.cache.entries()) {
      const age = now - item.timestamp;
      if (age > item.ttl) {
        expired++;
      } else {
        valid++;
      }
    }

    return {
      total: this.cache.size,
      valid,
      expired,
      enabled: this.enabled
    };
  }

  /**
   * Habilitar/deshabilitar cache
   *
   * @param enabled - true para habilitar, false para deshabilitar
   */
  setEnabled(enabled: boolean): void {
    this.enabled = enabled;
    if (!enabled) {
      this.clear();
    }
  }
}
