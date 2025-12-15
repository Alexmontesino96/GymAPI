# 🚀 Quick Reference - Endpoints de Eliminación (iOS)

**Guía ultra-rápida para desarrolladores iOS**

---

## 📊 Comparación de Endpoints

| Endpoint | Cuándo Usar | Tipo de Chat | Respuesta 200 | Respuesta Error Común |
|----------|-------------|--------------|---------------|----------------------|
| `DELETE /rooms/{id}` | Eliminar grupo normal | Grupo | `{"success": true, "deleted_from_stream": true}` | `404` → Usar endpoint huérfano |
| `DELETE /channels/orphan/{id}` | Eliminar grupo huérfano | Grupo | `{"success": true, "message": "..."}` | `403` → No eres owner |
| `DELETE /rooms/{id}/conversation` | Eliminar mensajes | Chat 1-to-1 | `{"success": true, "messages_deleted": 42}` | `400` → No es 1-to-1 |
| `POST /rooms/{id}/hide` | Ocultar chat | Chat 1-to-1 | `{"success": true, "is_hidden": true}` | `400` → Es grupo |
| `POST /rooms/{id}/leave` | Salir de grupo | Grupo | `{"success": true, "group_deleted": false}` | `400` → Es 1-to-1 |

---

## 🔀 Diagrama de Flujo Simplificado

```
┌────────────────────────────────────┐
│ Usuario presiona "Eliminar"        │
└───────────┬────────────────────────┘
            │
            ▼
    ¿Es chat 1-to-1?
            │
    ┌───────┴───────┐
    │               │
   SÍ              NO (Grupo)
    │               │
    ▼               ▼
┌─────────┐    ¿Quieres salir
│Ocultar? │     o eliminar?
│ Hide    │         │
└─────────┘    ┌────┴─────┐
    │          │          │
    ▼         Salir    Eliminar
┌─────────┐    │          │
│Eliminar │    ▼          ▼
│mensajes?│  Leave    DELETE /rooms/{id}
└─────────┘             │
    │              ┌────┴────┐
    ▼             200       404
DELETE              │         │
/conversation       ✅         ▼
    │                   DELETE /orphan/{id}
    ▼                        │
    ✅                   ┌───┴───┐
                        200    Error
                         │       │
                         ✅      ❌
```

---

## 💻 Código Esencial Swift

### 1. Método Principal con Fallback Automático

```swift
func deleteGroupSmart(roomId: Int, channelId: String) async throws {
    do {
        // Intentar endpoint normal
        try await apiClient.delete("/api/v1/chat/rooms/\(roomId)?hard_delete=true")
        print("✅ Grupo eliminado")

    } catch let error as APIError where error.statusCode == 404 {
        // Fallback: Intentar como huérfano
        try await apiClient.delete("/api/v1/chat/channels/orphan/\(channelId)")
        print("✅ Canal huérfano eliminado")
    }
}
```

### 2. Eliminar Conversación 1-to-1

```swift
func deleteConversation(roomId: Int) async throws {
    try await apiClient.delete("/api/v1/chat/rooms/\(roomId)/conversation")
    print("✅ Conversación eliminada (solo para ti)")
}
```

### 3. Manejo de Errores

```swift
switch error.statusCode {
case 400: showError("Solicitud inválida")
case 403: showError("Sin permisos")
case 404: /* Intentar endpoint huérfano */
case 409: showError("Usa endpoint normal, no huérfano")
case 500: showError("Error del servidor")
}
```

---

## 📋 Tabla de Códigos HTTP

| Código | Significado | Acción iOS |
|--------|-------------|-----------|
| **200** | ✅ Éxito | Actualizar UI, mostrar confirmación |
| **400** | ❌ Bad Request | Mostrar mensaje de error |
| **403** | 🔒 Forbidden | "No tienes permisos" |
| **404** | 🔍 Not Found | Intentar endpoint huérfano (grupos) |
| **409** | ⚠️ Conflict | "Usa endpoint normal" |
| **500** | 💥 Server Error | "Intenta más tarde" |

---

## 🎯 Casos de Uso Rápidos

### ✅ Usuario elimina chat 1-to-1
```swift
try await deleteConversation(roomId: 123)
```
→ Endpoint: `DELETE /rooms/123/conversation`

### ✅ Admin elimina grupo vacío
```swift
try await deleteGroupSmart(roomId: 456, channelId: "messaging:abc")
```
→ Endpoints: `DELETE /rooms/456` (o `/orphan/abc` si 404)

### ✅ Usuario sale de grupo
```swift
try await apiClient.post("/api/v1/chat/rooms/789/leave?auto_hide=true")
```
→ Endpoint: `POST /rooms/789/leave`

### ✅ Usuario oculta chat 1-to-1
```swift
try await apiClient.post("/api/v1/chat/rooms/123/hide")
```
→ Endpoint: `POST /rooms/123/hide`

---

## ⚠️ NUNCA Hacer

```swift
// ❌ NUNCA ELIMINAR DIRECTAMENTE DE STREAM
let channel = chatClient.channel(for: channelId)
try await channel.delete()  // 🚨 VULNERABILIDAD DE SEGURIDAD
```

**SIEMPRE usar endpoints del backend** que validan:
- gym_id
- permisos
- tipo de canal
- audit logging

---

## 🔑 Headers Requeridos

```swift
let headers = [
    "Authorization": "Bearer \(authToken)",
    "X-Gym-ID": "\(currentGymId)",
    "Content-Type": "application/json"
]
```

---

## 📦 Modelos de Respuesta

```swift
// Response eliminar grupo
struct ChatDeleteGroupResponse: Codable {
    let success: Bool
    let message: String
    let roomId: Int
    let deletedFromStream: Bool
}

// Response eliminar huérfano
struct DeleteOrphanChannelResponse: Codable {
    let success: Bool
    let message: String
}

// Response eliminar conversación
struct DeleteConversationResponse: Codable {
    let success: Bool
    let message: String
    let roomId: Int
    let messagesDeleted: Int
}
```

---

## ✅ Checklist de Implementación

- [ ] Implementar `deleteGroupSmart()` con fallback automático
- [ ] Implementar `deleteConversation()` para chats 1-to-1
- [ ] Manejo de errores por código HTTP (400, 403, 404, 409, 500)
- [ ] **REMOVER** llamadas directas a `streamProvider.deleteChannel()`
- [ ] Agregar confirmaciones antes de eliminar
- [ ] Testing de casos:
  - [ ] Eliminar grupo normal (200)
  - [ ] Eliminar grupo huérfano (404 → 200)
  - [ ] Eliminar conversación 1-to-1 (200)
  - [ ] Errores de permisos (403)

---

## 🔗 Links Útiles

- **Documentación completa**: `/docs/IOS_CHAT_DELETION_GUIDE.md`
- **API Docs**: `/docs/CHAT_MANAGEMENT_API.md`
- **Swagger**: `https://api.tugym.com/api/v1/docs`

---

**Versión:** 1.0 | **Fecha:** 2025-12-14
