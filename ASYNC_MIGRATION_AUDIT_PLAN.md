# Plan de Auditoría Async/Sync - Migración a AsyncSession

## Estado Actual
- ✅ **Users Module**: Completamente migrado y revisado (8 métodos corregidos)
- ✅ **Post Interactions**: Migrado (8 métodos corregidos)
- ✅ **Stories**: Parcialmente revisado (5 errores corregidos)
- ✅ **Activity Feed**: Corregido (dependency injection)
- ✅ **Events**: Corregido (commit faltante en cancelación)
- ✅ **Context/Workspace**: Corregido (chicken-egg problem)
- ✅ **Membership**: Corregido (timezone comparison)

## Módulos Pendientes de Revisión

### 🔴 PRIORIDAD ALTA (Módulos críticos en producción)

#### 1. **Posts & Media Module** (3 archivos)
**Archivos:**
- `app/services/post_service.py` (sync legacy)
- `app/services/async_post_service.py`
- `app/services/post_media_service.py` / `async_post_media_service.py`

**Puntos a revisar:**
- ✅ Verificar que NO se use `db.get(Model, id)`
- ✅ Todos los métodos async usen `AsyncSession`
- ✅ Todos los `db.execute()` tengan `await`
- ✅ Todos los `db.commit/rollback/refresh/delete` tengan `await`
- ✅ No haya mixing de métodos sync del repositorio
- ⚠️  Identificado: `db.get(Event, id)` en línea 489, 500

**Estimación errores potenciales:** 5-10

---

#### 2. **Stories Module** (2 archivos)
**Archivos:**
- `app/services/story_service.py` (sync legacy)
- `app/services/async_story_service.py`

**Puntos a revisar:**
- ✅ Ya se corrigieron 5 errores en endpoints
- ⚠️  Identificado: `db.get(User, id)` en línea 309
- ✅ Verificar service layer completo

**Estimación errores potenciales:** 3-5

---

#### 3. **Events & Attendance Module** (3 archivos)
**Archivos:**
- `app/services/event.py` (sync legacy)
- `app/services/async_event.py`
- `app/services/attendance.py` / `async_attendance.py`

**Puntos a revisar:**
- ✅ Transacciones de cancelación (ya corregido un commit faltante)
- ✅ Verificar todos los flujos de pago de eventos
- ✅ Check-in/check-out async
- ✅ Generación de QR codes

**Estimación errores potenciales:** 8-12

---

#### 4. **Schedule & Classes Module** (2 archivos)
**Archivos:**
- `app/services/schedule.py` (sync legacy)
- `app/services/async_schedule.py`

**Puntos a revisar:**
- ✅ Reservas de clases
- ✅ Cancelaciones con transacciones
- ✅ Waitlists
- ✅ Capacidad dinámica

**Estimación errores potenciales:** 6-10

---

#### 5. **Chat Module** (4 archivos)
**Archivos:**
- `app/services/chat.py` (sync legacy)
- `app/services/async_chat.py`
- `app/services/gym_chat.py` / `async_gym_chat.py`
- `app/services/chat_analytics.py` / `async_chat_analytics.py`

**Puntos a revisar:**
- ✅ Stream Chat integration
- ✅ Webhooks de autorización
- ✅ Creación de canales
- ✅ Multi-tenancy con prefijos

**Estimación errores potenciales:** 10-15

---

### 🟡 PRIORIDAD MEDIA (Módulos importantes)

#### 6. **Billing & Stripe Module** (6 archivos)
**Archivos:**
- `app/services/stripe_service.py` / `async_stripe_service.py`
- `app/services/stripe_connect_service.py` / `async_stripe_connect_service.py`
- `app/services/billing_module.py` / `async_billing_module.py`
- `app/services/membership.py` / `async_membership.py` (✅ ya corregido timezone)

**Puntos a revisar:**
- ✅ Webhooks de Stripe
- ✅ Creación de suscripciones
- ✅ Ciclos de facturación
- ✅ Customer portal
- ✅ Payment links

**Estimación errores potenciales:** 12-18

---

#### 7. **Nutrition Module** (4 archivos)
**Archivos:**
- `app/services/nutrition.py`
- `app/services/nutrition_ai.py` / `async_nutrition_ai.py`
- `app/services/nutrition_notification_service.py` / `async_nutrition_notification_service_optimized.py`

**Puntos a revisar:**
- ✅ OpenAI GPT-4o-mini integration
- ✅ Análisis de imágenes de comidas
- ✅ Cálculo de macros
- ✅ Cache de resultados

**Estimación errores potenciales:** 8-12

---

#### 8. **Gym Management Module** (4 archivos)
**Archivos:**
- `app/services/gym.py` / `async_gym.py`
- `app/services/gym_revenue.py` / `async_gym_revenue.py`
- `app/services/module.py` / `async_module.py`

**Puntos a revisar:**
- ✅ Creación/actualización de gyms
- ✅ Gestión de módulos activados
- ✅ Revenue tracking
- ✅ Multi-tenant validation

**Estimación errores potenciales:** 6-10

---

### 🟢 PRIORIDAD BAJA (Módulos auxiliares)

#### 9. **Notifications Module** (3 archivos)
**Archivos:**
- `app/services/notification_service.py` / `async_notification_service.py`
- `app/services/sqs_notification_service.py` / `async_sqs_notification_service.py`

**Puntos a revisar:**
- ✅ OneSignal integration
- ✅ Push notifications
- ✅ Segmentación por roles
- ✅ SQS queue processing

**Estimación errores potenciales:** 5-8

---

#### 10. **Survey Module** (2 archivos)
**Archivos:**
- `app/services/survey.py` / `async_survey.py`

**Puntos a revisar:**
- ✅ Creación de encuestas
- ✅ Respuestas
- ✅ Estadísticas

**Estimación errores potenciales:** 4-6

---

#### 11. **Trainer Management Module** (4 archivos)
**Archivos:**
- `app/services/trainer_member.py` / `async_trainer_member.py`
- `app/services/trainer_setup.py` / `async_trainer_setup.py`

**Puntos a revisar:**
- ✅ Asignación de miembros
- ✅ Permisos de trainers
- ✅ Setup inicial

**Estimación errores potenciales:** 5-8

---

#### 12. **Storage & Media Module** (3 archivos)
**Archivos:**
- `app/services/storage.py` / `async_storage.py`
- `app/services/media_service.py` / `async_media_service.py`

**Puntos a revisar:**
- ✅ Supabase integration
- ✅ File uploads
- ✅ Image processing
- ✅ Thumbnails

**Estimación errores potenciales:** 4-6

---

#### 13. **Queue & SQS Module** (3 archivos)
**Archivos:**
- `app/services/aws_sqs.py` / `async_aws_sqs.py`
- `app/services/queue_services.py` / `async_queue_services.py`

**Puntos a revisar:**
- ✅ Queue management
- ✅ Dead letter queues
- ✅ Message processing

**Estimación errores potenciales:** 4-6

---

#### 14. **Activity Feed Module** (2 archivos)
**Archivos:**
- `app/services/activity_feed_service.py` / `async_activity_feed_service.py`
- `app/services/activity_aggregator.py` / `async_activity_aggregator.py`

**Status:** ✅ Ya corregido dependency injection
**Puntos a revisar:**
- ✅ Redis operations
- ✅ Aggregations
- ✅ Rankings

**Estimación errores potenciales:** 2-4 (ya corregidos 2)

---

#### 15. **Feed Ranking Module** (2 archivos)
**Archivos:**
- `app/services/feed_ranking_service.py` / `async_feed_ranking_service.py`

**Puntos a revisar:**
- ✅ Algoritmo de ranking
- ✅ Batch calculations
- ✅ Affinity scores

**Estimación errores potenciales:** 5-8

---

#### 16. **Auth0 Management Module** (3 archivos)
**Archivos:**
- `app/services/auth0_mgmt.py` / `async_auth0_mgmt.py`
- `app/services/auth0_sync.py` / `async_auth0_sync.py`

**Puntos a revisar:**
- ✅ User management
- ✅ Roles sync
- ✅ Email updates
- ✅ Rate limiting

**Estimación errores potenciales:** 6-10

---

#### 17. **User Stats Module** (2 archivos)
**Archivos:**
- `app/services/user_stats.py` / `async_user_stats.py`

**Puntos a revisar:**
- ✅ Attendance stats
- ✅ Progress tracking
- ✅ Analytics

**Estimación errores potenciales:** 8-12

---

#### 18. **Cache Service** (2 archivos)
**Archivos:**
- `app/services/cache_service.py`
- `app/services/async_cache_service.py`

**Puntos a revisar:**
- ✅ Redis operations
- ✅ Serialization
- ✅ TTL management

**Estimación errores potenciales:** 3-5

---

#### 19. **Health Service** (1 archivo)
**Archivos:**
- `app/services/health.py`

**Puntos a revisar:**
- ✅ Health checks
- ✅ DB connection tests

**Estimación errores potenciales:** 1-2

---

## Patrones de Errores Comunes a Buscar

### 1. **NameError: 'select' is not defined**
```python
# ❌ MAL
result = await db.execute(select(Model).where(...))

# ✅ BIEN
from sqlalchemy import select
result = await db.execute(select(Model).where(...))
```

### 2. **AttributeError: 'AsyncSession' object has no attribute 'get'**
```python
# ❌ MAL
user = db.get(User, user_id)

# ✅ BIEN
result = await db.execute(select(User).where(User.id == user_id))
user = result.scalar_one_or_none()
```

### 3. **Coroutine no awaited**
```python
# ❌ MAL
result = db.execute(query)
db.commit()

# ✅ BIEN
result = await db.execute(query)
await db.commit()
```

### 4. **Async method con Session en vez de AsyncSession**
```python
# ❌ MAL
async def my_method(self, db: Session):
    result = await db.execute(...)

# ✅ BIEN
async def my_method(self, db: AsyncSession):
    result = await db.execute(...)
```

### 5. **Timezone-aware vs naive datetime comparison**
```python
# ❌ MAL
is_expired = user_gym.membership_expires_at < datetime.now(timezone.utc)

# ✅ BIEN
expires_at = user_gym.membership_expires_at
if expires_at.tzinfo is None:
    expires_at = expires_at.replace(tzinfo=timezone.utc)
is_expired = expires_at < datetime.now(timezone.utc)
```

### 6. **Transaction no committed**
```python
# ❌ MAL
await repository.delete(item)
await db.flush()
# Missing commit!

# ✅ BIEN
await repository.delete(item)
await db.commit()
```

### 7. **Using asyncio.run() inside async function**
```python
# ❌ MAL
async def my_method():
    result = asyncio.run(async_function())

# ✅ BIEN
async def my_method():
    result = await async_function()
```

---

## Metodología de Revisión por Agente

Cada agente especializado deberá:

1. **Scan de imports**
   - Verificar que todos los archivos async importen `AsyncSession`
   - Verificar import de `select` donde se use
   - Verificar imports de timezone para comparaciones de fechas

2. **Análisis de signatures**
   - Identificar todos los métodos `async def`
   - Verificar que reciban `db: AsyncSession` no `db: Session`
   - Identificar métodos que deberían ser async pero son sync

3. **Scan de operaciones DB**
   - Buscar todos los `db.execute()` sin await
   - Buscar todos los `db.commit()` sin await
   - Buscar todos los `db.rollback()` sin await
   - Buscar todos los `db.refresh()` sin await
   - Buscar todos los `db.delete()` sin await
   - Buscar todos los `db.get(Model, id)` (no existe en AsyncSession)

4. **Análisis de transacciones**
   - Verificar que después de `db.flush()` haya `db.commit()`
   - Verificar que bloques try/except tengan rollback apropiados
   - Verificar que updates/deletes sean seguidos de commit

5. **Verificación de llamadas async**
   - Buscar llamadas a métodos async sin await
   - Buscar uso de `asyncio.run()` dentro de funciones async
   - Verificar que se usen versiones async de métodos de repositorio

6. **Report detallado**
   - Listar TODOS los errores encontrados con ubicación exacta
   - Categorizar por tipo de error
   - Sugerir correcciones específicas
   - Estimar severidad (crítico, alto, medio, bajo)

---

## Estimación Total de Errores

| Prioridad | Módulos | Errores Estimados |
|-----------|---------|-------------------|
| 🔴 Alta   | 5       | 40-62             |
| 🟡 Media  | 4       | 31-48             |
| 🟢 Baja   | 10      | 47-75             |
| **TOTAL** | **19**  | **118-185**       |

---

## Orden de Ejecución Recomendado

### Fase 1 - Críticos (Paralelo)
1. Posts & Media
2. Stories
3. Events & Attendance
4. Schedule & Classes
5. Chat

### Fase 2 - Importantes (Paralelo)
6. Billing & Stripe
7. Nutrition
8. Gym Management

### Fase 3 - Auxiliares (Paralelo)
9-19. Todos los demás módulos

---

## Métricas de Éxito

- ✅ 0 errores de `NameError: 'select' is not defined`
- ✅ 0 errores de `AttributeError: 'AsyncSession' has no attribute 'get'`
- ✅ 0 coroutines no awaited
- ✅ 0 métodos async con `Session` en vez de `AsyncSession`
- ✅ 0 timezone comparison errors
- ✅ 100% de transacciones con commit apropiado
- ✅ 0 uso de `asyncio.run()` en funciones async

---

## Notas Finales

- **Priorizar módulos en producción activa**
- **Ejecutar agentes en paralelo cuando sea posible**
- **Cada agente debe generar un reporte markdown detallado**
- **Agrupar correcciones por commit temático**
- **Testing después de cada batch de correcciones**
