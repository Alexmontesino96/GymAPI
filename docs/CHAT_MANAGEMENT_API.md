# API de Gestión de Chats - Documentación

Sistema de gestión de chats siguiendo el patrón de WhatsApp, permitiendo a los usuarios:
- 💬 **Ocultar** chats 1-to-1 temporalmente
- 🗑️ **Eliminar** mensajes de conversaciones (Delete For Me)
- 🚪 **Salir** de grupos
- ⚡ **Eliminar** grupos completamente (admin/creador)

## Tabla de Contenidos

- [Resumen de Endpoints](#resumen-de-endpoints)
- [Autenticación y Permisos](#autenticación-y-permisos)
- [Endpoints Detallados](#endpoints-detallados)
  - [Ocultar Chat 1-to-1](#1-ocultar-chat-1-to-1)
  - [Mostrar Chat Oculto](#2-mostrar-chat-oculto)
  - [Salir de Grupo](#3-salir-de-grupo)
  - [Eliminar Grupo](#4-eliminar-grupo)
  - [Eliminar Conversación (Delete For Me)](#5-eliminar-conversación-delete-for-me)
- [Matriz de Permisos](#matriz-de-permisos)
- [Casos de Uso Comunes](#casos-de-uso-comunes)
- [Códigos de Error](#códigos-de-error)
- [Integración con Listado de Chats](#integración-con-listado-de-chats)
- [Sincronización con Stream Chat](#sincronización-con-stream-chat)

---

## Resumen de Endpoints

| Método | Endpoint | Descripción | Scope Requerido |
|--------|----------|-------------|-----------------|
| `POST` | `/api/v1/chat/rooms/{room_id}/hide` | Ocultar chat 1-to-1 | `resource:read` |
| `POST` | `/api/v1/chat/rooms/{room_id}/show` | Mostrar chat oculto | `resource:read` |
| `POST` | `/api/v1/chat/rooms/{room_id}/leave` | Salir de grupo | `resource:read` |
| `DELETE` | `/api/v1/chat/rooms/{room_id}` | Eliminar grupo | `resource:write` |
| `DELETE` | `/api/v1/chat/rooms/{room_id}/conversation` | Eliminar conversación (Delete For Me) | `resource:write` |

**Base URL:** `https://tu-dominio.com/api/v1/chat`

**Headers requeridos:**
```http
Authorization: Bearer {AUTH0_TOKEN}
X-Gym-ID: {GYM_ID}
Content-Type: application/json
```

---

## Autenticación y Permisos

### Headers de Autenticación

Todos los endpoints requieren:

1. **Token JWT de Auth0:** En header `Authorization: Bearer {token}`
2. **Gym ID:** En header `X-Gym-ID: {gym_id}` para multi-tenancy

### Scopes OAuth2

- `resource:read` - Operaciones de lectura y modificación personal (hide, show, leave)
- `resource:write` - Operaciones de escritura administrativa (delete)

---

## Endpoints Detallados

### 1. Ocultar Chat 1-to-1

Oculta un chat directo de la vista del usuario sin afectar al otro participante.

**🔹 Patrón:** Solo aplica a chats directos 1-to-1. Para grupos, usar [Salir de Grupo](#3-salir-de-grupo).

```http
POST /api/v1/chat/rooms/{room_id}/hide
```

#### Parámetros de Path

| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `room_id` | integer | ✅ | ID de la sala de chat a ocultar |

#### Headers

```http
Authorization: Bearer {token}
X-Gym-ID: 1
Content-Type: application/json
```

#### Respuesta Exitosa (200 OK)

```json
{
  "success": true,
  "message": "Chat ocultado exitosamente",
  "room_id": 123,
  "is_hidden": true
}
```

#### Ejemplos de Uso

<details>
<summary><b>cURL</b></summary>

```bash
curl -X POST "https://api.tugym.com/api/v1/chat/rooms/123/hide" \
  -H "Authorization: Bearer eyJhbGc..." \
  -H "X-Gym-ID: 1"
```
</details>

<details>
<summary><b>JavaScript/Fetch</b></summary>

```javascript
const response = await fetch('https://api.tugym.com/api/v1/chat/rooms/123/hide', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${authToken}`,
    'X-Gym-ID': '1'
  }
});

const data = await response.json();
console.log(data.message); // "Chat ocultado exitosamente"
```
</details>

<details>
<summary><b>Python</b></summary>

```python
import requests

response = requests.post(
    'https://api.tugym.com/api/v1/chat/rooms/123/hide',
    headers={
        'Authorization': f'Bearer {auth_token}',
        'X-Gym-ID': '1'
    }
)

data = response.json()
print(data['message'])  # "Chat ocultado exitosamente"
```
</details>

#### Códigos de Respuesta

| Código | Descripción |
|--------|-------------|
| `200` | Chat ocultado exitosamente |
| `400` | El chat no es 1-to-1 (debe usar leave para grupos) |
| `403` | Usuario no es miembro del chat |
| `404` | Sala de chat no encontrada o usuario no encontrado |
| `500` | Error interno del servidor |

#### Notas Importantes

- ✅ **Solo chats 1-to-1:** Este endpoint solo funciona con chats directos
- ✅ **No afecta al otro usuario:** El otro participante sigue viendo el chat normalmente
- ✅ **Reversible:** Puede mostrarse nuevamente con [Show](#2-mostrar-chat-oculto)
- ✅ **Sincronización:** Se sincroniza automáticamente con Stream Chat
- ❌ **No funciona con grupos:** Para grupos, usar [Leave Group](#3-salir-de-grupo)

---

### 2. Mostrar Chat Oculto

Restaura la visibilidad de un chat previamente ocultado.

```http
POST /api/v1/chat/rooms/{room_id}/show
```

#### Parámetros de Path

| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `room_id` | integer | ✅ | ID de la sala de chat a mostrar |

#### Respuesta Exitosa (200 OK)

```json
{
  "success": true,
  "message": "Chat mostrado exitosamente",
  "room_id": 123,
  "is_hidden": false
}
```

#### Ejemplo de Uso

```bash
curl -X POST "https://api.tugym.com/api/v1/chat/rooms/123/show" \
  -H "Authorization: Bearer eyJhbGc..." \
  -H "X-Gym-ID: 1"
```

#### Respuestas Posibles

```json
// Si el chat ya estaba visible
{
  "success": true,
  "message": "El chat ya estaba visible",
  "room_id": 123,
  "is_hidden": false
}
```

---

### 3. Salir de Grupo

Permite al usuario salir de un grupo. El usuario es removido de la lista de miembros y opcionalmente el chat se oculta de su vista.

**🔹 Patrón WhatsApp:** Si eres el último miembro, el grupo se elimina automáticamente.

```http
POST /api/v1/chat/rooms/{room_id}/leave?auto_hide=true
```

#### Parámetros de Path

| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `room_id` | integer | ✅ | ID del grupo a abandonar |

#### Parámetros de Query

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `auto_hide` | boolean | `true` | Ocultar automáticamente el chat después de salir |

#### Respuesta Exitosa (200 OK)

```json
{
  "success": true,
  "message": "Has salido del grupo 'Entrenamiento Matutino'",
  "room_id": 456,
  "remaining_members": 3,
  "group_deleted": false,
  "auto_hidden": true
}
```

#### Ejemplo: Último Miembro Sale del Grupo

```json
{
  "success": true,
  "message": "Has salido del grupo 'Grupo Temporal'",
  "room_id": 789,
  "remaining_members": 0,
  "group_deleted": true,
  "auto_hidden": true
}
```

#### Ejemplos de Uso

<details>
<summary><b>Salir con auto-hide (recomendado)</b></summary>

```bash
curl -X POST "https://api.tugym.com/api/v1/chat/rooms/456/leave?auto_hide=true" \
  -H "Authorization: Bearer eyJhbGc..." \
  -H "X-Gym-ID: 1"
```
</details>

<details>
<summary><b>Salir sin ocultar</b></summary>

```bash
curl -X POST "https://api.tugym.com/api/v1/chat/rooms/456/leave?auto_hide=false" \
  -H "Authorization: Bearer eyJhbGc..." \
  -H "X-Gym-ID: 1"
```
</details>

<details>
<summary><b>JavaScript con manejo de grupo eliminado</b></summary>

```javascript
async function leaveGroup(roomId) {
  const response = await fetch(
    `https://api.tugym.com/api/v1/chat/rooms/${roomId}/leave?auto_hide=true`,
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${authToken}`,
        'X-Gym-ID': '1'
      }
    }
  );

  const data = await response.json();

  if (data.group_deleted) {
    console.log('Eras el último miembro. El grupo ha sido eliminado.');
  } else {
    console.log(`Has salido del grupo. Quedan ${data.remaining_members} miembros.`);
  }

  return data;
}
```
</details>

#### Códigos de Respuesta

| Código | Descripción |
|--------|-------------|
| `200` | Saliste del grupo exitosamente |
| `400` | No puedes salir de un chat 1-to-1 o de evento |
| `403` | No eres miembro del grupo |
| `404` | Grupo no encontrado |
| `500` | Error interno del servidor |

#### Comportamiento Especial

- 🔄 **Último miembro:** Si eres el último, el grupo se marca como `CLOSED` automáticamente
- 🔄 **Auto-hide:** Por defecto, el chat se oculta después de salir
- 🔄 **Stream Chat:** El usuario es removido del canal en Stream inmediatamente
- ❌ **Chats 1-to-1:** No permitido, usar [Hide](#1-ocultar-chat-1-to-1)
- ❌ **Chats de eventos:** No permitido, se cierran automáticamente al finalizar el evento

---

### 4. Eliminar Grupo

Elimina un grupo completamente. Solo disponible para administradores del gimnasio y creadores del grupo.

**🔹 Requisito:** Debes remover TODOS los miembros antes de eliminar el grupo.

```http
DELETE /api/v1/chat/rooms/{room_id}?hard_delete=false
```

#### Parámetros de Path

| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `room_id` | integer | ✅ | ID del grupo a eliminar |

#### Parámetros de Query

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `hard_delete` | boolean | `false` | Si `true`, elimina completamente de Stream Chat. Si `false`, solo marca como CLOSED en BD |

#### Respuesta Exitosa (200 OK)

```json
{
  "success": true,
  "message": "Grupo 'Sala de Administradores' eliminado exitosamente",
  "room_id": 789,
  "deleted_from_stream": true
}
```

#### Ejemplos de Uso

<details>
<summary><b>Soft Delete (solo marca como cerrado)</b></summary>

```bash
curl -X DELETE "https://api.tugym.com/api/v1/chat/rooms/789?hard_delete=false" \
  -H "Authorization: Bearer eyJhbGc..." \
  -H "X-Gym-ID: 1"
```
</details>

<details>
<summary><b>Hard Delete (elimina de Stream)</b></summary>

```bash
curl -X DELETE "https://api.tugym.com/api/v1/chat/rooms/789?hard_delete=true" \
  -H "Authorization: Bearer eyJhbGc..." \
  -H "X-Gym-ID: 1"
```
</details>

<details>
<summary><b>Flujo completo: Remover miembros y eliminar</b></summary>

```javascript
async function deleteGroupComplete(roomId) {
  // Paso 1: Obtener miembros del grupo
  const room = await fetch(
    `https://api.tugym.com/api/v1/chat/rooms/${roomId}`,
    { headers: { 'Authorization': `Bearer ${token}`, 'X-Gym-ID': '1' } }
  ).then(r => r.json());

  // Paso 2: Remover cada miembro
  for (const member of room.members) {
    await fetch(
      `https://api.tugym.com/api/v1/chat/rooms/${roomId}/members/${member.user_id}`,
      {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
          'X-Gym-ID': '1'
        }
      }
    );
  }

  // Paso 3: Eliminar el grupo
  const deleteResponse = await fetch(
    `https://api.tugym.com/api/v1/chat/rooms/${roomId}?hard_delete=true`,
    {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${token}`,
        'X-Gym-ID': '1'
      }
    }
  );

  return deleteResponse.json();
}
```
</details>

#### Códigos de Respuesta

| Código | Descripción |
|--------|-------------|
| `200` | Grupo eliminado exitosamente |
| `400` | El grupo tiene miembros (debes removerlos primero) o es un chat inválido |
| `403` | Sin permisos para eliminar este grupo |
| `404` | Grupo no encontrado |
| `500` | Error interno del servidor |

#### Reglas de Permisos

| Rol | Puede Eliminar |
|-----|----------------|
| **MEMBER** | ❌ Ningún grupo |
| **TRAINER** | ✅ Solo grupos que creó |
| **ADMIN** | ✅ Cualquier grupo del gimnasio |
| **OWNER** | ✅ Cualquier grupo del gimnasio |

#### Restricciones

- ⚠️ **Grupo vacío:** DEBE estar vacío (0 miembros) antes de eliminar
- ⚠️ **Chats 1-to-1:** No se pueden eliminar, usar [Hide](#1-ocultar-chat-1-to-1)
- ⚠️ **Chats de eventos:** Se gestionan automáticamente, no se pueden eliminar manualmente
- ⚠️ **Hard delete:** Acción irreversible, todos los mensajes se pierden

---

### 5. Eliminar Conversación (Delete For Me)

Elimina todos los mensajes de una conversación 1-to-1 solo para el usuario que lo solicita. El otro participante mantiene su historial intacto.

**🔹 Patrón WhatsApp:** Implementa el comportamiento "Eliminar Para Mí" de WhatsApp.

```http
DELETE /api/v1/chat/rooms/{room_id}/conversation
```

#### Parámetros de Path

| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `room_id` | integer | ✅ | ID de la conversación 1-to-1 |

#### Respuesta Exitosa (200 OK)

```json
{
  "success": true,
  "message": "Conversación eliminada para ti. El otro usuario mantiene su historial.",
  "room_id": 123,
  "messages_deleted": 42
}
```

#### Ejemplos de Uso

<details>
<summary><b>cURL</b></summary>

```bash
curl -X DELETE "https://api.tugym.com/api/v1/chat/rooms/123/conversation" \
  -H "Authorization: Bearer eyJhbGc..." \
  -H "X-Gym-ID: 1"
```
</details>

<details>
<summary><b>JavaScript con confirmación</b></summary>

```javascript
async function deleteConversation(roomId, otherUserName) {
  // Confirmación del usuario
  const confirmed = window.confirm(
    `¿Eliminar conversación con ${otherUserName}?\n\n` +
    `Se eliminarán todos los mensajes solo para ti.\n` +
    `${otherUserName} mantendrá su historial.\n\n` +
    `Esta acción no se puede deshacer.`
  );

  if (!confirmed) return;

  // Eliminar conversación
  const response = await fetch(
    `https://api.tugym.com/api/v1/chat/rooms/${roomId}/conversation`,
    {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${authToken}`,
        'X-Gym-ID': '1'
      }
    }
  );

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail);
  }

  const data = await response.json();
  console.log(`Eliminados ${data.messages_deleted} mensajes`);

  // El chat queda oculto automáticamente
  // Actualizar UI - remover de la lista
  removeChatFromList(roomId);

  return data;
}

// Uso
try {
  await deleteConversation(123, 'Juan Pérez');
  alert('Conversación eliminada exitosamente');
} catch (error) {
  alert(`Error: ${error.message}`);
}
```
</details>

<details>
<summary><b>Python</b></summary>

```python
import requests

def delete_conversation(room_id: int, auth_token: str, gym_id: int):
    """Elimina una conversación 1-to-1 (Delete For Me)"""
    response = requests.delete(
        f'https://api.tugym.com/api/v1/chat/rooms/{room_id}/conversation',
        headers={
            'Authorization': f'Bearer {auth_token}',
            'X-Gym-ID': str(gym_id)
        }
    )

    if response.status_code == 200:
        data = response.json()
        print(f"✅ Eliminados {data['messages_deleted']} mensajes")
        print(f"   {data['message']}")
        return data
    else:
        error = response.json()
        raise Exception(f"❌ Error: {error['detail']}")

# Uso
try:
    delete_conversation(room_id=123, auth_token="...", gym_id=1)
except Exception as e:
    print(str(e))
```
</details>

#### Códigos de Respuesta

| Código | Descripción |
|--------|-------------|
| `200` | Conversación eliminada exitosamente |
| `400` | Solo puedes eliminar conversaciones 1-to-1 (no grupos) |
| `403` | No eres miembro de esta conversación |
| `404` | Conversación no encontrada |
| `500` | Error interno del servidor |

#### Comportamiento Detallado

##### ✅ Qué SE elimina:
- Todos los mensajes de la conversación **solo para ti**
- Hasta 1000 mensajes por llamada (procesamiento en batch)
- Usa soft delete en Stream Chat (hard=False)

##### ✅ Qué NO se afecta:
- Historial del otro usuario permanece intacto
- El otro usuario no recibe ninguna notificación
- Metadatos del canal en Stream Chat

##### 🔄 Auto-hide:
- El chat se oculta automáticamente después de eliminar
- No aparece en `/my-rooms` (a menos que uses `include_hidden=true`)

##### ⚠️ Comportamiento con nuevos mensajes:
- Si recibes un nuevo mensaje, el chat **reaparece**
- El historial anterior sigue eliminado
- Solo el nuevo mensaje aparece

#### Diferencias con Hide

| Aspecto | Hide | Delete For Me |
|---------|------|---------------|
| **Mensajes** | Se mantienen | Se eliminan |
| **Reversible** | ✅ Sí (con Show) | ❌ No |
| **Auto-hide** | Sí | Sí |
| **Otro usuario** | No afectado | No afectado |
| **Uso recomendado** | Ocultar temporalmente | Eliminar historial sensible |

#### Casos de Uso

**Cuándo usar Delete For Me:**
- ✅ Quieres borrar completamente el historial
- ✅ Información sensible o privacidad
- ✅ "Empezar de cero" en una conversación
- ✅ Similar a WhatsApp "Eliminar Para Mí"

**Cuándo usar Hide:**
- ✅ Solo ocultar temporalmente
- ✅ Reducir ruido visual
- ✅ Mantener historial disponible

#### Notas Importantes

- ✅ **Solo chats 1-to-1:** No funciona con grupos (usar [Leave](#3-salir-de-grupo))
- ✅ **Unilateral:** Solo afecta a quien ejecuta la acción
- ✅ **Permanente:** No se puede recuperar el historial eliminado
- ✅ **Límite:** Procesa hasta 1000 mensajes por llamada
- ⚠️ **Stream Chat:** Usa soft delete para preservar mensajes del otro usuario
- ⚠️ **Reaparece:** Si recibes un mensaje nuevo, el chat vuelve a aparecer (vacío)

---

## Matriz de Permisos

### Por Tipo de Chat

| Operación | Chat 1-to-1 | Grupo Normal | Chat de Evento |
|-----------|-------------|--------------|----------------|
| **Hide** | ✅ Todos | ❌ Usar Leave | ❌ No permitido |
| **Show** | ✅ Todos | ✅ Si ya salió | ❌ No permitido |
| **Delete For Me** | ✅ Todos | ❌ Usar Leave | ❌ No permitido |
| **Leave** | ❌ Usar Hide/Delete | ✅ Todos | ❌ Auto-cerrado |
| **Delete Group** | ❌ Usar Delete For Me | ✅ Admin/Creador | ❌ Solo admin/auto |

### Por Rol de Usuario

| Rol | Hide | Show | Delete For Me | Leave Group | Delete Group Propio | Delete Group Cualquiera |
|-----|------|------|---------------|-------------|---------------------|-------------------------|
| **MEMBER** | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| **TRAINER** | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| **ADMIN** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **OWNER** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

---

## Casos de Uso Comunes

### 1. Usuario Oculta Chat Molesto 1-to-1

**Escenario:** Un miembro recibe spam de otro usuario y quiere ocultarlo.

```javascript
// Usuario oculta el chat
const response = await fetch('/api/v1/chat/rooms/123/hide', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'X-Gym-ID': '1'
  }
});

// El chat desaparece de su lista (el otro usuario sigue viéndolo)
```

**Resultado:**
- ✅ Chat ocultado solo para el usuario
- ✅ No aparece en `/my-rooms` (sin `include_hidden=true`)
- ✅ El otro participante NO se entera

---

### 2. Usuario Sale de Grupo de WhatsApp

**Escenario:** Miembro decide abandonar un grupo de entrenamiento.

```javascript
// Usuario sale del grupo
const response = await fetch('/api/v1/chat/rooms/456/leave?auto_hide=true', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'X-Gym-ID': '1'
  }
});

const data = await response.json();

if (data.group_deleted) {
  alert('Eras el último miembro. El grupo ha sido eliminado.');
} else {
  alert(`Has salido del grupo. Quedan ${data.remaining_members} miembros.`);
}
```

**Resultado:**
- ✅ Usuario removido del grupo en Stream Chat
- ✅ Chat ocultado automáticamente
- ✅ Si era el último, grupo marcado como CLOSED

---

### 3. Admin Elimina Grupo Temporal Vacío

**Escenario:** Admin creó un grupo temporal, todos salieron, ahora quiere eliminarlo.

```javascript
// Paso 1: Verificar que esté vacío
const room = await fetch(`/api/v1/chat/rooms/789`, {
  headers: { 'Authorization': `Bearer ${token}`, 'X-Gym-ID': '1' }
}).then(r => r.json());

console.log(`Miembros: ${room.members.length}`); // Debe ser 0

// Paso 2: Eliminar el grupo
if (room.members.length === 0) {
  const response = await fetch('/api/v1/chat/rooms/789?hard_delete=true', {
    method: 'DELETE',
    headers: {
      'Authorization': `Bearer ${token}`,
      'X-Gym-ID': '1'
    }
  });

  console.log('Grupo eliminado permanentemente');
}
```

**Resultado:**
- ✅ Grupo eliminado de Stream Chat
- ✅ Todos los mensajes borrados
- ✅ Marcado como CLOSED en BD

---

### 4. Usuario Elimina Conversación Sensible (Delete For Me)

**Escenario:** Usuario compartió información sensible y quiere eliminar completamente su historial.

```javascript
// Confirmar antes de eliminar
async function deletePrivateConversation(roomId, otherUserName) {
  const confirmed = window.confirm(
    `¿Eliminar conversación con ${otherUserName}?\n\n` +
    `Se eliminarán TODOS los mensajes solo para ti.\n` +
    `${otherUserName} mantendrá su historial completo.\n\n` +
    `Esta acción NO se puede deshacer.`
  );

  if (!confirmed) return;

  try {
    const response = await fetch(
      `https://api.tugym.com/api/v1/chat/rooms/${roomId}/conversation`,
      {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'X-Gym-ID': '1'
        }
      }
    );

    if (!response.ok) {
      throw new Error('Error eliminando conversación');
    }

    const data = await response.json();

    console.log(`✅ Eliminados ${data.messages_deleted} mensajes`);
    console.log(`   ${data.message}`);

    // Chat se oculta automáticamente
    removeChatFromList(roomId);

    alert('Conversación eliminada exitosamente');
    navigateTo('/chats');

  } catch (error) {
    alert(`Error: ${error.message}`);
  }
}

// Uso
deletePrivateConversation(123, 'María López');
```

**Resultado:**
- ✅ Todos los mensajes eliminados solo para ti
- ✅ María mantiene su historial intacto
- ✅ Chat oculto automáticamente de tu lista
- ✅ María NO recibe notificación
- ⚠️ Si María envía un mensaje nuevo, el chat reaparece (vacío para ti)

**Diferencia con Hide:**
- **Hide**: Solo oculta, mensajes permanecen → puedes ver historial si reaparece
- **Delete For Me**: Mensajes eliminados permanentemente → si reaparece, no hay historial

---

### 5. Listar Chats Excluyendo Ocultos

**Escenario:** Mostrar solo chats activos en la UI principal.

```javascript
// Obtener solo chats visibles (default)
const visibleChats = await fetch('/api/v1/chat/my-rooms', {
  headers: {
    'Authorization': `Bearer ${token}`,
    'X-Gym-ID': '1'
  }
}).then(r => r.json());

console.log('Chats activos:', visibleChats.length);

// Obtener TODOS los chats (incluyendo ocultos)
const allChats = await fetch('/api/v1/chat/my-rooms?include_hidden=true', {
  headers: {
    'Authorization': `Bearer ${token}`,
    'X-Gym-ID': '1'
  }
}).then(r => r.json());

console.log('Total (con ocultos):', allChats.length);
```

---

## Códigos de Error

### Errores Comunes

#### 400 Bad Request

```json
{
  "detail": "Solo puedes ocultar chats directos 1-to-1. Para grupos, debes salir primero usando 'leave group'."
}
```

**Causas:**
- Intentar ocultar un grupo (debe usar leave)
- Intentar salir de chat 1-to-1 (debe usar hide)
- Intentar eliminar conversación de un grupo (debe usar leave)
- Intentar eliminar grupo con miembros
- Intentar salir/eliminar chat de evento

**Ejemplos específicos:**

**Delete For Me en grupo:**
```json
{
  "detail": "Solo puedes eliminar conversaciones 1-to-1. Para grupos, usa la opción 'salir del grupo'."
}
```

**Leave en chat 1-to-1:**
```json
{
  "detail": "No puedes salir de un chat directo 1-to-1. Usa la opción 'ocultar' en su lugar."
}
```

**Delete grupo con miembros:**
```json
{
  "detail": "Debes remover a todos los miembros (3 restantes) antes de eliminar el grupo."
}
```

---

#### 403 Forbidden

```json
{
  "detail": "No eres miembro de esta sala de chat"
}
```

**Causas:**
- Usuario no es miembro del chat
- Trainer intenta eliminar grupo de otro
- Member intenta eliminar cualquier grupo

---

#### 404 Not Found

```json
{
  "detail": "Sala de chat 123 no encontrada"
}
```

**Causas:**
- Chat ID inválido
- Chat pertenece a otro gimnasio
- Usuario no encontrado en BD

---

#### 500 Internal Server Error

```json
{
  "detail": "Error al salir del grupo: Connection to Stream failed"
}
```

**Causas:**
- Error de conexión con Stream Chat
- Error de base de datos
- Error de sincronización

---

## Integración con Listado de Chats

### Endpoint `/my-rooms` Actualizado

```http
GET /api/v1/chat/my-rooms?include_hidden=false
```

**Comportamiento nuevo:**
- Por defecto excluye chats ocultos (`include_hidden=false`)
- Con `include_hidden=true` muestra todos los chats

**Ejemplo:**

```javascript
// Solo chats visibles (recomendado para UI principal)
const activeChats = await fetch('/api/v1/chat/my-rooms', {
  headers: { 'Authorization': `Bearer ${token}`, 'X-Gym-ID': '1' }
}).then(r => r.json());

// Todos los chats (para sección "Chats archivados")
const archivedChats = await fetch('/api/v1/chat/my-rooms?include_hidden=true', {
  headers: { 'Authorization': `Bearer ${token}`, 'X-Gym-ID': '1' }
}).then(r => r.json());

// Filtrar solo los ocultos
const hiddenOnly = archivedChats.filter(chat =>
  !activeChats.find(active => active.id === chat.id)
);
```

---

## Sincronización con Stream Chat

Todas las operaciones se sincronizan automáticamente con Stream Chat:

| Operación | Acción en Stream | Acción en BD Local |
|-----------|------------------|-------------------|
| **Hide** | `channel.hide(user_id)` | Insert en `chat_member_hidden` |
| **Show** | `channel.show(user_id)` | Delete de `chat_member_hidden` |
| **Delete For Me** | `channel.delete_message(msg_id, hard=False)` por cada mensaje | Insert en `chat_member_hidden` (auto-hide) |
| **Leave** | `channel.remove_members([user_id])` | Delete de `chat_members` |
| **Delete Group** | `channel.delete()` + `truncate()` | Update `status = CLOSED` |

**Manejo de errores:** Si Stream falla, la operación continúa en BD local y se loguea el error para retry posterior.

---

## Notas Técnicas

### Multi-tenancy

- Todos los endpoints validan que el chat pertenezca al `gym_id` del header `X-Gym-ID`
- No es posible acceder a chats de otros gimnasios

### Cache

- Operaciones invalidan cache automáticamente
- Las keys de cache afectadas: `channel_{room_id}`, `user_rooms_{user_id}`

### Stream Chat IDs

El sistema usa IDs internos en formato `user_{id}` para Stream Chat. La conversión es automática.

---

## Quick Reference - Guía Rápida

### ¿Qué Endpoint Usar?

```
┌─ ¿Es chat 1-to-1 o grupo?
│
├─ Chat 1-to-1
│  │
│  ├─ ¿Quieres solo ocultarlo?
│  │  └─ POST /rooms/{id}/hide ✅
│  │
│  ├─ ¿Quieres eliminar los mensajes?
│  │  └─ DELETE /rooms/{id}/conversation ✅ (Delete For Me)
│  │
│  └─ ¿Quieres mostrarlo de nuevo?
│     └─ POST /rooms/{id}/show ✅
│
└─ Grupo
   │
   ├─ ¿Quieres salir del grupo?
   │  └─ POST /rooms/{id}/leave ✅
   │
   ├─ ¿Eres admin y quieres eliminarlo? (debe estar vacío)
   │  └─ DELETE /rooms/{id} ✅
   │
   └─ ¿Quieres mostrarlo después de salir?
      └─ POST /rooms/{id}/show ✅
```

### Comparación Rápida

| Necesito... | Chat 1-to-1 | Grupo |
|-------------|-------------|-------|
| **Ocultar temporalmente** | `POST /hide` | `POST /leave` |
| **Eliminar mensajes** | `DELETE /conversation` | N/A (usa leave) |
| **Mostrar de nuevo** | `POST /show` | `POST /show` |
| **Eliminar completamente** | N/A (usa /conversation) | `DELETE /rooms/{id}` (admin) |

### Checklist por Operación

#### ✅ Hide Chat
- [ ] Es chat 1-to-1
- [ ] Solo quiero ocultarlo
- [ ] Quiero poder verlo después

#### ✅ Delete For Me
- [ ] Es chat 1-to-1
- [ ] Quiero borrar mi historial
- [ ] Entiendo que es permanente
- [ ] El otro usuario mantiene su historial

#### ✅ Leave Group
- [ ] Es un grupo
- [ ] Quiero salir definitivamente
- [ ] Entiendo que necesito que me agreguen de nuevo

#### ✅ Delete Group
- [ ] Es un grupo
- [ ] Soy admin/creador
- [ ] Removí TODOS los miembros
- [ ] Entiendo que es permanente

---

## Recursos Adicionales

### Documentación Relacionada
- 📖 [Guía Detallada: Delete For Me](./CHAT_DELETE_CONVERSATION_GUIDE.md) - Guía completa con implementación iOS
- 📖 [Stream Chat Documentation](https://getstream.io/chat/docs/) - Documentación oficial de Stream
- 📖 [Auth0 Scopes](https://auth0.com/docs/get-started/apis/scopes) - Guía de scopes OAuth2

### Referencias de Patrones
- 💬 [WhatsApp Delete vs Clear](https://mobiletrans.wondershare.com/whatsapp/clear-chat-vs-delete-chat.html)
- 💬 [WhatsApp Group Management](https://blog.peppercloud.com/how-to-delete-a-whatsapp-group/)
- 🔧 [Stream Chat Hide/Mute](https://getstream.io/chat/docs/python/muting_channels/)
- 🔧 [Stream Chat Delete Messages](https://getstream.io/chat/docs/python/send_message/?language=python#deleting-a-message)

---

**Versión:** 1.1.0
**Última actualización:** 2025-12-13
**Endpoints base:** `/api/v1/chat`
**Incluye:** Hide, Show, Leave, Delete Group, Delete For Me (NEW)
