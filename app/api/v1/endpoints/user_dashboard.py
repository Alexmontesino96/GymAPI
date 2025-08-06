"""
User Dashboard API Endpoints

Este módulo proporciona endpoints optimizados para el dashboard de usuario,
incluyendo resúmenes rápidos, estadísticas comprehensivas y análisis de tendencias.

Todos los endpoints están optimizados para performance con caching inteligente
y diseñados para soportar alta concurrencia sin saturar la base de datos.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Security, status, Request
from sqlalchemy.orm import Session
from redis.asyncio import Redis

from app.db.session import get_db
from app.db.redis_client import get_redis_client
from app.core.auth0_fastapi import Auth0User, auth
from app.core.tenant import verify_gym_access, GymSchema
from app.middleware.rate_limit import limiter
from app.services.user_stats import user_stats_service
from app.services.user import user_service
from app.schemas.user_stats import (
    DashboardSummary, ComprehensiveUserStats, WeeklySummary, MonthlyTrends,
    PeriodType
)
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/dashboard/summary", response_model=DashboardSummary)
@limiter.limit("30/minute")  # Rate limit más alto para endpoint crítico
async def get_dashboard_summary(
    request: Request,
    db: Session = Depends(get_db),
    current_gym: GymSchema = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:read"]),
    redis_client: Redis = Depends(get_redis_client)
) -> DashboardSummary:
    """
    Obtiene resumen ultra rápido para dashboard principal.
    
    **Optimizado para ser < 50ms** con cache agresivo y datos esenciales.
    Este endpoint debe ser la primera carga del dashboard.
    
    **Características:**
    - ⚡ Ultra rápido (< 50ms target)
    - 🚀 Cache agresivo (15 minutos)
    - 📊 Solo datos esenciales
    - 🔄 Actualización automática en background
    
    **Permissions:**
    - Requires 'resource:read' scope (todos los usuarios autenticados)
    
    **Returns:**
    - Resumen con métricas clave: racha, entrenamientos semanales, próxima clase
    - Estado de membresía y progreso de objetivos
    - Logro más reciente y estadísticas rápidas
    """
    try:
        # Obtener usuario interno
        user = await user_service.get_user_by_auth0_id_cached(
            db, auth0_id=current_user.id, redis_client=redis_client
        )
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado en la base de datos"
            )
        
        # Obtener resumen optimizado
        summary = await user_stats_service.get_dashboard_summary(
            db=db,
            user_id=user.id,
            gym_id=current_gym.id,
            redis_client=redis_client
        )
        
        logger.info(f"Dashboard summary served for user {user.id}, gym {current_gym.id}")
        return summary
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting dashboard summary: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor al obtener resumen del dashboard"
        )


@router.get("/stats/comprehensive", response_model=ComprehensiveUserStats)
@limiter.limit("10/minute")  # Rate limit moderado para endpoint pesado
async def get_comprehensive_stats(
    request: Request,
    period: PeriodType = Query(PeriodType.month, description="Período de análisis"),
    include_goals: bool = Query(True, description="Incluir progreso de objetivos"),
    db: Session = Depends(get_db),
    current_gym: GymSchema = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:read"]),
    redis_client: Redis = Depends(get_redis_client)
) -> ComprehensiveUserStats:
    """
    Obtiene estadísticas comprehensivas del usuario.
    
    **Endpoint principal para análisis detallado** con todas las métricas
    disponibles agregadas de múltiples fuentes.
    
    **Características:**
    - 📊 Estadísticas completas de fitness, eventos, social y salud
    - 📈 Análisis de tendencias y progreso de objetivos
    - 🎯 Recomendaciones personalizadas
    - ⚡ Cache inteligente con TTL diferenciado por período
    - 🔄 Cálculo en background para datos frecuentes
    
    **Períodos soportados:**
    - `week`: Última semana (cache 30 min)
    - `month`: Último mes (cache 1 hora)
    - `quarter`: Último trimestre (cache 2 horas)
    - `year`: Último año (cache 4 horas)
    
    **Permissions:**
    - Requires 'resource:read' scope
    
    **Performance:**
    - Target: < 200ms con cache
    - Fallback: < 2s sin cache
    """
    try:
        # Obtener usuario interno
        user = await user_service.get_user_by_auth0_id_cached(
            db, auth0_id=current_user.id, redis_client=redis_client
        )
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado en la base de datos"
            )
        
        # Validar período
        if period not in [PeriodType.week, PeriodType.month, PeriodType.quarter, PeriodType.year]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Período inválido. Use: week, month, quarter, year"
            )
        
        # Obtener estadísticas comprehensivas
        stats = await user_stats_service.get_comprehensive_stats(
            db=db,
            user_id=user.id,
            gym_id=current_gym.id,
            period=period,
            include_goals=include_goals,
            redis_client=redis_client
        )
        
        logger.info(f"Comprehensive stats served for user {user.id}, period {period.value}")
        return stats
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting comprehensive stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor al obtener estadísticas comprehensivas"
        )


@router.get("/stats/fitness", response_model=dict)
@limiter.limit("20/minute")
async def get_fitness_stats(
    request: Request,
    period: PeriodType = Query(PeriodType.month, description="Período de análisis"),
    db: Session = Depends(get_db),
    current_gym: GymSchema = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:read"]),
    redis_client: Redis = Depends(get_redis_client)
) -> dict:
    """
    Obtiene solo métricas de fitness (endpoint modular).
    
    **Endpoint específico para métricas de fitness** optimizado para
    cargas parciales del dashboard.
    
    **Incluye:**
    - Clases asistidas vs programadas
    - Tasa de asistencia y horas totales
    - Rachas actuales y históricas
    - Tipos de clase favoritos
    - Horarios pico de entrenamiento
    - Estimación de calorías quemadas
    
    **Performance:** Target < 100ms
    """
    try:
        user = await user_service.get_user_by_auth0_id_cached(
            db, auth0_id=current_user.id, redis_client=redis_client
        )
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )
        
        # Obtener stats completas y extraer solo fitness
        stats = await user_stats_service.get_comprehensive_stats(
            db=db,
            user_id=user.id,
            gym_id=current_gym.id,
            period=period,
            include_goals=False,  # No necesarios para fitness
            redis_client=redis_client
        )
        
        return {
            "user_id": stats.user_id,
            "period": stats.period,
            "fitness_metrics": stats.fitness_metrics.dict(),
            "trends": {
                "attendance_trend": stats.trends.attendance_trend,
                "workout_intensity_trend": stats.trends.workout_intensity_trend
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting fitness stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error obteniendo estadísticas de fitness"
        )


@router.get("/stats/social", response_model=dict)
@limiter.limit("20/minute")
async def get_social_stats(
    request: Request,
    period: PeriodType = Query(PeriodType.month, description="Período de análisis"),
    db: Session = Depends(get_db),
    current_gym: GymSchema = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:read"]),
    redis_client: Redis = Depends(get_redis_client)
) -> dict:
    """
    Obtiene solo métricas sociales y de engagement.
    
    **Endpoint específico para métricas sociales** con datos de chat,
    interacciones y engagement comunitario.
    
    **Incluye:**
    - Mensajes de chat enviados
    - Salas de chat activas
    - Puntuación social (0-10)
    - Interacciones con entrenadores
    - Tendencias de engagement social
    
    **Performance:** Target < 100ms
    """
    try:
        user = await user_service.get_user_by_auth0_id_cached(
            db, auth0_id=current_user.id, redis_client=redis_client
        )
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )
        
        # Obtener stats completas y extraer solo social
        stats = await user_stats_service.get_comprehensive_stats(
            db=db,
            user_id=user.id,
            gym_id=current_gym.id,
            period=period,
            include_goals=False,
            redis_client=redis_client
        )
        
        return {
            "user_id": stats.user_id,
            "period": stats.period,
            "social_metrics": stats.social_metrics.dict(),
            "trends": {
                "social_engagement_trend": stats.trends.social_engagement_trend
            },
            "events_social": {
                "events_attended": stats.events_metrics.events_attended,
                "favorite_event_types": stats.events_metrics.favorite_event_types
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting social stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error obteniendo estadísticas sociales"
        )


@router.get("/stats/health", response_model=dict)
@limiter.limit("15/minute")
async def get_health_stats(
    request: Request,
    include_goals: bool = Query(True, description="Incluir progreso de objetivos"),
    db: Session = Depends(get_db),
    current_gym: GymSchema = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:read"]),
    redis_client: Redis = Depends(get_redis_client)
) -> dict:
    """
    Obtiene métricas de salud y objetivos personales.
    
    **Endpoint específico para métricas de salud** incluyendo datos
    biométricos y progreso de objetivos personales.
    
    **Incluye:**
    - Peso, altura y IMC actuales
    - Cambios de peso en el período
    - Progreso de objetivos personales
    - Categorización de salud
    - Recomendaciones de salud
    
    **Privacy Note:** Solo el propio usuario puede acceder a sus métricas de salud.
    
    **Performance:** Target < 150ms
    """
    try:
        user = await user_service.get_user_by_auth0_id_cached(
            db, auth0_id=current_user.id, redis_client=redis_client
        )
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )
        
        # Para métricas de salud, usar período mensual por defecto
        stats = await user_stats_service.get_comprehensive_stats(
            db=db,
            user_id=user.id,
            gym_id=current_gym.id,
            period=PeriodType.month,
            include_goals=include_goals,
            redis_client=redis_client
        )
        
        return {
            "user_id": stats.user_id,
            "health_metrics": stats.health_metrics.dict(),
            "membership_utilization": stats.membership_utilization.dict(),
            "health_recommendations": [
                rec for rec in stats.recommendations 
                if any(keyword in rec.lower() for keyword in ['health', 'weight', 'goal', 'nutrition'])
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting health stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error obteniendo estadísticas de salud"
        )


@router.post("/stats/refresh")
@limiter.limit("3/minute")  # Límite muy estricto para refresh manual
async def refresh_user_stats(
    request: Request,
    db: Session = Depends(get_db),
    current_gym: GymSchema = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:write"]),
    redis_client: Redis = Depends(get_redis_client)
) -> dict:
    """
    Fuerza actualización de estadísticas del usuario.
    
    **Endpoint para refresh manual** que invalida caches y recalcula
    todas las estadísticas. Usar con moderación.
    
    **Uso casos:**
    - Después de completar un entrenamiento importante
    - Tras actualizar objetivos personales
    - Para debugging o testing
    
    **Rate Limited:** 3 requests por minuto por usuario
    
    **Permissions:**
    - Requires 'resource:write' scope
    """
    try:
        user = await user_service.get_user_by_auth0_id_cached(
            db, auth0_id=current_user.id, redis_client=redis_client
        )
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )
        
        # Invalidar caches relacionadas
        cache_patterns = [
            f"dashboard_summary:{user.id}:{current_gym.id}",
            f"comprehensive_stats:{user.id}:{current_gym.id}:*"
        ]
        
        if redis_client:
            for pattern in cache_patterns:
                try:
                    # Eliminar caches que coincidan con el patrón
                    keys = await redis_client.keys(pattern)
                    if keys:
                        await redis_client.delete(*keys)
                        logger.info(f"Invalidated {len(keys)} cache keys for pattern: {pattern}")
                except Exception as e:
                    logger.warning(f"Error invalidating cache pattern {pattern}: {e}")
        
        # Recalcular estadísticas
        await user_stats_service.get_comprehensive_stats(
            db=db,
            user_id=user.id,
            gym_id=current_gym.id,
            period=PeriodType.month,
            include_goals=True,
            redis_client=redis_client
        )
        
        logger.info(f"Stats refreshed for user {user.id}, gym {current_gym.id}")
        
        return {
            "message": "Estadísticas actualizadas correctamente",
            "user_id": user.id,
            "refreshed_at": str(datetime.utcnow()),
            "cache_invalidated": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error refreshing stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error actualizando estadísticas"
        )


@router.get("/dashboard/health")
async def get_dashboard_health(
    request: Request,
    redis_client: Redis = Depends(get_redis_client)
) -> dict:
    """
    Health check para el sistema de dashboard.
    
    **Endpoint público** para verificar el estado del sistema de dashboard
    y sus componentes críticos.
    
    **Verifica:**
    - Conectividad con Redis
    - Performance del cache
    - Estado de background jobs
    - Métricas del sistema
    
    **No requiere autenticación** - es un health check público
    """
    try:
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "services": {},
            "metrics": {}
        }
        
        # Verificar Redis connectivity
        try:
            await redis_client.ping()
            redis_info = await redis_client.info()
            health_status["services"]["redis"] = {
                "status": "healthy",
                "connected_clients": redis_info.get("connected_clients", 0),
                "used_memory_human": redis_info.get("used_memory_human", "unknown")
            }
        except Exception as e:
            health_status["services"]["redis"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health_status["status"] = "degraded"
        
        # Verificar cache hit ratios (estimado)
        try:
            # Obtener sample de cache keys para estimar hit ratio
            sample_keys = await redis_client.keys("dashboard_summary:*")
            cache_keys_count = len(sample_keys)
            
            health_status["metrics"]["cache"] = {
                "dashboard_cache_keys": cache_keys_count,
                "estimated_active_users": cache_keys_count,
                "cache_status": "active" if cache_keys_count > 0 else "empty"
            }
        except Exception as e:
            health_status["metrics"]["cache"] = {
                "error": "Could not retrieve cache metrics",
                "details": str(e)
            }
        
        # Verificar background jobs (básico - verificar que el scheduler esté corriendo)
        try:
            from app.core.scheduler import get_scheduler
            scheduler = get_scheduler()
            
            if scheduler and scheduler.running:
                job_count = len(scheduler.get_jobs())
                health_status["services"]["scheduler"] = {
                    "status": "running",
                    "active_jobs": job_count
                }
            else:
                health_status["services"]["scheduler"] = {
                    "status": "stopped",
                    "active_jobs": 0
                }
                health_status["status"] = "degraded"
                
        except Exception as e:
            health_status["services"]["scheduler"] = {
                "status": "unknown", 
                "error": str(e)
            }
        
        # Performance metrics
        health_status["metrics"]["performance"] = {
            "target_dashboard_response": "< 50ms",
            "target_comprehensive_stats": "< 200ms",
            "target_cache_hit_ratio": "> 70%"
        }
        
        return health_status
        
    except Exception as e:
        logger.error(f"Error in dashboard health check: {e}", exc_info=True)
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "error": "Health check failed",
            "details": str(e)
        }