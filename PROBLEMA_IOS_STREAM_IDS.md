# 🔴 PROBLEMA CRÍTICO: iOS no puede acceder a canales de Stream Chat

**Fecha:** 2025-12-15
**Severidad:** CRÍTICA - Chat completamente roto en iOS
**Estado:** REQUIERE MIGRACIÓN DE DATOS URGENTE

---

## 🐛 Error Reportado

```
ERROR: GetOrCreateChannel failed with error:
"User 'gym_4_user_10' with role 'user' from team 'gym_4'
is not allowed to perform action ReadChannel in scope 'messaging'"

Status Code: 403
```

---

## 🔍 Análisis del Problema

### Estado Actual del Sistema

#### 1. **Backend (Código corregido ✅)**
```python
# Token generado para iOS
user_stream_id = "gym_4_user_10"  # Formato multi-tenant ✅
team = "gym_4"
```

#### 2. **Base de Datos (NO migrada ❌)**
```sql
-- ChatRoom table
stream_channel_id = "direct_user_10_user_8"  # Formato legacy ❌
```

#### 3. **Stream.io (NO migrado ❌)**
```javascript
// Canal existente
channel_id: "direct_user_10_user_8"
members: ["user_10", "user_8"]  // Legacy ❌
```

### Flujo del Error

```
1. iOS solicita salas de chat a /api/v1/chat/my-rooms
   ↓
2. Backend devuelve desde BD:
   {
     "stream_channel_id": "direct_user_10_user_8",  // Legacy
     "name": "Chat Alex Montesino - Jose Paul Rodriguez"
   }
   ↓
3. iOS conecta a Stream con:
   - Usuario: "gym_4_user_10" (multi-tenant)
   - Team: "gym_4"
   ↓
4. iOS intenta acceder al canal: "direct_user_10_user_8"
   ↓
5. Stream verifica permisos:
   - Canal "direct_user_10_user_8" tiene miembros: ["user_10", "user_8"]
   - Usuario solicitante: "gym_4_user_10"
   - "gym_4_user_10" NO está en la lista de miembros
   ↓
6. Stream RECHAZA con 403 Forbidden ❌
```

---

## ❌ POR QUÉ FALLA

### Problema de Identidad
- El usuario `gym_4_user_10` es una **identidad diferente** a `user_10`
- Stream los ve como **dos usuarios distintos**
- Aunque representan a la misma persona, tienen IDs diferentes

### Problema de Membresía
- Canal legacy tiene miembros: `["user_10", "user_8"]`
- Usuario conectado: `gym_4_user_10`
- **NO hay match** → Acceso denegado

### Problema de Teams
- Usuario tiene `team: "gym_4"`
- Stream aplica **team-based permissions**
- Los canales legacy **no tienen team asignado** o tienen configuración incorrecta

---

## 🎯 CAUSA RAÍZ

**LA MIGRACIÓN DE DATOS NO SE EJECUTÓ**

Aunque corregimos el código en commit `05dd685` y `f413ffa`:
- ✅ Backend genera usuarios multi-tenant: `gym_4_user_10`
- ✅ Código crea canales con formato correcto
- ❌ **Datos existentes NO fueron migrados**
- ❌ Canales en BD siguen con IDs legacy
- ❌ Canales en Stream siguen con miembros legacy

---

## 🚨 IMPACTO

### Funcionalidad Afectada
- ❌ **Chat completamente roto** en iOS
- ❌ Usuarios no pueden abrir conversaciones existentes
- ❌ Usuarios no pueden enviar/recibir mensajes
- ⚠️ Nuevas conversaciones podrían funcionar (con formato correcto)

### Usuarios Afectados
- **Gimnasio 4:** 3 canales reportados (probablemente más)
- **Otros gimnasios:** Mismo problema esperado
- **100% de usuarios** con chats existentes afectados

### Datos de los Logs
```
✅ Salas cargadas desde API: 3
   - direct_user_10_user_8
   - room_General_10
   - direct_user_10_user_11

❌ Error 403 en TODAS (3/3)
```

---

## ✅ SOLUCIONES

### Opción A: EJECUTAR MIGRACIÓN (RECOMENDADO - URGENTE)

**Qué hace:**
1. Crea usuarios en Stream con IDs multi-tenant
2. Crea nuevos canales con IDs multi-tenant
3. Agrega usuarios multi-tenant como miembros
4. Actualiza BD con nuevos `stream_channel_id`

**Cómo ejecutar:**
```bash
# Desde servidor Render (requiere acceso SSH)
python scripts/migrate_stream_with_users.py --gym-id 4

# Validar
python scripts/audit_stream_sync.py --gym-id 4
```

**Resultado esperado:**
```javascript
// ANTES
channel_id: "direct_user_10_user_8"
members: ["user_10", "user_8"]

// DESPUÉS
channel_id: "direct_gym_4_user_10_gym_4_user_8"
members: ["gym_4_user_10", "gym_4_user_8"]
```

**Documentación:** Ver `MIGRACION_STREAM_MULTI_TENANT_FINAL.md`

---

### Opción B: PARCHE TEMPORAL EN BACKEND (NO RECOMENDADO)

**Transformar IDs al devolver a iOS:**

```python
# En /api/v1/chat/my-rooms
for room in rooms:
    # Convertir legacy a multi-tenant
    if not room.stream_channel_id.startswith(f"gym_{current_gym.id}"):
        # Transformar ID
        room.stream_channel_id = convert_to_multitenant(
            room.stream_channel_id,
            current_gym.id
        )
```

**Problemas:**
- ❌ Stream aún no tiene esos canales
- ❌ iOS seguiría recibiendo 403
- ❌ No resuelve el problema de fondo
- ❌ Solo mueve el error a otro lugar

**NO IMPLEMENTAR - Solo documentado para referencia**

---

### Opción C: HOTFIX - Usar usuarios legacy temporalmente

**Revertir código a generar usuarios legacy:**

**Problemas:**
- ❌ Regresión de todas las correcciones
- ❌ Rompe multi-tenancy
- ❌ No es solución, solo oculta el problema
- ❌ Crea más deuda técnica

**NO IMPLEMENTAR**

---

## 🎯 SOLUCIÓN RECOMENDADA

### **EJECUTAR MIGRACIÓN INMEDIATAMENTE**

**Prioridad:** CRÍTICA P0
**Tiempo estimado:** 15-30 minutos
**Downtime:** Ninguno (migración en background)

### Pasos:

1. **Acceder al servidor de producción**
   ```bash
   render ssh <servicio-gymapi>
   ```

2. **Dry-run para gimnasio 4**
   ```bash
   python scripts/migrate_stream_with_users.py --gym-id 4 --dry-run
   ```

3. **Revisar output**
   - Verificar usuarios a crear
   - Verificar canales a migrar
   - Confirmar que todo se ve correcto

4. **Ejecutar migración real**
   ```bash
   python scripts/migrate_stream_with_users.py --gym-id 4
   ```

5. **Validar resultado**
   ```bash
   python scripts/audit_stream_sync.py --gym-id 4
   # Debe mostrar: "synced": 100%
   ```

6. **Test desde iOS**
   - Cerrar y reabrir app
   - Abrir chat existente
   - Enviar mensaje
   - Verificar que funciona

7. **Migrar otros gimnasios**
   ```bash
   python scripts/migrate_stream_with_users.py  # Todos los gyms
   ```

---

## 📊 VERIFICACIÓN POST-MIGRACIÓN

### Checks en Stream Dashboard
1. Ir a https://dashboard.getstream.io/
2. Verificar usuarios: `gym_4_user_10`, `gym_4_user_11`, etc.
3. Verificar canales con formato multi-tenant
4. Verificar membresías correctas

### Checks en iOS
- [ ] App conecta sin errores
- [ ] Lista de chats se carga correctamente
- [ ] Chats se abren sin error 403
- [ ] Mensajes se envían/reciben correctamente
- [ ] No hay errores en logs

### Checks en Backend
```bash
# Verificar BD
SELECT stream_channel_id FROM chat_rooms WHERE gym_id = 4;
# Debe mostrar: direct_gym_4_user_X_gym_4_user_Y

# Verificar auditoría
cat audit_stream_sync_*.json | grep "synced"
# Debe mostrar: "synced": 100%
```

---

## 🔒 PREVENCIÓN FUTURA

### 1. Tests de integración
Agregar tests que verifiquen:
- Usuario puede conectarse a Stream
- Usuario puede acceder a sus canales
- IDs tienen formato multi-tenant correcto

### 2. Monitoreo
- Alert si hay errores 403 en Stream
- Dashboard de sincronización BD ↔ Stream
- Audit diario automático

### 3. Documentación
- ✅ `MIGRACION_STREAM_MULTI_TENANT_FINAL.md`
- ✅ Este documento de troubleshooting

---

## 📝 NOTAS

### Archivos de referencia
- `MIGRACION_STREAM_MULTI_TENANT_FINAL.md` - Guía de migración
- `FIX_STREAM_MULTI_TENANT.md` - Análisis original
- `scripts/migrate_stream_with_users.py` - Script de migración
- `scripts/audit_stream_sync.py` - Script de auditoría

### Commits relacionados
- `ccac27b` - Fix job de contadores diarios
- `05dd685` - Completar migración a multi-tenant (código)
- `f413ffa` - Implementar Stream IDs multi-tenant (código)

### Estado actual (2025-12-15)
- ✅ Código backend 100% corregido
- ✅ Tests pasando (3/3)
- ❌ Datos NO migrados
- ❌ iOS NO funcional
- 🔴 **REQUIERE MIGRACIÓN URGENTE**

---

**ACCIÓN REQUERIDA:** Ejecutar migración de datos desde servidor de producción
**Responsable:** Alex Montesino
**ETA:** Inmediato
