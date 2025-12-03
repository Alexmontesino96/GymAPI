# ROADMAP COMPLETO DE MIGRACIÓN ASYNC - FASE 2

## 📊 Análisis Completo del Proyecto

**Total de endpoints identificados**: ~297 endpoints en 36 archivos

---

## 🔥 PRIORIDAD ALTA (Críticos de Performance)

### 1. **users.py** - 27 endpoints (1 migrado = 26 pendientes)
**Estado**: 🟡 1/27 migrado (4%)
- ✅ GET /profile/me - MIGRADO
- ⏳ GET /profile
- ⏳ PUT /profile
- ⏳ POST /profile/image
- ⏳ POST /profile/data
- ⏳ GET /last-attendance
- ⏳ GET /check-email-availability
- ⏳ POST /change-email
- ⏳ POST /sync-email (webhook)
- ⏳ GET /{user_id}
- ⏳ PUT /{user_id}
- ⏳ DELETE /{user_id}
- ⏳ PUT /{user_id}/role
- ⏳ GET / (list users)
- ⏳ GET /search
- ⏳ GET /public/{user_id}
- ⏳ Y ~11 endpoints más de gestión de usuarios

**Impacto**: MUY ALTO - Usado en casi todas las requests
**Estimado**: 2-3 días

---

### 2. **gyms.py** - 15 endpoints
**Estado**: 🔴 0/15 migrado (0%)
- ⏳ GET / (list gyms)
- ⏳ POST / (create gym)
- ⏳ GET /{gym_id}
- ⏳ PUT /{gym_id}
- ⏳ DELETE /{gym_id}
- ⏳ POST /{gym_id}/members
- ⏳ GET /{gym_id}/members
- ⏳ DELETE /{gym_id}/members/{user_id}
- ⏳ PUT /{gym_id}/members/{user_id}/role
- ⏳ GET /{gym_id}/stats
- ⏳ Y ~5 endpoints más

**Impacto**: MUY ALTO - Base de arquitectura multi-tenant
**Estimado**: 2 días

---

### 3. **schedule/classes.py** - 8 endpoints
**Estado**: 🔴 0/8 migrado (0%)
- ⏳ GET / (list classes)
- ⏳ POST / (create class)
- ⏳ GET /{class_id}
- ⏳ PUT /{class_id}
- ⏳ DELETE /{class_id}
- ⏳ POST /{class_id}/duplicate
- ⏳ GET /{class_id}/participants
- ⏳ GET /instructor/{instructor_id}

**Impacto**: ALTO - Feature core del negocio
**Estimado**: 1 día

---

### 4. **schedule/sessions.py** - 12 endpoints
**Estado**: 🔴 0/12 migrado (0%)
- ⏳ GET / (list sessions)
- ⏳ POST / (create session)
- ⏳ GET /{session_id}
- ⏳ PUT /{session_id}
- ⏳ DELETE /{session_id}
- ⏳ POST /{session_id}/check-in
- ⏳ GET /{session_id}/attendance
- ⏳ GET /upcoming
- ⏳ GET /past
- ⏳ Y ~3 endpoints más

**Impacto**: ALTO - Operaciones diarias
**Estimado**: 1-2 días

---

### 5. **schedule/participation.py** - 13 endpoints
**Estado**: 🔴 0/13 migrado (0%)
- ⏳ POST /reserve
- ⏳ DELETE /cancel
- ⏳ GET /my-reservations
- ⏳ GET /session/{session_id}/participants
- ⏳ POST /waitlist
- ⏳ Y ~8 endpoints más

**Impacto**: ALTO - UX crítico
**Estimado**: 1-2 días

---

## ⚡ PRIORIDAD MEDIA (Performance y Features)

### 6. **events.py** - 19 endpoints
**Estado**: 🔴 0/19 migrado (0%)
**Impacto**: MEDIO - Feature importante pero menos frecuente
**Estimado**: 2 días

### 7. **attendance.py** - 1 endpoint
**Estado**: 🔴 0/1 migrado (0%)
- ⏳ POST /check-in
**Impacto**: ALTO - Crítico pero simple
**Estimado**: 1 hora

### 8. **activity_feed.py** - 8 endpoints
**Estado**: 🔴 0/8 migrado (0%)
**Impacto**: MEDIO - Social features
**Estimado**: 1 día

### 9. **chat.py** - 21 endpoints
**Estado**: 🔴 0/21 migrado (0%)
**Impacto**: MEDIO-ALTO - Tiempo real
**Estimado**: 2-3 días

### 10. **schedule/** (otros módulos)
- **gym_hours.py**: 6 endpoints
- **categories.py**: 5 endpoints
- **special_days.py**: 7 endpoints
**Estimado**: 1-2 días total

---

## 📝 PRIORIDAD BAJA (Menos Frecuentes)

### 11. **nutrition.py** - 33 endpoints
**Estado**: 🔴 0/33 migrado (0%)
**Impacto**: BAJO - Módulo opcional
**Estimado**: 3-4 días

### 12. **memberships.py** - 24 endpoints
**Estado**: 🔴 0/24 migrado (0%)
**Impacto**: MEDIO - Billing
**Estimado**: 2-3 días

### 13. **posts.py** - 20 endpoints
**Estado**: 🔴 0/20 migrado (0%)
**Impacto**: BAJO - Social features
**Estimado**: 2 días

### 14. **stories.py** - 12 endpoints
**Estado**: 🔴 0/12 migrado (0%)
**Impacto**: BAJO - Social features
**Estimado**: 1 día

### 15. **surveys.py** - 15 endpoints
**Estado**: 🔴 0/15 migrado (0%)
**Impacto**: BAJO - Feedback
**Estimado**: 1-2 días

### 16. **Otros módulos** (~50 endpoints restantes)
- trainer_member.py: 9
- user_dashboard.py: 7
- notification.py: 5
- stripe_connect.py: 5
- modules.py: 6
- webhooks/stream_webhooks.py: 8
- auth/*: ~18
- Y otros...
**Estimado**: 3-5 días total

---

## 📅 CRONOGRAMA ESTIMADO

### **Sprint 1: Core Users & Gyms** (Días 1-5)
- ✅ Día 1: user_service async (COMPLETADO)
- ✅ Día 1: GET /profile/me (COMPLETADO)
- 🔄 Día 2: Resto de users.py (26 endpoints)
- 📅 Día 3-4: gyms.py (15 endpoints)
- 📅 Día 5: Testing y validación

### **Sprint 2: Schedule Core** (Días 6-12)
- 📅 Día 6-7: schedule/classes.py (8)
- 📅 Día 8-9: schedule/sessions.py (12)
- 📅 Día 10-11: schedule/participation.py (13)
- 📅 Día 12: Testing y validación

### **Sprint 3: Events & Attendance** (Días 13-18)
- 📅 Día 13-14: events.py (19)
- 📅 Día 15: attendance.py (1)
- 📅 Día 16: activity_feed.py (8)
- 📅 Día 17-18: Testing y validación

### **Sprint 4: Chat & Social** (Días 19-25)
- 📅 Día 19-21: chat.py (21)
- 📅 Día 22-23: posts.py (20)
- 📅 Día 24: stories.py (12)
- 📅 Día 25: Testing

### **Sprint 5: Business Logic** (Días 26-35)
- 📅 Día 26-28: memberships.py (24)
- 📅 Día 29-32: nutrition.py (33)
- 📅 Día 33-34: surveys.py (15)
- 📅 Día 35: Testing

### **Sprint 6: Finales & Polish** (Días 36-42)
- 📅 Día 36-38: Módulos restantes (~50)
- 📅 Día 39-40: Testing completo
- 📅 Día 41-42: Performance tuning y documentación

---

## 🎯 MÉTRICAS DE ÉXITO

### Por Sprint:
- ✅ Todos los tests pasan
- ✅ P95 latency <100ms en endpoints migrados
- ✅ Sin errores en logs de staging (24h)
- ✅ Code coverage >80%

### Final (6 semanas):
- 🎯 297 endpoints migrados a async
- 🎯 P50: <30ms
- 🎯 P95: <100ms
- 🎯 P99: <200ms
- 🎯 Throughput: >1000 req/s
- 🎯 Error rate: <0.01%

---

## 📋 CHECKLIST POR ENDPOINT

Antes de marcar como completo:
- [ ] Cambiar `Session` → `AsyncSession`
- [ ] Cambiar `get_db()` → `get_async_db()`
- [ ] Cambiar service calls a versión `_async()`
- [ ] Agregar `await` donde corresponda
- [ ] Usar eager loading si hay relaciones
- [ ] Actualizar tests
- [ ] Verificar invalidación de caché
- [ ] Performance test (<100ms P95)
- [ ] Documentar cambios

---

**Última actualización**: 2025-12-02
**Estado actual**: SEMANA 1 - user_repository ✅ COMPLETADO → gym_repository en progreso

## 🚀 ACTUALIZACIÓN SEMANA 1 - DÍA 1

### ✅ user_repository: 15/15 métodos async (100% COMPLETADO)

✅ **Métodos async completados (11 específicos de User):**
1. `get_by_email_async()` - Query simple por email
2. `get_by_auth0_id_async()` - CRÍTICO - Autenticación
3. `get_by_role_async()` - Filtrado por rol con paginación
4. `get_by_role_and_gym_async()` - Filtrado por rol y gym
5. `search_async()` - Búsqueda avanzada con múltiples filtros
6. `get_public_participants_async()` - Perfiles públicos de participantes
7. `get_gym_participants_async()` - Usuarios completos de un gym
8. `create_async()` - CRUD - Creación de usuarios
9. `update_async()` - CRUD - Actualización de usuarios
10. `create_from_auth0_async()` - Creación desde Auth0
11. `get_all_gym_users_async()` - Todos los usuarios de un gym

✅ **Métodos async de BaseRepository (4):**
12. `get_async()` - Obtener usuario por ID con tenant filter
13. `get_multi_async()` - Obtener múltiples usuarios con filtros
14. `remove_async()` - Eliminar usuario con verificación tenant
15. `exists_async()` - Verificar existencia con tenant filter

**Commits realizados:**
- `94c3ab0` - 7 primeros métodos async
- `84cf526` - 4 métodos adicionales async
- `dfd10b9` - 4 métodos BaseRepository async ✅ **COMPLETADO**

**Siguiente:** gym_repository (12 métodos estimados)

---

**Última actualización**: 2025-12-02
**Estado anterior**: Sprint 1 - Día 2 (users.py en progreso)
