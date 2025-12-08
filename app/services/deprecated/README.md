# Deprecated Services

Este directorio contiene servicios legacy que han sido reemplazados por versiones async.

## Archivos Deprecados

### ✅ post_service.py (27 errores)
- **Reemplazado por:** `async_post_service.py`
- **Razón:** Arquitectura híbrida incorrecta: métodos `async def` con `Session` sync
- **Errores:**
  - 23 missing awaits en operaciones DB
  - 2 `db.get()` no disponibles
  - 2 timezone-naive `datetime.utcnow()`
- **Estado:** No se usa en ningún endpoint

### ✅ story_service.py (28 errores)
- **Reemplazado por:** `async_story_service.py`
- **Razón:** Todos los métodos async pero sin `await` en operaciones DB
- **Errores:**
  - 14 missing awaits en `db.execute()`
  - 10 missing awaits en `db.commit()`
  - 6 missing awaits en `db.refresh()`
  - 1 `db.get(User, id)` no disponible
- **Estado:** No se usa en ningún endpoint

### ✅ billing_module.py (11 errores)
- **Reemplazado por:** `async_billing_module.py`
- **Razón:** Métodos async con Session sync y llamadas a servicios sync
- **Errores:**
  - Llamadas sync a `module_service` sin await
  - Métodos async con `Session` en lugar de `AsyncSession`
- **Estado:** No se usa en ningún endpoint

### ✅ gym_revenue.py (est. 5 errores)
- **Reemplazado por:** `async_gym_revenue.py` (0 errores, ⭐⭐⭐⭐⭐)
- **Razón:** Métodos async con Session sync
- **Errores:**
  - Métodos async con `Session` en lugar de `AsyncSession`
  - Posibles missing awaits en operaciones DB
- **Estado:** Migrado completamente - no se usa en ningún endpoint
- **Fecha deprecación:** 2025-12-07 (Batch 19)

## Total de Errores Eliminados: 71

Al deprecar estos archivos, eliminamos 71 errores del total de 332 identificados en el plan de auditoría.

## Archivos Legacy que AÚN SE USAN (No Deprecar)

### ⚠️ event.py
- **Usado en:** `app/api/v1/endpoints/worker.py`, `app/services/__init__.py`
- **Tiene versión async:** `async_event.py` ✅
- **Acción requerida:** Migrar worker.py a usar async_event_service

### ⚠️ attendance.py
- **Usado en:** `app/services/user.py` (3 instancias)
- **Tiene versión async:** `async_attendance.py` ✅
- **Acción requerida:** Migrar user.py a usar async_attendance_service

### ⚠️ gym.py
- **Usado en:** `app/api/v1/endpoints/users.py`, `app/api/v1/endpoints/schedule/sessions.py`, `app/services/attendance.py`
- **Tiene versión async:** `async_gym.py` ✅
- **Acción requerida:** Migrar endpoints a usar async_gym_service

### ⚠️ membership.py
- **Usado en:** `app/services/async_billing_module.py`, `app/services/stripe_service.py`, `app/services/async_user_stats.py`, `app/services/billing_module.py`, `app/services/user_stats.py`
- **Tiene versión async:** `async_membership.py` ✅
- **Acción requerida:** Migrar todos los servicios async a usar AsyncMembershipService

### ⚠️ chat.py
- **Usado en:** `app/services/gym_chat.py`, `app/services/async_gym_chat.py`, `app/webhooks/stream_security.py`, `app/core/scheduler.py`, `app/api/v1/endpoints/webhooks/stream_webhooks.py`
- **Tiene versión async:** `async_chat.py` ✅
- **Acción requerida:** Migrar todos a usar async_chat_service

### ⚠️ stripe_connect_service.py (27 errores)
- **Usado en:** `app/services/membership.py`, `app/services/stripe_service.py` (12 instancias)
- **Tiene versión async:** `async_stripe_connect_service.py` ✅
- **Acción requerida:** Migrar stripe_service.py a usar AsyncStripeConnectService

## Fecha de Deprecación
2025-12-07
