# 🔔 Mejoras de Seguridad y Rendimiento - Sistema de Notificaciones de Nutrición

## 📊 Análisis Ejecutivo

El sistema de notificaciones implementado es funcional pero requiere optimizaciones críticas para producción a escala.

### 🚨 Prioridad CRÍTICA (Implementar YA)

#### 1. Rate Limiting en Endpoints de Notificaciones

**Problema:** Sin límites, un usuario puede hacer spam de notificaciones.

**Solución:**
```python
# app/api/v1/endpoints/nutrition.py

from app.middleware.rate_limit import limiter

@router.post("/notifications/test")
@limiter.limit("5 per hour")  # Máximo 5 pruebas por hora
def send_test_notification(...):
    ...

@router.put("/notifications/settings")
@limiter.limit("10 per day")  # Máximo 10 cambios de config por día
def update_notification_settings(...):
    ...
```

#### 2. Queue System para Notificaciones Masivas

**Problema:** Si 1000 usuarios tienen notificación a las 13:00, el sistema se sobrecarga.

**Solución con Celery:**
```python
# app/tasks/nutrition_notifications.py
from celery import Celery
from typing import List

app = Celery('nutrition_notifications')

@app.task(rate_limit='100/m')  # 100 notificaciones por minuto
def send_meal_reminder_task(user_id: int, meal_type: str, meal_name: str):
    """Task asíncrono para enviar recordatorio"""
    # Lógica de envío
    pass

@app.task
def send_batch_reminders(user_data: List[dict]):
    """Enviar recordatorios en batch"""
    for data in user_data:
        send_meal_reminder_task.delay(**data)
```

**Alternativa con AWS SQS (ya configurado):**
```python
# app/services/nutrition_notification_service.py
import boto3
import json

class NutritionNotificationService:
    def __init__(self):
        self.sqs = boto3.client('sqs',
            region_name=os.environ.get('AWS_REGION', 'us-east-1')
        )
        self.queue_url = os.environ.get('SQS_NOTIFICATIONS_QUEUE_URL')

    def queue_meal_reminder(self, user_id: int, meal_type: str):
        """Encolar recordatorio para procesamiento asíncrono"""
        message = {
            'type': 'meal_reminder',
            'user_id': user_id,
            'meal_type': meal_type,
            'timestamp': datetime.utcnow().isoformat()
        }

        self.sqs.send_message(
            QueueUrl=self.queue_url,
            MessageBody=json.dumps(message),
            DelaySeconds=0
        )
```

#### 3. Cache de Configuraciones con Redis

**Problema:** Se consulta la BD en cada check de notificaciones.

**Solución:**
```python
# app/services/nutrition_notification_service.py
from app.db.redis_client import get_redis_client
import json

class NutritionNotificationService:
    async def get_users_for_notification(self, gym_id: int, meal_type: str, time_str: str):
        """Obtener usuarios con cache"""
        redis = await get_redis_client()

        # Cache key con TTL de 5 minutos
        cache_key = f"nutrition:reminders:{gym_id}:{meal_type}:{time_str}"

        # Intentar obtener de cache
        cached = await redis.get(cache_key)
        if cached:
            return json.loads(cached)

        # Si no está en cache, consultar BD
        users = self._query_users_for_time(gym_id, meal_type, time_str)

        # Guardar en cache
        await redis.setex(cache_key, 300, json.dumps(users))

        return users
```

### ⚠️ Prioridad ALTA (Próxima Semana)

#### 4. Multi-Gym Support en Scheduler

**Problema:** Jobs hardcodeados para gym_id=1

**Solución:**
```python
# app/core/scheduler.py
def init_nutrition_jobs(scheduler):
    """Inicializar jobs para todos los gimnasios"""
    from app.db.session import SessionLocal
    from app.models.gym import Gym

    db = SessionLocal()
    try:
        # Obtener todos los gimnasios activos
        active_gyms = db.query(Gym).filter(
            Gym.is_active == True,
            Gym.modules.contains(['nutrition'])  # Solo gyms con módulo nutrición
        ).all()

        for gym in active_gyms:
            # Crear jobs para cada gimnasio
            for hour in [6, 7, 8, 9, 10]:  # Desayuno
                scheduler.add_job(
                    lambda g=gym.id, h=hour: send_meal_reminders_job(g, "breakfast", f"{h:02d}:00"),
                    trigger=CronTrigger(hour=hour, minute=0),
                    id=f'nutrition_breakfast_{gym.id}_{hour:02d}00',
                    replace_existing=True
                )
    finally:
        db.close()
```

#### 5. Auditoría de Cambios

**Problema:** No hay registro de cambios de configuración.

**Solución:**
```python
# app/models/nutrition.py
class NotificationAuditLog(Base):
    __tablename__ = "nutrition_notification_audit"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"))
    plan_id = Column(Integer, ForeignKey("nutrition_plans.id"))
    action = Column(String)  # 'enabled', 'disabled', 'time_changed'
    old_value = Column(JSON)
    new_value = Column(JSON)
    ip_address = Column(String)
    user_agent = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
```

#### 6. Métricas y Monitoreo

**Solución con Prometheus:**
```python
# app/metrics/nutrition.py
from prometheus_client import Counter, Histogram, Gauge

# Contadores
notifications_sent = Counter('nutrition_notifications_sent_total',
    'Total notificaciones enviadas', ['type', 'gym_id'])
notifications_failed = Counter('nutrition_notifications_failed_total',
    'Total notificaciones fallidas', ['type', 'gym_id', 'error'])

# Histogramas
notification_latency = Histogram('nutrition_notification_latency_seconds',
    'Latencia de envío de notificaciones', ['type'])

# Gauges
active_notification_users = Gauge('nutrition_active_notification_users',
    'Usuarios con notificaciones activas', ['gym_id'])

# Uso en el servicio
class NutritionNotificationService:
    def send_meal_reminder(self, ...):
        start_time = time.time()
        try:
            # Enviar notificación
            result = self._send(...)

            notifications_sent.labels(type='meal_reminder', gym_id=gym_id).inc()
            notification_latency.labels(type='meal_reminder').observe(
                time.time() - start_time
            )

        except Exception as e:
            notifications_failed.labels(
                type='meal_reminder',
                gym_id=gym_id,
                error=type(e).__name__
            ).inc()
```

### 💡 Prioridad MEDIA (Próximo Sprint)

#### 7. Notificaciones Inteligentes

**Implementar ML para optimizar horarios:**
```python
class SmartNotificationScheduler:
    def predict_best_time(self, user_id: int, meal_type: str):
        """Predecir mejor hora basado en comportamiento"""
        # Analizar:
        # - Horarios de comidas completadas históricamente
        # - Horarios de apertura de app
        # - Zona horaria del usuario
        # - Días de la semana vs fin de semana

        return optimal_time
```

#### 8. Fallback System

**Implementar múltiples canales:**
```python
class MultiChannelNotification:
    async def send_with_fallback(self, user_id: int, message: dict):
        """Intentar múltiples canales"""
        # 1. Push notification
        if not await self.send_push(user_id, message):
            # 2. Email
            if not await self.send_email(user_id, message):
                # 3. SMS (si configurado)
                if not await self.send_sms(user_id, message):
                    # 4. In-app notification
                    await self.save_in_app_notification(user_id, message)
```

### 📊 Benchmarks de Rendimiento Esperados

| Métrica | Actual (Estimado) | Con Mejoras | Target Producción |
|---------|------------------|-------------|-------------------|
| Notificaciones/segundo | 10-20 | 100-200 | 500+ |
| Latencia P95 | 2-5s | 500ms | <200ms |
| Tasa de entrega | 80% | 95% | 99%+ |
| Costo por 1000 notif | $0.50 | $0.30 | $0.10 |
| Usuarios concurrentes | 100 | 1,000 | 10,000+ |

### 🛡️ Checklist de Seguridad

- [ ] Rate limiting implementado
- [ ] Logs de auditoría activos
- [ ] Validación de inputs exhaustiva
- [ ] Sanitización de contenido de notificaciones
- [ ] Encriptación de datos sensibles en tránsito
- [ ] Tokens de notificación con expiración
- [ ] Monitoring de intentos de abuso
- [ ] Backup plan si OneSignal falla
- [ ] GDPR compliance (opt-in/opt-out claro)
- [ ] Testing de penetración

### 📈 KPIs a Monitorear

1. **Engagement**
   - Click-through rate de notificaciones
   - Tiempo hasta apertura
   - Acciones post-notificación

2. **Técnicos**
   - Latencia de entrega
   - Tasa de fallo
   - Carga del sistema en horas pico

3. **Negocio**
   - Retención de usuarios con notificaciones vs sin
   - Completación de comidas post-recordatorio
   - Satisfacción del usuario

### 🚀 Plan de Implementación

#### Fase 1 (Esta Semana)
1. ✅ Sistema básico de notificaciones (COMPLETADO)
2. 🔄 Rate limiting
3. 🔄 Cache con Redis

#### Fase 2 (Próxima Semana)
4. Queue system (SQS/Celery)
5. Multi-gym support
6. Auditoría básica

#### Fase 3 (En 2 Semanas)
7. Métricas con Prometheus
8. Dashboard de monitoreo
9. Alertas automáticas

#### Fase 4 (Próximo Mes)
10. ML para optimización
11. Multi-channel support
12. A/B testing de horarios

### 🎯 Conclusión

El sistema implementado es un **MVP funcional** pero requiere las optimizaciones listadas para ser **production-ready** a escala. Las mejoras críticas (rate limiting, queues, cache) deben implementarse antes del lanzamiento para evitar problemas de rendimiento y seguridad.

**Recomendación:** Implementar Fases 1-2 antes de activar notificaciones para todos los usuarios.