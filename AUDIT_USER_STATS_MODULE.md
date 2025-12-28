# Auditoría Async/Sync - User Stats Module (Prioridad Baja #17)

**Fecha:** 2025-12-07
**Auditor:** Claude Code
**Módulo:** User Stats
**Archivos Auditados:**
- `app/services/user_stats.py`
- `app/services/async_user_stats.py`
- `app/services/chat_analytics.py` (dependencia)
- `app/services/user.py` (dependencia)

---

## Resumen Ejecutivo

### Estado General: ⚠️ ERRORES CRÍTICOS ENCONTRADOS

**Problemas Críticos:** 3
**Problemas Menores:** 0
**Warnings:** 2

### Hallazgos Principales

1. **ERROR CRÍTICO #1**: `user_stats.py` (sync) está llamando métodos async sin `await` (líneas 813, 1391)
2. **ERROR CRÍTICO #2**: `async_user_stats.py` está llamando métodos sync en contexto async (línea 805)
3. **ERROR CRÍTICO #3**: `async_user_stats.py` está usando `Session` sync incorrectamente (línea 164)
4. **WARNING #1**: Método `get_user_social_score()` no existe en `chat_analytics_service`
5. **WARNING #2**: Mix de `datetime.utcnow()` (deprecated) y `datetime.now(timezone.utc)`

---

## Metodología de Auditoría (6 Pasos)

### ✅ Paso 1: Identificación de Sesiones de BD

#### `app/services/user_stats.py` (SYNC - LEGACY)
- **Tipo esperado:** `Session` (sync)
- **Líneas críticas:**
  - L43-49: `get_dashboard_summary(db: Session, ...)`
  - L87-95: `get_comprehensive_stats(db: Session, ...)`
  - L145-234: `_compute_dashboard_summary(db: Session, ...)`
  - Todos los métodos internos usan `Session`

#### `app/services/async_user_stats.py` (ASYNC - NUEVO)
- **Tipo esperado:** `AsyncSession`
- **Líneas críticas:**
  - L45-51: `get_dashboard_summary(db: AsyncSession, ...)`
  - L89-97: `get_comprehensive_stats(db: AsyncSession, ...)`
  - L147-236: `_compute_dashboard_summary(db: AsyncSession, ...)`
  - Todos los métodos internos usan `AsyncSession` ✅

---

### ✅ Paso 2: Verificación de Declaraciones async/await

#### `app/services/user_stats.py` (SYNC)

**Métodos públicos - TODOS declarados como `async` (CORRECTO para migración progresiva):**
```python
L43:  async def get_dashboard_summary(self, db: Session, ...) -> DashboardSummary:
L87:  async def get_comprehensive_stats(self, db: Session, ...) -> ComprehensiveUserStats:
L145: async def _compute_dashboard_summary(self, db: Session, ...) -> DashboardSummary:
```

**Métodos privados async:**
- L315: `async def _calculate_current_streak_fast()`
- L367: `async def _calculate_longest_streak()`
- L427: `async def _get_weekly_workout_count()`
- L460: `async def _get_next_scheduled_class()`
- L512: `async def _compute_fitness_metrics()`
- L685: `async def _compute_events_metrics()`
- L799: `async def _compute_social_metrics()`
- L905: `async def _compute_health_metrics()`
- L927: `async def _compute_app_usage_metrics()`
- L994: `async def _compute_membership_utilization()`
- L1139: `async def _get_recent_achievements()`
- L1174: `async def _analyze_trends()`
- L1194: `async def _generate_recommendations()`
- L1232: `async def get_last_attendance_date()`
- L1328: `async def _calculate_quick_stats()`

**Métodos síncronos (helpers):**
- L888: `def _calculate_social_score()` ✅
- L1095: `def _calculate_membership_value_score()` ✅
- L1110: `def _generate_membership_recommendations()` ✅
- L1303: `def _calculate_period_dates()` ✅

#### `app/services/async_user_stats.py` (ASYNC)

**IDÉNTICA estructura a sync** - Todos los métodos correctamente declarados como `async` ✅

---

### ⚠️ Paso 3: Análisis de Queries a Base de Datos

#### `app/services/user_stats.py` (SYNC - LEGACY)

**❌ ERRORES ENCONTRADOS:**

**Todas las queries usan `await db.execute()` - CORRECTO para AsyncSession:**
```python
L187: result_user_gym = await db.execute(stmt_user_gym)  ✅
L338: result = await db.execute(stmt)                     ✅
L453: result = await db.execute(stmt)                     ✅
L489: result = await db.execute(stmt)                     ✅
L572: res_counts = await db.execute(stmt_counts)          ✅
... (60+ queries todas con await)
```

**PROBLEMA:** El archivo `user_stats.py` está declarado como SYNC pero:
- ✅ **Usa `await db.execute()` correctamente** (preparado para AsyncSession)
- ✅ **Usa select() de SQLAlchemy 2.0** (correcto)
- ❌ **Recibe `Session` sync en type hints** pero debería recibir `AsyncSession`

**CONCLUSIÓN:** Este archivo parece ser una **versión intermedia mal etiquetada**. Debería llamarse `async_user_stats_legacy.py` o refactorizarse completamente.

#### `app/services/async_user_stats.py` (ASYNC - NUEVO)

**✅ CORRECTAS - Todas las queries usan `await db.execute()`:**
```python
L185: result = await db.execute(...)                      ✅
L329: result = await db.execute(...)                      ✅
L441: result = await db.execute(...)                      ✅
L472: result = await db.execute(...)                      ✅
L540: result = await db.execute(...)                      ✅
... (60+ queries todas correctas)
```

**✅ Uso correcto de SQLAlchemy 2.0:**
- `select()` en lugar de `query()`
- `result.scalar()`, `result.scalars()`, `result.first()`
- Relaciones pre-cargadas con `selectinload()` cuando necesario

---

### 🔴 Paso 4: Revisión de Llamadas a Servicios Externos

#### **ERROR CRÍTICO #1: user_stats.py línea 813**

```python
# app/services/user_stats.py:813
user_chat_activity = await chat_analytics_service.get_user_chat_activity(db, user_id)
```

**Problema:**
- `chat_analytics_service.get_user_chat_activity()` es un método **ASYNC**
- Se está llamando con `await` ✅
- Pero el servicio espera `AsyncSession`, no `Session` ❌

**Verificación en `chat_analytics.py`:**
```python
# app/services/chat_analytics.py:97
async def get_user_chat_activity(self, db: AsyncSession, user_id: int) -> Dict[str, Any]:
```

**Impacto:**
- 🔴 **FALLO EN RUNTIME** cuando se llama desde `user_stats.py` con `Session` sync
- El método espera `AsyncSession` pero recibe `Session`

---

#### **ERROR CRÍTICO #2: async_user_stats.py línea 805**

```python
# app/services/async_user_stats.py:805
user_chat_activity = chat_analytics_service.get_user_chat_activity(db, user_id)
```

**Problema:**
- `get_user_chat_activity()` es **ASYNC** pero se llama **SIN AWAIT** ❌
- Esto retorna una coroutine sin ejecutar

**Corrección requerida:**
```python
user_chat_activity = await chat_analytics_service.get_user_chat_activity(db, user_id)
```

---

#### **ERROR CRÍTICO #3: user_stats.py línea 164**

```python
# app/services/user_stats.py:162-164
# Obtener datos básicos del usuario
user = user_service.get_user(db, user_id=user_id)
if not user:
    raise ValueError(f"Usuario {user_id} no encontrado")
```

**Problema:**
- `user_service.get_user()` es un método **SYNC** (línea 373 en user.py)
- Se llama **SIN AWAIT** desde un contexto async ❌
- Recibe `Session` pero debería usar método async

**Verificación en `user.py`:**
```python
# app/services/user.py:373
def get_user(self, db: Session, user_id: int) -> Optional[UserModel]:
    user = user_repository.get(db, id=user_id)
    return user
```

**Corrección requerida:**
```python
# Usar versión async
user = await user_service.get_user_async(db, user_id=user_id)
```

---

#### **WARNING #1: Método get_user_social_score() no existe**

**Líneas afectadas:**
- `user_stats.py:1391`
- `async_user_stats.py:1369`

```python
# Ambos archivos, método _calculate_quick_stats()
social_score = await chat_analytics_service.get_user_social_score(
    db, user_id, gym_id, days=30
)
```

**Problema:**
- El método `get_user_social_score()` **NO EXISTE** en `ChatAnalyticsService`
- Métodos disponibles:
  - `get_gym_chat_summary()`
  - `get_user_chat_activity()`
  - `get_popular_chat_times()`
  - `get_event_chat_effectiveness()`
  - `get_chat_health_metrics()`

**Impacto:**
- 🟡 **AttributeError en runtime** cuando se intenta calcular quick_stats
- El código tiene un try/except que captura el error y usa fallback (L1395-1396)

**Corrección sugerida:**
```python
# Implementar el método faltante en ChatAnalyticsService
async def get_user_social_score(
    self,
    db: AsyncSession,
    user_id: int,
    gym_id: int,
    days: int = 30
) -> float:
    """Calcula social score basado en actividad de chat."""
    activity = await self.get_user_chat_activity(db, user_id)

    if "error" in activity:
        return 0.0

    # Algoritmo simple basado en métricas
    total_chats = activity.get("total_chats", 0)
    recent_activity = activity.get("recent_activity", 0)

    score = min((total_chats * 0.5 + recent_activity * 2), 10.0)
    return score
```

---

### ✅ Paso 5: Análisis de Repositorios

**Repositorios referenciados:**
- `class_participation_repository` (línea 24 en ambos archivos) - No usado directamente ✅
- `event_participation_repository` (línea 25 en ambos archivos) - No usado directamente ✅

**Métodos de servicio usados:**
- `user_service.get_user()` - SYNC ❌ (debería ser async)
- `membership_service` - No usado directamente ✅
- `chat_analytics_service.get_user_chat_activity()` - ASYNC ✅
- `chat_analytics_service.get_user_social_score()` - NO EXISTE ❌
- `health_service.get_recent_achievement_async()` - ASYNC ✅
- `health_service.calculate_health_metrics_async()` - ASYNC ✅
- `health_service.get_user_achievements_async()` - ASYNC ✅

**Todos los accesos directos a BD usan `await db.execute()` correctamente** ✅

---

### ✅ Paso 6: Problemas de Concurrencia y Timezone

#### **WARNING #2: Mix de datetime utilities**

**En `user_stats.py`:**
```python
L965: days_since_last = (datetime.utcnow() - user_gym.last_app_access).days
L973: weeks_since_joined = max(1, (datetime.utcnow() - user_gym.created_at).days // 7)
```

**En `async_user_stats.py`:**
```python
L169: today = datetime.now(timezone.utc).date()
L952: days_since_last = (datetime.now(timezone.utc) - user_gym.last_app_access).days
L960: weeks_since_joined = max(1, (datetime.now(timezone.utc) - user_gym.created_at).days // 7)
```

**Problema:**
- `user_stats.py` usa `datetime.utcnow()` (deprecated en Python 3.12+)
- `async_user_stats.py` usa `datetime.now(timezone.utc)` (correcto) ✅

**Recomendación:**
- Migrar todo a `datetime.now(timezone.utc)` para consistencia

#### **Concurrencia:**
- ✅ Todos los métodos async pueden correr concurrentemente
- ✅ No hay uso de variables globales mutables
- ✅ Cache con Redis es thread-safe
- ✅ No hay race conditions aparentes

---

## Análisis de Attendance Stats (Foco Especial)

### **Implementación Actual:**

Ambos archivos implementan un **sistema temporal de asistencia** documentado en líneas 522-530:

```python
"""
NOTA TEMPORAL: Sistema de Asistencia Simplificado
==================================================
Mientras se implementa el sistema de escaneo QR en el gimnasio,
asumimos que los usuarios con estado REGISTERED asistieron si:
- La sesión ya terminó (end_time < now)
- No cancelaron su participación

TODO: Remover esta lógica cuando se implemente:
- Escaneo de QR en entrada del gimnasio
- Actualización automática a estado ATTENDED
- Proceso de marcado de NO_SHOW para ausencias
"""
```

### **Queries de asistencia:**

**1. Current Streak (L315-365):**
```python
# Obtiene fechas únicas de asistencia de los últimos 30 días
select(func.date(ClassParticipation.created_at))
.where(
    ClassParticipation.status == ClassParticipationStatus.ATTENDED,
    func.date(ClassParticipation.created_at) >= thirty_days_ago
)
.distinct()
.order_by(func.date(ClassParticipation.created_at).desc())
```
✅ **Correcta** - Usa await, filtro eficiente con índice

**2. Weekly Workout Count (L427-458):**
```python
# Cuenta clases asistidas en la semana
select(func.count(ClassParticipation.id))
.where(
    ClassParticipation.status == ClassParticipationStatus.ATTENDED,
    func.date(ClassParticipation.created_at) >= week_start,
    func.date(ClassParticipation.created_at) <= week_end
)
```
✅ **Correcta** - Usa await, rango de fechas óptimo

**3. Fitness Metrics con lógica temporal (L540-580):**
```python
# Cuenta clases con lógica ATTENDED o REGISTERED pasadas
select(
    func.count(
        case(
            (ClassParticipation.status == ClassParticipationStatus.ATTENDED, 1),
            ((ClassParticipation.status == ClassParticipationStatus.REGISTERED) &
             (ClassSession.end_time < now), 1),
            else_=None
        )
    ).label('attended_classes')
)
.join(ClassSession)
```
✅ **Correcta** - JOIN necesario para verificar end_time, usa await

**4. Last Attendance Date (L1218-1285):**
```python
select(ClassParticipation)
.where(
    ClassParticipation.status == ClassParticipationStatus.ATTENDED,
    ClassParticipation.attendance_time.isnot(None)
)
.order_by(ClassParticipation.attendance_time.desc())
```
✅ **Correcta** - Usa await, caché de 10 minutos

### **Métricas calculadas:**
- `classes_attended` - Clases confirmadas asistidas ✅
- `classes_scheduled` - Clases registradas (futuras + pasadas) ✅
- `attendance_rate` - Porcentaje de asistencia ✅
- `total_workout_hours` - Basado en duración de clases ✅
- `streak_current` - Racha actual de días consecutivos ✅
- `streak_longest` - Racha más larga histórica ✅

**Todas las implementaciones son idénticas entre sync/async excepto por los errores documentados.**

---

## Progress Tracking (Foco Especial)

### **Health Metrics Integration:**

Ambos archivos delegan a `health_service` para métricas de progreso (L905-926):

```python
async def _compute_health_metrics(
    self,
    db: AsyncSession,  # ✅ Correcto en async_user_stats.py
    user_id: int,
    gym_id: int,
    period_start: datetime,
    period_end: datetime,
    include_goals: bool
) -> HealthMetrics:
    # Usar health service async para obtener métricas reales
    return await health_service.calculate_health_metrics_async(
        db, user_id, gym_id
    )
```

✅ **Delegación correcta** - El health_service maneja:
- BMI calculations
- Body measurements tracking
- Goal progress
- Achievement tracking

### **Achievements Tracking:**

```python
async def _get_recent_achievements(
    self,
    db: AsyncSession,
    user_id: int,
    gym_id: int,
    period_start: datetime,
    period_end: datetime
) -> List[Achievement]:
    # Obtener achievements del período usando el health service async
    user_achievements = await health_service.get_user_achievements_async(db, user_id, gym_id)

    # Filtrar por período
    recent_achievements = []
    for achievement in user_achievements:
        if period_start <= achievement.earned_at <= period_end:
            recent_achievements.append(Achievement(...))
```

✅ **Correcto** - Filtra achievements por período y convierte a schema

### **App Usage Metrics:**

```python
async def _compute_app_usage_metrics(...) -> AppUsageMetrics:
    # Obtiene UserGym con métricas de uso
    user_gym = await db.execute(
        select(UserGym).where(
            UserGym.user_id == user_id,
            UserGym.gym_id == gym_id
        )
    )

    return AppUsageMetrics(
        last_access=user_gym.last_app_access,
        total_sessions=user_gym.total_app_opens,
        sessions_this_month=user_gym.monthly_app_opens,
        avg_sessions_per_week=...,
        consecutive_days=...,
        is_active_today=...
    )
```

✅ **Correcta** - Calcula métricas de engagement

---

## Analytics (Foco Especial)

### **1. Trend Analysis (L1160-1178):**

```python
async def _analyze_trends(...) -> TrendAnalysis:
    # TODO: Implementar análisis real de tendencias
    return TrendAnalysis(
        attendance_trend=TrendDirection.increasing,
        workout_intensity_trend=TrendDirection.stable,
        social_engagement_trend=TrendDirection.increasing
    )
```

⚠️ **NO IMPLEMENTADO** - Retorna valores hardcodeados

**Recomendación:**
```python
# Implementar análisis real comparando períodos
previous_period_start = period_start - (period_end - period_start)
previous_fitness = await self._compute_fitness_metrics(
    db, user_id, gym_id, previous_period_start, period_start
)

attendance_trend = (
    TrendDirection.increasing if fitness.attendance_rate > previous_fitness.attendance_rate
    else TrendDirection.decreasing if fitness.attendance_rate < previous_fitness.attendance_rate
    else TrendDirection.stable
)
```

### **2. Social Metrics (L791-872):**

```python
async def _compute_social_metrics(...) -> SocialMetrics:
    # Usar chat_analytics_service
    user_chat_activity = await chat_analytics_service.get_user_chat_activity(db, user_id)

    chat_rooms_active = user_chat_activity.get("total_rooms", 0)
    chat_messages_sent = max(0, chat_rooms_active * 5)  # Estimación

    social_score = self._calculate_social_score(...)
```

✅ **Correcta en user_stats.py** (línea 813 con await)
❌ **INCORRECTA en async_user_stats.py** (línea 805 sin await)

**Social Score Algorithm:**
```python
def _calculate_social_score(self, chat_rooms: int, messages: int, recent_days: int) -> float:
    rooms_score = min(chat_rooms * 0.5, 4.0)      # Max 4 puntos
    messages_score = min(messages * 0.02, 3.0)     # Max 3 puntos
    activity_score = min(recent_days * 0.5, 3.0)   # Max 3 puntos
    return min(rooms_score + messages_score + activity_score, 10.0)
```

✅ **Algoritmo simple pero efectivo**

### **3. Recommendations Engine (L1180-1216):**

```python
async def _generate_recommendations(...) -> List[str]:
    recommendations = []

    if fitness.attendance_rate < 70:
        recommendations.append("Try scheduling classes in advance...")

    if len(fitness.favorite_class_types) < 3:
        recommendations.append("Try a new class type...")

    if social.social_score < 5:
        recommendations.append("Join community chats...")
```

✅ **Implementación básica funcional** - Genera recomendaciones basadas en umbrales

### **4. Membership Utilization (L981-1079):**

```python
async def _compute_membership_utilization(...) -> MembershipUtilization:
    # Calcular tasa de utilización
    classes_attended_count = await db.execute(
        select(func.count(ClassParticipation.id))
        .where(ClassParticipation.status == ATTENDED, ...)
    )

    estimated_available_classes = period_days * 2  # 2 clases/día
    utilization_rate = (classes_attended / estimated_available_classes) * 100

    value_score = self._calculate_membership_value_score(...)
    recommended_actions = self._generate_membership_recommendations(...)
```

✅ **Análisis completo de ROI de membresía** - Incluye:
- Tasa de utilización
- Value score (0-10)
- Días hasta renovación
- Recomendaciones personalizadas

---

## Resumen de Errores por Archivo

### `app/services/user_stats.py` (SYNC - LEGACY)

| Línea | Severidad | Descripción | Corrección |
|-------|-----------|-------------|------------|
| 12 | 🔴 CRÍTICO | Type hint `Session` pero código usa async patterns | Cambiar a `AsyncSession` |
| 164 | 🔴 CRÍTICO | Llama `user_service.get_user()` sync sin await | Usar `get_user_async()` |
| 813 | 🔴 CRÍTICO | Pasa `Session` a método que espera `AsyncSession` | N/A (se resuelve cambiando type hints) |
| 1391 | 🟡 WARNING | Llama método inexistente `get_user_social_score()` | Implementar método o remover |
| 965, 973 | 🟡 WARNING | Usa `datetime.utcnow()` deprecated | Cambiar a `datetime.now(timezone.utc)` |

### `app/services/async_user_stats.py` (ASYNC - NUEVO)

| Línea | Severidad | Descripción | Corrección |
|-------|-----------|-------------|------------|
| 164 | 🔴 CRÍTICO | Llama `user_service.get_user()` sync sin await | Usar `get_user_async()` |
| 805 | 🔴 CRÍTICO | Llama método async sin `await` | Agregar `await` |
| 1369 | 🟡 WARNING | Llama método inexistente `get_user_social_score()` | Implementar método o remover |

### `app/services/chat_analytics.py` (DEPENDENCIA)

| Línea | Severidad | Descripción | Corrección |
|-------|-----------|-------------|------------|
| N/A | 🟡 WARNING | Falta método `get_user_social_score()` | Implementar según especificación |

---

## Plan de Corrección Recomendado

### **Prioridad 1 - CRÍTICA (Bloquea funcionalidad)**

#### 1.1 Corregir `async_user_stats.py` línea 805
```python
# ANTES
user_chat_activity = chat_analytics_service.get_user_chat_activity(db, user_id)

# DESPUÉS
user_chat_activity = await chat_analytics_service.get_user_chat_activity(db, user_id)
```

#### 1.2 Corregir ambos archivos línea ~164
```python
# ANTES (user_stats.py y async_user_stats.py)
user = user_service.get_user(db, user_id=user_id)

# DESPUÉS
user = await user_service.get_user_async(db, user_id=user_id)
```

#### 1.3 Renombrar/refactorizar `user_stats.py`
**Opción A:** Eliminar archivo (duplicado innecesario)
```bash
git rm app/services/user_stats.py
```

**Opción B:** Refactorizar a verdadero sync
```python
# Cambiar TODAS las signatures de async a sync
def get_dashboard_summary(self, db: Session, ...) -> DashboardSummary:
    # Usar métodos sync de repositorios
    user = user_repository.get(db, id=user_id)
```

**Recomendación:** **Opción A** - El archivo async es superior y completo.

### **Prioridad 2 - ALTA (Mejora funcionalidad)**

#### 2.1 Implementar `get_user_social_score()` en `ChatAnalyticsService`
```python
# app/services/chat_analytics.py

async def get_user_social_score(
    self,
    db: AsyncSession,
    user_id: int,
    gym_id: int,
    days: int = 30
) -> float:
    """
    Calcula un score social (0-10) basado en actividad de chat.

    Args:
        db: Sesión async
        user_id: ID del usuario
        gym_id: ID del gimnasio
        days: Días hacia atrás para analizar

    Returns:
        float: Score entre 0.0 y 10.0
    """
    # Obtener actividad del usuario
    activity = await self.get_user_chat_activity(db, user_id)

    if "error" in activity:
        return 0.0

    # Filtrar solo chats del gym específico
    total_rooms = activity.get("gym_distribution", {}).get(gym_id, 0)
    recent_activity = activity.get("recent_activity", 0)

    # Calcular score (algoritmo mejorado)
    rooms_score = min(total_rooms * 0.5, 4.0)       # Max 4 puntos
    recent_score = min(recent_activity * 0.3, 3.0)   # Max 3 puntos
    engagement_score = 3.0 if recent_activity > 0 else 0  # 3 puntos por estar activo

    total_score = rooms_score + recent_score + engagement_score
    return round(min(total_score, 10.0), 1)
```

### **Prioridad 3 - MEDIA (Mejoras de calidad)**

#### 3.1 Migrar datetime utilities
```python
# Buscar y reemplazar en ambos archivos
datetime.utcnow() → datetime.now(timezone.utc)
```

#### 3.2 Implementar análisis real de tendencias
```python
async def _analyze_trends(
    self,
    db: AsyncSession,
    user_id: int,
    gym_id: int,
    period_start: datetime,
    period_end: datetime
) -> TrendAnalysis:
    """Analiza tendencias comparando con período anterior."""

    # Calcular período anterior (misma duración)
    period_duration = period_end - period_start
    previous_start = period_start - period_duration
    previous_end = period_start

    # Obtener métricas de ambos períodos
    current_fitness = await self._compute_fitness_metrics(
        db, user_id, gym_id, period_start, period_end
    )
    previous_fitness = await self._compute_fitness_metrics(
        db, user_id, gym_id, previous_start, previous_end
    )

    # Comparar asistencia
    attendance_trend = (
        TrendDirection.increasing
        if current_fitness.attendance_rate > previous_fitness.attendance_rate + 5
        else TrendDirection.decreasing
        if current_fitness.attendance_rate < previous_fitness.attendance_rate - 5
        else TrendDirection.stable
    )

    # Comparar intensidad (basado en horas totales)
    intensity_trend = (
        TrendDirection.increasing
        if current_fitness.total_workout_hours > previous_fitness.total_workout_hours * 1.1
        else TrendDirection.decreasing
        if current_fitness.total_workout_hours < previous_fitness.total_workout_hours * 0.9
        else TrendDirection.stable
    )

    # Social engagement (simplificado por ahora)
    social_engagement_trend = TrendDirection.stable

    return TrendAnalysis(
        attendance_trend=attendance_trend,
        workout_intensity_trend=intensity_trend,
        social_engagement_trend=social_engagement_trend
    )
```

### **Prioridad 4 - BAJA (Optimizaciones)**

#### 4.1 Agregar índices de BD recomendados
```sql
-- Para optimizar queries de attendance
CREATE INDEX idx_class_participation_attendance
ON class_participation(member_id, gym_id, status, created_at);

CREATE INDEX idx_class_participation_attendance_time
ON class_participation(member_id, gym_id, status, attendance_time DESC);
```

#### 4.2 Paralelizar cálculos en `_compute_comprehensive_stats`
```python
import asyncio

async def _compute_comprehensive_stats(...):
    # Ejecutar cálculos independientes en paralelo
    fitness_task = asyncio.create_task(
        self._compute_fitness_metrics(db, user_id, gym_id, period_start, period_end)
    )
    events_task = asyncio.create_task(
        self._compute_events_metrics(db, user_id, gym_id, period_start, period_end)
    )
    social_task = asyncio.create_task(
        self._compute_social_metrics(db, user_id, gym_id, period_start, period_end)
    )
    health_task = asyncio.create_task(
        self._compute_health_metrics(db, user_id, gym_id, period_start, period_end, include_goals)
    )

    # Esperar todos los resultados
    fitness_metrics, events_metrics, social_metrics, health_metrics = await asyncio.gather(
        fitness_task, events_task, social_task, health_task
    )
```

---

## Testing Recomendado

### **Tests Unitarios Críticos:**

```python
# tests/services/test_async_user_stats.py

import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.async_user_stats import async_user_stats_service

@pytest.mark.asyncio
async def test_compute_social_metrics_awaits_chat_activity():
    """Verifica que se usa await correctamente con chat_analytics_service."""
    db = AsyncMock()

    # Mock del servicio de chat
    with patch('app.services.async_user_stats.chat_analytics_service') as mock_chat:
        mock_chat.get_user_chat_activity = AsyncMock(return_value={
            "total_rooms": 5,
            "recent_activity": 3
        })

        result = await async_user_stats_service._compute_social_metrics(
            db, user_id=1, gym_id=1,
            period_start=datetime.now(),
            period_end=datetime.now()
        )

        # Verificar que se llamó con await
        mock_chat.get_user_chat_activity.assert_awaited_once()
        assert result.chat_rooms_active == 5

@pytest.mark.asyncio
async def test_compute_dashboard_uses_async_user_service():
    """Verifica que se usa get_user_async en lugar de get_user."""
    db = AsyncMock()

    with patch('app.services.async_user_stats.user_service') as mock_user:
        mock_user.get_user_async = AsyncMock(return_value=MagicMock(id=1))

        await async_user_stats_service._compute_dashboard_summary(db, 1, 1)

        # Verificar que NO se llamó al método sync
        assert not hasattr(mock_user, 'get_user') or not mock_user.get_user.called
        # Verificar que se llamó al método async
        mock_user.get_user_async.assert_awaited_once()
```

### **Tests de Integración:**

```python
@pytest.mark.asyncio
async def test_dashboard_summary_end_to_end(async_db, test_user, test_gym):
    """Test end-to-end del dashboard summary."""
    summary = await async_user_stats_service.get_dashboard_summary(
        db=async_db,
        user_id=test_user.id,
        gym_id=test_gym.id,
        redis_client=None  # Sin cache para test
    )

    assert summary.user_id == test_user.id
    assert summary.current_streak >= 0
    assert summary.weekly_workouts >= 0
    assert 0 <= summary.monthly_goal_progress <= 100
```

---

## Conclusiones

### **Archivo user_stats.py (SYNC):**
- ❌ **NO ES REALMENTE SYNC** - Usa async patterns pero declara Session sync
- ❌ **3 errores críticos** que causan fallos en runtime
- 🗑️ **RECOMENDACIÓN:** Eliminar - Es una versión inconsistente y confusa

### **Archivo async_user_stats.py (ASYNC):**
- ✅ **BIEN ESTRUCTURADO** - Diseño correcto con AsyncSession
- ❌ **2 errores críticos** fáciles de corregir
- ✅ **Implementación completa** de attendance, progress y analytics
- ⚠️ **Falta método** en dependencia externa
- 🎯 **RECOMENDACIÓN:** Mantener como versión oficial tras correcciones

### **Funcionalidades Especiales:**
- ✅ **Attendance Stats:** Implementación robusta con lógica temporal documentada
- ✅ **Progress Tracking:** Correcta delegación a health_service
- ⚠️ **Analytics:** Trend analysis no implementado, social score con método faltante
- ✅ **Membership Utilization:** Análisis completo de ROI

### **Impacto en Producción:**
- 🔴 **BLOQUEANTE:** Los 3 errores críticos causan excepciones en runtime
- 🟡 **DEGRADADO:** Social score fallback funciona pero pierde funcionalidad
- ✅ **CACHE:** Sistema de Redis bien implementado con fallbacks

### **Estimación de Corrección:**
- **Prioridad 1:** 2-3 horas (correcciones críticas)
- **Prioridad 2:** 3-4 horas (implementar método faltante)
- **Prioridad 3:** 2-3 horas (mejoras de calidad)
- **Total:** 7-10 horas de desarrollo + 2-3 horas de testing

---

## Comandos de Verificación

```bash
# Buscar todos los usos de chat_analytics_service
grep -rn "chat_analytics_service\." app/services/user_stats.py app/services/async_user_stats.py

# Buscar métodos sync llamados sin await
grep -rn "user_service\.get_user(" app/services/async_user_stats.py

# Verificar type hints de Session vs AsyncSession
grep -rn "db: Session" app/services/async_user_stats.py

# Buscar datetime.utcnow()
grep -rn "datetime\.utcnow()" app/services/user_stats.py app/services/async_user_stats.py
```

---

**FIN DE AUDITORÍA**
