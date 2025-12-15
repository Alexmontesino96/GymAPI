# 📱 Guía para Frontend iOS - Eliminación de Chats

**Audiencia:** Desarrolladores iOS
**Objetivo:** Entender qué endpoint usar en cada caso para eliminar chats/canales
**Última actualización:** 2025-12-14

---

## 📋 Tabla de Contenidos

- [Resumen Rápido](#resumen-rápido)
- [3 Endpoints Disponibles](#3-endpoints-disponibles)
- [Árbol de Decisión](#árbol-de-decisión)
- [Flujo Recomendado](#flujo-recomendado)
- [Implementación Swift](#implementación-swift)
- [Manejo de Errores](#manejo-de-errores)
- [Casos de Uso Reales](#casos-de-uso-reales)
- [FAQs](#faqs)

---

## Resumen Rápido

### ¿Qué endpoint usar?

```
┌─ ¿El usuario quiere eliminar un chat?
│
├─ ¿Es un chat 1-to-1?
│  │
│  ├─ ¿Quiere eliminar solo los mensajes? → DELETE /rooms/{id}/conversation
│  └─ ¿Quiere solo ocultarlo? → POST /rooms/{id}/hide
│
└─ ¿Es un grupo?
   │
   ├─ ¿Quiere salir del grupo? → POST /rooms/{id}/leave
   └─ ¿Es admin y quiere eliminarlo? → DELETE /rooms/{id}
       │
       └─ Si retorna 404 → DELETE /channels/orphan/{channel_id}
```

---

## 3 Endpoints Disponibles

### 1️⃣ Eliminar Grupo Normal (Cuando existe en BD)

```http
DELETE /api/v1/chat/rooms/{room_id}?hard_delete=true
```

**Cuándo usar:**
- ✅ Eliminar un grupo que creaste
- ✅ Eres admin y quieres eliminar cualquier grupo
- ✅ El grupo está vacío (sin miembros)

**Requisitos:**
- 🔐 Debes ser admin/owner o creador del grupo
- 👥 El grupo DEBE estar vacío (0 miembros)
- 📊 El `room_id` debe existir en la base de datos

**Respuesta exitosa (200):**
```json
{
  "success": true,
  "message": "Grupo 'Entrenamiento Matutino' eliminado exitosamente",
  "room_id": 123,
  "deleted_from_stream": true
}
```

**Errores comunes:**
```json
// 404 - Room no existe en BD
{
  "detail": "Sala de chat 123 no encontrada"
}

// 400 - Grupo tiene miembros
{
  "detail": "Debes remover a todos los miembros (3 restantes) antes de eliminar el grupo."
}

// 403 - Sin permisos
{
  "detail": "No tienes permisos para eliminar este grupo."
}
```

---

### 2️⃣ Eliminar Canal Huérfano (Cuando NO existe en BD)

```http
DELETE /api/v1/chat/channels/orphan/{channel_id}
```

**Cuándo usar:**
- ✅ El endpoint normal retornó **404**
- ✅ El chat aparece en iOS pero no en backend
- ✅ Error de sincronización BD ↔ Stream
- ✅ Chat "fantasma" o "huérfano"

**Requisitos:**
- 🔐 Debes ser owner (creador) del canal en Stream
- ❌ El canal NO debe existir en BD
- 🏢 El canal debe pertenecer al gym actual
- ⚠️ NO puede ser canal de evento

**Respuesta exitosa (200):**
```json
{
  "success": true,
  "message": "Canal huérfano eliminado correctamente"
}
```

**Errores comunes:**
```json
// 409 - Canal SÍ existe en BD (usar endpoint normal)
{
  "detail": "El canal existe en la base de datos. Usa el endpoint DELETE /rooms/{room_id} para eliminarlo."
}

// 403 - No eres owner
{
  "detail": "Solo el creador (owner) puede eliminar canales huérfanos. Tu rol actual: member"
}

// 403 - Canal de otro gym
{
  "detail": "El canal pertenece a otro gimnasio. Canal team: gym_2, gym esperado: gym_1"
}

// 403 - Canal de evento
{
  "detail": "Los canales de eventos no pueden eliminarse manualmente."
}

// 404 - Canal no existe en Stream
{
  "detail": "Canal messaging:abc123 no encontrado en Stream"
}
```

---

### 3️⃣ Eliminar Conversación 1-to-1 (Delete For Me)

```http
DELETE /api/v1/chat/rooms/{room_id}/conversation
```

**Cuándo usar:**
- ✅ Eliminar mensajes de chat 1-to-1 (solo para ti)
- ✅ Implementar patrón "Eliminar Para Mí" de WhatsApp
- ✅ El otro usuario mantiene su historial

**NO usar para:**
- ❌ Grupos (usar `/leave` en su lugar)
- ❌ Solo ocultar (usar `/hide` en su lugar)

**Respuesta exitosa (200):**
```json
{
  "success": true,
  "message": "Conversación eliminada para ti. El otro usuario mantiene su historial.",
  "room_id": 123,
  "messages_deleted": 42
}
```

**Errores comunes:**
```json
// 400 - Es un grupo, no 1-to-1
{
  "detail": "Solo puedes eliminar conversaciones 1-to-1. Para grupos, usa la opción 'salir del grupo'."
}

// 403 - No eres miembro
{
  "detail": "No eres miembro de esta conversación"
}
```

---

## Árbol de Decisión

```
Usuario presiona "Eliminar" en un chat
│
├─ ¿Es chat 1-to-1?
│  │
│  YES → ¿Quiere eliminar mensajes o solo ocultar?
│         │
│         ├─ Eliminar mensajes → DELETE /rooms/{id}/conversation ✅
│         └─ Solo ocultar → POST /rooms/{id}/hide ✅
│
└─ ¿Es un grupo?
   │
   YES → ¿Quiere salir o eliminarlo completamente?
         │
         ├─ Solo salir → POST /rooms/{id}/leave ✅
         │
         └─ Eliminar grupo → DELETE /rooms/{id}
                             │
                             ├─ 200 OK → ✅ Eliminado
                             │
                             └─ 404 Not Found → DELETE /channels/orphan/{channel_id}
                                                 │
                                                 ├─ 200 OK → ✅ Huérfano eliminado
                                                 └─ Error → ❌ Mostrar al usuario
```

---

## Flujo Recomendado

### Caso 1: Eliminar Grupo Normal

```swift
func deleteGroup(roomId: Int) async throws {
    // Paso 1: Intentar endpoint normal
    try await apiClient.delete("/api/v1/chat/rooms/\(roomId)?hard_delete=true")

    // Si llega aquí, eliminación exitosa
    print("✅ Grupo eliminado correctamente")
}
```

---

### Caso 2: Eliminar Grupo con Fallback a Huérfano

```swift
func deleteGroupWithFallback(roomId: Int, channelId: String) async throws {
    do {
        // Paso 1: Intentar endpoint normal
        try await apiClient.delete("/api/v1/chat/rooms/\(roomId)?hard_delete=true")
        print("✅ Grupo eliminado (existía en BD)")

    } catch let error as APIError where error.statusCode == 404 {
        // Paso 2: Si 404, el grupo no existe en BD → intentar huérfano
        print("⚠️ Grupo no en BD, intentando eliminar como huérfano...")

        try await apiClient.delete("/api/v1/chat/channels/orphan/\(channelId)")
        print("✅ Canal huérfano eliminado correctamente")

    } catch {
        // Otros errores (403, 400, etc.)
        throw error
    }
}
```

---

### Caso 3: Eliminar Conversación 1-to-1 (Delete For Me)

```swift
func deleteConversation(roomId: Int) async throws {
    // Endpoint específico para 1-to-1
    try await apiClient.delete("/api/v1/chat/rooms/\(roomId)/conversation")

    print("✅ Conversación eliminada solo para ti")
    // El otro usuario mantiene su historial
}
```

---

## Implementación Swift

### 1. Extension de ChatManagementService

```swift
extension ChatManagementService {

    // MARK: - Eliminar Grupo Normal

    /// Elimina un grupo del gimnasio
    /// - Parameters:
    ///   - roomId: ID del grupo en la base de datos
    ///   - hardDelete: Si true, elimina de Stream. Si false, solo marca como cerrado
    /// - Throws: APIError con códigos:
    ///   - 404: Grupo no encontrado
    ///   - 403: Sin permisos
    ///   - 400: Grupo tiene miembros
    func deleteGroup(roomId: Int, hardDelete: Bool = true) async throws {
        let endpoint = "/api/v1/chat/rooms/\(roomId)?hard_delete=\(hardDelete)"

        let response: ChatDeleteGroupResponse = try await apiClient.delete(endpoint)

        print("✅ \(response.message)")
        print("   Eliminado de Stream: \(response.deleted_from_stream)")
    }

    // MARK: - Eliminar Canal Huérfano

    /// Elimina un canal que NO existe en la base de datos
    /// - Parameter channelId: ID del canal en Stream (ej: "messaging:abc123" o "abc123")
    /// - Throws: APIError con códigos:
    ///   - 409: Canal existe en BD (usar deleteGroup en su lugar)
    ///   - 403: Sin permisos, canal de otro gym, o canal de evento
    ///   - 404: Canal no encontrado en Stream
    func deleteOrphanChannel(channelId: String) async throws {
        let endpoint = "/api/v1/chat/channels/orphan/\(channelId)"

        let response: DeleteOrphanChannelResponse = try await apiClient.delete(endpoint)

        print("✅ \(response.message)")
    }

    // MARK: - Eliminar Conversación (Delete For Me)

    /// Elimina mensajes de una conversación 1-to-1 solo para ti
    /// - Parameter roomId: ID de la conversación
    /// - Throws: APIError con códigos:
    ///   - 400: No es chat 1-to-1
    ///   - 403: No eres miembro
    func deleteConversation(roomId: Int) async throws {
        let endpoint = "/api/v1/chat/rooms/\(roomId)/conversation"

        let response: DeleteConversationResponse = try await apiClient.delete(endpoint)

        print("✅ \(response.message)")
        print("   Mensajes eliminados: \(response.messages_deleted)")
    }

    // MARK: - Flujo Completo con Fallback

    /// Elimina un grupo con fallback automático a huérfano
    /// - Parameters:
    ///   - roomId: ID del grupo en BD
    ///   - channelId: ID del canal en Stream (para fallback)
    func deleteGroupSmart(roomId: Int, channelId: String) async throws {
        do {
            // Intentar eliminación normal
            try await deleteGroup(roomId: roomId, hardDelete: true)

        } catch let error as APIError where error.statusCode == 404 {
            // Si 404, intentar como huérfano
            print("⚠️ Grupo no en BD, eliminando como huérfano...")
            try await deleteOrphanChannel(channelId: channelId)
        }
        // Otros errores se propagan
    }
}
```

---

### 2. Modelos de Respuesta

```swift
// Response para eliminar grupo normal
struct ChatDeleteGroupResponse: Codable {
    let success: Bool
    let message: String
    let roomId: Int
    let deletedFromStream: Bool

    enum CodingKeys: String, CodingKey {
        case success, message
        case roomId = "room_id"
        case deletedFromStream = "deleted_from_stream"
    }
}

// Response para eliminar canal huérfano
struct DeleteOrphanChannelResponse: Codable {
    let success: Bool
    let message: String
}

// Response para eliminar conversación (Delete For Me)
struct DeleteConversationResponse: Codable {
    let success: Bool
    let message: String
    let roomId: Int
    let messagesDeleted: Int

    enum CodingKeys: String, CodingKey {
        case success, message
        case roomId = "room_id"
        case messagesDeleted = "messages_deleted"
    }
}
```

---

### 3. ViewModel de UI

```swift
class ChatDetailViewModel: ObservableObject {
    @Published var isDeleting = false
    @Published var errorMessage: String?

    let chatService = ChatManagementService.shared

    // MARK: - Eliminar según tipo de chat

    func deleteChat(conversation: Conversation) async {
        isDeleting = true
        errorMessage = nil

        do {
            if conversation.isDirect {
                // Chat 1-to-1: Mostrar opciones
                await showDeleteOptions(conversation: conversation)
            } else {
                // Grupo: Mostrar opciones
                await showGroupDeleteOptions(conversation: conversation)
            }
        } catch {
            errorMessage = error.localizedDescription
        }

        isDeleting = false
    }

    // MARK: - Opciones para chat 1-to-1

    private func showDeleteOptions(conversation: Conversation) async {
        // Mostrar sheet con opciones:
        // 1. "Eliminar Para Mí" → deleteConversation
        // 2. "Ocultar Chat" → hideChat
    }

    private func deleteConversationForMe(roomId: Int) async throws {
        // Confirmación
        let confirmed = await showConfirmation(
            title: "¿Eliminar conversación?",
            message: "Se eliminarán todos los mensajes solo para ti. El otro usuario mantendrá su historial.\n\nEsta acción no se puede deshacer."
        )

        guard confirmed else { return }

        // Eliminar
        try await chatService.deleteConversation(roomId: roomId)

        // Actualizar UI
        await removeFromList(roomId: roomId)
        await showSuccess(message: "Conversación eliminada")
    }

    // MARK: - Opciones para grupo

    private func showGroupDeleteOptions(conversation: Conversation) async {
        let isAdmin = currentUser.isAdmin

        if isAdmin {
            // Mostrar opciones:
            // 1. "Salir del Grupo" → leaveGroup
            // 2. "Eliminar Grupo" → deleteGroup (si está vacío)
        } else {
            // Solo mostrar:
            // 1. "Salir del Grupo" → leaveGroup
        }
    }

    private func deleteGroup(conversation: Conversation) async throws {
        // Validar que está vacío
        guard conversation.memberCount == 0 else {
            throw ChatError.groupNotEmpty("Debes remover a todos los miembros primero")
        }

        // Confirmación
        let confirmed = await showConfirmation(
            title: "¿Eliminar grupo '\(conversation.name)'?",
            message: "El grupo se eliminará permanentemente junto con todos los mensajes.\n\nEsta acción no se puede deshacer."
        )

        guard confirmed else { return }

        // Eliminar con fallback automático
        try await chatService.deleteGroupSmart(
            roomId: conversation.roomId,
            channelId: conversation.streamChannelId
        )

        // Actualizar UI
        await removeFromList(roomId: conversation.roomId)
        await showSuccess(message: "Grupo eliminado correctamente")
    }
}
```

---

## Manejo de Errores

### Tabla de Códigos de Error

| Código | Significado | Acción Recomendada |
|--------|-------------|-------------------|
| **200** | Éxito | Actualizar UI, mostrar confirmación |
| **400** | Bad Request | Mostrar mensaje de error al usuario |
| **403** | Sin permisos | Mostrar "No tienes permisos para esta acción" |
| **404** | No encontrado | Intentar endpoint de huérfanos (grupos) |
| **409** | Conflicto | Usar endpoint normal en lugar de huérfano |
| **500** | Error servidor | Mostrar "Error del servidor, intenta más tarde" |

---

### Switch Statement para Errores

```swift
func handleDeleteError(_ error: Error) {
    guard let apiError = error as? APIError else {
        showError("Error desconocido: \(error.localizedDescription)")
        return
    }

    switch apiError.statusCode {
    case 400:
        // Bad Request
        showError(apiError.message ?? "Solicitud inválida")

    case 403:
        // Forbidden
        if apiError.message?.contains("owner") == true {
            showError("Solo el creador puede eliminar este canal")
        } else if apiError.message?.contains("gimnasio") == true {
            showError("Este canal pertenece a otro gimnasio")
        } else if apiError.message?.contains("evento") == true {
            showError("Los canales de eventos no pueden eliminarse")
        } else {
            showError("No tienes permisos para esta acción")
        }

    case 404:
        // Not Found
        print("⚠️ Recurso no encontrado, puede ser huérfano")
        // El código ya debería haber intentado fallback
        showError("El chat no existe")

    case 409:
        // Conflict
        showError("El canal existe en la base de datos. Usa la opción de eliminar grupo normal.")

    case 500:
        // Server Error
        showError("Error del servidor. Por favor, intenta más tarde.")

    default:
        showError("Error: \(apiError.message ?? "Desconocido")")
    }
}
```

---

## Casos de Uso Reales

### Caso 1: Usuario Elimina Chat 1-to-1 con Entrenador

```swift
// Contexto:
// - Chat directo entre miembro y entrenador
// - Usuario quiere eliminar historial

Task {
    do {
        // Mostrar opciones
        let action = await showActionSheet(
            title: "¿Qué deseas hacer?",
            options: [
                "Eliminar Para Mí",  // Borra mensajes
                "Ocultar Chat",      // Solo oculta
                "Cancelar"
            ]
        )

        switch action {
        case "Eliminar Para Mí":
            try await chatService.deleteConversation(roomId: conversation.roomId)
            showSuccess("Conversación eliminada. El entrenador mantiene su historial.")

        case "Ocultar Chat":
            try await chatService.hideChat(roomId: conversation.roomId)
            showSuccess("Chat ocultado")
        }

    } catch {
        handleDeleteError(error)
    }
}
```

**Endpoint usado:** `DELETE /rooms/{roomId}/conversation`

---

### Caso 2: Admin Elimina Grupo Vacío

```swift
// Contexto:
// - Admin quiere eliminar grupo "Clase Yoga"
// - El grupo está vacío (todos salieron)

Task {
    do {
        // Validar que está vacío
        guard conversation.memberCount == 0 else {
            showError("Debes remover a todos los miembros primero")
            return
        }

        // Confirmar
        let confirmed = await showConfirmation(
            title: "¿Eliminar '\(conversation.name)'?",
            message: "Se eliminará permanentemente con todos los mensajes."
        )

        guard confirmed else { return }

        // Eliminar
        try await chatService.deleteGroup(
            roomId: conversation.roomId,
            hardDelete: true
        )

        showSuccess("Grupo eliminado correctamente")
        navigateBack()

    } catch let error as APIError where error.statusCode == 404 {
        // Grupo no en BD, intentar como huérfano
        print("⚠️ Grupo huérfano, intentando endpoint especial...")

        try await chatService.deleteOrphanChannel(
            channelId: conversation.streamChannelId
        )

        showSuccess("Canal huérfano eliminado correctamente")
        navigateBack()

    } catch {
        handleDeleteError(error)
    }
}
```

**Endpoints usados:**
1. `DELETE /rooms/{roomId}?hard_delete=true` (intento inicial)
2. `DELETE /channels/orphan/{channelId}` (fallback si 404)

---

### Caso 3: Chat Aparece en iOS pero No en Backend (Huérfano)

```swift
// Contexto:
// - Usuario ve un chat en la lista de iOS
// - Al intentar abrirlo, backend retorna 404
// - Es un chat huérfano (error de sincronización)

Task {
    do {
        // Usuario presiona "Eliminar" en el chat

        // Paso 1: Intentar endpoint normal
        try await chatService.deleteGroup(
            roomId: conversation.roomId,
            hardDelete: true
        )

        // Si llega aquí, eliminado exitosamente
        print("✅ Chat eliminado")

    } catch let error as APIError where error.statusCode == 404 {
        // Paso 2: Es huérfano, usar endpoint especial
        print("⚠️ Chat no existe en backend, eliminando como huérfano...")

        do {
            try await chatService.deleteOrphanChannel(
                channelId: conversation.streamChannelId
            )

            showSuccess("Chat huérfano eliminado correctamente")
            removeFromList()

        } catch let orphanError as APIError {
            // Manejo específico de errores de huérfano
            switch orphanError.statusCode {
            case 403:
                if orphanError.message?.contains("owner") == true {
                    showError("Solo el creador puede eliminar este chat")
                } else {
                    showError("No tienes permisos para eliminar este chat")
                }
            case 404:
                showError("El chat no existe en ningún lado")
            default:
                handleDeleteError(orphanError)
            }
        }
    } catch {
        handleDeleteError(error)
    }
}
```

**Flujo:**
1. Intenta: `DELETE /rooms/{roomId}` → 404
2. Fallback: `DELETE /channels/orphan/{channelId}` → 200 ✅

---

## FAQs

### ❓ ¿Cuál es la diferencia entre "Eliminar Para Mí" y "Ocultar"?

| Aspecto | Ocultar (Hide) | Eliminar Para Mí (Delete) |
|---------|----------------|---------------------------|
| **Mensajes** | Se mantienen | Se eliminan |
| **Reversible** | ✅ Sí (con Show) | ❌ No |
| **Endpoint** | `POST /rooms/{id}/hide` | `DELETE /rooms/{id}/conversation` |
| **Uso** | Ocultar temporalmente | Borrar historial permanentemente |

---

### ❓ ¿Qué hacer si el endpoint normal retorna 404?

```swift
// Si DELETE /rooms/{id} retorna 404:
// → Intentar DELETE /channels/orphan/{channel_id}

do {
    try await deleteGroup(roomId: roomId)
} catch let error as APIError where error.statusCode == 404 {
    // Intentar como huérfano
    try await deleteOrphanChannel(channelId: channelId)
}
```

---

### ❓ ¿Puedo eliminar un chat directamente desde Stream SDK?

**❌ NO** - Nunca uses:
```swift
// ❌ NUNCA HACER ESTO
let channel = chatClient.channel(for: channelId)
try await channel.delete()  // VULNERABILIDAD DE SEGURIDAD
```

**✅ SIEMPRE** usa los endpoints del backend:
```swift
// ✅ CORRECTO
try await chatService.deleteGroupSmart(roomId: roomId, channelId: channelId)
```

**Razón:** El backend valida:
- ✅ gym_id correcto
- ✅ Permisos de usuario
- ✅ Tipo de canal
- ✅ Audit logging

Stream solo valida si eres "owner", no valida gym_id ni lógica de negocio.

---

### ❓ ¿Qué significa "Canal Huérfano"?

Un canal huérfano es un chat que:
- ✅ Existe en Stream Chat
- ❌ NO existe en la base de datos local
- 🔄 Se creó en Stream pero falló la creación en BD
- 🔄 Se eliminó de BD pero quedó en Stream

**Cómo identificarlo:**
```swift
// Endpoint normal retorna 404
try await deleteGroup(roomId: 123)
// Error: 404 Not Found

// Es huérfano → usar endpoint especial
try await deleteOrphanChannel(channelId: "messaging:abc123")
// Success: 200 OK
```

---

### ❓ ¿Puedo eliminar canales de eventos?

**❌ NO** - Los canales de eventos:
- Se crean automáticamente con cada evento
- Se cierran automáticamente al finalizar el evento
- Solo administradores pueden gestionarlos
- NO pueden eliminarse manualmente por usuarios

**Si intentas:**
```json
// Response 403 Forbidden
{
  "detail": "Los canales de eventos no pueden eliminarse manualmente."
}
```

---

### ❓ ¿Qué pasa si el grupo tiene miembros?

**NO puedes eliminar** un grupo con miembros.

```swift
// Error 400 Bad Request
{
  "detail": "Debes remover a todos los miembros (3 restantes) antes de eliminar el grupo."
}
```

**Solución:**
1. Remover todos los miembros primero
2. Luego eliminar el grupo vacío

O simplemente usa `POST /rooms/{id}/leave` para salir.

---

### ❓ ¿Cuándo usar hard_delete=true vs false?

```swift
// hard_delete=true (RECOMENDADO)
try await deleteGroup(roomId: roomId, hardDelete: true)
// → Elimina de Stream + marca CLOSED en BD
// → Mensajes se borran permanentemente
```

```swift
// hard_delete=false
try await deleteGroup(roomId: roomId, hardDelete: false)
// → Solo marca CLOSED en BD
// → Mensajes permanecen en Stream (pueden recuperarse)
```

**Recomendación:** Usa `hardDelete: true` siempre a menos que necesites preservar historial.

---

## 🎯 Checklist de Implementación

### Para el equipo iOS:

- [ ] Implementar `ChatManagementService.deleteGroup()`
- [ ] Implementar `ChatManagementService.deleteOrphanChannel()`
- [ ] Implementar `ChatManagementService.deleteConversation()`
- [ ] Implementar `ChatManagementService.deleteGroupSmart()` (con fallback)
- [ ] Crear modelos de respuesta (`ChatDeleteGroupResponse`, etc.)
- [ ] Implementar manejo de errores por código (400, 403, 404, 409, 500)
- [ ] Actualizar UI para mostrar opciones correctas (1-to-1 vs grupo)
- [ ] Agregar confirmaciones antes de eliminar
- [ ] **REMOVER** todas las llamadas directas a `streamProvider.deleteChannel()`
- [ ] Testing de flujo completo:
  - [ ] Eliminar grupo normal (200)
  - [ ] Eliminar grupo huérfano (404 → 200)
  - [ ] Eliminar conversación 1-to-1 (200)
  - [ ] Intentar eliminar sin permisos (403)
  - [ ] Intentar eliminar canal de otro gym (403)

---

## 📚 Referencias

- **API Documentation**: `/docs/CHAT_MANAGEMENT_API.md`
- **Security Analysis**: `/ANALISIS_SEGURIDAD_DELETE_STREAM.md`
- **Stream Best Practices**: `/STREAM_OFFICIAL_BEST_PRACTICES.md`
- **Backend Swagger**: `https://api.tugym.com/api/v1/docs`

---

## 🆘 Soporte

Si tienes dudas o encuentras errores:
1. Consultar esta documentación
2. Revisar los ejemplos de código
3. Contactar al equipo de backend

---

**Última actualización:** 2025-12-14
**Versión:** 1.0
**Autor:** Backend Team
