# 🚀 Plan de Implementación: Activity Feed Anónimo con Cantidades

## 📋 Resumen Ejecutivo

Implementación de un Activity Feed **completamente anónimo** que muestra cantidades y estadísticas agregadas sin exponer nombres de usuarios. Arquitectura 100% Redis con TTL automático.

**Principio Core**: *"Números que motivan, sin nombres que comprometan"*

## 🎯 Objetivos

- **Engagement**: +25-30% en actividad diaria
- **Privacidad**: 100% anónimo, sin nombres de usuarios
- **Performance**: <50ms latencia
- **Mantenimiento**: Zero (TTL automático en Redis)

## 📊 Tipos de Actividades (Sin Nombres)

### 1. 💪 Actividad en Tiempo Real
```
Ejemplos:
- "💪 12 personas entrenando ahora"
- "🔥 5 personas en CrossFit matutino"
- "🏃 3 personas corriendo en caminadoras"
```

### 2. ⭐ Logros Agregados
```
Ejemplos:
- "⭐ 3 personas alcanzaron 100 clases este mes"
- "🔥 7 usuarios con racha de 30+ días"
- "🎯 15 metas personales cumplidas esta semana"
```

### 3. 📈 Estado de Clases
```
Ejemplos:
- "🔥 Spinning 7pm: 18/20 lugares ocupados"
- "⚡ HIIT: Clase más popular hoy (25 asistentes)"
- "📊 Yoga: +40% asistencia vs semana pasada"
```

### 4. 👥 Actividad Social Agregada
```
Ejemplos:
- "👥 8 grupos de amigos entrenando juntos hoy"
- "🤝 15 nuevas conexiones esta semana"
- "💬 200+ mensajes de motivación intercambiados"
```

### 5. 🏆 Rankings Anónimos
```
Ejemplos:
- "🥇 Top 3 en consistencia: 45, 42, 40 días"
- "📊 Percentil 90: 20+ clases al mes"
- "⚡ Récord del día: 2.5 horas de entrenamiento"
```

### 6. 🎯 Métricas Motivacionales
```
Ejemplos:
- "📈 85% de miembros mejoraron vs mes pasado"
- "💪 1,500 horas totales entrenadas esta semana"
- "🎉 50 PRs (Personal Records) en el gym este mes"
```

## 🏗️ Arquitectura Técnica

### Stack Tecnológico
```yaml
Storage: Redis (100% efímero)
Backend: FastAPI + Python
Real-time: Redis Pub/Sub
Cache: Redis con TTL automático
No Database: Sin persistencia permanente
```

### Estructura de Datos en Redis

```python
# Estructura de keys en Redis
REDIS_SCHEMA = {
    # Contadores en tiempo real
    "gym:{gym_id}:realtime:training_count": "12",  # INT
    "gym:{gym_id}:realtime:by_class:{class_type}": "5",  # INT

    # Agregados del día
    "gym:{gym_id}:daily:achievements_count": "7",  # INT
    "gym:{gym_id}:daily:total_hours": "156.5",  # FLOAT
    "gym:{gym_id}:daily:attendance": "89",  # INT

    # Rankings (sorted sets)
    "gym:{gym_id}:rankings:consistency": {  # ZSET
        "anonymous_1": 45,
        "anonymous_2": 42,
        "anonymous_3": 40
    },

    # Feed temporal (list)
    "gym:{gym_id}:feed:activities": [  # LIST con TTL
        '{"type": "realtime", "message": "12 personas entrenando", "timestamp": "..."}',
        '{"type": "achievement", "message": "3 personas alcanzaron 100 clases", "timestamp": "..."}'
    ]
}

# TTLs por tipo
TTL_CONFIG = {
    "realtime": 300,      # 5 minutos
    "daily": 86400,       # 24 horas
    "weekly": 604800,     # 7 días
    "feed": 3600,         # 1 hora
}
```

## 💻 Implementación Detallada

### Fase 1: Core Service (Día 1-3)

#### 1.1 Activity Feed Service

```python
# app/services/activity_feed_service.py

from typing import List, Dict, Any
import json
import asyncio
from datetime import datetime, timedelta
from redis.asyncio import Redis
from app.db.redis_client import get_redis_client

class ActivityFeedService:
    """
    Servicio para gestionar Activity Feed anónimo basado en cantidades
    """

    def __init__(self, redis: Redis):
        self.redis = redis

    async def publish_realtime_activity(
        self,
        gym_id: int,
        activity_type: str,
        count: int,
        metadata: Dict = None
    ):
        """Publica actividad en tiempo real (solo cantidades)"""

        # Actualizar contador
        key = f"gym:{gym_id}:realtime:{activity_type}"
        await self.redis.setex(key, 300, count)  # 5 min TTL

        # Crear mensaje para feed
        activity = {
            "type": "realtime",
            "subtype": activity_type,
            "count": count,
            "message": self._generate_message(activity_type, count, metadata),
            "timestamp": datetime.utcnow().isoformat(),
            "icon": self._get_icon(activity_type)
        }

        # Agregar al feed
        feed_key = f"gym:{gym_id}:feed:activities"
        await self.redis.lpush(feed_key, json.dumps(activity))
        await self.redis.ltrim(feed_key, 0, 99)  # Mantener últimas 100
        await self.redis.expire(feed_key, 3600)  # 1 hora TTL

        # Publicar para subscriptores real-time
        await self.redis.publish(
            f"gym:{gym_id}:feed:updates",
            json.dumps(activity)
        )

    async def update_aggregate_stats(
        self,
        gym_id: int,
        stat_type: str,
        value: Any,
        increment: bool = False
    ):
        """Actualiza estadísticas agregadas"""

        key = f"gym:{gym_id}:daily:{stat_type}"

        if increment:
            await self.redis.incr(key)
        else:
            await self.redis.setex(key, 86400, value)  # 24h TTL

    async def get_feed(
        self,
        gym_id: int,
        limit: int = 20,
        offset: int = 0
    ) -> List[Dict]:
        """Obtiene el feed de actividades"""

        feed_key = f"gym:{gym_id}:feed:activities"

        # Obtener actividades del feed
        raw_activities = await self.redis.lrange(
            feed_key,
            offset,
            offset + limit - 1
        )

        activities = []
        for raw in raw_activities:
            try:
                activity = json.loads(raw)
                activities.append(activity)
            except:
                continue

        # Enriquecer con estadísticas actuales
        activities = await self._enrich_with_current_stats(gym_id, activities)

        return activities

    async def get_realtime_summary(self, gym_id: int) -> Dict:
        """Obtiene resumen en tiempo real"""

        # Obtener todos los contadores actuales
        pattern = f"gym:{gym_id}:realtime:*"
        keys = await self.redis.keys(pattern)

        summary = {
            "total_training": 0,
            "by_area": {},
            "popular_classes": [],
            "peak_time": False
        }

        for key in keys:
            value = await self.redis.get(key)
            if value:
                key_parts = key.decode().split(":")
                if "training_count" in key_parts:
                    summary["total_training"] = int(value)
                elif "by_class" in key_parts:
                    class_name = key_parts[-1]
                    summary["by_area"][class_name] = int(value)

        # Determinar si es hora pico (>20 personas)
        summary["peak_time"] = summary["total_training"] > 20

        return summary

    async def generate_motivational_insights(self, gym_id: int) -> List[str]:
        """Genera insights motivacionales basados en datos agregados"""

        insights = []

        # Total de personas entrenando
        training_count = await self.redis.get(f"gym:{gym_id}:realtime:training_count")
        if training_count and int(training_count) > 10:
            insights.append(f"🔥 ¡{training_count} guerreros activos ahora mismo!")

        # Logros del día
        achievements = await self.redis.get(f"gym:{gym_id}:daily:achievements_count")
        if achievements and int(achievements) > 5:
            insights.append(f"⭐ {achievements} logros desbloqueados hoy")

        # Récords rotos
        prs = await self.redis.get(f"gym:{gym_id}:daily:personal_records")
        if prs and int(prs) > 0:
            insights.append(f"💪 {prs} récords personales superados")

        # Consistencia grupal
        streak_count = await self.redis.get(f"gym:{gym_id}:daily:active_streaks")
        if streak_count and int(streak_count) > 10:
            insights.append(f"🔥 {streak_count} personas con racha activa")

        return insights

    def _generate_message(
        self,
        activity_type: str,
        count: int,
        metadata: Dict = None
    ) -> str:
        """Genera mensaje legible para la actividad"""

        messages = {
            "training_count": f"{count} personas entrenando ahora",
            "class_checkin": f"{count} personas en {metadata.get('class_name', 'clase')}",
            "achievement_unlocked": f"{count} logros desbloqueados",
            "streak_milestone": f"{count} personas con racha de {metadata.get('days', '7')}+ días",
            "pr_broken": f"{count} récords personales rotos",
            "goal_completed": f"{count} metas cumplidas"
        }

        return messages.get(activity_type, f"{count} actividades")

    def _get_icon(self, activity_type: str) -> str:
        """Retorna emoji apropiado para el tipo de actividad"""

        icons = {
            "training_count": "💪",
            "class_checkin": "📍",
            "achievement_unlocked": "⭐",
            "streak_milestone": "🔥",
            "pr_broken": "🏆",
            "goal_completed": "🎯",
            "social_activity": "👥",
            "class_popular": "📈"
        }

        return icons.get(activity_type, "📊")
```

#### 1.2 Event Aggregator

```python
# app/services/activity_aggregator.py

class ActivityAggregator:
    """
    Agrega eventos del sistema en estadísticas anónimas
    """

    def __init__(self, feed_service: ActivityFeedService):
        self.feed_service = feed_service

    async def on_class_checkin(self, event: Dict):
        """Procesa check-in a clase"""

        gym_id = event["gym_id"]
        class_name = event["class_name"]

        # Incrementar contador de clase
        class_key = f"gym:{gym_id}:realtime:by_class:{class_name}"
        await self.feed_service.redis.incr(class_key)
        await self.feed_service.redis.expire(class_key, 300)

        # Incrementar total
        total_key = f"gym:{gym_id}:realtime:training_count"
        current = await self.feed_service.redis.incr(total_key)
        await self.feed_service.redis.expire(total_key, 300)

        # Publicar si es múltiplo de 5
        if current % 5 == 0:
            await self.feed_service.publish_realtime_activity(
                gym_id=gym_id,
                activity_type="training_count",
                count=current
            )

    async def on_achievement_unlocked(self, event: Dict):
        """Procesa logro desbloqueado (sin nombre)"""

        gym_id = event["gym_id"]
        achievement_type = event["achievement_type"]

        # Incrementar contador diario
        await self.feed_service.update_aggregate_stats(
            gym_id=gym_id,
            stat_type="achievements_count",
            value=1,
            increment=True
        )

        # Obtener total del día
        key = f"gym:{gym_id}:daily:achievements_count"
        count = await self.feed_service.redis.get(key)

        # Publicar cada 5 logros
        if int(count or 0) % 5 == 0:
            await self.feed_service.publish_realtime_activity(
                gym_id=gym_id,
                activity_type="achievement_unlocked",
                count=int(count),
                metadata={"type": achievement_type}
            )

    async def on_streak_milestone(self, event: Dict):
        """Procesa hito de racha (anónimo)"""

        gym_id = event["gym_id"]
        days = event["streak_days"]

        # Contar personas con rachas activas
        if days in [7, 30, 60, 90, 365]:
            key = f"gym:{gym_id}:daily:streak_{days}"
            await self.feed_service.redis.incr(key)
            await self.feed_service.redis.expire(key, 86400)

            count = await self.feed_service.redis.get(key)

            await self.feed_service.publish_realtime_activity(
                gym_id=gym_id,
                activity_type="streak_milestone",
                count=int(count),
                metadata={"days": days}
            )

    async def calculate_hourly_summary(self, gym_id: int):
        """Calcula resumen cada hora"""

        # Obtener estadísticas
        stats = await self._gather_hourly_stats(gym_id)

        # Generar mensajes motivacionales
        messages = []

        if stats["total_attendance"] > 50:
            messages.append(f"🔥 {stats['total_attendance']} asistencias en la última hora")

        if stats["new_prs"] > 10:
            messages.append(f"💪 {stats['new_prs']} nuevos récords personales")

        if stats["goals_completed"] > 5:
            messages.append(f"🎯 {stats['goals_completed']} metas alcanzadas")

        # Publicar resumen
        for message in messages:
            activity = {
                "type": "hourly_summary",
                "message": message,
                "timestamp": datetime.utcnow().isoformat()
            }

            feed_key = f"gym:{gym_id}:feed:activities"
            await self.feed_service.redis.lpush(feed_key, json.dumps(activity))
```

### Fase 2: API Endpoints (Día 4-5)

```python
# app/api/v1/endpoints/activity_feed.py

from fastapi import APIRouter, Depends, Query
from typing import List, Optional
from app.services.activity_feed_service import ActivityFeedService
from app.core.tenant import get_tenant_id
from redis.asyncio import Redis
from app.db.redis_client import get_redis_client

router = APIRouter(prefix="/activity-feed", tags=["Activity Feed"])

@router.get("/", response_model=List[Dict])
async def get_activity_feed(
    gym_id: int = Depends(get_tenant_id),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    redis: Redis = Depends(get_redis_client)
):
    """
    Obtiene el feed de actividades anónimo

    Todas las actividades muestran cantidades sin nombres de usuarios.
    """
    feed_service = ActivityFeedService(redis)
    activities = await feed_service.get_feed(gym_id, limit, offset)

    return {
        "activities": activities,
        "count": len(activities),
        "has_more": len(activities) == limit
    }

@router.get("/realtime", response_model=Dict)
async def get_realtime_stats(
    gym_id: int = Depends(get_tenant_id),
    redis: Redis = Depends(get_redis_client)
):
    """
    Obtiene estadísticas en tiempo real

    Retorna contadores actuales de personas entrenando.
    """
    feed_service = ActivityFeedService(redis)
    summary = await feed_service.get_realtime_summary(gym_id)

    return summary

@router.get("/insights", response_model=List[str])
async def get_motivational_insights(
    gym_id: int = Depends(get_tenant_id),
    redis: Redis = Depends(get_redis_client)
):
    """
    Obtiene insights motivacionales basados en actividad

    Mensajes generados dinámicamente según la actividad actual.
    """
    feed_service = ActivityFeedService(redis)
    insights = await feed_service.generate_motivational_insights(gym_id)

    return {"insights": insights}

@router.get("/rankings/anonymous", response_model=Dict)
async def get_anonymous_rankings(
    gym_id: int = Depends(get_tenant_id),
    metric: str = Query("consistency", regex="^(consistency|attendance|improvement)$"),
    redis: Redis = Depends(get_redis_client)
):
    """
    Obtiene rankings anónimos (solo números)

    Muestra top performers sin identificar usuarios.
    """
    key = f"gym:{gym_id}:rankings:{metric}"

    # Obtener top 10
    top_scores = await redis.zrevrange(key, 0, 9, withscores=True)

    rankings = []
    for i, (_, score) in enumerate(top_scores, 1):
        rankings.append({
            "position": i,
            "value": int(score),
            "label": f"Posición {i}"
        })

    return {
        "metric": metric,
        "rankings": rankings,
        "unit": _get_unit_for_metric(metric)
    }

@router.websocket("/ws")
async def websocket_feed(
    websocket: WebSocket,
    gym_id: int = Depends(get_tenant_id),
    redis: Redis = Depends(get_redis_client)
):
    """
    WebSocket para actualizaciones en tiempo real
    """
    await websocket.accept()

    # Subscribir a actualizaciones
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"gym:{gym_id}:feed:updates")

    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True)
            if message:
                await websocket.send_text(message["data"])
    except WebSocketDisconnect:
        await pubsub.unsubscribe()

def _get_unit_for_metric(metric: str) -> str:
    units = {
        "consistency": "días consecutivos",
        "attendance": "clases este mes",
        "improvement": "% mejora"
    }
    return units.get(metric, "puntos")
```

### Fase 3: Scheduled Jobs (Día 6)

```python
# app/core/scheduled_jobs.py

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.services.activity_feed_service import ActivityFeedService
from app.services.activity_aggregator import ActivityAggregator

def setup_feed_jobs(scheduler: AsyncIOScheduler):
    """Configura jobs para el Activity Feed"""

    # Cada 5 minutos: actualizar contadores en tiempo real
    scheduler.add_job(
        update_realtime_counters,
        'interval',
        minutes=5,
        id='update_realtime_counters',
        replace_existing=True
    )

    # Cada hora: generar resumen
    scheduler.add_job(
        generate_hourly_summary,
        'cron',
        minute=0,
        id='generate_hourly_summary',
        replace_existing=True
    )

    # Diario a las 6 AM: resetear contadores diarios
    scheduler.add_job(
        reset_daily_counters,
        'cron',
        hour=6,
        minute=0,
        id='reset_daily_counters',
        replace_existing=True
    )

    # Cada 30 minutos: limpiar datos expirados
    scheduler.add_job(
        cleanup_expired_data,
        'interval',
        minutes=30,
        id='cleanup_expired_data',
        replace_existing=True
    )

async def update_realtime_counters():
    """Actualiza contadores basados en datos actuales"""

    redis = await get_redis_client()
    feed_service = ActivityFeedService(redis)

    # Para cada gimnasio activo
    gyms = await get_active_gyms()

    for gym_id in gyms:
        # Contar usuarios activos actualmente
        active_count = await count_active_users_in_gym(gym_id)

        if active_count > 0:
            await feed_service.publish_realtime_activity(
                gym_id=gym_id,
                activity_type="training_count",
                count=active_count
            )

async def generate_hourly_summary():
    """Genera resumen horario de actividad"""

    redis = await get_redis_client()
    aggregator = ActivityAggregator(ActivityFeedService(redis))

    gyms = await get_active_gyms()

    for gym_id in gyms:
        await aggregator.calculate_hourly_summary(gym_id)

async def cleanup_expired_data():
    """Limpieza automática (aunque Redis TTL lo maneja)"""

    # Redis TTL maneja la expiración automáticamente
    # Este job es para logging y monitoreo

    redis = await get_redis_client()

    # Log de memoria usada
    info = await redis.info("memory")
    used_memory = info.get("used_memory_human", "unknown")

    logger.info(f"Redis memory usage: {used_memory}")
```

## 📅 Timeline de Implementación

### Semana 1: Foundation
| Día | Tareas | Entregables |
|-----|--------|-------------|
| 1-2 | Core Service Development | `ActivityFeedService` completo |
| 3 | Event Aggregator | Sistema de agregación funcionando |
| 4-5 | API Endpoints | REST API + WebSocket |

### Semana 2: Integration & Polish
| Día | Tareas | Entregables |
|-----|--------|-------------|
| 6 | Scheduled Jobs | Jobs automáticos configurados |
| 7 | Testing | Suite de tests completa |
| 8-9 | Integration | Integración con eventos existentes |
| 10 | Optimization | Performance tuning |

## 📊 Métricas de Éxito

### KPIs Técnicos
```python
TECHNICAL_KPIS = {
    "response_time": "< 50ms p95",
    "memory_usage": "< 50MB per gym",
    "availability": "> 99.9%",
    "error_rate": "< 0.1%"
}
```

### KPIs de Negocio
```python
BUSINESS_KPIS = {
    "daily_active_users": "+25%",
    "session_duration": "+20%",
    "user_interactions": "+30%",
    "feature_adoption": "> 60% in 30 days"
}
```

### KPIs de Privacidad
```python
PRIVACY_KPIS = {
    "data_exposed": "0 personal identifiers",
    "privacy_complaints": "0",
    "gdpr_compliance": "100%",
    "user_trust_score": "> 90%"
}
```

## 🔧 Configuración

### Variables de Entorno
```bash
# Redis Configuration
REDIS_URL=redis://localhost:6379/0
REDIS_MAX_CONNECTIONS=50

# Activity Feed Settings
FEED_MAX_ITEMS=100
FEED_DEFAULT_TTL=3600
REALTIME_UPDATE_INTERVAL=300

# Privacy Settings
ANONYMIZE_ALL_ACTIVITIES=true
MIN_AGGREGATION_THRESHOLD=3
SHOW_USER_NAMES=false
```

### Feature Flags
```python
FEATURE_FLAGS = {
    "activity_feed_enabled": True,
    "realtime_updates": True,
    "websocket_enabled": True,
    "anonymous_only": True,  # Siempre true
    "show_rankings": True,
    "motivational_insights": True
}
```

## 🧪 Testing Strategy

### Unit Tests
```python
# tests/test_activity_feed.py

async def test_anonymous_activity_creation():
    """Verifica que las actividades nunca contengan nombres"""

    activity = await feed_service.publish_realtime_activity(
        gym_id=1,
        activity_type="training_count",
        count=15
    )

    assert "name" not in activity
    assert "user" not in activity
    assert activity["count"] == 15

async def test_aggregation_threshold():
    """Verifica que no se muestren cantidades < 3"""

    activity = await feed_service.publish_realtime_activity(
        gym_id=1,
        activity_type="training_count",
        count=2
    )

    assert activity is None  # No debe publicarse
```

### Load Tests
```python
# tests/load/test_feed_performance.py

async def test_feed_under_load():
    """Prueba con 1000 requests concurrentes"""

    tasks = []
    for _ in range(1000):
        tasks.append(feed_service.get_feed(gym_id=1))

    start = time.time()
    results = await asyncio.gather(*tasks)
    duration = time.time() - start

    assert duration < 5  # Menos de 5 segundos para 1000 requests
    assert all(r is not None for r in results)
```

## 🚀 Deployment

### Docker Configuration
```dockerfile
# Dockerfile addition
ENV ACTIVITY_FEED_ENABLED=true
ENV ANONYMOUS_ONLY=true
ENV REDIS_URL=redis://redis:6379/0
```

### Health Checks
```python
@router.get("/health")
async def feed_health_check(redis: Redis = Depends(get_redis_client)):
    """Health check del Activity Feed"""

    try:
        # Verificar Redis
        await redis.ping()

        # Verificar memoria
        info = await redis.info("memory")
        used_memory_mb = float(info.get("used_memory", 0)) / 1024 / 1024

        return {
            "status": "healthy",
            "redis": "connected",
            "memory_usage_mb": round(used_memory_mb, 2),
            "anonymous_mode": True
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }
```

## 📈 Monitoreo

### Prometheus Metrics
```python
# Métricas para Grafana
feed_requests = Counter('activity_feed_requests_total', 'Total feed requests')
feed_latency = Histogram('activity_feed_latency_seconds', 'Feed response time')
active_users_gauge = Gauge('gym_active_users', 'Currently active users')
```

### Alertas
```yaml
alerts:
  - name: HighFeedLatency
    condition: feed_latency > 100ms
    severity: warning

  - name: RedisMemoryHigh
    condition: redis_memory > 100MB
    severity: critical

  - name: PrivacyBreach
    condition: user_name_exposed == true
    severity: critical
    action: immediate_shutdown
```

## ✅ Checklist Pre-Launch

- [ ] Todos los nombres de usuario removidos
- [ ] Agregación mínima de 3 configurada
- [ ] TTLs automáticos verificados
- [ ] WebSocket funcionando
- [ ] Tests de privacidad pasando
- [ ] Monitoreo configurado
- [ ] Feature flags listos
- [ ] Documentación actualizada

## 🎯 Resultado Esperado

Un Activity Feed que:
- **Motiva** sin exponer identidades
- **Engancha** con números y tendencias
- **Protege** la privacidad al 100%
- **Escala** sin mantenimiento
- **Performa** en < 50ms

---

*Plan preparado por: Claude*
*Fecha: 2024-11-28*
*Estado: LISTO PARA IMPLEMENTACIÓN*
*Tiempo estimado: 10 días*
*Complejidad: Media*
*Riesgo: Bajo (sin exposición de datos personales)*