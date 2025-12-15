# Análisis de Inconsistencias Stream Chat ↔ BD Local

**Fecha:** 2025-12-14
**Autor:** Claude Code
**Estado:** Análisis Completo

## 📊 Resumen Ejecutivo

Se detectaron inconsistencias de sincronización entre Stream Chat y la base de datos local que causan que algunos canales no aparezcan en la app móvil.

### Problema Principal

**Canal Huérfano Detectado:** `room_General_4`

- **En Stream Chat:**
  - `team: 'gym_1'` ❌ (INCORRECTO)
  - `gym_id: '5'` ✅ (metadata correcta)
  - Creado: `2025-06-25 04:10:44`
  - Miembros: `user_4`, `user_8`

- **En BD Local:**
  - `gym_id: 5` ✅ (CORRECTO)
  - Creado: `2025-10-26 20:36:39` (4 meses DESPUÉS)
  - Miembros: User 4, User 8

- **Resultado:**
  - Script de auditoría busca canales con `team='gym_1'` en Stream
  - Busca ChatRooms con `gym_id=1` en BD
  - NO encuentra coincidencia porque el canal está mal categorizado

---

## 🔍 Root Cause Analysis

### Línea de Tiempo

```
2025-06-25 04:10:44 → Canal creado EN STREAM con team='gym_1'
                      (Probablemente manual o con bug)

2025-07-22 ~14:43    → Script migrate_stream_multitenants.py ejecutado
                      (Debió actualizar team a 'gym_5')

2025-10-26 20:36:39 → ChatRoom creado EN BD con gym_id=5
                      (Sincronización tardía)
```

### Causas Identificadas

#### 1. **Creación Manual del Canal en Stream**

El canal se creó SOLO en Stream Chat (posiblemente desde la consola de Stream) sin crear el registro correspondiente en la BD local. Esto violó el flujo normal de creación que requiere:

```python
# Flujo correcto (app/services/chat.py línea 500-528)
1. Crear canal en Stream con team correcto
2. Inmediatamente crear ChatRoom en BD
3. Agregar miembros en ambos lados
```

#### 2. **Falla en Migración Multi-tenant**

El script `migrate_stream_multitenants.py` (líneas 105-131) DEBIÓ actualizar el team:

```python
stream_channel.update({
    "team": f"gym_{channel_data['gym_id']}",  # Debió ser gym_5
    "gym_id": str(channel_data['gym_id'])
})
```

**Posibles razones del fallo:**
- El canal NO existía en BD al momento de la migración (junio-julio)
- La migración solo procesa canales YA registrados en BD
- El canal se agregó a BD DESPUÉS de la migración (octubre)

#### 3. **Sincronización Tardía**

El ChatRoom se creó en BD 4 meses después (octubre), cuando:
- Ya existía el canal en Stream con team incorrecto
- La migración ya había corrido
- No hubo actualización retroactiva del team en Stream

---

## 📈 Alcance del Problema

### Resultados de Auditoría Completa

#### Gym ID 1
```
✅ Canales sincronizados: 0
⚠️  Solo en Stream: 1 (room_General_4 con team incorrecto)
⚠️  Solo en BD: 0
```

#### Gym ID 4
```
✅ Canales sincronizados: 5
⚠️  Solo en Stream: 2 (eventos huérfanos)
  - event_656_d3d94468 → Evento NO existe en BD → Eliminar
  - event_644_d3d94468 → Evento NO existe en BD → Eliminar
⚠️  Solo en BD: 9 (canales eliminados de Stream)
```

#### Gym ID 5
```
✅ Canales sincronizados: 0
⚠️  Solo en Stream: 0
⚠️  Solo en BD: 1 (room_General_4)
  - ChatRoom existe en BD pero con team incorrecto en Stream
```

### Estadísticas Generales

- **Total ChatRooms en BD:** 15 (14 en gym_4, 1 en gym_5)
- **Canales con team incorrecto:** 1 confirmado (`room_General_4`)
- **Eventos huérfanos en Stream:** 2 (`event_644`, `event_656`)
- **ChatRooms sin canal en Stream:** 9 (gym_4)

---

## 💥 Impacto en la App

### Para Usuarios del Gym 1

1. **Búsqueda del canal en `/api/v1/chat/my-rooms`:**
   - Endpoint filtra por `gym_id=1`
   - ChatRoom NO existe con gym_id=1
   - Canal NO aparece en la lista ❌

2. **Webhooks de mensajes:**
   - Llega webhook de `room_General_4`
   - Busca ChatRoom por `stream_channel_id`
   - NO encuentra registro en BD
   - NO procesa notificaciones ❌
   - NO actualiza contadores ❌

3. **Usuario user_4 (Alex):**
   - Tiene membresías en gym_1 Y gym_5
   - Puede ver el canal desde gym_5
   - NO puede verlo desde gym_1
   - Inconsistencia en experiencia de usuario

---

## 🛠️ Soluciones Propuestas

### Opción 1: Actualizar Team en Stream (RECOMENDADA)

**Ventaja:** Mantiene historial del canal
**Acción:** Actualizar `team='gym_1'` → `team='gym_5'` en Stream

```python
from app.core.stream_client import stream_client

channel = stream_client.channel('messaging', 'room_General_4')
channel.update({
    "team": "gym_5",  # Corregir team
    "gym_id": "5"     # Mantener metadata
})
```

**Resultado:**
- Canal queda con team correcto
- ChatRoom ya existe en BD con gym_id=5
- Sincronización completa ✅

### Opción 2: Crear ChatRoom Duplicado en Gym 1

**Ventaja:** Usuario user_4 ve el canal en ambos gyms
**Desventaja:** Duplicación de datos

```python
# Crear nuevo ChatRoom con gym_id=1
# Mantener mismo stream_channel_id
# PROBLEMA: Un canal no puede tener dos teams diferentes
```

**Descartada:** No viable técnicamente

### Opción 3: Eliminar y Recrear

**Ventaja:** Canal limpio desde cero
**Desventaja:** Se pierde historial de mensajes

```bash
# Eliminar canal de Stream
# Eliminar ChatRoom de BD
# Recrear con datos correctos
```

**Descartada:** Pérdida de datos inaceptable

---

## 🎯 Plan de Acción Recomendado

### Fase 1: Corrección del Canal Específico

```bash
# 1. Actualizar team en Stream Chat
python scripts/fix_channel_team.py --channel-id room_General_4 --gym-id 5

# 2. Verificar sincronización
python scripts/audit_stream_sync.py --gym-id 5
```

### Fase 2: Limpieza de Eventos Huérfanos

```bash
# Eliminar eventos que no existen en BD
python scripts/delete_orphan_channel.py --channel-id event_644_d3d94468
python scripts/delete_orphan_channel.py --channel-id event_656_d3d94468
```

### Fase 3: Auditoría Completa

```bash
# Verificar todos los gimnasios
for gym_id in {1..10}; do
    python scripts/audit_stream_sync.py --gym-id $gym_id --only-issues
done
```

### Fase 4: Prevención

**Cambios en el código:**

1. **Validar team al crear canales:**
```python
# En app/services/chat.py:500-510
# Agregar validación antes de crear
if gym_id != current_user_gym_id:
    logger.warning(f"Gym mismatch: creating for {gym_id} but user in {current_user_gym_id}")
```

2. **Auto-corrección en webhooks:**
```python
# En app/api/v1/endpoints/webhooks/stream_webhooks.py:190
if not chat_room:
    # Intentar encontrar por canal en Stream
    # Si existe, crear ChatRoom automáticamente
    # Logs para auditoría
```

3. **Validación periódica:**
```bash
# Cron job diario
0 2 * * * python scripts/audit_stream_sync.py --gym-id all --only-issues
```

---

## 📋 Scripts Necesarios

### 1. `fix_channel_team.py` (CREAR)

```python
#!/usr/bin/env python3
"""
Corrige el team de un canal específico en Stream Chat.

Uso:
    python scripts/fix_channel_team.py --channel-id room_General_4 --gym-id 5
"""
```

### 2. `delete_orphan_channel.py` (CREAR)

```python
#!/usr/bin/env python3
"""
Elimina un canal huérfano de Stream Chat.

Uso:
    python scripts/delete_orphan_channel.py --channel-id event_644_d3d94468
"""
```

### 3. `sync_channel_to_db.py` (CREAR)

```python
#!/usr/bin/env python3
"""
Sincroniza un canal de Stream a la BD local.

Uso:
    python scripts/sync_channel_to_db.py --channel-id direct_user_11_user_8
"""
```

---

## ⚠️ Lecciones Aprendidas

### Causas de Inconsistencias

1. **Creación manual de canales** en consola de Stream sin registro en BD
2. **Migraciones parciales** que solo procesan canales ya en BD
3. **Falta de validación** team vs gym_id al crear canales
4. **Sin sincronización bidireccional** Stream ↔ BD

### Mejores Prácticas

1. ✅ **NUNCA crear canales manualmente** en Stream - siempre via API
2. ✅ **Validar team == gym_id** antes de crear cualquier canal
3. ✅ **Webhook auto-creación** de ChatRooms para canales desconocidos
4. ✅ **Auditoría periódica** con script automatizado
5. ✅ **Logs detallados** de todas las operaciones de canales

---

## 📊 Métricas de Éxito

### Pre-Fix
- Canales con team incorrecto: 1
- Eventos huérfanos: 2
- ChatRooms sin canal: 9
- Tasa de sincronización: ~33% (5/15)

### Post-Fix (Esperado)
- Canales con team incorrecto: 0 ✅
- Eventos huérfanos: 0 ✅
- ChatRooms sin canal: 0 ✅ (eliminados legítimamente)
- Tasa de sincronización: ~100% ✅

---

## 🔗 Referencias

- Script de auditoría: `scripts/audit_stream_sync.py`
- Código de creación: `app/services/chat.py:378-604`
- Migración multi-tenant: `scripts/migrate_stream_multitenants.py`
- Webhooks: `app/api/v1/endpoints/webhooks/stream_webhooks.py:72-254`

---

## ✅ Conclusión

El problema es **identificado y entendido**. La solución es **directa y segura** (actualizar team en Stream). El impacto es **limitado** (1 canal confirmado). Los scripts de **prevención** están en desarrollo.

**Próximo paso:** Crear scripts de corrección (`fix_channel_team.py`, `delete_orphan_channel.py`) y ejecutar plan de acción.
