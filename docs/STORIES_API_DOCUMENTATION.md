# API de Historias - Documentación Completa

## 📚 Índice
- [Autenticación](#autenticación)
- [Endpoints](#endpoints)
  - [Crear Historia](#1-crear-historia)
  - [Obtener Feed de Historias](#2-obtener-feed-de-historias)
  - [Obtener Historias de Usuario](#3-obtener-historias-de-usuario)
  - [Obtener Historia Específica](#4-obtener-historia-específica)
  - [Marcar Historia como Vista](#5-marcar-historia-como-vista)
  - [Obtener Viewers de Historia](#6-obtener-viewers-de-historia)
  - [Agregar Reacción](#7-agregar-reacción)
  - [Actualizar Historia](#8-actualizar-historia)
  - [Eliminar Historia](#9-eliminar-historia)
  - [Reportar Historia](#10-reportar-historia)
  - [Crear Highlight](#11-crear-highlight)
- [Tipos de Datos](#tipos-de-datos)
- [Códigos de Error](#códigos-de-error)

## 🔐 Autenticación

Todos los endpoints requieren autenticación mediante JWT token de Auth0.

**Headers requeridos:**
```http
Authorization: Bearer {jwt_token}
```

El token debe incluir el `gym_id` en los custom claims para la segmentación multi-tenant.

---

## 📡 Endpoints

### 1. Crear Historia

**POST** `/api/v1/stories/`

Crea una nueva historia en el gimnasio actual.

#### Request

**Content-Type:** `multipart/form-data` o `application/x-www-form-urlencoded`

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `caption` | string | No | Texto o caption de la historia (máx. 500 caracteres) |
| `story_type` | string | Sí | Tipo: `image`, `video`, `text`, `workout`, `achievement` |
| `privacy` | string | No | Nivel: `public`, `followers`, `close_friends`, `private` (default: `public`) |
| `duration_hours` | integer | No | Duración antes de expirar: 1-48 horas (default: 24) |
| `workout_data` | string (JSON) | No* | Datos del entrenamiento (requerido si `story_type=workout`) |
| `media` | file | No* | Archivo de imagen/video a subir |
| `media_url` | string | No* | URL de media ya subida (alternativo a `media`) |

*Al menos uno de `media` o `media_url` es requerido para tipos `image` y `video`.

#### Ejemplo de Request

```bash
curl -X POST http://localhost:8000/api/v1/stories/ \
  -H "Authorization: Bearer {token}" \
  -F "caption=Nuevo PR en sentadilla! 💪" \
  -F "story_type=image" \
  -F "privacy=public" \
  -F "duration_hours=24" \
  -F "media=@/path/to/image.jpg"
```

#### Response (201 Created)

```json
{
  "id": 123,
  "gym_id": 4,
  "user_id": 456,
  "story_type": "image",
  "caption": "Nuevo PR en sentadilla! 💪",
  "privacy": "public",
  "media_url": "https://storage.supabase.co/stories/gym_4/user_456/abc123.jpg",
  "thumbnail_url": "https://storage.supabase.co/stories/gym_4/user_456/abc123_thumb.jpg",
  "workout_data": null,
  "view_count": 0,
  "reaction_count": 0,
  "is_pinned": false,
  "is_expired": false,
  "is_own_story": true,
  "has_viewed": false,
  "has_reacted": false,
  "created_at": "2025-11-08T10:30:00Z",
  "expires_at": "2025-11-09T10:30:00Z",
  "user_info": {
    "id": 456,
    "name": "Juan Pérez",
    "avatar": "https://example.com/avatar.jpg"
  }
}
```

---

### 2. Obtener Feed de Historias

**GET** `/api/v1/stories/feed`

Obtiene el feed de historias del gimnasio, agrupadas por usuario.

#### Query Parameters

| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `limit` | integer | No | Número de historias por página (1-100, default: 25) |
| `offset` | integer | No | Offset para paginación (default: 0) |
| `filter_type` | string | No | Filtro: `all`, `following`, `close_friends` |
| `story_types` | array | No | Filtrar por tipos específicos |

#### Ejemplo de Request

```bash
curl -X GET "http://localhost:8000/api/v1/stories/feed?limit=10&filter_type=all" \
  -H "Authorization: Bearer {token}"
```

#### Response (200 OK)

```json
{
  "user_stories": [
    {
      "user_id": 456,
      "user_name": "Juan Pérez",
      "user_avatar": "https://example.com/avatar1.jpg",
      "has_unseen": true,
      "stories": [
        {
          "id": 123,
          "story_type": "image",
          "caption": "Día de piernas 🦵",
          "media_url": "https://storage.example.com/story1.jpg",
          "thumbnail_url": "https://storage.example.com/story1_thumb.jpg",
          "created_at": "2025-11-08T10:00:00Z",
          "expires_at": "2025-11-09T10:00:00Z",
          "is_pinned": false,
          "has_viewed": false,
          "view_count": 15,
          "reaction_count": 5
        },
        {
          "id": 124,
          "story_type": "text",
          "caption": "Sin excusas! 💯",
          "media_url": null,
          "created_at": "2025-11-08T11:00:00Z",
          "expires_at": "2025-11-09T11:00:00Z",
          "is_pinned": false,
          "has_viewed": true,
          "view_count": 10,
          "reaction_count": 3
        }
      ]
    },
    {
      "user_id": 789,
      "user_name": "María García",
      "user_avatar": "https://example.com/avatar2.jpg",
      "has_unseen": false,
      "stories": [
        {
          "id": 125,
          "story_type": "workout",
          "caption": "Rutina completa ✅",
          "media_url": null,
          "workout_data": {
            "exercise": "Bench Press",
            "weight": 80,
            "reps": 10,
            "sets": 4
          },
          "created_at": "2025-11-08T09:00:00Z",
          "expires_at": "2025-11-09T09:00:00Z",
          "is_pinned": false,
          "has_viewed": true,
          "view_count": 20,
          "reaction_count": 8
        }
      ]
    }
  ],
  "total_users": 2,
  "has_more": false,
  "next_offset": null,
  "last_update": "2025-11-08T12:00:00Z"
}
```

---

### 3. Obtener Historias de Usuario

**GET** `/api/v1/stories/user/{user_id}`

Obtiene todas las historias de un usuario específico.

#### Path Parameters

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `user_id` | integer | ID del usuario |

#### Query Parameters

| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `include_expired` | boolean | No | Incluir historias expiradas (solo propias, default: false) |

#### Ejemplo de Request

```bash
curl -X GET "http://localhost:8000/api/v1/stories/user/456?include_expired=false" \
  -H "Authorization: Bearer {token}"
```

#### Response (200 OK)

```json
{
  "stories": [
    {
      "id": 123,
      "gym_id": 4,
      "user_id": 456,
      "story_type": "image",
      "caption": "Nuevo PR! 💪",
      "privacy": "public",
      "media_url": "https://storage.example.com/story.jpg",
      "thumbnail_url": "https://storage.example.com/story_thumb.jpg",
      "view_count": 25,
      "reaction_count": 10,
      "is_expired": false,
      "is_own_story": false,
      "has_viewed": true,
      "has_reacted": false,
      "created_at": "2025-11-08T10:00:00Z",
      "expires_at": "2025-11-09T10:00:00Z",
      "user_info": {
        "id": 456,
        "name": "Juan Pérez",
        "avatar": "https://example.com/avatar.jpg"
      }
    }
  ],
  "total": 1,
  "has_more": false,
  "next_offset": null
}
```

---

### 4. Obtener Historia Específica

**GET** `/api/v1/stories/{story_id}`

Obtiene los detalles de una historia específica.

#### Path Parameters

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `story_id` | integer | ID de la historia |

#### Ejemplo de Request

```bash
curl -X GET "http://localhost:8000/api/v1/stories/123" \
  -H "Authorization: Bearer {token}"
```

#### Response (200 OK)

```json
{
  "id": 123,
  "gym_id": 4,
  "user_id": 456,
  "story_type": "image",
  "caption": "Día de piernas 🦵",
  "privacy": "public",
  "media_url": "https://storage.example.com/story.jpg",
  "thumbnail_url": "https://storage.example.com/story_thumb.jpg",
  "workout_data": null,
  "view_count": 30,
  "reaction_count": 12,
  "is_pinned": false,
  "is_expired": false,
  "is_own_story": false,
  "has_viewed": true,
  "has_reacted": true,
  "created_at": "2025-11-08T10:00:00Z",
  "expires_at": "2025-11-09T10:00:00Z",
  "user_info": {
    "id": 456,
    "name": "Juan Pérez",
    "avatar": "https://example.com/avatar.jpg"
  }
}
```

---

### 5. Marcar Historia como Vista

**POST** `/api/v1/stories/{story_id}/view`

Marca una historia como vista por el usuario actual.

#### Path Parameters

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `story_id` | integer | ID de la historia |

#### Request Body (Opcional)

```json
{
  "view_duration_seconds": 5,
  "device_info": "iOS"
}
```

#### Ejemplo de Request

```bash
curl -X POST "http://localhost:8000/api/v1/stories/123/view" \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"view_duration_seconds": 3}'
```

#### Response (200 OK)

```json
{
  "success": true,
  "message": "Historia marcada como vista"
}
```

---

### 6. Obtener Viewers de Historia

**GET** `/api/v1/stories/{story_id}/viewers`

Obtiene la lista de usuarios que vieron una historia. **Solo el dueño de la historia puede ver esta información.**

#### Path Parameters

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `story_id` | integer | ID de la historia |

#### Ejemplo de Request

```bash
curl -X GET "http://localhost:8000/api/v1/stories/123/viewers" \
  -H "Authorization: Bearer {token}"
```

#### Response (200 OK)

```json
[
  {
    "viewer_id": 789,
    "viewer_name": "María García",
    "viewer_avatar": "https://example.com/avatar1.jpg",
    "viewed_at": "2025-11-08T10:15:00Z",
    "view_duration_seconds": 5
  },
  {
    "viewer_id": 101,
    "viewer_name": "Carlos López",
    "viewer_avatar": "https://example.com/avatar2.jpg",
    "viewed_at": "2025-11-08T10:30:00Z",
    "view_duration_seconds": 3
  }
]
```

#### Response (403 Forbidden) - Si no eres el dueño

```json
{
  "detail": "No tienes permiso para ver esta información"
}
```

---

### 7. Agregar Reacción

**POST** `/api/v1/stories/{story_id}/reaction`

Agrega una reacción con emoji a una historia.

#### Path Parameters

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `story_id` | integer | ID de la historia |

#### Request Body

```json
{
  "emoji": "🔥",
  "message": "Increíble progreso!"
}
```

**Emojis permitidos:** 💪, 🔥, ❤️, 👏, 💯, 🎯, ⚡, 🏆, 💥, 🙌

#### Ejemplo de Request

```bash
curl -X POST "http://localhost:8000/api/v1/stories/123/reaction" \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"emoji": "🔥", "message": "Excelente forma!"}'
```

#### Response (200 OK)

```json
{
  "success": true,
  "reaction_id": 456,
  "message": "Reacción agregada exitosamente"
}
```

---

### 8. Actualizar Historia

**PUT** `/api/v1/stories/{story_id}`

Actualiza el caption o privacidad de una historia. **Solo el dueño puede actualizar.**

#### Path Parameters

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `story_id` | integer | ID de la historia |

#### Request Body

```json
{
  "caption": "Nuevo caption actualizado",
  "privacy": "followers"
}
```

#### Ejemplo de Request

```bash
curl -X PUT "http://localhost:8000/api/v1/stories/123" \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"caption": "PR actualizado: 150kg! 💪🔥"}'
```

#### Response (200 OK)

```json
{
  "id": 123,
  "gym_id": 4,
  "user_id": 456,
  "story_type": "image",
  "caption": "PR actualizado: 150kg! 💪🔥",
  "privacy": "followers",
  "media_url": "https://storage.example.com/story.jpg",
  "thumbnail_url": "https://storage.example.com/story_thumb.jpg",
  "view_count": 30,
  "reaction_count": 12,
  "is_expired": false,
  "is_own_story": true,
  "has_viewed": false,
  "has_reacted": false,
  "created_at": "2025-11-08T10:00:00Z",
  "expires_at": "2025-11-09T10:00:00Z",
  "user_info": {
    "id": 456,
    "name": "Tu Nombre",
    "avatar": "https://example.com/tu-avatar.jpg"
  }
}
```

---

### 9. Eliminar Historia

**DELETE** `/api/v1/stories/{story_id}`

Elimina una historia (soft delete). **Solo el dueño puede eliminar.**

#### Path Parameters

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `story_id` | integer | ID de la historia |

#### Ejemplo de Request

```bash
curl -X DELETE "http://localhost:8000/api/v1/stories/123" \
  -H "Authorization: Bearer {token}"
```

#### Response (200 OK)

```json
{
  "success": true,
  "message": "Historia eliminada exitosamente"
}
```

#### Response (403 Forbidden) - Si no eres el dueño

```json
{
  "detail": "No tienes permiso para eliminar esta historia"
}
```

---

### 10. Reportar Historia

**POST** `/api/v1/stories/{story_id}/report`

Reporta una historia por contenido inapropiado.

#### Path Parameters

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `story_id` | integer | ID de la historia |

#### Request Body

```json
{
  "reason": "inappropriate",
  "description": "Contenido ofensivo en la imagen"
}
```

**Razones válidas:** `spam`, `inappropriate`, `harassment`, `violence`, `false_information`, `other`

#### Ejemplo de Request

```bash
curl -X POST "http://localhost:8000/api/v1/stories/123/report" \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"reason": "spam", "description": "Publicidad no autorizada"}'
```

#### Response (200 OK)

```json
{
  "success": true,
  "report_id": 789,
  "message": "Historia reportada exitosamente. Será revisada por los administradores."
}
```

#### Response (400 Bad Request) - Si ya reportaste

```json
{
  "detail": "Ya has reportado esta historia"
}
```

---

### 11. Crear Highlight

**POST** `/api/v1/stories/highlights`

Crea una colección destacada de historias (no expiran).

#### Request Body

```json
{
  "title": "Mis mejores PRs",
  "cover_image_url": "https://example.com/cover.jpg",
  "story_ids": [123, 124, 125]
}
```

#### Ejemplo de Request

```bash
curl -X POST "http://localhost:8000/api/v1/stories/highlights" \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Progreso 2025",
    "story_ids": [123, 124, 125]
  }'
```

#### Response (200 OK)

```json
{
  "success": true,
  "highlight_id": 10,
  "message": "Highlight creado exitosamente"
}
```

---

## 📊 Tipos de Datos

### StoryType (Enum)
- `image` - Historia con imagen
- `video` - Historia con video
- `text` - Historia de solo texto
- `workout` - Historia con datos de entrenamiento
- `achievement` - Historia de logro alcanzado

### StoryPrivacy (Enum)
- `public` - Visible para todos los miembros del gimnasio
- `followers` - Solo seguidores (no implementado aún)
- `close_friends` - Solo amigos cercanos (no implementado aún)
- `private` - Solo visible para el creador

### WorkoutData (JSON)
```json
{
  "exercise": "Bench Press",
  "weight": 100,
  "weight_unit": "kg",
  "reps": 10,
  "sets": 4,
  "duration_minutes": 45,
  "calories_burned": 300,
  "notes": "Felt strong today!"
}
```

---

## 🚨 Códigos de Error

| Código | Descripción | Ejemplo de Respuesta |
|--------|-------------|---------------------|
| 400 | Bad Request - Datos inválidos | `{"detail": "workout_data debe ser un JSON válido"}` |
| 401 | Unauthorized - Sin autenticación | `{"detail": "Not authenticated"}` |
| 403 | Forbidden - Sin permisos | `{"detail": "No tienes permiso para ver esta historia"}` |
| 404 | Not Found - Recurso no encontrado | `{"detail": "Historia no encontrada"}` |
| 413 | Payload Too Large - Archivo muy grande | `{"detail": "El archivo excede el tamaño máximo permitido (10MB)"}` |
| 422 | Unprocessable Entity - Validación fallida | `{"detail": [{"loc": ["body", "emoji"], "msg": "Emoji inválido"}]}` |
| 500 | Internal Server Error | `{"detail": "Error al crear la historia"}` |
| 503 | Service Unavailable | `{"detail": "Servicio de almacenamiento no disponible"}` |

---

## 🔄 Paginación

Los endpoints que retornan listas usan paginación con los siguientes parámetros:

- `limit`: Número máximo de items por página (default: 25, max: 100)
- `offset`: Número de items a saltar (para páginas siguientes)

**Respuesta de paginación:**
```json
{
  "items": [...],
  "total": 150,
  "has_more": true,
  "next_offset": 25
}
```

---

## 💡 Ejemplos de Uso Completos

### Flujo Completo: Crear y Ver Historia

```bash
# 1. Crear una historia con imagen
curl -X POST http://localhost:8000/api/v1/stories/ \
  -H "Authorization: Bearer ${TOKEN}" \
  -F "caption=Mi rutina de hoy 💪" \
  -F "story_type=image" \
  -F "privacy=public" \
  -F "media=@workout.jpg"

# Response: {"id": 123, "media_url": "...", ...}

# 2. Obtener el feed de historias
curl -X GET "http://localhost:8000/api/v1/stories/feed" \
  -H "Authorization: Bearer ${TOKEN}"

# 3. Marcar una historia como vista
curl -X POST "http://localhost:8000/api/v1/stories/123/view" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d '{"view_duration_seconds": 5}'

# 4. Agregar una reacción
curl -X POST "http://localhost:8000/api/v1/stories/123/reaction" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"emoji": "🔥", "message": "Brutal!"}'

# 5. Ver quién vio tu historia (solo si eres el dueño)
curl -X GET "http://localhost:8000/api/v1/stories/123/viewers" \
  -H "Authorization: Bearer ${TOKEN}"
```

### Crear Historia de Entrenamiento

```bash
curl -X POST http://localhost:8000/api/v1/stories/ \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "caption=Nuevo récord personal!" \
  -d "story_type=workout" \
  -d 'workout_data={"exercise":"Deadlift","weight":200,"weight_unit":"kg","reps":5,"sets":3}'
```

### Crear Historia de Solo Texto

```bash
curl -X POST http://localhost:8000/api/v1/stories/ \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "caption=La disciplina supera al talento cuando el talento no tiene disciplina 💯" \
  -d "story_type=text" \
  -d "privacy=public"
```

---

## 🔒 Consideraciones de Seguridad

1. **Autenticación**: Todos los endpoints requieren JWT válido
2. **Multi-tenancy**: Las historias están aisladas por `gym_id`
3. **Rate Limiting**: Aplicado automáticamente por el middleware
4. **Tamaño de archivos**: Límites de 10MB para imágenes, 50MB para videos
5. **Validación de contenido**: Sistema de reportes para contenido inapropiado
6. **Permisos**: Solo el dueño puede editar/eliminar sus historias

---

## 📱 Integración con Apps Móviles

### Headers Recomendados

```http
Authorization: Bearer {jwt_token}
X-Gym-ID: 4
X-App-Version: 1.0.0
X-Platform: iOS/Android
User-Agent: GymApp/1.0
```

### Manejo de Errores

```javascript
try {
  const response = await fetch('/api/v1/stories/', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`
    },
    body: formData
  });

  if (!response.ok) {
    const error = await response.json();

    switch (response.status) {
      case 401:
        // Renovar token
        await refreshToken();
        break;
      case 403:
        // Sin permisos
        showError('No tienes permisos para realizar esta acción');
        break;
      case 413:
        // Archivo muy grande
        showError('El archivo es demasiado grande');
        break;
      case 404:
        // Módulo no habilitado
        showError('Las historias no están disponibles');
        break;
      default:
        showError(error.detail || 'Error desconocido');
    }
  }
} catch (error) {
  // Error de red
  showError('Error de conexión');
}
```

---

## 🎯 Tips y Mejores Prácticas

1. **Optimización de Imágenes**: Comprimir antes de subir para mejorar velocidad
2. **Lazy Loading**: Cargar historias bajo demanda en el feed
3. **Precarga**: Precargar la siguiente historia mientras se ve la actual
4. **Cache Local**: Guardar historias vistas en cache local
5. **Retry Logic**: Reintentar automáticamente en caso de error de red
6. **Feedback Visual**: Mostrar progreso de upload para archivos grandes

---

*Última actualización: 8 de Noviembre de 2025*