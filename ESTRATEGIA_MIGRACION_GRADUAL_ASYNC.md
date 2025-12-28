# Estrategia de Migración Gradual Async - Endpoint por Endpoint

**Fecha:** 2025-12-08
**Autor:** Claude Code
**Contexto:** Rollback de migración masiva con avalancha de errores
**Commit base:** 0951faf (main antes de migración)

---

## 📋 RESUMEN EJECUTIVO

### Problema Identificado

La migración masiva en la rama `feature/async-phase2-repositories-week1` intentó migrar **todos los endpoints y servicios a async de golpe**, resultando en:

- **158 archivos modificados** (~53,000 líneas agregadas)
- **312 endpoints afectados** en 36 archivos
- **Múltiples errores críticos** documentados en 7 auditorías
- **Mezcla async/sync** causando bugs difíciles de debuggear
- **Problemas de performance** (redis.keys(), queries bloqueantes)

### Lecciones Aprendidas

1. ❌ **Migrar todo de golpe** causa cascada de errores interdependientes
2. ❌ **No priorizar por criticidad** genera bugs en endpoints clave
3. ❌ **Falta de testing incremental** hace difícil identificar regresiones
4. ❌ **Archivos sync/async duplicados** crean confusión y bugs

### Nueva Estrategia: Migración Incremental

✅ **Endpoint por endpoint** (o módulo pequeño completo)
✅ **Priorizar por tráfico y criticidad**
✅ **Testing exhaustivo** antes de siguiente migración
✅ **Evitar duplicación** - migrar completamente o no migrar

---

## 🎯 CRITERIOS DE PRIORIZACIÓN

### Tier 1: CRÍTICOS (Migrar primero)
- **Alta frecuencia de uso** (checkins, auth, usuarios)
- **Operaciones de lectura** (más fáciles de migrar)
- **Sin dependencias complejas**
- **Impacto en UX/rendimiento**

### Tier 2: IMPORTANTES (Migrar después)
- **Frecuencia media** (eventos, clases, posts)
- **Mix lectura/escritura**
- **Algunas dependencias externas**
- **Funcionalidades core del gimnasio**

### Tier 3: SECUNDARIOS (Migrar al final)
- **Baja frecuencia** (admin, configuración)
- **Operaciones complejas** (facturación, webhooks)
- **Muchas dependencias externas** (Stripe, Auth0)
- **Funcionalidades auxiliares**

---

## 📊 ANÁLISIS DE ENDPOINTS POR PRIORIDAD

### 🔴 TIER 1: ENDPOINTS CRÍTICOS (10 endpoints)

#### 1. **Attendance (Check-ins)**
**Archivo:** `app/api/v1/endpoints/attendance.py`
**Endpoints:** `POST /attendance/checkin`
**Frecuencia:** **MUY ALTA** (cada vez que un usuario entra al gym)
**Complejidad:** 🟢 **BAJA**
**Servicios:** `attendance_service`, `user_service`

**Por qué primero:**
- Es el endpoint más usado diariamente
- Operación simple de escritura
- Mejora inmediata de performance
- Bajo riesgo de bugs

**Estimación:** 2-3 horas
**Testing:** Simulación de múltiples checkins concurrentes

---

#### 2. **User Info (Perfil de Usuario)**
**Archivo:** `app/api/v1/endpoints/users.py`
**Endpoints:**
- `GET /users/me` - Perfil actual
- `GET /users/{user_id}` - Ver perfil
- `PATCH /users/{user_id}` - Actualizar perfil

**Frecuencia:** **MUY ALTA** (cada apertura de app)
**Complejidad:** 🟢 **BAJA**
**Servicios:** `user_service`

**Por qué primero:**
- Carga con cada sesión de usuario
- Principalmente lectura (GET)
- Caché Redis fácil de implementar
- Crítico para UX

**Estimación:** 3-4 horas
**Testing:** Verificar caché, actualización de perfil

---

#### 3. **User Dashboard (Stats de Usuario)**
**Archivo:** `app/api/v1/endpoints/user_dashboard.py`
**Endpoints:**
- `GET /dashboard/summary` - Resumen de stats
- `GET /dashboard/stats` - Stats detalladas

**Frecuencia:** **ALTA** (pantalla principal de app)
**Complejidad:** 🟡 **MEDIA** (agregaciones)
**Servicios:** `async_user_stats` (ya existe pero con bugs)

**Por qué primero:**
- Primera pantalla que ven usuarios
- Beneficio inmediato con queries async
- Ya existe versión async parcial

**Estimación:** 4-5 horas (corregir async_user_stats)
**Testing:** Verificar cálculos de stats, caché

---

#### 4. **Schedule - Sessions (Horario de Clases)**
**Archivo:** `app/api/v1/endpoints/schedule/sessions.py`
**Endpoints:**
- `GET /schedule/sessions` - Listar clases
- `GET /schedule/sessions/today` - Clases de hoy
- `GET /schedule/sessions/{id}` - Detalle de clase

**Frecuencia:** **MUY ALTA** (usuarios revisan horarios constantemente)
**Complejidad:** 🟢 **BAJA-MEDIA**
**Servicios:** `async_schedule` (ya migrado)

**Por qué primero:**
- Alto tráfico de lectura
- Ya tiene repositorio async
- Mejora UX de navegación

**Estimación:** 3 horas
**Testing:** Filtros, paginación, caché de horarios

---

#### 5. **Schedule - Participation (Reservas de Clases)**
**Archivo:** `app/api/v1/endpoints/schedule/participation.py`
**Endpoints:**
- `POST /schedule/participation` - Reservar clase
- `DELETE /schedule/participation/{id}` - Cancelar reserva
- `GET /schedule/participation/user/{user_id}` - Ver reservas

**Frecuencia:** **ALTA** (reservas diarias)
**Complejidad:** 🟡 **MEDIA** (validación capacidad)
**Servicios:** `async_schedule`

**Por qué primero:**
- Operación crítica del negocio
- Beneficio con async (múltiples reservas concurrentes)
- Ya tiene servicio async

**Estimación:** 4-5 horas (validaciones complejas)
**Testing:** Capacidad máxima, cancelaciones, conflictos

---

#### 6. **Events - List & Participation**
**Archivo:** `app/api/v1/endpoints/events.py`
**Endpoints:**
- `GET /events` - Listar eventos
- `GET /events/{id}` - Detalle evento
- `POST /events/{id}/participate` - Participar

**Frecuencia:** **ALTA** (eventos semanales/mensuales)
**Complejidad:** 🟡 **MEDIA**
**Servicios:** `async_event` (ya existe)

**Por qué primero:**
- Alto engagement de usuarios
- Mix lectura/escritura
- Ya tiene repositorio async

**Estimación:** 4 horas
**Testing:** Participación, notificaciones, caché

---

#### 7. **Activity Feed (Feed de Actividades)**
**Archivo:** `app/api/v1/endpoints/activity_feed.py`
**Endpoints:**
- `GET /activity-feed/realtime` - Feed en tiempo real
- `GET /activity-feed/summary` - Resumen de actividades

**Frecuencia:** **ALTA** (gamificación, engagement)
**Complejidad:** 🟡 **MEDIA** (Redis intensivo)
**Servicios:** `async_activity_feed_service` (migrado con bugs)

**Por qué tier 1:**
- Alto tráfico de lectura
- Beneficio inmediato con async Redis
- **YA MIGRADO pero con bugs críticos (redis.keys())**

**Estimación:** 3 horas (solo arreglar bugs existentes)
**Testing:** Performance con muchas keys en Redis

**NOTA:** Ver `ACTIVITY_FEED_ASYNC_AUDIT.md` para errores específicos

---

#### 8. **Auth - Login & Token Refresh**
**Archivo:** `app/api/v1/endpoints/auth/tokens.py`
**Endpoints:**
- `POST /auth/token` - Login
- `POST /auth/refresh` - Refresh token

**Frecuencia:** **MUY ALTA** (cada sesión)
**Complejidad:** 🟢 **BAJA** (Auth0 ya maneja async)
**Servicios:** `auth0_service`

**Por qué primero:**
- Crítico para acceso a la app
- Auth0 SDK ya soporta async
- Mejora latencia de login

**Estimación:** 2-3 horas
**Testing:** Login, refresh, expiración tokens

---

#### 9. **Context (Multi-tenancy Info)**
**Archivo:** `app/api/v1/endpoints/context.py`
**Endpoints:**
- `GET /context/gym` - Info del gym actual
- `GET /context/user` - Info del usuario actual

**Frecuencia:** **ALTA** (cada carga de app)
**Complejidad:** 🟢 **BAJA**
**Servicios:** `gym_service`, `user_service`

**Por qué primero:**
- Carga al iniciar app
- Muy cacheable
- Simple de migrar

**Estimación:** 2 horas
**Testing:** Multi-tenancy, caché

---

#### 10. **Gyms - Basic Info**
**Archivo:** `app/api/v1/endpoints/gyms.py`
**Endpoints:**
- `GET /gyms/{id}` - Info del gym
- `GET /gyms/{id}/stats` - Stats del gym

**Frecuencia:** **MEDIA-ALTA** (admin dashboard)
**Complejidad:** 🟢 **BAJA-MEDIA**
**Servicios:** `async_gym` (ya existe)

**Por qué tier 1:**
- Dashboard de admin
- Ya migrado parcialmente
- Bajo riesgo

**Estimación:** 3 horas
**Testing:** Stats, permisos admin

---

### 🟡 TIER 2: ENDPOINTS IMPORTANTES (12 endpoints)

#### 11. **Posts (Social Feed)**
**Archivo:** `app/api/v1/endpoints/posts.py`
**Complejidad:** 🟡 **MEDIA** (interacciones, media)
**Estimación:** 5-6 horas
**Servicios:** `async_post_service` (ya existe)

#### 12. **Stories**
**Archivo:** `app/api/v1/endpoints/stories.py`
**Complejidad:** 🟡 **MEDIA** (media, expiración)
**Estimación:** 4 horas
**Servicios:** `async_story_service` (ya existe)

#### 13. **Chat (Mensajería)**
**Archivo:** `app/api/v1/endpoints/chat.py`
**Complejidad:** 🔴 **ALTA** (Stream Chat SDK, webhooks)
**Estimación:** 8-10 horas
**Servicios:** `async_chat` (ya existe pero complejo)

**NOTA:** Stream Chat SDK no es totalmente async - wrapper cuidadoso

#### 14. **Notifications**
**Archivo:** `app/api/v1/endpoints/notification.py`
**Complejidad:** 🟡 **MEDIA** (OneSignal, segmentación)
**Estimación:** 4 horas
**Servicios:** `async_notification_service` (ya existe)

#### 15. **Surveys**
**Archivo:** `app/api/v1/endpoints/surveys.py`
**Complejidad:** 🟡 **MEDIA** (respuestas, stats)
**Estimación:** 5 horas
**Servicios:** `async_survey` (migrado con bugs datetime.utcnow)

#### 16. **Trainer-Member (Relaciones)**
**Archivo:** `app/api/v1/endpoints/trainer_member.py`
**Complejidad:** 🟡 **MEDIA**
**Estimación:** 4 horas
**Servicios:** `async_trainer_member` (ya migrado)

#### 17. **Schedule - Classes (Gestión de Clases)**
**Archivo:** `app/api/v1/endpoints/schedule/classes.py`
**Complejidad:** 🟡 **MEDIA** (CRUD completo)
**Estimación:** 5 horas

#### 18. **Schedule - Categories**
**Archivo:** `app/api/v1/endpoints/schedule/categories.py`
**Complejidad:** 🟢 **BAJA**
**Estimación:** 2 horas

#### 19. **Schedule - Gym Hours**
**Archivo:** `app/api/v1/endpoints/schedule/gym_hours.py`
**Complejidad:** 🟢 **BAJA-MEDIA**
**Estimación:** 3 horas

#### 20. **Schedule - Special Days**
**Archivo:** `app/api/v1/endpoints/schedule/special_days.py`
**Complejidad:** 🟢 **BAJA-MEDIA**
**Estimación:** 3 horas

#### 21. **Nutrition**
**Archivo:** `app/api/v1/endpoints/nutrition.py`
**Complejidad:** 🔴 **ALTA** (OpenAI, análisis de imágenes)
**Estimación:** 6-8 horas
**Servicios:** `async_nutrition_ai` (ya existe)

**NOTA:** OpenAI SDK no es totalmente async

#### 22. **Modules (Configuración)**
**Archivo:** `app/api/v1/endpoints/modules.py`
**Complejidad:** 🟢 **BAJA**
**Estimación:** 2 horas

---

### 🟢 TIER 3: ENDPOINTS SECUNDARIOS (14 endpoints)

#### 23. **Memberships (Gestión de Membresías)**
**Archivo:** `app/api/v1/endpoints/memberships.py`
**Complejidad:** 🔴 **ALTA** (Stripe, facturación)
**Estimación:** 8-10 horas
**Servicios:** `async_membership` (ya existe pero complejo)

**NOTA:** Stripe SDK es sync - usar con cuidado

#### 24. **Stripe Connect**
**Archivo:** `app/api/v1/endpoints/stripe_connect.py`
**Complejidad:** 🔴 **MUY ALTA** (Stripe Connect API)
**Estimación:** 10-12 horas
**Servicios:** `async_stripe_connect_service` (ya existe)

**ADVERTENCIA:** Stripe sync puede bloquear event loop

#### 25. **Payment Pages**
**Archivo:** `app/api/v1/endpoints/payment_pages.py`
**Complejidad:** 🟡 **MEDIA**
**Estimación:** 4 horas

#### 26. **Admin - Trainer Registration**
**Archivo:** `app/api/v1/endpoints/auth/trainer_registration.py`
**Complejidad:** 🔴 **ALTA** (Auth0, Stripe, multi-paso)
**Estimación:** 6-8 horas

**NOTA:** Ver `TRAINER_MANAGEMENT_ASYNC_AUDIT.md` - **2 errores críticos ya identificados**

#### 27. **Admin - Admin Panel**
**Archivo:** `app/api/v1/endpoints/auth/admin.py`
**Complejidad:** 🟡 **MEDIA**
**Estimación:** 4 horas

#### 28. **Admin Diagnostics**
**Archivo:** `app/api/v1/endpoints/admin_diagnostics.py`
**Complejidad:** 🟡 **MEDIA** (stats, health checks)
**Estimación:** 4 horas

#### 29. **Webhooks - Stream Chat**
**Archivo:** `app/api/v1/endpoints/webhooks/stream_webhooks.py`
**Complejidad:** 🔴 **ALTA** (validación, autorización)
**Estimación:** 6 horas

**NOTA:** Crítico para seguridad del chat

#### 30. **Webhooks - Stripe**
**Archivo:** `app/api/v1/endpoints/webhooks/stripe_webhooks.py` (si existe)
**Complejidad:** 🔴 **MUY ALTA** (eventos, idempotencia)
**Estimación:** 8-10 horas

**ADVERTENCIA:** Errores aquí afectan facturación

#### 31-36. **Otros Endpoints Admin/Worker**
- `worker.py` - Background jobs
- Otros endpoints de configuración

---

## 📅 PLAN DE MIGRACIÓN INCREMENTAL

### Fase 1: Foundation (Semana 1) - 5 endpoints
**Objetivo:** Migrar endpoints de lectura más usados + infraestructura base

1. **DÍA 1-2:** User Info (`users.py` - GET endpoints)
   - Migrar solo lecturas primero
   - Setup async user repository
   - Testing exhaustivo de caché

2. **DÍA 2-3:** Context (`context.py`)
   - Info de gym/user
   - Caché agresivo

3. **DÍA 3-4:** Auth Tokens (`auth/tokens.py`)
   - Login/refresh async
   - Critical path optimizado

4. **DÍA 4-5:** Attendance Check-in (`attendance.py`)
   - Endpoint más usado
   - Testing de concurrencia

5. **DÍA 5:** User Dashboard (`user_dashboard.py`)
   - Corregir async_user_stats existente
   - Stats async con caché

**Entregables:** 5 endpoints migrados, 100% testeados
**Métrica de éxito:** Latencia reducida >30%, sin errores en producción

---

### Fase 2: Core Funcionalidades (Semana 2-3) - 8 endpoints
**Objetivo:** Clases, eventos, actividad

1. **DÍA 6-7:** Schedule Sessions (`schedule/sessions.py`)
2. **DÍA 8-9:** Schedule Participation (`schedule/participation.py`)
3. **DÍA 10-11:** Events List & Participation (`events.py`)
4. **DÍA 12-13:** Activity Feed (`activity_feed.py` - arreglar bugs)
5. **DÍA 14-15:** Gyms Basic Info (`gyms.py`)

**Entregables:** 13 endpoints totales (acumulado)
**Métrica de éxito:** 40% endpoints críticos migrados

---

### Fase 3: Social & Engagement (Semana 4) - 6 endpoints
**Objetivo:** Posts, stories, notificaciones

1. **DÍA 16-17:** Posts (`posts.py`)
2. **DÍA 18-19:** Stories (`stories.py`)
3. **DÍA 20-21:** Notifications (`notification.py`)
4. **DÍA 22:** Modules (`modules.py`)

**Entregables:** 19 endpoints totales
**Métrica de éxito:** 60% endpoints migrados

---

### Fase 4: Schedule Completo (Semana 5) - 4 endpoints

1. **DÍA 23-24:** Schedule Classes (`schedule/classes.py`)
2. **DÍA 25:** Schedule Categories (`schedule/categories.py`)
3. **DÍA 26:** Schedule Gym Hours (`schedule/gym_hours.py`)
4. **DÍA 27:** Schedule Special Days (`schedule/special_days.py`)

**Entregables:** 23 endpoints totales
**Métrica de éxitud:** Módulo Schedule 100% async

---

### Fase 5: Funcionalidades Complejas (Semana 6-7) - 5 endpoints
**ADVERTENCIA:** Estas migraciones requieren cuidado extra

1. **DÍA 28-30:** Chat (`chat.py`)
   - Stream Chat wrapper async
   - Testing intensivo

2. **DÍA 31-32:** Surveys (`surveys.py`)
   - Corregir bugs datetime.utcnow

3. **DÍA 33-34:** Trainer-Member (`trainer_member.py`)
   - Ya migrado, solo testing

4. **DÍA 35-37:** Nutrition (`nutrition.py`)
   - OpenAI async wrapper
   - Testing con imágenes

**Entregables:** 28 endpoints totales
**Métrica de éxito:** 80% endpoints migrados

---

### Fase 6: Admin & Billing (Semana 8-10) - Últimos endpoints
**ADVERTENCIA:** Alta complejidad, Stripe sync

1. **Semana 8:** Memberships (`memberships.py`)
2. **Semana 9:** Stripe Connect (`stripe_connect.py`)
3. **Semana 9:** Payment Pages, Trainer Registration
4. **Semana 10:** Webhooks (Stream, Stripe)
5. **Semana 10:** Admin endpoints, diagnostics

**Entregables:** 36 endpoints totales (100%)
**Métrica de éxito:** Migración completa, sin deuda técnica

---

## ✅ PROCESO DE MIGRACIÓN POR ENDPOINT

### Checklist para Cada Endpoint

#### 1. Preparación (30 min)
```bash
# Crear rama específica
git checkout main
git pull origin main
git checkout -b async/endpoint-{nombre}-{fecha}

# Leer código actual
# Identificar servicios usados
# Verificar si ya existe versión async del servicio
```

#### 2. Análisis de Dependencias (1 hora)
```python
# Documentar en markdown:
# - Servicios llamados
# - Repositorios usados
# - APIs externas (Stripe, Auth0, etc.)
# - Queries DB actuales
# - Uso de caché Redis
```

#### 3. Migración (2-8 horas según complejidad)
```python
# A. Cambiar imports
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.async_user import async_user_repository

# B. Cambiar signature del endpoint
@router.get("/users/me")
async def get_current_user_info(  # async def
    db: AsyncSession = Depends(get_async_db),  # AsyncSession
    ...
):

# C. Cambiar llamadas a servicios
user = await user_service.get_user(db, user_id)  # await

# D. Migrar queries si es necesario
result = await db.execute(select(User).where(User.id == user_id))
user = result.scalar_one_or_none()

# E. Redis async
await redis.set(key, value)  # await
value = await redis.get(key)  # await
```

#### 4. Testing (2-3 horas)
```bash
# Tests unitarios
pytest tests/api/test_{endpoint}.py -v

# Tests de integración
pytest tests/integration/test_{módulo}.py -v

# Load testing (opcional para críticos)
locust -f tests/load/test_{endpoint}_load.py

# Manual testing
curl -X GET http://localhost:8000/api/v1/{endpoint}
```

#### 5. Code Review & Merge (1 hora)
```bash
# Self-review
git diff main...HEAD

# Verificar checklist:
# - [ ] Sin db.query() (solo select() con await)
# - [ ] Sin Session sync
# - [ ] Todos los servicios son async
# - [ ] Redis operations con await
# - [ ] No hay datetime.utcnow() (usar datetime.now(timezone.utc))
# - [ ] Tests pasan 100%
# - [ ] Sin imports de servicios sync

# Merge a main
git checkout main
git merge --no-ff async/endpoint-{nombre}-{fecha}
git push origin main
```

#### 6. Deploy & Monitor (1-2 días)
```bash
# Deploy a staging
git push staging main

# Monitor errors
tail -f logs/app.log | grep ERROR

# Monitor performance
# - Latencia P50, P95, P99
# - Error rate
# - Throughput

# Si todo OK, deploy a prod
git push production main
```

---

## 🚨 ERRORES COMUNES A EVITAR

### 1. Mixing Sync/Async Services
```python
# ❌ MAL
from app.services.user import user_service  # sync
async def my_endpoint(db: AsyncSession):
    user = await user_service.get_user(db, id)  # ERROR!

# ✅ BIEN
from app.services.async_user import async_user_service
async def my_endpoint(db: AsyncSession):
    user = await async_user_service.get_user(db, id)
```

### 2. Olvidar await en Operaciones Async
```python
# ❌ MAL
user = user_service.get_user(db, id)  # Devuelve coroutine sin ejecutar

# ✅ BIEN
user = await user_service.get_user(db, id)
```

### 3. Usar db.query() con AsyncSession
```python
# ❌ MAL
users = db.query(User).filter(User.gym_id == gym_id).all()

# ✅ BIEN
result = await db.execute(select(User).where(User.gym_id == gym_id))
users = result.scalars().all()
```

### 4. Redis Operations sin await
```python
# ❌ MAL
redis.set(key, value)  # No hace nada
data = redis.get(key)  # Devuelve coroutine

# ✅ BIEN
await redis.set(key, value)
data = await redis.get(key)
```

### 5. Usar redis.keys() (bloqueante)
```python
# ❌ MAL - Bloquea todo Redis
keys = await redis.keys("gym:*:users:*")

# ✅ BIEN - Usar SCAN
async def scan_keys(pattern: str):
    keys = []
    cursor = 0
    while True:
        cursor, partial = await redis.scan(cursor, match=pattern, count=100)
        keys.extend(partial)
        if cursor == 0:
            break
    return keys
```

### 6. datetime.utcnow() en lugar de timezone-aware
```python
# ❌ MAL - Deprecated
created_at = datetime.utcnow()

# ✅ BIEN
from datetime import datetime, timezone
created_at = datetime.now(timezone.utc)
```

### 7. No Manejar Excepciones Async
```python
# ❌ MAL
try:
    user = await user_service.get_user(db, id)
except Exception:  # Muy genérico
    pass

# ✅ BIEN
from sqlalchemy.exc import NoResultFound
try:
    user = await user_service.get_user(db, id)
except NoResultFound:
    raise HTTPException(status_code=404, detail="User not found")
```

---

## 📊 MÉTRICAS DE ÉXITO

### Por Endpoint Migrado
- ✅ **Latencia P95:** Reducción >20%
- ✅ **Error rate:** <0.1% (mismo que antes)
- ✅ **Test coverage:** >80%
- ✅ **Code review:** Aprobado por 2+ personas

### Por Fase Completada
- ✅ **Endpoints sin regresiones:** 100%
- ✅ **Performance mejorado:** >30% en promedio
- ✅ **Deuda técnica:** 0 (no dejar archivos duplicados)

### Global (Al Completar Migración)
- ✅ **100% endpoints async**
- ✅ **0 archivos sync legacy**
- ✅ **Performance general:** >40% mejora
- ✅ **Throughput:** >50% aumento en capacidad

---

## 🛠️ HERRAMIENTAS Y SCRIPTS

### Script de Verificación Pre-Merge
```bash
#!/bin/bash
# scripts/verify_async_migration.sh

echo "🔍 Verificando migración async..."

# 1. Verificar no hay db.query()
echo "Verificando db.query()..."
if grep -r "db.query(" app/api/v1/endpoints/ 2>/dev/null; then
    echo "❌ ERROR: Encontrado db.query() sync"
    exit 1
fi

# 2. Verificar no hay Session sync
echo "Verificando Session sync..."
if grep -r "Session = Depends" app/api/v1/endpoints/ 2>/dev/null; then
    echo "❌ ERROR: Encontrado Session sync"
    exit 1
fi

# 3. Verificar no hay datetime.utcnow()
echo "Verificando datetime.utcnow()..."
if grep -r "datetime.utcnow()" app/ 2>/dev/null; then
    echo "⚠️  WARNING: Encontrado datetime.utcnow() deprecated"
fi

# 4. Verificar tests pasan
echo "Ejecutando tests..."
pytest tests/ -v --tb=short || exit 1

echo "✅ Verificación completa - Todo OK"
```

### Script de Detección de Archivos Duplicados
```bash
#!/bin/bash
# scripts/find_duplicate_services.sh

echo "🔍 Buscando servicios duplicados sync/async..."

for file in app/services/async_*.py; do
    base=$(basename "$file" | sed 's/async_//')
    sync_file="app/services/$base"

    if [ -f "$sync_file" ]; then
        echo "⚠️  DUPLICADO: $sync_file <-> $file"
    fi
done
```

---

## 📚 RECURSOS Y REFERENCIAS

### Documentación de Errores Existentes
- `ACTIVITY_FEED_ASYNC_AUDIT.md` - 6 errores críticos (redis.keys, mezcla sync/async)
- `TRAINER_MANAGEMENT_ASYNC_AUDIT.md` - 2 errores críticos (imports incorrectos)
- `AUDIT_USER_STATS_MODULE.md` - 3 errores críticos (await faltantes)
- `AUDIT_AUTH0_MANAGEMENT.md` - Problemas con Auth0 async
- `FEED_RANKING_ASYNC_AUDIT.md` - Performance issues
- `HEALTH_SERVICE_ASYNC_AUDIT.md` - Problemas de queries
- `AUDIT_CACHE_SERVICE.md` - Redis optimization issues

### SQLAlchemy 2.0 Async Patterns
```python
# Select
result = await db.execute(select(User).where(User.id == id))
user = result.scalar_one_or_none()

# Insert
db.add(new_user)
await db.flush()  # Para obtener ID antes de commit
await db.commit()

# Update
stmt = update(User).where(User.id == id).values(name="New Name")
await db.execute(stmt)
await db.commit()

# Delete
stmt = delete(User).where(User.id == id)
await db.execute(stmt)
await db.commit()

# Joins
stmt = select(User).join(UserGym).where(UserGym.gym_id == gym_id)
result = await db.execute(stmt)
users = result.scalars().all()
```

### Redis Async Best Practices
```python
# Pipeline para múltiples ops
pipe = redis.pipeline()
pipe.set("key1", "value1")
pipe.set("key2", "value2")
pipe.incr("counter")
await pipe.execute()  # 1 round-trip en lugar de 3

# Evitar keys() - usar SCAN
async for key in redis.scan_iter(match="pattern:*", count=100):
    value = await redis.get(key)

# Usar estructuras de datos Redis
await redis.hset("user:1", mapping={"name": "John", "age": 30})
user_data = await redis.hgetall("user:1")
```

---

## 🎯 PRÓXIMOS PASOS INMEDIATOS

### Esta Semana (Semana 1)
1. ✅ **HOY:** Revisar y aprobar esta estrategia
2. ✅ **HOY:** Crear issue/ticket para cada endpoint Tier 1
3. ✅ **MAÑANA:** Empezar con `users.py` (GET endpoints)
4. ✅ **DÍA 3-4:** Migrar `context.py` y `auth/tokens.py`
5. ✅ **DÍA 5:** Migrar `attendance.py`

### Preparación
```bash
# 1. Limpiar estado actual
git checkout main
git branch -D feature/async-phase2-repositories-week1  # Eliminar rama fallida

# 2. Crear estructura de tracking
mkdir -p docs/async-migration/
touch docs/async-migration/progress.md

# 3. Setup scripts de verificación
chmod +x scripts/verify_async_migration.sh
chmod +x scripts/find_duplicate_services.sh
```

---

## 📞 SOPORTE Y PREGUNTAS

### Problemas Comunes
- **"¿Qué hago si el servicio async ya existe pero tiene bugs?"**
  → Arreglar bugs primero antes de usarlo en endpoint. Ver auditorías.

- **"¿Migrar endpoint con API externa sync (Stripe, OpenAI)?"**
  → Usar `asyncio.to_thread()` o dejar para Tier 3.

- **"¿Qué hacer con archivos sync duplicados?"**
  → NO importarlos en endpoints async. Deprecar después.

### Contacto
- **Documentación:** Ver `CLAUDE.md` para arquitectura general
- **Auditorías:** Ver archivos `*_AUDIT.md` para errores conocidos
- **Testing:** Ver `TESTING_GUIDE.md` (si existe)

---

## 📝 CONCLUSIÓN

Esta estrategia de migración gradual permite:

1. ✅ **Reducir riesgo** - Un endpoint a la vez
2. ✅ **Testing exhaustivo** - Cada migración validada
3. ✅ **Rollback fácil** - Si falla un endpoint, no afecta el resto
4. ✅ **Priorizar valor** - Endpoints más usados primero
5. ✅ **Aprender incremental** - Ajustar proceso según feedback

**Estimación total:** 8-10 semanas para migración completa y segura
**Beneficio esperado:** >40% mejora en latencia, >50% en throughput

---

**Autor:** Claude Code
**Última actualización:** 2025-12-08
**Versión:** 1.0
**Estado:** ✅ Listo para implementar
