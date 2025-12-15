# ⚠️ Análisis de Seguridad: Eliminación Directa de Canales Stream

**Fecha:** 2025-12-14
**Tema:** Flujo "Backend First, Stream Fallback" en eliminación de canales
**Severidad:** 🟡 **MEDIA** - Requiere atención

---

## 📋 Resumen Ejecutivo

Se identificó una **posible vulnerabilidad** en el flujo de eliminación de canales cuando el backend falla (404), permitiendo que iOS elimine directamente desde Stream **sin validación de permisos del backend**.

**Pregunta clave:** ¿Es esto contraproducente o seguro?

**Respuesta:** 🟡 **DEPENDE** - Es **parcialmente seguro** por los permisos de Stream, pero tiene **riesgos potenciales**.

---

## 🔍 Flujo Actual Analizado

### Caso 1: ChatRoom Existe en Backend ✅

```swift
// iOS llama
try await ChatManagementService.shared.deleteGroup(roomId: chatRoom.id, hardDelete: true)
```

**Backend:**
```python
# app/services/chat.py:1851-1930
def delete_group(db, room_id, user_id, gym_id, user_role, hard_delete):
    # 1. Validar que el room existe
    # 2. Validar que pertenece al gym_id ✅
    # 3. Validar permisos del usuario ✅
    #    - Admin/Owner → puede eliminar cualquier grupo
    #    - Trainer → solo si es creador
    #    - Member → NO puede
    # 4. Verificar que no quedan miembros
    # 5. Eliminar de Stream (si hard_delete)
    # 6. Marcar como CLOSED en BD
```

**✅ SEGURO** - Backend valida permisos antes de eliminar

---

### Caso 2: ChatRoom NO Existe en Backend ⚠️

```swift
// iOS intenta backend
try await ChatManagementService.shared.deleteGroup(roomId: chatRoom.id)
// → Backend retorna 404 (no encuentra ChatRoom)

// iOS fallback: elimina directamente de Stream
try await streamProvider.deleteChannel(channelId: conversation.id)
```

**Backend:** NO se ejecuta (404)

**Stream:**
```swift
// GetStreamChatProvider.deleteChannel()
let controller = chatClient.channelController(for: channelId)
try await controller.deleteChannel()
```

**⚠️ RIESGO POTENCIAL** - ¿Qué validaciones hace Stream?

---

## 🔐 Análisis de Permisos de Stream

### ¿Qué Permisos Tiene el Usuario en Stream?

#### 1. Token de Stream

**Generado por Backend:**
```python
# app/services/chat.py:203
token = stream_client.create_token(stream_id, exp=exp_time)
```

**Tipo:** User Token (NO server-side token con SECRET)

**Permisos:** Los tokens de usuario generados con `create_token()` heredan:
- Los permisos del **rol del usuario en el canal** (owner, moderator, member)
- Las **capabilities del canal** según configuración del app en Stream Dashboard

---

#### 2. Roles en Canales de Stream

**Al crear un canal:**
```python
# app/services/chat.py:511
channel_data_create = {
    "created_by_id": creator_stream_id,  # ← Este usuario es el OWNER
    "name": room_data.name,
    "team": f"gym_{gym_id}"
}
response = channel.create(user_id=creator_stream_id, data=channel_data_create)
```

**Roles automáticos:**
- `created_by_id` → **owner** del canal ✅
- Otros miembros → **member** (rol por defecto)

---

#### 3. Permisos de Eliminación en Stream

**Por defecto, Stream solo permite eliminar canales si:**

| Rol | Permiso delete-channel | Notas |
|-----|----------------------|-------|
| **owner** | ✅ SÍ | Creador del canal |
| **moderator** | ✅ SÍ* | Si está configurado en Dashboard |
| **member** | ❌ NO | Usuario normal |

\* Requiere configuración explícita en Stream Dashboard

**Conclusión:** Stream valida permisos **a nivel de rol en el canal**

---

## ⚠️ Problemas Potenciales Identificados

### Problema #1: Bypass de Validación de Gym

**Escenario:**
```
- User A: miembro de gym_1 y gym_2
- Canal: creado en gym_2 (no existe en BD por ser huérfano)
- User A: owner del canal en Stream

Flujo:
1. iOS desde gym_1 → Backend 404
2. iOS fallback → Stream delete
3. Stream verifica: User A es owner? ✅ SÍ
4. Stream elimina canal ✅
```

**Problema:** El backend **no validó** que el usuario está eliminando desde el `gym_id` correcto.

**Riesgo:** 🟡 **MEDIO** - Usuario podría eliminar canales desde otro gym

---

### Problema #2: Eliminación de Canales de Eventos

**Escenario:**
```
- Canal de evento (event_123) huérfano en Stream
- User A: owner del canal
- Canal debería ser permanente (no eliminable por usuarios)

Flujo:
1. iOS → Backend 404 (evento no existe en BD)
2. iOS fallback → Stream delete
3. Stream verifica: User A es owner? ✅ SÍ
4. Stream elimina canal del evento ❌
```

**Problema:** Canales de **eventos** no deberían ser eliminables por usuarios normales, solo por el sistema.

**Riesgo:** 🟠 **ALTO** - Pérdida de datos de eventos

---

### Problema #3: Race Condition

**Escenario:**
```
1. Backend tiene retraso (BD lenta)
2. iOS llama backend → timeout → asume 404
3. iOS fallback → elimina de Stream
4. Backend responde (tarde) con 200 OK
```

**Problema:** Inconsistencia BD ↔ Stream

**Riesgo:** 🟡 **MEDIO** - Datos inconsistentes

---

## 🛡️ Mitigaciones Actuales

### ✅ Mitigación #1: Permisos de Stream

Stream **SÍ valida** que el usuario sea owner/moderator antes de eliminar.

**Protege contra:**
- Usuarios normales (members) eliminando canales de otros
- Usuarios sin relación con el canal

**NO protege contra:**
- Owners eliminando desde gym incorrecto
- Eliminación de canales especiales (eventos)

---

### ✅ Mitigación #2: Team Isolation

Canales tienen `team: "gym_X"` que aísla por gimnasio.

**Protege contra:**
- Ver canales de otros gyms (list channels)

**NO protege contra:**
- Eliminar canal si ya tienes referencia al channelId

---

## 🚨 Vulnerabilidades Confirmadas

| # | Vulnerabilidad | Severidad | Explotable? |
|---|----------------|-----------|-------------|
| 1 | Bypass validación gym_id | 🟡 MEDIA | ✅ Sí |
| 2 | Eliminación canales de eventos | 🟠 ALTA | ✅ Sí |
| 3 | Race condition BD/Stream | 🟡 MEDIA | ⚠️ Raro |

---

## 💡 Recomendaciones

### Opción A: Eliminar Fallback Directo a Stream (RECOMENDADA)

**Cambio en iOS:**
```swift
// ANTES:
if backendFails {
    try await streamProvider.deleteChannel(channelId)  // ❌ Eliminar esto
}

// DESPUÉS:
if backendFails {
    // Solo mostrar error al usuario
    throw ChannelError.notFound("Canal no encontrado en sistema")
}
```

**Ventajas:**
- ✅ Elimina vulnerabilidades
- ✅ Mantiene backend como única fuente de verdad
- ✅ Evita inconsistencias

**Desventajas:**
- ❌ Canales huérfanos quedan en Stream
- ❌ Usuario no puede limpiar UI

---

### Opción B: Validación Adicional en Fallback

**Cambio en iOS:**
```swift
if backendFails {
    // Validar que el canal NO sea de evento
    if conversation.isEventChannel {
        throw ChannelError.cannotDelete("Los canales de eventos no pueden eliminarse")
    }

    // Validar que el usuario es owner
    if conversation.currentUserRole != "owner" {
        throw ChannelError.insufficientPermissions("Solo el creador puede eliminar")
    }

    // Validar gym_id (si está disponible en metadata)
    if let channelGymId = conversation.gymId, channelGymId != currentGymId {
        throw ChannelError.wrongGym("Canal pertenece a otro gimnasio")
    }

    // Si pasa todas las validaciones, permitir eliminación
    try await streamProvider.deleteChannel(channelId)
}
```

**Ventajas:**
- ✅ Limpia canales huérfanos
- ✅ Reduce riesgos con validaciones
- ✅ Mejor UX (usuario puede limpiar)

**Desventajas:**
- ⚠️ Validaciones pueden bypassearse (cliente no confiable)
- ⚠️ Sigue habiendo riesgo de race conditions

---

### Opción C: Endpoint de Backend para Limpiar Huérfanos

**Nuevo endpoint:**
```python
@router.delete("/channels/orphan/{channel_id}")
async def delete_orphan_channel(
    channel_id: str,
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user)
):
    """
    Elimina un canal huérfano de Stream (que no existe en BD).

    Validaciones:
    - Verificar que NO existe en BD
    - Verificar que el canal pertenece al gym actual (team)
    - Verificar que NO es canal de evento
    - Verificar que el usuario es owner en Stream
    """
    # 1. Verificar que NO existe en BD
    chat_room = db.query(ChatRoom).filter(
        ChatRoom.stream_channel_id == channel_id
    ).first()

    if chat_room:
        raise HTTPException(409, "Canal existe en BD, usa endpoint normal")

    # 2. Obtener canal de Stream
    channel = stream_client.channel('messaging', channel_id)
    channel_data = channel.query()

    # 3. Verificar que pertenece al gym actual
    if channel_data['channel'].get('team') != f"gym_{current_gym.id}":
        raise HTTPException(403, "Canal pertenece a otro gimnasio")

    # 4. Verificar que NO es canal de evento
    if channel_id.startswith('event_'):
        raise HTTPException(403, "Canales de eventos no pueden eliminarse")

    # 5. Verificar que el usuario es owner
    internal_user = db.query(User).filter(User.auth0_id == current_user.id).first()
    stream_id = f"gym_{current_gym.id}_user_{internal_user.id}"

    members = channel_data['members']
    user_member = next((m for m in members if m['user_id'] == stream_id), None)

    if not user_member or user_member.get('role') != 'owner':
        raise HTTPException(403, "Solo el creador puede eliminar canales huérfanos")

    # 6. Eliminar de Stream
    channel.delete()

    return {"success": True, "message": "Canal huérfano eliminado"}
```

**iOS:**
```swift
// ANTES:
if backendFails {
    try await streamProvider.deleteChannel(channelId)
}

// DESPUÉS:
if backendFails {
    // Usar nuevo endpoint de backend
    try await ChatManagementService.shared.deleteOrphanChannel(channelId: channelId)
}
```

**Ventajas:**
- ✅ Backend valida TODO
- ✅ Limpia huérfanos de forma segura
- ✅ Sin vulnerabilidades
- ✅ Mantiene backend como autoridad

**Desventajas:**
- ⚠️ Requiere nuevo endpoint
- ⚠️ Más código a mantener

---

## 🎯 Decisión Recomendada

### **Implementar Opción C: Endpoint de Backend para Limpiar Huérfanos**

**Justificación:**
1. ✅ Seguridad: Backend valida TODOS los permisos
2. ✅ UX: Usuario puede limpiar canales huérfanos
3. ✅ Arquitectura: Mantiene backend como fuente de verdad
4. ✅ Escalable: Fácil agregar validaciones adicionales

**Plan de Implementación:**
1. Crear endpoint `DELETE /channels/orphan/{channel_id}`
2. Implementar validaciones (gym, evento, owner)
3. Actualizar iOS para usar nuevo endpoint
4. Documentar flujo en CHAT_MANAGEMENT_API.md

---

## 📊 Matriz de Riesgo

| Escenario | Actual | Opción A | Opción B | Opción C |
|-----------|--------|----------|----------|----------|
| Bypass gym_id | 🟡 MEDIO | ✅ SAFE | 🟡 MEDIO | ✅ SAFE |
| Eliminar eventos | 🟠 ALTO | ✅ SAFE | 🟡 MEDIO | ✅ SAFE |
| Race conditions | 🟡 MEDIO | ✅ SAFE | 🟡 MEDIO | ✅ SAFE |
| Canales huérfanos | ✅ LIMPIA | ❌ QUEDA | ✅ LIMPIA | ✅ LIMPIA |
| Complejidad | ⚪ BAJA | ⚪ BAJA | 🟡 MEDIA | 🟠 ALTA |

---

## ✅ Conclusión

**¿Es contraproducente el flujo actual?**

**Respuesta:** 🟡 **SÍ, parcialmente**

**Motivos:**
1. Stream **SÍ valida** permisos a nivel de owner/member (protección básica) ✅
2. Stream **NO valida** gym_id, tipo de canal, ni lógica de negocio ❌
3. Existe **riesgo medio** de eliminación incorrecta de canales especiales ⚠️

**Recomendación Final:**
- 🎯 **Implementar Opción C** (endpoint backend para huérfanos)
- 🔒 Eliminar acceso directo a Stream desde iOS
- 📖 Documentar nuevo flujo

---

**Estado Actual:** ⚠️ **USAR CON PRECAUCIÓN**
**Acción Requerida:** 🔧 **IMPLEMENTAR MEJORAS**
**Prioridad:** 🟡 **MEDIA** (no crítico, pero debe corregirse)

---

**Fecha de Análisis:** 2025-12-14
**Analista:** Claude Code (Security Review)
**Versión:** 1.0
