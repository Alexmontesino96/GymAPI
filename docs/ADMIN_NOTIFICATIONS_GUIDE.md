# Guía de Notificaciones Push para Admins/Owners

## Descripción

Sistema de notificaciones push para que **OWNERS y ADMINS** de gimnasios puedan enviar mensajes a sus miembros usando OneSignal.

---

## 🔑 Permisos Requeridos

**Roles permitidos:**
- ✅ **OWNER** - Dueño del gimnasio
- ✅ **ADMIN** - Administrador del gimnasio
- ❌ **TRAINER** - No permitido
- ❌ **MEMBER** - No permitido

---

## 📡 Endpoints Disponibles

### 1. Enviar a Usuarios Específicos

**Endpoint:** `POST /api/v1/notifications/send`

**Descripción:** Envía notificación a una lista específica de usuarios por sus IDs.

**Headers:**
```json
{
  "Authorization": "Bearer <token_auth0>",
  "Content-Type": "application/json"
}
```

**Request Body:**
```json
{
  "user_ids": ["123", "456", "789"],
  "title": "Nuevo Horario de Clases",
  "message": "Revisa los nuevos horarios para la próxima semana",
  "data": {
    "type": "schedule_update",
    "action": "open_schedule",
    "schedule_id": "42"
  }
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Notification queued for 3 recipients"
}
```

**Errores:**
- **401** - No autenticado
- **403** - No tienes permisos de admin/owner
- **422** - Datos inválidos

---

### 2. Enviar a TODOS los Miembros del Gym

**Endpoint:** `POST /api/v1/notifications/send-to-gym`

**Descripción:** Envía notificación a **TODOS** los usuarios del gimnasio actual.

**Headers:**
```json
{
  "Authorization": "Bearer <token_auth0>",
  "Content-Type": "application/json"
}
```

**Request Body:**
```json
{
  "title": "Cierre Temporal por Mantenimiento",
  "message": "El gimnasio estará cerrado el próximo lunes por mantenimiento",
  "data": {
    "type": "announcement",
    "priority": "high"
  }
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Notificación programada para 150 usuarios del gimnasio"
}
```

**Response (200) - Sin usuarios:**
```json
{
  "success": false,
  "errors": ["No hay usuarios registrados en este gimnasio"]
}
```

**Errores:**
- **401** - No autenticado
- **403** - No tienes permisos de admin/owner
- **422** - Datos inválidos

---

## 📋 Campos del Request

### NotificationSend (usuarios específicos)

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `user_ids` | `string[]` | ✅ Sí | Lista de IDs de usuarios destinatarios |
| `title` | `string` | ✅ Sí | Título de la notificación (max 65 chars para OneSignal) |
| `message` | `string` | ✅ Sí | Mensaje de la notificación (max 180 chars recomendado) |
| `data` | `object` | ❌ No | Datos adicionales para la app (JSON libre) |

### GymNotificationRequest (todos los usuarios)

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `title` | `string` | ✅ Sí | Título de la notificación |
| `message` | `string` | ✅ Sí | Mensaje de la notificación |
| `data` | `object` | ❌ No | Datos adicionales para la app |

---

## 💻 Ejemplos de Código

### JavaScript (Fetch)

```javascript
const API_BASE = 'https://gymapi-eh6m.onrender.com/api/v1';

// Obtener token de autenticación (Auth0)
const token = await getAuthToken(); // Tu función de Auth0

// Opción 1: Enviar a usuarios específicos
async function sendToSpecificUsers(userIds, title, message, data = null) {
  const response = await fetch(`${API_BASE}/notifications/send`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      user_ids: userIds,
      title,
      message,
      data
    })
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Error enviando notificación');
  }

  return await response.json();
}

// Opción 2: Enviar a todos los usuarios del gym
async function sendToAllGymMembers(title, message, data = null) {
  const response = await fetch(`${API_BASE}/notifications/send-to-gym`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      title,
      message,
      data
    })
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Error enviando notificación');
  }

  return await response.json();
}

// Uso
try {
  // Enviar a usuarios específicos
  const result1 = await sendToSpecificUsers(
    ['user_123', 'user_456'],
    'Nueva Clase de Yoga',
    'Revisa la nueva clase de yoga los martes a las 6pm',
    { type: 'new_class', class_id: '42' }
  );
  console.log(result1.message); // "Notification queued for 2 recipients"

  // Enviar a todos
  const result2 = await sendToAllGymMembers(
    'Cierre por Mantenimiento',
    'El gimnasio estará cerrado mañana por mantenimiento',
    { type: 'announcement', priority: 'high' }
  );
  console.log(result2.message); // "Notificación programada para 150 usuarios..."

} catch (error) {
  console.error('Error:', error.message);
}
```

---

### Axios

```javascript
import axios from 'axios';

const api = axios.create({
  baseURL: 'https://gymapi-eh6m.onrender.com/api/v1',
  headers: {
    'Authorization': `Bearer ${token}`
  }
});

// Enviar a usuarios específicos
const sendToUsers = async (userIds, title, message, data) => {
  try {
    const { data: response } = await api.post('/notifications/send', {
      user_ids: userIds,
      title,
      message,
      data
    });

    return response;
  } catch (error) {
    if (error.response?.status === 403) {
      throw new Error('No tienes permisos para enviar notificaciones');
    }
    throw error;
  }
};

// Enviar a todos del gym
const sendToGym = async (title, message, data) => {
  try {
    const { data: response } = await api.post('/notifications/send-to-gym', {
      title,
      message,
      data
    });

    return response;
  } catch (error) {
    if (error.response?.status === 403) {
      throw new Error('No tienes permisos de administrador');
    }
    throw error;
  }
};
```

---

### React Hook

```javascript
import { useState } from 'react';
import axios from 'axios';

export function useNotifications(authToken) {
  const [sending, setSending] = useState(false);
  const [error, setError] = useState(null);

  const api = axios.create({
    baseURL: 'https://gymapi-eh6m.onrender.com/api/v1',
    headers: {
      'Authorization': `Bearer ${authToken}`
    }
  });

  const sendToUsers = async (userIds, title, message, data = null) => {
    setSending(true);
    setError(null);

    try {
      const { data } = await api.post('/notifications/send', {
        user_ids: userIds,
        title,
        message,
        data
      });

      return data;
    } catch (err) {
      const errorMsg = err.response?.data?.detail || 'Error enviando notificación';
      setError(errorMsg);
      throw new Error(errorMsg);
    } finally {
      setSending(false);
    }
  };

  const sendToAllMembers = async (title, message, data = null) => {
    setSending(true);
    setError(null);

    try {
      const { data } = await api.post('/notifications/send-to-gym', {
        title,
        message,
        data
      });

      return data;
    } catch (err) {
      const errorMsg = err.response?.data?.detail || 'Error enviando notificación';
      setError(errorMsg);
      throw new Error(errorMsg);
    } finally {
      setSending(false);
    }
  };

  return {
    sendToUsers,
    sendToAllMembers,
    sending,
    error
  };
}

// Uso en componente
function NotificationPanel() {
  const { authToken } = useAuth(); // Tu hook de autenticación
  const { sendToAllMembers, sending, error } = useNotifications(authToken);

  const [title, setTitle] = useState('');
  const [message, setMessage] = useState('');

  const handleSend = async () => {
    try {
      const result = await sendToAllMembers(title, message, {
        type: 'manual_notification',
        sent_at: new Date().toISOString()
      });

      alert(`✅ ${result.message}`);
      setTitle('');
      setMessage('');
    } catch (error) {
      alert(`❌ ${error.message}`);
    }
  };

  return (
    <div>
      <h2>Enviar Notificación a Todos los Miembros</h2>

      <input
        type="text"
        placeholder="Título"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        maxLength={65}
      />

      <textarea
        placeholder="Mensaje"
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        maxLength={180}
      />

      <button onClick={handleSend} disabled={sending || !title || !message}>
        {sending ? 'Enviando...' : 'Enviar Notificación'}
      </button>

      {error && <div className="error">{error}</div>}
    </div>
  );
}
```

---

## 📊 Casos de Uso

### 1. Anuncio General

```javascript
await sendToAllGymMembers(
  'Nuevo Horario de Verano',
  'A partir del lunes, el gimnasio abrirá de 6am a 10pm',
  {
    type: 'announcement',
    category: 'schedule',
    priority: 'normal'
  }
);
```

### 2. Evento Especial

```javascript
await sendToAllGymMembers(
  'Clase Especial de Spinning',
  'Este sábado a las 10am con instructor invitado. ¡Regístrate!',
  {
    type: 'event',
    event_id: '123',
    action: 'open_event_details'
  }
);
```

### 3. Recordatorio de Pago

```javascript
const usersWithPendingPayment = ['user_1', 'user_2', 'user_3'];

await sendToSpecificUsers(
  usersWithPendingPayment,
  'Pago Pendiente',
  'Tu mensualidad está próxima a vencer. Paga antes del viernes para evitar cargos',
  {
    type: 'payment_reminder',
    due_date: '2024-12-25',
    action: 'open_billing'
  }
);
```

### 4. Cierre Temporal

```javascript
await sendToAllGymMembers(
  'Cierre por Mantenimiento',
  'El gimnasio estará cerrado mañana de 8am a 12pm por mantenimiento de aires acondicionados',
  {
    type: 'maintenance',
    priority: 'high',
    start_time: '2024-12-20T08:00:00Z',
    end_time: '2024-12-20T12:00:00Z'
  }
);
```

### 5. Nuevo Contenido

```javascript
await sendToAllGymMembers(
  'Nueva Rutina Disponible',
  'Revisa la nueva rutina de fuerza para principiantes en la app',
  {
    type: 'new_content',
    content_type: 'routine',
    content_id: '456',
    action: 'open_routine'
  }
);
```

---

## 🎯 Campo `data` - Mejores Prácticas

El campo `data` es un JSON libre que puedes usar para enviar información adicional a la app móvil:

### Estructura Recomendada

```javascript
{
  type: string,        // Tipo de notificación (announcement, event, payment, etc)
  action: string,      // Acción que debe realizar la app (open_screen, open_url, etc)
  priority: string,    // Prioridad (low, normal, high, urgent)

  // Campos específicos según el tipo
  event_id: number,
  class_id: number,
  user_id: string,
  url: string,

  // Metadata adicional
  timestamp: string,
  expires_at: string
}
```

### Ejemplos

**Abrir pantalla específica:**
```json
{
  "type": "navigation",
  "action": "open_screen",
  "screen": "EventDetails",
  "params": {
    "event_id": "123"
  }
}
```

**Abrir URL externa:**
```json
{
  "type": "link",
  "action": "open_url",
  "url": "https://mi-gimnasio.com/promo-verano"
}
```

**Deep link en la app:**
```json
{
  "type": "deeplink",
  "action": "navigate",
  "path": "/classes/42",
  "priority": "normal"
}
```

---

## 🔔 Límites y Consideraciones

### OneSignal

- **Título:** Máximo 65 caracteres (recomendado para visualización óptima)
- **Mensaje:** Máximo 180 caracteres (recomendado, puede ser más pero se trunca)
- **Data:** Sin límite estricto pero mantenerlo < 2KB

### Rate Limiting

- **Endpoint:** No hay límite específico actualmente
- **Recomendación:** No enviar más de 1 notificación por minuto a todos los usuarios

### Procesamiento

- Las notificaciones se **procesan en background** (no bloquean la respuesta)
- El endpoint responde inmediatamente aunque la notificación aún no se haya enviado
- OneSignal puede tardar unos segundos en entregar las notificaciones

---

## ⚠️ Errores Comunes

### Error 403: Forbidden

```json
{
  "detail": "Insufficient permissions"
}
```

**Causa:** El usuario no tiene rol de ADMIN u OWNER.
**Solución:** Verificar que el token Auth0 corresponda a un usuario con permisos de administrador.

### Error 422: Validation Error

```json
{
  "detail": [
    {
      "loc": ["body", "title"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

**Causa:** Falta un campo requerido (title o message).
**Solución:** Enviar todos los campos obligatorios.

### Error 401: Unauthorized

```json
{
  "detail": "Not authenticated"
}
```

**Causa:** Token Auth0 faltante o inválido.
**Solución:** Incluir header `Authorization: Bearer <token>` válido.

---

## 📱 Integración con Dispositivos

### Registro de Dispositivos

Antes de recibir notificaciones, los usuarios deben registrar sus dispositivos:

**Endpoint:** `POST /api/v1/notifications/devices`

```json
{
  "device_token": "ExponentPushToken[xxxxxxxxxxxxxx]",
  "platform": "ios"
}
```

Ver documentación completa de registro de dispositivos en la sección de usuarios.

---

## 🧪 Testing

### Probar en Swagger

1. Ir a https://gymapi-eh6m.onrender.com/api/v1/docs
2. Autorizar con token de ADMIN/OWNER
3. Usar endpoint `POST /api/v1/notifications/send-to-gym`
4. Enviar notificación de prueba

### Ejemplo con cURL

```bash
curl -X 'POST' \
  'https://gymapi-eh6m.onrender.com/api/v1/notifications/send-to-gym' \
  -H 'Authorization: Bearer <tu_token_aqui>' \
  -H 'Content-Type: application/json' \
  -d '{
  "title": "Prueba de Notificación",
  "message": "Esta es una prueba del sistema de notificaciones",
  "data": {
    "type": "test",
    "timestamp": "2024-12-19T10:00:00Z"
  }
}'
```

---

## 📚 Referencias

- **OneSignal Docs:** https://documentation.onesignal.com
- **Límites de caracteres:** https://documentation.onesignal.com/docs/message-limits
- **Rich notifications:** https://documentation.onesignal.com/docs/rich-media

---

## ✅ Checklist de Implementación Frontend

- [ ] Obtener token Auth0 del usuario autenticado
- [ ] Verificar que el usuario tenga rol ADMIN u OWNER
- [ ] Implementar formulario para título y mensaje
- [ ] Validar longitud de título (≤65 chars) y mensaje (≤180 chars)
- [ ] Manejar estados de loading durante envío
- [ ] Mostrar mensaje de éxito con número de destinatarios
- [ ] Manejar errores (403, 401, 422) con mensajes claros
- [ ] Implementar campo `data` opcional para casos avanzados
- [ ] Probar con usuarios reales antes de producción
