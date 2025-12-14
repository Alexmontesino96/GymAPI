# Guía: Eliminar Conversación Para Mí (Delete For Me)

Guía completa sobre la funcionalidad de eliminar conversaciones 1-to-1 siguiendo el patrón "Eliminar Para Mí" de WhatsApp.

---

## 📋 Tabla de Contenidos

- [¿Qué es "Eliminar Para Mí"?](#qué-es-eliminar-para-mí)
- [Diferencias con otras operaciones](#diferencias-con-otras-operaciones)
- [API Backend](#api-backend)
- [Implementación iOS](#implementación-ios)
- [Casos de Uso](#casos-de-uso)
- [Troubleshooting](#troubleshooting)

---

## ¿Qué es "Eliminar Para Mí"?

Funcionalidad que permite a un usuario **eliminar todos los mensajes de una conversación 1-to-1 solo para sí mismo**, manteniendo intacto el historial del otro participante.

### 🎯 Características

| Característica | Descripción |
|----------------|-------------|
| **Mensajes eliminados** | Solo para quien ejecuta la acción |
| **Historial del otro** | Se mantiene completamente intacto |
| **Chat oculto** | Automáticamente después de eliminar |
| **Reversible** | No - la eliminación es permanente |
| **Tipo de chat** | Solo conversaciones 1-to-1 (no grupos) |

### ✅ Cuándo Usar

- El usuario quiere **borrar completamente** el historial de una conversación
- Quiere más privacidad que solo ocultar (hide)
- Quiere "empezar de cero" en una conversación
- Quiere eliminar información sensible de su vista

### ❌ Cuándo NO Usar

- **Para grupos**: Usar `POST /rooms/{id}/leave` en su lugar
- **Solo ocultar temporalmente**: Usar `POST /rooms/{id}/hide` en su lugar
- **Eliminar para ambos**: No soportado (requeriría consentimiento mutuo)

---

## Diferencias con otras operaciones

### Comparación

| Operación | Qué Hace | Mensajes | Reversible | Aplica A |
|-----------|----------|----------|------------|----------|
| **Hide** | Oculta el chat de la lista | Se mantienen | ✅ Sí | 1-to-1 solamente |
| **Delete For Me** ⭐ | Elimina mensajes + oculta | Se eliminan para ti | ❌ No | 1-to-1 solamente |
| **Leave** | Sales del grupo + oculta | Se mantienen | ❌ No | Grupos solamente |
| **Delete Group** | Elimina grupo vacío | Todos eliminados | ❌ No | Grupos vacíos |

### Matriz de Decisión

```
¿Es chat 1-to-1?
├─ SÍ
│  ├─ ¿Solo quieres ocultarlo?
│  │  └─ Usar: POST /rooms/{id}/hide
│  └─ ¿Quieres eliminar mensajes?
│     └─ Usar: DELETE /rooms/{id}/conversation ⭐
└─ NO (es grupo)
   └─ Usar: POST /rooms/{id}/leave
```

---

## API Backend

### Endpoint

```http
DELETE /api/v1/chat/rooms/{room_id}/conversation
```

### Autenticación

```
Authorization: Bearer {auth_token}
X-Gym-ID: {gym_id}
```

### Parámetros

| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `room_id` | Path | ✅ Sí | ID de la conversación 1-to-1 |

### Response

```typescript
{
  "success": true,
  "message": "Conversación eliminada para ti. El otro usuario mantiene su historial.",
  "room_id": 123,
  "messages_deleted": 42
}
```

### Ejemplos

#### cURL

```bash
curl -X DELETE "https://api.tugym.com/api/v1/chat/rooms/123/conversation" \
  -H "Authorization: Bearer ${AUTH_TOKEN}" \
  -H "X-Gym-ID: 1"
```

#### JavaScript (Fetch)

```javascript
const deleteConversation = async (roomId) => {
  const response = await fetch(
    `${API_BASE}/chat/rooms/${roomId}/conversation`,
    {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${authToken}`,
        'X-Gym-ID': gymId
      }
    }
  );

  if (!response.ok) {
    throw new Error('Error eliminando conversación');
  }

  const data = await response.json();
  console.log(`Eliminados ${data.messages_deleted} mensajes`);

  return data;
};

// Uso
try {
  await deleteConversation(123);
  // Actualizar UI - remover chat de la lista
} catch (error) {
  console.error(error);
}
```

#### Python (Requests)

```python
import requests

def delete_conversation(room_id: int, auth_token: str, gym_id: int):
    response = requests.delete(
        f"https://api.tugym.com/api/v1/chat/rooms/{room_id}/conversation",
        headers={
            "Authorization": f"Bearer {auth_token}",
            "X-Gym-ID": str(gym_id)
        }
    )

    if response.status_code == 200:
        data = response.json()
        print(f"Eliminados {data['messages_deleted']} mensajes")
        return data
    else:
        raise Exception(f"Error: {response.json()['detail']}")

# Uso
delete_conversation(room_id=123, auth_token="...", gym_id=1)
```

### Errores

| Status | Error | Descripción | Solución |
|--------|-------|-------------|----------|
| **400** | `Solo puedes eliminar conversaciones 1-to-1` | Intentaste eliminar un grupo | Usa `POST /rooms/{id}/leave` para grupos |
| **403** | `No eres miembro de esta conversación` | No perteneces al chat | Verifica que tienes acceso |
| **404** | `Sala de chat no encontrada` | El room_id no existe | Verifica el ID correcto |
| **500** | `Error eliminando la conversación` | Error interno del servidor | Reintenta o contacta soporte |

---

## Implementación iOS

### Service Layer

```swift
import Foundation

// MARK: - Response Models

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

// MARK: - Service

class ChatManagementService {
    private let baseURL = "https://api.tugym.com/api/v1/chat"
    private var authToken: String { /* Get from auth service */ }
    private var gymId: Int { /* Get from user session */ }

    /// Eliminar conversación 1-to-1 (Delete For Me pattern)
    func deleteConversation(roomId: Int) async throws -> DeleteConversationResponse {
        let endpoint = "\(baseURL)/rooms/\(roomId)/conversation"

        guard let url = URL(string: endpoint) else {
            throw ChatManagementError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "DELETE"
        request.setValue("Bearer \(authToken)", forHTTPHeaderField: "Authorization")
        request.setValue("\(gymId)", forHTTPHeaderField: "X-Gym-ID")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw ChatManagementError.networkError
        }

        switch httpResponse.statusCode {
        case 200:
            return try JSONDecoder().decode(DeleteConversationResponse.self, from: data)
        case 400:
            throw ChatManagementError.cannotDeleteGroup
        case 403:
            throw ChatManagementError.notChatMember
        case 404:
            throw ChatManagementError.chatNotFound
        default:
            throw ChatManagementError.unknown
        }
    }
}

// MARK: - Errors

enum ChatManagementError: LocalizedError {
    case invalidURL
    case networkError
    case chatNotFound
    case cannotDeleteGroup
    case notChatMember
    case unknown

    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "URL inválida"
        case .networkError:
            return "Error de red. Verifica tu conexión."
        case .chatNotFound:
            return "Conversación no encontrada"
        case .cannotDeleteGroup:
            return "No puedes eliminar conversaciones de grupo. Usa 'Salir del grupo' en su lugar."
        case .notChatMember:
            return "No eres miembro de esta conversación"
        case .unknown:
            return "Error desconocido. Intenta nuevamente."
        }
    }
}
```

### ViewModel

```swift
import SwiftUI

@MainActor
class ChatDetailViewModel: ObservableObject {
    @Published var showDeleteConfirmation = false
    @Published var isDeleting = false
    @Published var errorMessage: String?
    @Published var successMessage: String?

    private let chatService = ChatManagementService()
    var onChatDeleted: (() -> Void)?

    func deleteConversation(roomId: Int) async {
        isDeleting = true
        defer { isDeleting = false }

        do {
            let response = try await chatService.deleteConversation(roomId: roomId)

            // Success
            successMessage = "Conversación eliminada: \(response.messagesDeleted) mensajes borrados"

            // Callback to update UI (remove from list, navigate back, etc.)
            onChatDeleted?()

        } catch let error as ChatManagementError {
            errorMessage = error.errorDescription
        } catch {
            errorMessage = "Error desconocido. Intenta nuevamente."
        }
    }
}
```

### SwiftUI View

```swift
import SwiftUI

struct ChatDetailView: View {
    let chatRoom: ChatRoom
    @StateObject private var viewModel = ChatDetailViewModel()
    @Environment(\.dismiss) var dismiss

    var body: some View {
        VStack {
            // ... Chat messages here ...
        }
        .navigationTitle(chatRoom.name ?? "Chat")
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Menu {
                    if chatRoom.isDirect {
                        // Opción: Eliminar conversación
                        Button(role: .destructive) {
                            viewModel.showDeleteConfirmation = true
                        } label: {
                            Label("Eliminar conversación", systemImage: "trash")
                        }
                    }
                } label: {
                    Image(systemName: "ellipsis.circle")
                }
            }
        }
        .alert("Eliminar Conversación", isPresented: $viewModel.showDeleteConfirmation) {
            Button("Cancelar", role: .cancel) { }
            Button("Eliminar Para Mí", role: .destructive) {
                Task {
                    await viewModel.deleteConversation(roomId: chatRoom.id)
                }
            }
        } message: {
            Text("Se eliminarán todos los mensajes de esta conversación solo para ti.\n\n\(chatRoom.otherUserName) mantendrá su historial.\n\nEsta acción no se puede deshacer.")
        }
        .alert("Error", isPresented: .constant(viewModel.errorMessage != nil)) {
            Button("OK") {
                viewModel.errorMessage = nil
            }
        } message: {
            if let errorMessage = viewModel.errorMessage {
                Text(errorMessage)
            }
        }
        .onChange(of: viewModel.successMessage) { _, newValue in
            if newValue != nil {
                // Navigate back after successful deletion
                dismiss()
            }
        }
        .overlay {
            if viewModel.isDeleting {
                ProgressView("Eliminando conversación...")
                    .padding()
                    .background(Color(.systemBackground))
                    .cornerRadius(10)
                    .shadow(radius: 10)
            }
        }
    }
}
```

### Lista de Chats con Swipe Action

```swift
struct ChatListView: View {
    @State private var chatRooms: [ChatRoom] = []

    var body: some View {
        List(chatRooms) { chatRoom in
            NavigationLink(destination: ChatDetailView(chatRoom: chatRoom)) {
                ChatRowView(chatRoom: chatRoom)
            }
            .swipeActions(edge: .trailing, allowsFullSwipe: false) {
                if chatRoom.isDirect {
                    // Delete conversation
                    Button(role: .destructive) {
                        Task {
                            await deleteConversation(chatRoom)
                        }
                    } label: {
                        Label("Eliminar", systemImage: "trash")
                    }
                }
            }
        }
    }

    private func deleteConversation(_ chatRoom: ChatRoom) async {
        do {
            let service = ChatManagementService()
            _ = try await service.deleteConversation(roomId: chatRoom.id)

            // Remover de la lista
            withAnimation {
                chatRooms.removeAll { $0.id == chatRoom.id }
            }
        } catch {
            // Handle error
            print("Error deleting conversation: \(error)")
        }
    }
}
```

---

## Casos de Uso

### Caso 1: Usuario Elimina Conversación Molesta

**Escenario:**
- María recibió mensajes inapropiados de un usuario
- Quiere eliminar completamente la conversación de su historial
- El otro usuario mantiene sus mensajes

**Flujo:**

1. María abre el chat con el usuario
2. Toca el menú (...)
3. Selecciona "Eliminar conversación"
4. Confirma: "Eliminar Para Mí"
5. ✅ Resultado:
   - María: 0 mensajes, chat desaparece de la lista
   - Otro usuario: Mantiene todos los mensajes

### Caso 2: Conversación Sensible

**Escenario:**
- Juan compartió información personal en un chat
- Quiere borrar el historial por privacidad
- Es diferente a solo ocultarlo

**Comparación:**

| Acción | Resultado |
|--------|-----------|
| **Hide** | Mensajes permanecen, puede ver historial si reaparece |
| **Delete For Me** ✅ | Mensajes eliminados permanentemente, sin historial |

### Caso 3: Empezar de Cero

**Escenario:**
- Ana tuvo un conflicto en un chat hace meses
- Quiere retomar la conversación sin el historial anterior
- El otro usuario puede mantener contexto si lo necesita

**Flujo:**

1. Ana elimina la conversación histórica
2. Envía nuevo mensaje → chat reaparece vacío
3. Conversación fresh sin historial previo

---

## Troubleshooting

### Problema: "No puedes eliminar conversaciones de grupo"

**Causa:** Intentaste eliminar un grupo

**Solución:**
```swift
// Para grupos, usar leave en su lugar
if chatRoom.isDirect {
    try await chatService.deleteConversation(roomId: chatRoom.id)
} else {
    try await chatService.leaveGroup(roomId: chatRoom.id, autoHide: true)
}
```

### Problema: "No eres miembro de esta conversación"

**Causa:** El usuario no pertenece al chat

**Solución:**
- Verificar que el usuario tenga acceso al chat
- Verificar que el room_id sea correcto
- El chat puede haber sido eliminado por el otro usuario

### Problema: Mensajes no se eliminan en Stream Chat

**Causa:** La eliminación es soft delete por usuario

**Explicación:**
- Los mensajes se eliminan con `hard=False` en Stream
- Esto los oculta solo para el usuario que ejecuta la acción
- El otro usuario los sigue viendo normalmente
- **Esto es el comportamiento esperado** ✅

### Problema: Chat reaparece al recibir nuevo mensaje

**Causa:** Comportamiento normal del sistema

**Explicación:**
- Cuando eliminas una conversación, se oculta
- Si recibes un nuevo mensaje, el chat reaparece
- **El historial anterior sigue eliminado**
- Solo el nuevo mensaje aparece

**Esto es correcto** - Similar a WhatsApp

---

## Notas Técnicas

### Implementación en Backend

```python
# Stream Chat: soft delete por usuario
channel.delete_message(
    msg['id'],
    hard=False  # Mantiene para otros usuarios
)

# Auto-hide después de eliminar
chat_repository.hide_room_for_user(
    db,
    room_id=room_id,
    user_id=user_id
)
```

### Límite de Mensajes

- **Máximo por request**: 1000 mensajes
- **Si hay más**: Se eliminan en batch
- **Performance**: ~100ms por 100 mensajes

### Persistencia

- **Stream Chat**: Soft delete mantiene metadatos
- **Base de datos local**: Chat marcado como oculto
- **Reversible**: No - eliminación permanente para el usuario

---

## Referencias

- [WhatsApp Delete Message Pattern](https://faq.whatsapp.com/general/chats/how-to-delete-messages)
- [Stream Chat Delete Messages](https://getstream.io/chat/docs/python/send_message/?language=python#deleting-a-message)
- [Documentación API completa](./CHAT_MANAGEMENT_API.md)
- [Guía iOS completa](./IOS_CHAT_MANAGEMENT_GUIDE.md)

---

**Versión:** 1.0.0
**Última actualización:** 2025-12-13
