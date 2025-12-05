"""
Activity Feed API Endpoints.

Endpoints para el feed de actividades anónimo que muestra estadísticas
agregadas sin exponer identidades de usuarios.
"""

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, HTTPException, status
from typing import List, Dict, Optional
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
import json
import logging

from app.db.redis_client import get_redis_client
from app.core.tenant import get_tenant_id
from app.services.async_activity_feed_service import async_activity_feed_service, AsyncActivityFeedService
from app.services.activity_aggregator import ActivityAggregator
from app.core.dependencies import module_enabled


# Dependency para obtener instancia del servicio
async def get_activity_feed_service(redis: Redis = Depends(get_redis_client)) -> AsyncActivityFeedService:
    """Inyecta instancia del servicio con Redis."""
    return async_activity_feed_service(redis)

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Activity Feed"]
    # dependencies=[module_enabled("activity_feed")]  # TODO: Agregar módulo a BD
)


@router.get("/", summary="Obtener feed de actividades")
async def get_activity_feed(
    gym_id: int = Depends(get_tenant_id),
    limit: int = Query(20, ge=1, le=100, description="Número de actividades a retornar"),
    offset: int = Query(0, ge=0, description="Offset para paginación"),
    service: AsyncActivityFeedService = Depends(get_activity_feed_service)
) -> Dict:
    """
    Obtiene el feed de actividades anónimo.

    Todas las actividades muestran solo cantidades agregadas sin nombres de usuarios.
    Perfecto para mantener la motivación respetando la privacidad.

    Returns:
        - activities: Lista de actividades del feed
        - count: Número de actividades retornadas
        - has_more: Si hay más actividades disponibles
    """
    try:
        activities = await service.get_feed(gym_id, limit, offset)

        return {
            "activities": activities,
            "count": len(activities),
            "has_more": len(activities) == limit,
            "offset": offset,
            "limit": limit
        }
    except Exception as e:
        logger.error(f"Error obteniendo feed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener el feed de actividades"
        )


@router.get("/realtime", summary="Estadísticas en tiempo real")
async def get_realtime_stats(
    gym_id: int = Depends(get_tenant_id),
    redis: Redis = Depends(get_redis_client)
) -> Dict:
    """
    Obtiene estadísticas en tiempo real del gimnasio.

    Muestra:
    - Total de personas entrenando ahora
    - Distribución por áreas/clases
    - Clases populares actuales
    - Si es hora pico

    Returns:
        Resumen con estadísticas actuales anónimas
    """
    try:
        summary = await async_activity_feed_service.get_realtime_summary(redis, gym_id)

        return {
            "status": "success",
            "data": summary
        }
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas en tiempo real: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener estadísticas en tiempo real"
        )


@router.get("/insights", summary="Insights motivacionales")
async def get_motivational_insights(
    gym_id: int = Depends(get_tenant_id),
    redis: Redis = Depends(get_redis_client)
) -> Dict:
    """
    Obtiene insights motivacionales basados en la actividad actual.

    Genera mensajes dinámicos como:
    - "🔥 45 guerreros activos ahora mismo!"
    - "⭐ 12 logros desbloqueados hoy"
    - "💪 8 récords personales superados"

    Returns:
        Lista de insights motivacionales
    """
    try:
        insights = await async_activity_feed_service.generate_motivational_insights(redis, gym_id)

        return {
            "insights": insights,
            "count": len(insights)
        }
    except Exception as e:
        logger.error(f"Error generando insights: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al generar insights motivacionales"
        )


@router.get("/rankings/{ranking_type}", summary="Rankings anónimos")
async def get_anonymous_rankings(
    ranking_type: str,
    gym_id: int = Depends(get_tenant_id),
    period: str = Query("weekly", regex="^(daily|weekly|monthly)$", description="Período del ranking"),
    limit: int = Query(10, ge=1, le=50, description="Número de posiciones a mostrar"),
    redis: Redis = Depends(get_redis_client)
) -> Dict:
    """
    Obtiene rankings anónimos (solo valores, sin nombres).

    Tipos disponibles:
    - consistency: Días consecutivos de entrenamiento
    - attendance: Clases asistidas
    - improvement: Porcentaje de mejora

    Args:
        ranking_type: Tipo de ranking a obtener
        period: Período del ranking (daily, weekly, monthly)
        limit: Número de posiciones top a mostrar

    Returns:
        Rankings con posiciones y valores anónimos
    """
    # Validar tipo de ranking
    valid_types = ["consistency", "attendance", "improvement", "activity", "dedication"]
    if ranking_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipo de ranking inválido. Tipos válidos: {valid_types}"
        )

    try:
        rankings = await async_activity_feed_service.get_anonymous_rankings(
            redis=redis,
            gym_id=gym_id,
            ranking_type=ranking_type,
            period=period,
            limit=limit
        )

        # Obtener unidad según el tipo
        units = {
            "consistency": "días consecutivos",
            "attendance": "clases",
            "improvement": "% mejora",
            "activity": "horas",
            "dedication": "puntos"
        }

        return {
            "type": ranking_type,
            "period": period,
            "rankings": rankings,
            "unit": units.get(ranking_type, "puntos"),
            "count": len(rankings)
        }
    except Exception as e:
        logger.error(f"Error obteniendo rankings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener rankings"
        )


@router.post("/test/generate-activity", summary="Generar actividad de prueba")
async def generate_test_activity(
    activity_type: str = Query(..., description="Tipo de actividad"),
    count: int = Query(..., ge=1, description="Cantidad para la actividad"),
    gym_id: int = Depends(get_tenant_id),
    redis: Redis = Depends(get_redis_client)
) -> Dict:
    """
    Endpoint de prueba para generar actividades.

    **Solo para desarrollo/testing**

    Args:
        activity_type: Tipo de actividad a generar
        count: Cantidad/número para mostrar

    Returns:
        Actividad generada
    """
    try:
        activity = await async_activity_feed_service.publish_realtime_activity(
            redis=redis,
            gym_id=gym_id,
            activity_type=activity_type,
            count=count,
            metadata={"source": "test"}
        )

        if activity:
            return {
                "status": "success",
                "activity": activity
            }
        else:
            return {
                "status": "not_published",
                "reason": f"Count {count} below threshold"
            }
    except Exception as e:
        logger.error(f"Error generando actividad de prueba: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al generar actividad: {str(e)}"
        )


@router.get("/stats/summary", summary="Resumen de estadísticas del día")
async def get_daily_stats_summary(
    gym_id: int = Depends(get_tenant_id),
    redis: Redis = Depends(get_redis_client)
) -> Dict:
    """
    Obtiene resumen de estadísticas del día.

    Incluye:
    - Total de personas que han entrenado
    - Logros desbloqueados
    - Récords personales
    - Clases completadas
    - Horas totales de entrenamiento

    Returns:
        Resumen con todas las estadísticas del día
    """
    try:
        # ✅ Optimización: Obtener todas las stats con un solo pipeline
        stats_keys = {
            "attendance": f"gym:{gym_id}:daily:attendance",
            "achievements": f"gym:{gym_id}:daily:achievements_count",
            "personal_records": f"gym:{gym_id}:daily:personal_records",
            "goals_completed": f"gym:{gym_id}:daily:goals_completed",
            "classes_completed": f"gym:{gym_id}:daily:classes_completed",
            "total_hours": f"gym:{gym_id}:daily:total_hours",
            "active_streaks": f"gym:{gym_id}:daily:active_streaks"
        }

        pipe = redis.pipeline()
        for key in stats_keys.values():
            pipe.get(key)
        values = await pipe.execute()

        # Mapear resultados
        stats = {}
        for (stat_name, key), value in zip(stats_keys.items(), values):
            if value:
                # Decodificar bytes si es necesario
                if isinstance(value, bytes):
                    value = value.decode()
                stats[stat_name] = float(value) if stat_name == "total_hours" else int(value)
            else:
                stats[stat_name] = 0

        # Calcular algunas métricas derivadas
        stats["average_class_size"] = (
            round(stats["attendance"] / stats["classes_completed"], 1)
            if stats["classes_completed"] > 0 else 0
        )

        stats["engagement_score"] = min(100, (
            (stats["attendance"] * 2) +
            (stats["achievements"] * 5) +
            (stats["personal_records"] * 10) +
            (stats["goals_completed"] * 3)
        ))

        return {
            "date": "today",
            "stats": stats,
            "highlights": _generate_highlights(stats)
        }
    except Exception as e:
        logger.error(f"Error obteniendo resumen de estadísticas: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener resumen de estadísticas"
        )


@router.websocket("/ws")
async def websocket_feed(
    websocket: WebSocket,
    gym_id: int = Query(...),
    redis: Redis = Depends(get_redis_client)
):
    """
    WebSocket para recibir actualizaciones del feed en tiempo real.

    Se suscribe al canal del gimnasio y envía actualizaciones cuando
    ocurren nuevas actividades.
    """
    await websocket.accept()
    logger.info(f"WebSocket conectado para gym {gym_id}")

    # Crear pubsub y suscribir al canal
    pubsub = redis.pubsub()
    channel = f"gym:{gym_id}:feed:updates"

    try:
        await pubsub.subscribe(channel)
        logger.info(f"Suscrito a canal: {channel}")

        # Enviar mensaje de bienvenida
        await websocket.send_json({
            "type": "connection",
            "message": "Conectado al feed en tiempo real",
            "gym_id": gym_id
        })

        # Loop principal para recibir mensajes
        while True:
            # Obtener mensaje del canal
            message = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=1.0
            )

            if message and message["type"] == "message":
                try:
                    # Decodificar y enviar
                    data = message["data"]
                    if isinstance(data, bytes):
                        data = data.decode('utf-8')

                    activity = json.loads(data)
                    await websocket.send_json({
                        "type": "activity",
                        "data": activity
                    })
                except json.JSONDecodeError as e:
                    logger.error(f"Error decodificando mensaje: {e}")
                except Exception as e:
                    logger.error(f"Error procesando mensaje: {e}")

    except WebSocketDisconnect:
        logger.info(f"WebSocket desconectado para gym {gym_id}")
    except Exception as e:
        logger.error(f"Error en WebSocket: {e}")
        await websocket.close(code=1000, reason=str(e))
    finally:
        # Limpiar suscripción
        try:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
        except:
            pass


@router.get("/health", summary="Health check del Activity Feed")
async def feed_health_check(
    redis: Redis = Depends(get_redis_client)
) -> Dict:
    """
    Health check del sistema de Activity Feed.

    Verifica:
    - Conexión con Redis
    - Uso de memoria
    - Configuración de privacidad

    Returns:
        Estado del sistema
    """
    try:
        # Verificar Redis
        await redis.ping()

        # Obtener info de memoria
        info = await redis.info("memory")
        used_memory_mb = float(info.get("used_memory", 0)) / 1024 / 1024

        # Contar keys de activity feed
        feed_keys = await redis.keys("gym:*:feed:*")
        realtime_keys = await redis.keys("gym:*:realtime:*")
        daily_keys = await redis.keys("gym:*:daily:*")

        return {
            "status": "healthy",
            "redis": "connected",
            "memory_usage_mb": round(used_memory_mb, 2),
            "anonymous_mode": True,  # Siempre true
            "privacy_compliant": True,
            "keys_count": {
                "feed": len(feed_keys),
                "realtime": len(realtime_keys),
                "daily": len(daily_keys),
                "total": len(feed_keys) + len(realtime_keys) + len(daily_keys)
            },
            "configuration": {
                "min_aggregation_threshold": 3,
                "show_user_names": False,
                "ttl_enabled": True
            }
        }
    except Exception as e:
        logger.error(f"Health check falló: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "redis": "disconnected"
        }


def _generate_highlights(stats: Dict) -> List[str]:
    """
    Genera highlights basados en las estadísticas.

    Args:
        stats: Diccionario con estadísticas

    Returns:
        Lista de highlights motivacionales
    """
    highlights = []

    if stats.get("attendance", 0) > 100:
        highlights.append(f"🔥 Día increíble con {stats['attendance']} asistencias")

    if stats.get("personal_records", 0) > 10:
        highlights.append(f"💪 {stats['personal_records']} récords rotos hoy")

    if stats.get("achievements", 0) > 20:
        highlights.append(f"⭐ {stats['achievements']} logros desbloqueados")

    if stats.get("active_streaks", 0) > 50:
        highlights.append(f"🔥 {stats['active_streaks']} rachas activas")

    if stats.get("engagement_score", 0) > 80:
        highlights.append("🏆 Engagement excepcional del gimnasio")

    return highlights[:3]  # Máximo 3 highlights