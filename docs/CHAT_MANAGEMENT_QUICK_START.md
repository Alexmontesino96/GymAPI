# Chat Management - Guía Rápida

Referencia rápida de los endpoints de gestión de chats estilo WhatsApp.

## 🚀 Quick Start

### Configuración

```javascript
const API_BASE = 'https://api.tugym.com/api/v1/chat';
const headers = {
  'Authorization': `Bearer ${authToken}`,
  'X-Gym-ID': '1',
  'Content-Type': 'application/json'
};
```

---

## 📋 Endpoints

### 1. Ocultar Chat 1-to-1

```javascript
// POST /rooms/{room_id}/hide
await fetch(`${API_BASE}/rooms/123/hide`, {
  method: 'POST',
  headers
});

// ✅ Chat ocultado solo para ti
// ✅ El otro usuario no se entera
```

---

### 2. Mostrar Chat Oculto

```javascript
// POST /rooms/{room_id}/show
await fetch(`${API_BASE}/rooms/123/show`, {
  method: 'POST',
  headers
});

// ✅ Chat visible nuevamente
```

---

### 3. Salir de Grupo

```javascript
// POST /rooms/{room_id}/leave?auto_hide=true
const response = await fetch(`${API_BASE}/rooms/456/leave?auto_hide=true`, {
  method: 'POST',
  headers
});

const data = await response.json();

if (data.group_deleted) {
  console.log('Eras el último miembro, grupo eliminado');
} else {
  console.log(`Quedan ${data.remaining_members} miembros`);
}

// ✅ Removido del grupo en Stream
// ✅ Chat ocultado automáticamente
// ✅ Si último miembro → grupo cerrado
```

---

### 4. Eliminar Grupo (Admin/Creador)

```javascript
// DELETE /rooms/{room_id}?hard_delete=true
// ⚠️ REQUISITO: Grupo DEBE estar vacío (0 miembros)

await fetch(`${API_BASE}/rooms/789?hard_delete=true`, {
  method: 'DELETE',
  headers
});

// ✅ Grupo eliminado de Stream
// ✅ Todos los mensajes borrados
// ❌ Acción irreversible
```

---

## 📊 Matriz de Permisos

| Acción | Member | Trainer | Admin/Owner |
|--------|--------|---------|-------------|
| Hide 1-to-1 | ✅ | ✅ | ✅ |
| Leave grupo | ✅ | ✅ | ✅ |
| Delete propio grupo | ❌ | ✅ | ✅ |
| Delete cualquier grupo | ❌ | ❌ | ✅ |

---

## 🎯 Reglas por Tipo de Chat

### Chat 1-to-1 (Directo)

```javascript
✅ Hide - Oculta solo para ti
✅ Show - Muestra oculto
❌ Leave - Usar Hide
❌ Delete - Usar Hide
```

### Grupo Normal

```javascript
❌ Hide - Usar Leave
✅ Leave - Salir del grupo
✅ Delete - Solo admin/creador (si vacío)
```

### Chat de Evento

```javascript
❌ Hide - No permitido
❌ Leave - Se cierra automáticamente al finalizar evento
❌ Delete - Solo limpieza automática admin
```

---

## 🔍 Listar Chats

### Solo chats visibles (default)

```javascript
const activeChats = await fetch(`${API_BASE}/my-rooms`, { headers })
  .then(r => r.json());

console.log('Chats activos:', activeChats.length);
```

### Incluir chats ocultos

```javascript
const allChats = await fetch(`${API_BASE}/my-rooms?include_hidden=true`, { headers })
  .then(r => r.json());

const hiddenChats = allChats.filter(chat => chat.is_hidden);
console.log('Chats ocultos:', hiddenChats.length);
```

---

## 💡 Casos de Uso Comunes

### Caso 1: Usuario oculta spam

```javascript
// Ocultar chat molesto
await fetch(`${API_BASE}/rooms/123/hide`, {
  method: 'POST',
  headers
});

// ✅ Chat desaparece de la lista
// ✅ Otro usuario NO notificado
```

### Caso 2: Usuario sale de grupo

```javascript
// Salir y ocultar
const { group_deleted, remaining_members } = await fetch(
  `${API_BASE}/rooms/456/leave?auto_hide=true`,
  { method: 'POST', headers }
).then(r => r.json());

if (group_deleted) {
  alert('Grupo eliminado (eras el último)');
} else {
  alert(`Saliste del grupo. Quedan ${remaining_members} miembros`);
}
```

### Caso 3: Admin limpia grupo vacío

```javascript
// Verificar vacío
const room = await fetch(`${API_BASE}/rooms/789`, { headers })
  .then(r => r.json());

if (room.members.length === 0) {
  // Eliminar permanentemente
  await fetch(`${API_BASE}/rooms/789?hard_delete=true`, {
    method: 'DELETE',
    headers
  });

  console.log('Grupo eliminado ✅');
} else {
  console.log(`⚠️ Quedan ${room.members.length} miembros. Removerlos primero.`);
}
```

---

## ⚠️ Errores Comunes

### 400: Chat incorrecto

```json
{
  "detail": "Solo puedes ocultar chats directos 1-to-1. Para grupos, debes salir primero usando 'leave group'."
}
```

**Solución:** Verificar tipo de chat antes de llamar hide/leave

---

### 403: Sin permisos

```json
{
  "detail": "Los entrenadores solo pueden eliminar grupos que ellos crearon."
}
```

**Solución:** Verificar rol y creador del grupo

---

### 400: Grupo no vacío

```json
{
  "detail": "Debes remover a todos los miembros (3 restantes) antes de eliminar el grupo."
}
```

**Solución:** Remover todos los miembros primero

---

## 🧪 Testing

### cURL Examples

```bash
# Hide chat
curl -X POST "https://api.tugym.com/api/v1/chat/rooms/123/hide" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "X-Gym-ID: 1"

# Leave group
curl -X POST "https://api.tugym.com/api/v1/chat/rooms/456/leave?auto_hide=true" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "X-Gym-ID: 1"

# Delete group (hard)
curl -X DELETE "https://api.tugym.com/api/v1/chat/rooms/789?hard_delete=true" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "X-Gym-ID: 1"
```

---

## 📚 Documentación Completa

Para ejemplos detallados, códigos de error y más información:

👉 [Ver documentación completa](./CHAT_MANAGEMENT_API.md)

---

## 🔗 Enlaces Útiles

- [Stream Chat Docs](https://getstream.io/chat/docs/)
- [Auth0 JWT Tokens](https://auth0.com/docs/secure/tokens/json-web-tokens)
- [Multi-tenancy Guide](../CLAUDE.md#arquitectura-multi-tenant)

---

**Versión:** 1.0.0
**Última actualización:** 2025-12-13
