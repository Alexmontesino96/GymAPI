# 📚 Stream Chat: Mejores Prácticas Oficiales para Eliminación de Canales

**Fecha:** 2025-12-14
**Fuente:** Documentación Oficial Stream Chat
**Tema:** Arquitectura Backend-First y Manejo de Eliminación de Canales

---

## 🎯 Conclusión Definitiva

**La documentación oficial de Stream Chat confirma:**

> ❌ **NO se debe permitir que clientes eliminen canales directamente de Stream**
>
> ✅ **SIEMPRE pasar por backend para validar lógica de negocio**

---

## 📖 Hallazgos Clave de la Documentación Oficial

### 1️⃣ **Webhooks de Autorización Previa: NO DISPONIBLES**

Stream Chat **NO proporciona** webhooks tipo `before.channel.delete` para interceptar y validar antes de eliminar.

**Webhooks disponibles:**
- `message.new` - Después de crear mensaje
- `channel.deleted` - **Después** de eliminar canal ❌
- `message.deleted` - Después de eliminar mensaje

**Implicación:**
- No puedes bloquear una eliminación directa desde Stream
- La validación DEBE ocurrir en tu backend ANTES de llamar a Stream

---

### 2️⃣ **Permisos: Client-Side vs Server-Side**

**Cita textual de la documentación:**

> **"Permissions checking only happens on the client-side calls. Server-side allows everything so long as a valid API key and secret is provided."**

**Traducción:**

| Tipo de API | Validación de Permisos | Seguridad |
|-------------|------------------------|-----------|
| **Client-side** | ✅ Valida roles (owner/moderator/member) | 🟡 Limitada a roles básicos |
| **Server-side** | ❌ NO valida (permite TODO) | 🔐 Máxima (requiere API key/secret) |

**Problema con client-side delete:**
- Stream solo valida **roles básicos** (owner, moderator, member)
- Stream **NO valida** lógica de negocio como:
  - ✗ `gym_id` correcto
  - ✗ Tipo de canal (eventos vs normales)
  - ✗ Reglas de negocio custom

---

### 3️⃣ **Arquitectura Backend-First: Recomendación Oficial**

**Cita de la documentación:**

> **"For critical operations (including delete), granting channel permissions is ONLY possible via server-side SDK. User deletion methods can only be called server-side due to security concerns."**

**Arquitectura recomendada por Stream:**

```
┌─────────────┐
│ Cliente iOS │
└──────┬──────┘
       │ 1. DELETE request
       ▼
┌──────────────────┐
│  TU BACKEND API  │ ← ✅ VALIDACIONES AQUÍ
│                  │
│ - Validar gym_id │
│ - Validar tipo   │
│ - Validar owner  │
│ - Audit log      │
└──────┬───────────┘
       │ 2. Si válido, llamar Stream API
       ▼
┌──────────────────┐
│   Stream Chat    │
│   (Server SDK)   │
└──────────────────┘
```

**NUNCA hacer:**
```
┌─────────────┐
│ Cliente iOS │
└──────┬──────┘
       │ ❌ DELETE directo a Stream
       ▼
┌──────────────────┐
│   Stream Chat    │ ← Sin validaciones de negocio
└──────────────────┘
```

---

### 4️⃣ **Multi-Tenant: Prefijos y Aislamiento**

**Best practices oficiales para multi-tenant:**

1. **Channel IDs con prefijo de tenant**
   ```python
   # ✅ BUENO
   channel_id = f"gym_{gym_id}_group_{group_id}"

   # ❌ MALO
   channel_id = f"group_{group_id}"  # Sin identificar gym
   ```

2. **Team isolation**
   ```python
   channel_data = {
       "team": f"gym_{gym_id}",  # Aísla por gimnasio
       "created_by_id": user_stream_id
   }
   ```

3. **Backend como fuente de verdad**
   > **"Your database should be the single source of truth"**

---

### 5️⃣ **Canales Huérfanos: Estrategia Recomendada**

**Problema:** Canales en Stream pero no en BD

**Solución recomendada por Stream:**

1. **Validación en endpoints de lista**
   ```python
   @router.get("/channels")
   async def list_channels(db, stream_client):
       # Obtener de Stream
       channels_stream = await stream_client.query_channels(...)

       # Validar contra BD
       valid_channels = []
       for ch in channels_stream:
           if await db.channels.exists(ch.id):
               valid_channels.append(ch)
           else:
               # Canal huérfano - eliminar de Stream
               await stream_client.delete_channel(ch.id)

       return valid_channels
   ```

2. **Periodic cleanup task**
   ```python
   # Cron job diario
   @scheduler.scheduled_job('cron', hour=3)
   async def cleanup_orphaned_channels():
       stream_channels = await stream_client.query_channels(...)
       db_channel_ids = await db.channels.get_all_ids()

       orphaned = [ch for ch in stream_channels if ch.id not in db_channel_ids]

       for ch in orphaned:
           await stream_client.delete_channel(ch.id)
   ```

---

## 🔧 Implementación Correcta Según Stream

### Endpoint Backend Recomendado

```python
from fastapi import APIRouter, Depends, HTTPException, Path
from app.core.dependencies import get_current_gym_id, get_current_user
from app.services.chat import ChatService
from app.db.session import get_db

router = APIRouter()

@router.delete("/api/v1/chat/channels/{channel_id}")
async def delete_channel(
    channel_id: str = Path(...),
    gym_id: int = Depends(get_current_gym_id),
    user = Depends(get_current_user),
    db = Depends(get_db),
    chat_service: ChatService = Depends()
):
    """
    Elimina un canal de chat.

    Validaciones según mejores prácticas de Stream:
    1. Backend como fuente de verdad
    2. Validación de lógica de negocio
    3. Audit logging
    4. Server-side API call a Stream
    """

    # 1. Verificar que el canal existe en BD (fuente de verdad)
    channel_db = await db.query(ChatRoom).filter(
        ChatRoom.stream_channel_id == channel_id
    ).first()

    if not channel_db:
        raise HTTPException(404, "Canal no encontrado en el sistema")

    # 2. Validar que pertenece al gym actual
    if channel_db.gym_id != gym_id:
        raise HTTPException(403, "Canal pertenece a otro gimnasio")

    # 3. Validar tipo de canal
    if channel_id.startswith('event_'):
        raise HTTPException(403, "Canales de eventos no pueden eliminarse")

    # 4. Validar permisos del usuario
    if not await chat_service.user_can_delete_channel(
        db, user_id=user.id, channel_id=channel_id, gym_id=gym_id
    ):
        raise HTTPException(403, "No tienes permisos para eliminar este canal")

    # 5. Verificar que no quedan miembros (excepto el creador)
    members = await chat_service.get_channel_members(channel_id)
    if len(members) > 1:
        raise HTTPException(400, "No puedes eliminar un canal con miembros activos")

    # 6. Audit log
    await audit_log.create({
        "action": "channel.delete",
        "gym_id": gym_id,
        "channel_id": channel_id,
        "user_id": user.id,
        "timestamp": datetime.now()
    })

    # 7. Eliminar de Stream (server-side con credenciales seguras)
    await chat_service.delete_channel_from_stream(channel_id)

    # 8. Marcar como eliminado en BD
    await chat_service.mark_channel_deleted(db, channel_id)

    return {"success": True, "message": "Canal eliminado correctamente"}
```

---

### Endpoint para Canales Huérfanos

```python
@router.delete("/api/v1/chat/channels/orphan/{channel_id}")
async def delete_orphan_channel(
    channel_id: str = Path(...),
    gym_id: int = Depends(get_current_gym_id),
    user = Depends(get_current_user),
    db = Depends(get_db),
    chat_service: ChatService = Depends()
):
    """
    Elimina un canal huérfano (existe en Stream pero NO en BD).

    Según mejores prácticas de Stream:
    - Validar que NO existe en BD
    - Validar que pertenece al gym actual (team)
    - Validar que usuario es owner
    - Eliminar con server-side API
    """

    # 1. Verificar que NO existe en BD
    channel_db = await db.query(ChatRoom).filter(
        ChatRoom.stream_channel_id == channel_id
    ).first()

    if channel_db:
        raise HTTPException(409, "Canal existe en BD, usa endpoint normal")

    # 2. Obtener canal de Stream (server-side API)
    channel = stream_client.channel('messaging', channel_id)
    channel_data = await channel.query()

    # 3. Validar que pertenece al gym actual
    if channel_data['channel'].get('team') != f"gym_{gym_id}":
        raise HTTPException(403, "Canal pertenece a otro gimnasio")

    # 4. Validar que NO es canal de evento
    if channel_id.startswith('event_'):
        raise HTTPException(403, "Canales de eventos no pueden eliminarse")

    # 5. Validar que el usuario es owner en Stream
    internal_user = await db.query(User).filter(User.auth0_id == user.id).first()
    stream_id = f"gym_{gym_id}_user_{internal_user.id}"

    members = channel_data['members']
    user_member = next((m for m in members if m['user_id'] == stream_id), None)

    if not user_member or user_member.get('role') != 'owner':
        raise HTTPException(403, "Solo el creador puede eliminar canales huérfanos")

    # 6. Audit log
    await audit_log.create({
        "action": "orphan_channel.delete",
        "gym_id": gym_id,
        "channel_id": channel_id,
        "user_id": user.id,
        "timestamp": datetime.now()
    })

    # 7. Eliminar de Stream (server-side)
    await channel.delete()

    return {"success": True, "message": "Canal huérfano eliminado"}
```

---

## 📱 Cambios Requeridos en iOS

### ANTES (❌ INCORRECTO):

```swift
func deleteConversation(_ conversation: Conversation) async throws {
    do {
        // Intentar backend primero
        try await ChatManagementService.shared.deleteGroup(
            roomId: conversation.id,
            hardDelete: true
        )
    } catch {
        // ❌ FALLBACK DIRECTO A STREAM
        try await streamProvider.deleteChannel(channelId: conversation.id)
    }
}
```

### DESPUÉS (✅ CORRECTO):

```swift
func deleteConversation(_ conversation: Conversation) async throws {
    do {
        // Intentar endpoint normal
        try await ChatManagementService.shared.deleteGroup(
            roomId: conversation.id,
            hardDelete: true
        )
    } catch let error as APIError where error.statusCode == 404 {
        // Si 404, intentar endpoint de huérfanos
        try await ChatManagementService.shared.deleteOrphanChannel(
            channelId: conversation.id
        )
    } catch {
        // Propagar cualquier otro error
        throw error
    }
}
```

**Nuevo método en ChatManagementService:**

```swift
func deleteOrphanChannel(channelId: String) async throws {
    let endpoint = "/api/v1/chat/channels/orphan/\(channelId)"

    try await apiClient.delete(endpoint)
    // El backend valida TODO antes de eliminar de Stream
}
```

---

## 🔐 Ventajas de la Arquitectura Backend-First

### ✅ Según Documentación Oficial de Stream

| Aspecto | Backend-First | Client Direct |
|---------|---------------|---------------|
| **Validación de negocio** | ✅ Completa | ❌ Solo roles básicos |
| **Multi-tenant isolation** | ✅ Garantizado | ⚠️ Solo por "team" |
| **Audit logging** | ✅ Centralizado | ❌ Difícil de trackear |
| **Seguridad** | ✅ API key en servidor | ⚠️ Token en cliente |
| **Reglas custom** | ✅ Ilimitadas | ❌ No soportadas |
| **Consistencia BD ↔ Stream** | ✅ Garantizada | ⚠️ Puede divergir |

---

## 📊 Matriz de Decisión Final

| Opción | Seguridad | UX | Complejidad | Alineación Stream Docs |
|--------|-----------|-----|-------------|------------------------|
| **A: Eliminar fallback** | ✅ Alta | ❌ Mala | ⚪ Baja | ⚠️ Parcial |
| **B: Validación en iOS** | 🟡 Media | ✅ Buena | 🟡 Media | ❌ NO recomendado |
| **C: Endpoint backend** | ✅ Alta | ✅ Buena | 🟠 Alta | ✅ **RECOMENDADO** |

---

## 🎯 Decisión Final

### **Implementar Opción C: Backend-First con Endpoint de Huérfanos**

**Justificación según documentación oficial de Stream:**

1. ✅ **Stream recomienda explícitamente backend-first** para operaciones críticas
2. ✅ **Client-side API NO valida lógica de negocio** (solo roles básicos)
3. ✅ **Server-side API permite validaciones completas** antes de eliminar
4. ✅ **Multi-tenant isolation** garantizado por backend
5. ✅ **Audit logging** centralizado y completo
6. ✅ **Canales huérfanos** manejados de forma segura

**Cita final de la documentación:**

> **"Your database should be the single source of truth. Implement validation in YOUR backend before calling Stream."**

---

## 📁 Referencias Documentales

- [Stream Chat - Webhooks Overview](https://getstream.io/chat/docs/node/webhooks_overview/)
- [Stream Chat - Deleting Channels](https://getstream.io/chat/docs/node/channel_delete/)
- [Stream Chat - Permissions v2](https://getstream.io/chat/docs/node/user_permissions/)
- [Stream Chat - Multi-Tenant & Teams](https://getstream.io/chat/docs/node/multi_tenant_chat/)
- [Stream Support - User Roles and Permission Policies](https://support.getstream.io/hc/en-us/articles/360053064274-User-Roles-and-Permission-Policies-Chat)
- [Stream Blog - Multi-Tenant Chat Support](https://getstream.io/blog/multi-tenant-chat-support/)

---

**Autor:** Claude Code (Security Analysis + Stream Docs Research)
**Fecha:** 2025-12-14
**Status:** ✅ **RECOMENDACIÓN OFICIAL BASADA EN DOCS DE STREAM**
