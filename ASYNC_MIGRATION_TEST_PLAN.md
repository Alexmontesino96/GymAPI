# 🔬 Plan de Revisión y Testing - Migración Async

**Objetivo**: Validar todos los endpoints async módulo por módulo
**Fecha inicio**: 2025-12-05
**Estado**: En Progreso

---

## 📊 Resumen Ejecutivo

```
Total Módulos: 15
Endpoints Estimados: ~120
Prioridad: ALTA (Producción afectada)
Tiempo Estimado: 2-3 días
```

---

## 🎯 Estrategia de Testing

### Niveles de Testing

1. **Unit Tests**: Métodos individuales de servicios ✅
2. **Integration Tests**: Endpoints completos con DB real ⚠️ (Enfoque actual)
3. **E2E Tests**: Flujos completos de usuario 🔜

### Criterios de Éxito por Endpoint

- ✅ Status code 200/201 para casos válidos
- ✅ Status code 400/401/403/404 para casos inválidos
- ✅ Response schema correcto
- ✅ Sin errores `AttributeError: 'AsyncSession'`
- ✅ Tiempo de respuesta <500ms P95

---

## 📦 Módulos Priorizados

### PRIORIDAD 1: Core Funcionalidad (Crítico)

#### 1. Auth Module ⚠️
**Archivos**:
- `app/api/v1/endpoints/auth/admin.py`
- `app/api/v1/endpoints/auth/login.py`

**Endpoints Críticos**:
- [ ] `POST /api/v1/auth/login` - Login de usuario
- [ ] `POST /api/v1/auth/refresh` - Refresh token
- [ ] `GET /api/v1/auth/me` - Obtener perfil actual
- [ ] `POST /api/v1/auth/admin/create-platform-admin` - Crear admin

**Servicios Usados**:
- `user_service.get_user_by_auth0_id_cached()` ✅ Async
- `gym_service.check_user_in_gym()` ⚠️ Verificar

**Riesgos**:
- 🔴 ALTO - Sin auth, toda la app falla

---

#### 2. Users Module ⚠️
**Archivos**:
- `app/api/v1/endpoints/users.py`

**Endpoints Críticos**:
- [ ] `GET /api/v1/users/me` - Perfil del usuario
- [ ] `PUT /api/v1/users/me` - Actualizar perfil
- [ ] `GET /api/v1/users/{user_id}` - Ver usuario
- [ ] `GET /api/v1/users/` - Listar usuarios del gym
- [ ] `POST /api/v1/users/upload-avatar` - Upload avatar

**Servicios Usados**:
- `user_service.get_user_by_auth0_id_cached()` ✅
- `user_service.update_user_profile()` ⚠️
- `user_repository.get_gym_participants_async()` ✅

**Riesgos**:
- 🟡 MEDIO - Usuarios no pueden ver/editar perfiles

---

#### 3. Gyms Module ⚠️
**Archivos**:
- `app/api/v1/endpoints/gyms.py`

**Endpoints Críticos**:
- [ ] `GET /api/v1/gyms/me` - Mis gimnasios
- [ ] `GET /api/v1/gyms/{gym_id}` - Detalles del gym
- [ ] `POST /api/v1/gyms/{gym_id}/members` - Agregar miembro
- [ ] `DELETE /api/v1/gyms/{gym_id}/members/{user_id}` - Remover miembro
- [ ] `PUT /api/v1/gyms/{gym_id}/members/{user_id}/role` - Cambiar rol

**Servicios Usados**:
- `async_gym_service.check_user_in_gym()` ✅ (Corregido)
- `async_gym_service.add_user_to_gym()` ⚠️
- `async_gym_service.remove_user_from_gym()` ⚠️

**Riesgos**:
- 🔴 ALTO - Gestión de membresías es core

---

#### 4. Schedule Module 🔴
**Archivos**:
- `app/api/v1/endpoints/schedule/sessions.py`
- `app/api/v1/endpoints/schedule/classes.py`
- `app/api/v1/endpoints/schedule/participation.py`
- `app/api/v1/endpoints/schedule/categories.py`

**Endpoints Críticos**:
- [ ] `GET /api/v1/schedule/sessions` - Ver clases disponibles
- [ ] `POST /api/v1/schedule/sessions/{session_id}/participate` - Reservar clase
- [ ] `DELETE /api/v1/schedule/sessions/{session_id}/participate` - Cancelar reserva
- [ ] `GET /api/v1/schedule/sessions/{session_id}/participants` - Ver participantes
- [ ] `GET /api/v1/schedule/categories` - Categorías de clases

**Servicios Usados**:
- `async_schedule_service.get_sessions_by_date_range_cached()` ✅ (Corregido)
- `async_category_service.get_categories_by_gym()` ✅
- `user_service.check_user_gym_membership_cached()` ✅ (Corregido)

**Riesgos**:
- 🔴 CRÍTICO - Funcionalidad más usada de la app

---

### PRIORIDAD 2: Engagement Features (Importante)

#### 5. Events Module ⚠️
**Archivos**:
- `app/api/v1/endpoints/events.py`

**Endpoints Críticos**:
- [ ] `GET /api/v1/events/` - Listar eventos
- [ ] `GET /api/v1/events/{event_id}` - Ver evento
- [ ] `POST /api/v1/events/` - Crear evento
- [ ] `POST /api/v1/events/{event_id}/participate` - Participar en evento

**Servicios Usados**:
- `async_event_service.get_events_cached()` ✅ (Corregido)
- `async_event_repository.get_events_with_counts()` ✅ (Agregado)

**Riesgos**:
- 🟡 MEDIO - Eventos son importantes pero no bloqueantes

---

#### 6. Activity Feed Module ⚠️
**Archivos**:
- `app/api/v1/endpoints/activity_feed.py`

**Endpoints Críticos**:
- [ ] `GET /api/v1/activity-feed/` - Feed de actividades
- [ ] `POST /api/v1/activity-feed/mark-read` - Marcar leído

**Servicios Usados**:
- `async_activity_feed_service.get_user_feed()` ⚠️

**Riesgos**:
- 🟢 BAJO - Feature secundario

---

#### 7. Chat Module ⚠️
**Archivos**:
- `app/api/v1/endpoints/chat.py`

**Endpoints Críticos**:
- [ ] `GET /api/v1/chat/channels` - Listar canales
- [ ] `POST /api/v1/chat/channels/{channel_id}/join` - Unirse a canal
- [ ] `GET /api/v1/chat/token` - Obtener token de Stream

**Servicios Usados**:
- `async_chat_service.get_user_channels()` ⚠️
- `async_chat_service.create_channel()` ⚠️

**Riesgos**:
- 🟡 MEDIO - Comunicación importante

---

### PRIORIDAD 3: Business Features (Importante)

#### 8. Billing/Memberships Module ⚠️
**Archivos**:
- `app/api/v1/endpoints/memberships.py`
- `app/api/v1/endpoints/payment_pages.py`

**Endpoints Críticos**:
- [ ] `GET /api/v1/memberships/` - Planes disponibles
- [ ] `POST /api/v1/memberships/subscribe` - Suscribirse
- [ ] `GET /api/v1/memberships/my-subscription` - Mi suscripción

**Servicios Usados**:
- `async_membership_service.get_gym_memberships()` ⚠️
- `async_billing_service.create_subscription()` ⚠️

**Riesgos**:
- 🔴 CRÍTICO - Pagos no pueden fallar

---

#### 9. Surveys Module ✅
**Archivos**:
- `app/api/v1/endpoints/surveys.py`

**Endpoints Críticos**:
- [ ] `GET /api/v1/surveys/available` - Encuestas disponibles
- [ ] `POST /api/v1/surveys/responses` - Enviar respuesta

**Servicios Usados**:
- `async_survey_service.get_available_surveys()` ⚠️

**Riesgos**:
- 🟢 BAJO - Feature secundario

**Status**: ✅ Import de `select` corregido

---

### PRIORIDAD 4: Secondary Features (Opcional)

#### 10. Nutrition Module ⚠️
**Archivos**:
- `app/api/v1/endpoints/nutrition.py`

**Endpoints**:
- [ ] `POST /api/v1/nutrition/analyze` - Analizar comida

**Riesgos**:
- 🟢 BAJO - Feature premium

---

#### 11. Attendance Module ⚠️
**Archivos**:
- `app/api/v1/endpoints/attendance.py`

**Endpoints**:
- [ ] `POST /api/v1/attendance/check-in` - Check-in con QR

**Riesgos**:
- 🟡 MEDIO - Importante para algunos gyms

---

#### 12. Stories/Posts Module ⚠️
**Archivos**:
- `app/api/v1/endpoints/stories.py`
- `app/api/v1/endpoints/posts.py`

**Endpoints**:
- [ ] `GET /api/v1/stories/` - Ver historias
- [ ] `POST /api/v1/posts/` - Crear post

**Riesgos**:
- 🟢 BAJO - Features sociales

---

#### 13. Notifications Module ⚠️
**Archivos**:
- `app/api/v1/endpoints/notification.py`

**Endpoints**:
- [ ] `GET /api/v1/notifications/` - Ver notificaciones

**Riesgos**:
- 🟢 BAJO - Nice to have

---

#### 14. Webhooks Module ⚠️
**Archivos**:
- `app/api/v1/endpoints/webhooks/stripe.py`
- `app/api/v1/endpoints/webhooks/stream.py`

**Endpoints**:
- [ ] `POST /api/v1/webhooks/stripe` - Webhook de Stripe
- [ ] `POST /api/v1/webhooks/stream` - Webhook de Stream

**Riesgos**:
- 🔴 ALTO - Críticos para sincronización

---

#### 15. Admin/Worker Module ⚠️
**Archivos**:
- `app/api/v1/endpoints/admin_diagnostics.py`
- `app/api/v1/endpoints/worker.py`

**Endpoints**:
- [ ] `GET /api/v1/admin/diagnostics` - Diagnósticos

**Riesgos**:
- 🟢 BAJO - Solo admin

---

## 🧪 Plan de Ejecución de Tests

### Fase 1: Setup (30 min)
- [ ] Crear suite de tests automatizados
- [ ] Configurar tokens de autenticación
- [ ] Preparar base de datos de test

### Fase 2: Testing Prioridad 1 (4-6 horas)
- [ ] Auth Module
- [ ] Users Module
- [ ] Gyms Module
- [ ] Schedule Module

### Fase 3: Testing Prioridad 2 (3-4 horas)
- [ ] Events Module
- [ ] Activity Feed Module
- [ ] Chat Module

### Fase 4: Testing Prioridad 3 (2-3 horas)
- [ ] Billing/Memberships
- [ ] Surveys Module

### Fase 5: Testing Prioridad 4 (1-2 horas)
- [ ] Resto de módulos

### Fase 6: Fixes y Retesting (4-6 horas)
- [ ] Corregir errores encontrados
- [ ] Re-ejecutar tests
- [ ] Validar en producción

---

## 📈 Métricas de Éxito

```
Target:
- Tests pasando: >95%
- Endpoints funcionando: 100%
- Errores AsyncSession: 0
- Response time P95: <500ms
- Errores en producción: <1%
```

---

## 🔧 Herramientas

- **pytest**: Test runner
- **httpx**: Cliente HTTP async
- **pytest-asyncio**: Support para tests async
- **Custom test runner**: Script con tokens configurables

---

## 📝 Notas

- Todos los tests se ejecutarán contra la API de producción con datos reales
- Se usarán tokens de test proporcionados por el usuario
- Se validará tanto el happy path como casos de error
- Se medirán tiempos de respuesta para cada endpoint
