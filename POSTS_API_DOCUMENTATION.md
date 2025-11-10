# 📸 Documentación API de Posts

**Versión:** 1.0
**Base URL:** `/api/v1/posts`
**Autenticación:** Bearer Token (Auth0 JWT)
**Multi-tenancy:** Todos los endpoints requieren `gym_id` en el token JWT

---

## 📑 Índice de Endpoints

### CRUD de Posts
1. [POST /posts](#1-crear-post) - Crear post con galería
2. [GET /posts/{post_id}](#2-obtener-post-por-id) - Obtener post
3. [GET /posts/user/{user_id}](#3-obtener-posts-de-usuario) - Posts de usuario
4. [PUT /posts/{post_id}](#4-actualizar-post) - Editar post
5. [DELETE /posts/{post_id}](#5-eliminar-post) - Eliminar post

### Feeds
6. [GET /posts/feed/timeline](#6-feed-timeline) - Feed cronológico
7. [GET /posts/feed/explore](#7-feed-explorar) - Posts populares
8. [GET /posts/feed/location/{location}](#8-posts-por-ubicación) - Por ubicación

### Likes
9. [POST /posts/{post_id}/like](#9-toggle-like-en-post) - Like/Unlike post
10. [GET /posts/{post_id}/likes](#10-lista-de-likes-de-post) - Ver quién dio like

### Comentarios
11. [POST /posts/{post_id}/comment](#11-agregar-comentario) - Comentar
12. [GET /posts/{post_id}/comments](#12-obtener-comentarios) - Ver comentarios
13. [PUT /posts/comments/{comment_id}](#13-editar-comentario) - Editar comentario
14. [DELETE /posts/comments/{comment_id}](#14-eliminar-comentario) - Eliminar comentario
15. [POST /posts/comments/{comment_id}/like](#15-toggle-like-en-comentario) - Like comentario

### Reportes
16. [POST /posts/{post_id}/report](#16-reportar-post) - Reportar contenido

### Tags y Menciones
17. [GET /posts/events/{event_id}](#17-posts-por-evento) - Posts de evento
18. [GET /posts/sessions/{session_id}](#18-posts-por-sesión) - Posts de sesión/clase
19. [GET /posts/mentions/me](#19-mis-menciones) - Posts donde fui mencionado

---

## 🔐 Autenticación

Todos los endpoints requieren un token JWT de Auth0 en el header:

```bash
Authorization: Bearer <your_jwt_token>
```

El token debe contener:
- `gym_id` - ID del gimnasio (custom claim)
- `sub` - User ID de Auth0
- Scope adecuado según el rol (member, trainer, admin)

---

## 📝 CRUD de Posts

### 1. Crear Post

Crea un nuevo post con opción de galería (hasta 10 imágenes/videos).

**Endpoint:** `POST /api/v1/posts`

**Content-Type:** `multipart/form-data`

**Parámetros (Form Data):**

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `caption` | string | No | Texto del post (hasta 2200 caracteres) |
| `post_type` | string | Sí | Tipo: `single_image`, `gallery`, `video`, `workout` |
| `privacy` | string | No | `public` o `private` (default: `public`) |
| `location` | string | No | Ubicación (ej: "Gym Principal") |
| `files` | File[] | No* | Archivos de imagen/video (máx 10) |
| `workout_data_json` | string | No | JSON con datos de workout |
| `tagged_event_id` | integer | No | ID de evento a etiquetar |
| `tagged_session_id` | integer | No | ID de sesión/clase a etiquetar |
| `mentioned_user_ids_json` | string | No | JSON array de user IDs mencionados |

\* Requerido si `post_type` es `single_image`, `gallery` o `video`

**Validaciones:**
- Máximo 10 archivos para galería
- Imágenes: máx 10MB cada una (JPEG, PNG, GIF, WebP)
- Videos: máx 100MB cada uno (MP4, MOV, AVI)
- Caption: máx 2200 caracteres

**Request Example (cURL):**

```bash
curl -X POST "https://api.tu-gym.com/api/v1/posts" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "caption=¡Increíble entrenamiento hoy! 💪 @user_123" \
  -F "post_type=gallery" \
  -F "privacy=public" \
  -F "location=Gym Principal - Zona CrossFit" \
  -F "files=@image1.jpg" \
  -F "files=@image2.jpg" \
  -F "files=@image3.jpg" \
  -F "mentioned_user_ids_json=[123, 456]" \
  -F "tagged_event_id=10"
```

**Request Example (JavaScript/FormData):**

```javascript
const formData = new FormData();
formData.append('caption', '¡Increíble entrenamiento hoy! 💪');
formData.append('post_type', 'gallery');
formData.append('privacy', 'public');
formData.append('location', 'Gym Principal');

// Agregar múltiples archivos
files.forEach(file => {
  formData.append('files', file);
});

// Menciones
formData.append('mentioned_user_ids_json', JSON.stringify([123, 456]));

const response = await fetch('/api/v1/posts', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`
  },
  body: formData
});

const data = await response.json();
```

**Response 201 Created:**

```json
{
  "success": true,
  "post": {
    "id": 42,
    "user_id": 789,
    "gym_id": 1,
    "caption": "¡Increíble entrenamiento hoy! 💪 @user_123",
    "post_type": "gallery",
    "privacy": "public",
    "location": "Gym Principal - Zona CrossFit",
    "like_count": 0,
    "comment_count": 0,
    "view_count": 0,
    "share_count": 0,
    "is_edited": false,
    "is_deleted": false,
    "created_at": "2025-11-10T10:30:00Z",
    "updated_at": "2025-11-10T10:30:00Z",
    "edited_at": null,
    "workout_data": null,
    "media": [
      {
        "id": 1,
        "post_id": 42,
        "media_type": "image",
        "media_url": "https://storage.supabase.co/gym-posts/image1.jpg",
        "thumbnail_url": "https://storage.supabase.co/gym-posts/thumbnails/image1_thumb.jpg",
        "display_order": 0,
        "width": 1920,
        "height": 1080,
        "file_size": 2048576,
        "duration_seconds": null
      },
      {
        "id": 2,
        "post_id": 42,
        "media_type": "image",
        "media_url": "https://storage.supabase.co/gym-posts/image2.jpg",
        "thumbnail_url": "https://storage.supabase.co/gym-posts/thumbnails/image2_thumb.jpg",
        "display_order": 1,
        "width": 1920,
        "height": 1080,
        "file_size": 1856789
      }
    ],
    "tags": [
      {
        "id": 1,
        "post_id": 42,
        "tag_type": "mention",
        "tag_id": 123,
        "tagged_user": {
          "id": 123,
          "full_name": "Juan Pérez",
          "profile_picture_url": "https://..."
        }
      },
      {
        "id": 2,
        "post_id": 42,
        "tag_type": "event",
        "tag_id": 10,
        "tagged_event": {
          "id": 10,
          "title": "Torneo CrossFit 2025"
        }
      }
    ],
    "user": {
      "id": 789,
      "full_name": "María García",
      "profile_picture_url": "https://...",
      "role": "member"
    },
    "has_liked": false,
    "is_own_post": true
  }
}
```

**Errores Comunes:**

```json
// 400 - Archivo muy grande
{
  "detail": "El archivo image1.jpg excede el tamaño máximo de 10MB"
}

// 400 - Formato no soportado
{
  "detail": "Formato de archivo no soportado. Solo se permiten: JPEG, PNG, GIF, WebP"
}

// 400 - Demasiados archivos
{
  "detail": "Máximo 10 archivos permitidos en una galería"
}

// 400 - workout_data_json inválido
{
  "detail": "workout_data_json debe ser un JSON válido"
}

// 404 - Módulo no activado
{
  "detail": "Módulo no disponible"
}
```

---

### 2. Obtener Post por ID

Obtiene un post específico con toda su información.

**Endpoint:** `GET /api/v1/posts/{post_id}`

**Parámetros URL:**
- `post_id` (integer) - ID del post

**Permisos:**
- Posts públicos: cualquier usuario del gym
- Posts privados: solo el creador

**Request Example:**

```bash
curl -X GET "https://api.tu-gym.com/api/v1/posts/42" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

```javascript
const response = await fetch('/api/v1/posts/42', {
  headers: {
    'Authorization': `Bearer ${token}`
  }
});
const post = await response.json();
```

**Response 200 OK:**

```json
{
  "id": 42,
  "user_id": 789,
  "gym_id": 1,
  "caption": "¡Increíble entrenamiento hoy! 💪",
  "post_type": "gallery",
  "privacy": "public",
  "location": "Gym Principal",
  "like_count": 25,
  "comment_count": 8,
  "view_count": 150,
  "is_edited": false,
  "created_at": "2025-11-10T10:30:00Z",
  "media": [...],
  "tags": [...],
  "user": {
    "id": 789,
    "full_name": "María García",
    "profile_picture_url": "https://...",
    "role": "member"
  },
  "has_liked": true,
  "is_own_post": false
}
```

**Errores:**

```json
// 404 - Post no encontrado
{
  "detail": "Post no encontrado"
}

// 403 - Post privado de otro usuario
{
  "detail": "No tienes permiso para ver este post"
}
```

---

### 3. Obtener Posts de Usuario

Obtiene todos los posts de un usuario específico.

**Endpoint:** `GET /api/v1/posts/user/{user_id}`

**Parámetros URL:**
- `user_id` (integer) - ID del usuario

**Query Parameters:**

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `limit` | integer | 20 | Número de posts por página (máx 100) |
| `offset` | integer | 0 | Número de posts a saltar |

**Request Example:**

```bash
curl -X GET "https://api.tu-gym.com/api/v1/posts/user/789?limit=20&offset=0" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

```javascript
const response = await fetch(`/api/v1/posts/user/789?limit=20&offset=0`, {
  headers: { 'Authorization': `Bearer ${token}` }
});
const data = await response.json();
```

**Response 200 OK:**

```json
{
  "posts": [
    {
      "id": 42,
      "caption": "Post más reciente...",
      "post_type": "gallery",
      "like_count": 25,
      "comment_count": 8,
      "created_at": "2025-11-10T10:30:00Z",
      "media": [...],
      "user": {...},
      "has_liked": false
    },
    {
      "id": 41,
      "caption": "Post anterior...",
      // ...
    }
  ],
  "total": 45,
  "limit": 20,
  "offset": 0,
  "has_more": true,
  "next_offset": 20
}
```

**Notas:**
- Los posts se devuelven ordenados por `created_at` DESC (más recientes primero)
- Solo se incluyen posts públicos o privados del propio usuario
- El campo `has_more` indica si hay más posts disponibles

---

### 4. Actualizar Post

Edita un post existente. Solo el caption y location son editables.

**Endpoint:** `PUT /api/v1/posts/{post_id}`

**Parámetros URL:**
- `post_id` (integer) - ID del post

**Body (JSON):**

```json
{
  "caption": "Caption actualizado 🔥",
  "location": "Nueva ubicación"
}
```

**Campos opcionales:**
- `caption` (string, max 2200 caracteres)
- `location` (string, max 255 caracteres)

**Permisos:**
- Solo el creador del post puede editarlo

**Request Example:**

```bash
curl -X PUT "https://api.tu-gym.com/api/v1/posts/42" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "caption": "Caption actualizado 🔥",
    "location": "Gym Principal - Zona Funcional"
  }'
```

```javascript
const response = await fetch('/api/v1/posts/42', {
  method: 'PUT',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    caption: 'Caption actualizado 🔥',
    location: 'Gym Principal - Zona Funcional'
  })
});
const updatedPost = await response.json();
```

**Response 200 OK:**

```json
{
  "id": 42,
  "caption": "Caption actualizado 🔥",
  "location": "Gym Principal - Zona Funcional",
  "is_edited": true,
  "edited_at": "2025-11-10T11:45:00Z",
  "updated_at": "2025-11-10T11:45:00Z",
  // ... resto de campos
}
```

**Errores:**

```json
// 403 - No eres el dueño
{
  "detail": "No tienes permiso para editar este post"
}

// 404 - Post no encontrado
{
  "detail": "Post no encontrado"
}

// 400 - Caption muy largo
{
  "detail": "Caption excede el límite de 2200 caracteres"
}
```

**Notas:**
- No se pueden editar imágenes/videos después de crear el post
- El campo `is_edited` se marca como `true` automáticamente
- Se actualiza `edited_at` con el timestamp de la última edición

---

### 5. Eliminar Post

Elimina un post (soft delete).

**Endpoint:** `DELETE /api/v1/posts/{post_id}`

**Parámetros URL:**
- `post_id` (integer) - ID del post

**Permisos:**
- El creador del post
- Admins del gimnasio

**Request Example:**

```bash
curl -X DELETE "https://api.tu-gym.com/api/v1/posts/42" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

```javascript
const response = await fetch('/api/v1/posts/42', {
  method: 'DELETE',
  headers: {
    'Authorization': `Bearer ${token}`
  }
});
// Response 204 No Content (sin body)
```

**Response 204 No Content**

No hay body en la respuesta. Un status 204 indica éxito.

**Errores:**

```json
// 403 - Sin permisos
{
  "detail": "No tienes permiso para eliminar este post"
}

// 404 - Post no encontrado
{
  "detail": "Post no encontrado"
}
```

**Notas:**
- Es un soft delete: el post se marca como `is_deleted = true`
- Los archivos de media se eliminan de Supabase Storage
- El post se elimina de Stream Feeds
- Likes y comentarios asociados permanecen en la BD pero el post no es visible

---

## 📰 Feeds

### 6. Feed Timeline

Obtiene el feed cronológico de posts del gimnasio.

**Endpoint:** `GET /api/v1/posts/feed/timeline`

**Query Parameters:**

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `limit` | integer | 20 | Posts por página (máx 100) |
| `offset` | integer | 0 | Posts a saltar (paginación) |

**Request Example:**

```bash
curl -X GET "https://api.tu-gym.com/api/v1/posts/feed/timeline?limit=20&offset=0" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

```javascript
const response = await fetch('/api/v1/posts/feed/timeline?limit=20&offset=0', {
  headers: { 'Authorization': `Bearer ${token}` }
});
const feed = await response.json();
```

**Response 200 OK:**

```json
{
  "posts": [
    {
      "id": 50,
      "caption": "Post más reciente del gym...",
      "post_type": "single_image",
      "like_count": 15,
      "comment_count": 3,
      "created_at": "2025-11-10T14:30:00Z",
      "media": [...],
      "user": {
        "id": 123,
        "full_name": "Carlos López",
        "profile_picture_url": "https://..."
      },
      "has_liked": false,
      "is_own_post": false
    },
    // ... más posts
  ],
  "total_posts": 150,
  "feed_type": "timeline",
  "has_more": true,
  "next_offset": 20,
  "last_update": "2025-11-10T14:30:00Z"
}
```

**Notas:**
- Posts ordenados por `created_at` DESC (más recientes primero)
- Solo incluye posts públicos del gimnasio
- Implementación con Stream Feeds si está disponible, fallback a BD

---

### 7. Feed Explorar

Obtiene los posts más populares del gimnasio basado en engagement.

**Endpoint:** `GET /api/v1/posts/feed/explore`

**Query Parameters:**

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `limit` | integer | 20 | Posts por página (máx 100) |
| `offset` | integer | 0 | Posts a saltar |

**Algoritmo de Ranking:**

```
engagement_score = (likes × 1.0) + (comments × 2.0) - (age_hours × 0.1)
```

Los posts se ordenan por este score de mayor a menor.

**Request Example:**

```bash
curl -X GET "https://api.tu-gym.com/api/v1/posts/feed/explore?limit=20&offset=0" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

```javascript
const response = await fetch('/api/v1/posts/feed/explore?limit=20&offset=0', {
  headers: { 'Authorization': `Bearer ${token}` }
});
const exploreFeed = await response.json();
```

**Response 200 OK:**

```json
{
  "posts": [
    {
      "id": 45,
      "caption": "Post más popular esta semana 🔥",
      "like_count": 89,
      "comment_count": 34,
      "engagement_score": 145.2,
      "created_at": "2025-11-08T10:00:00Z",
      "media": [...],
      "user": {...}
    },
    // ... posts ordenados por engagement
  ],
  "total_posts": 50,
  "feed_type": "explore",
  "has_more": true,
  "next_offset": 20,
  "last_update": "2025-11-10T14:30:00Z"
}
```

**Notas:**
- Ideal para descubrir contenido popular
- Los posts recientes con mucho engagement aparecen primero
- Los posts muy antiguos (aunque tengan likes) bajan en el ranking

---

### 8. Posts por Ubicación

Obtiene posts filtrados por ubicación.

**Endpoint:** `GET /api/v1/posts/feed/location/{location}`

**Parámetros URL:**
- `location` (string) - Nombre de la ubicación (URL encoded)

**Query Parameters:**

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `limit` | integer | 20 | Posts por página |
| `offset` | integer | 0 | Posts a saltar |

**Request Example:**

```bash
# URL encode la ubicación
curl -X GET "https://api.tu-gym.com/api/v1/posts/feed/location/Gym%20Principal" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

```javascript
const location = encodeURIComponent('Gym Principal - Zona CrossFit');
const response = await fetch(`/api/v1/posts/feed/location/${location}?limit=20`, {
  headers: { 'Authorization': `Bearer ${token}` }
});
const posts = await response.json();
```

**Response 200 OK:**

```json
{
  "posts": [
    {
      "id": 48,
      "caption": "Entrenando en Gym Principal 💪",
      "location": "Gym Principal - Zona CrossFit",
      "created_at": "2025-11-10T12:00:00Z",
      // ...
    }
  ],
  "total": 12,
  "limit": 20,
  "offset": 0,
  "has_more": false,
  "next_offset": null
}
```

**Notas:**
- La búsqueda es case-insensitive
- Búsqueda parcial: busca posts que contengan el string de ubicación
- Útil para crear feeds por zona del gimnasio

---

## 👍 Likes

### 9. Toggle Like en Post

Agrega o quita un like de un post (toggle).

**Endpoint:** `POST /api/v1/posts/{post_id}/like`

**Parámetros URL:**
- `post_id` (integer) - ID del post

**Comportamiento:**
- Si el usuario NO ha dado like → agrega like
- Si el usuario YA dio like → quita like

**Request Example:**

```bash
curl -X POST "https://api.tu-gym.com/api/v1/posts/42/like" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

```javascript
const response = await fetch('/api/v1/posts/42/like', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`
  }
});
const result = await response.json();
```

**Response 200 OK (Like agregado):**

```json
{
  "success": true,
  "action": "liked",
  "total_likes": 26,
  "message": "Post liked exitosamente"
}
```

**Response 200 OK (Like quitado):**

```json
{
  "success": true,
  "action": "unliked",
  "total_likes": 25,
  "message": "Post unliked exitosamente"
}
```

**Notas:**
- El contador `like_count` se actualiza atómicamente en la BD
- No se pueden dar múltiples likes al mismo post (constraint de unicidad)
- El campo `action` indica qué acción se realizó

---

### 10. Lista de Likes de Post

Obtiene la lista de usuarios que dieron like a un post.

**Endpoint:** `GET /api/v1/posts/{post_id}/likes`

**Parámetros URL:**
- `post_id` (integer) - ID del post

**Query Parameters:**

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `limit` | integer | 20 | Usuarios por página |
| `offset` | integer | 0 | Usuarios a saltar |

**Request Example:**

```bash
curl -X GET "https://api.tu-gym.com/api/v1/posts/42/likes?limit=20&offset=0" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

```javascript
const response = await fetch('/api/v1/posts/42/likes?limit=20&offset=0', {
  headers: { 'Authorization': `Bearer ${token}` }
});
const likes = await response.json();
```

**Response 200 OK:**

```json
{
  "likes": [
    {
      "id": 150,
      "post_id": 42,
      "user_id": 123,
      "created_at": "2025-11-10T10:35:00Z",
      "user": {
        "id": 123,
        "full_name": "Carlos López",
        "profile_picture_url": "https://...",
        "role": "member"
      }
    },
    {
      "id": 151,
      "post_id": 42,
      "user_id": 456,
      "created_at": "2025-11-10T10:40:00Z",
      "user": {
        "id": 456,
        "full_name": "Ana Martínez",
        "profile_picture_url": "https://...",
        "role": "trainer"
      }
    }
  ],
  "total": 26,
  "limit": 20,
  "offset": 0,
  "has_more": true
}
```

**Notas:**
- Los likes se devuelven ordenados por `created_at` DESC (más recientes primero)
- Incluye información completa del usuario que dio like
- Útil para mostrar "A Juan, María y 24 personas más les gusta esto"

---

## 💬 Comentarios

### 11. Agregar Comentario

Agrega un comentario a un post.

**Endpoint:** `POST /api/v1/posts/{post_id}/comment`

**Parámetros URL:**
- `post_id` (integer) - ID del post

**Body (JSON):**

```json
{
  "text": "¡Excelente post! 🔥",
  "mentioned_user_ids": [123, 456]
}
```

**Campos:**
- `text` (string, requerido) - Texto del comentario (max 2200 caracteres)
- `mentioned_user_ids` (array[integer], opcional) - IDs de usuarios mencionados

**Request Example:**

```bash
curl -X POST "https://api.tu-gym.com/api/v1/posts/42/comment" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "¡Excelente entrenamiento! 💪 @user_123",
    "mentioned_user_ids": [123]
  }'
```

```javascript
const response = await fetch('/api/v1/posts/42/comment', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    text: '¡Excelente entrenamiento! 💪',
    mentioned_user_ids: [123]
  })
});
const result = await response.json();
```

**Response 200 OK:**

```json
{
  "success": true,
  "comment": {
    "id": 85,
    "post_id": 42,
    "user_id": 789,
    "text": "¡Excelente entrenamiento! 💪 @user_123",
    "like_count": 0,
    "is_edited": false,
    "is_deleted": false,
    "created_at": "2025-11-10T15:30:00Z",
    "updated_at": "2025-11-10T15:30:00Z",
    "user": {
      "id": 789,
      "full_name": "María García",
      "profile_picture_url": "https://...",
      "role": "member"
    },
    "has_liked": false
  }
}
```

**Errores:**

```json
// 400 - Texto vacío
{
  "detail": "El texto del comentario no puede estar vacío"
}

// 400 - Texto muy largo
{
  "detail": "El comentario excede el límite de 2200 caracteres"
}

// 404 - Post no encontrado
{
  "detail": "Post no encontrado"
}
```

**Notas:**
- El contador `comment_count` del post se incrementa automáticamente
- Se puede mencionar usuarios con `@user_id` en el texto
- El dueño del post podría recibir notificación (si está implementado)

---

### 12. Obtener Comentarios

Obtiene los comentarios de un post.

**Endpoint:** `GET /api/v1/posts/{post_id}/comments`

**Parámetros URL:**
- `post_id` (integer) - ID del post

**Query Parameters:**

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `limit` | integer | 20 | Comentarios por página |
| `offset` | integer | 0 | Comentarios a saltar |

**Request Example:**

```bash
curl -X GET "https://api.tu-gym.com/api/v1/posts/42/comments?limit=20&offset=0" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

```javascript
const response = await fetch('/api/v1/posts/42/comments?limit=20&offset=0', {
  headers: { 'Authorization': `Bearer ${token}` }
});
const comments = await response.json();
```

**Response 200 OK:**

```json
{
  "comments": [
    {
      "id": 85,
      "post_id": 42,
      "user_id": 789,
      "text": "¡Excelente entrenamiento! 💪",
      "like_count": 5,
      "is_edited": false,
      "created_at": "2025-11-10T15:30:00Z",
      "user": {
        "id": 789,
        "full_name": "María García",
        "profile_picture_url": "https://...",
        "role": "member"
      },
      "has_liked": true
    },
    {
      "id": 84,
      "text": "Muy buen post 👏",
      "like_count": 2,
      "created_at": "2025-11-10T14:00:00Z",
      "user": {...},
      "has_liked": false
    }
  ],
  "total": 8,
  "limit": 20,
  "offset": 0,
  "has_more": false
}
```

**Notas:**
- Comentarios ordenados por `created_at` ASC (más antiguos primero)
- El campo `has_liked` indica si el usuario actual dio like al comentario
- No hay comentarios anidados (solo un nivel)

---

### 13. Editar Comentario

Edita el texto de un comentario existente.

**Endpoint:** `PUT /api/v1/posts/comments/{comment_id}`

**Parámetros URL:**
- `comment_id` (integer) - ID del comentario

**Body (JSON):**

```json
{
  "text": "Texto actualizado del comentario ✨"
}
```

**Permisos:**
- Solo el creador del comentario puede editarlo

**Request Example:**

```bash
curl -X PUT "https://api.tu-gym.com/api/v1/posts/comments/85" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Texto actualizado del comentario ✨"
  }'
```

```javascript
const response = await fetch('/api/v1/posts/comments/85', {
  method: 'PUT',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    text: 'Texto actualizado del comentario ✨'
  })
});
const updatedComment = await response.json();
```

**Response 200 OK:**

```json
{
  "id": 85,
  "text": "Texto actualizado del comentario ✨",
  "is_edited": true,
  "edited_at": "2025-11-10T16:00:00Z",
  "updated_at": "2025-11-10T16:00:00Z",
  // ... resto de campos
}
```

**Errores:**

```json
// 403 - No eres el dueño
{
  "detail": "No tienes permiso para editar este comentario"
}

// 404 - Comentario no encontrado
{
  "detail": "Comentario no encontrado"
}
```

**Notas:**
- Se marca automáticamente como editado (`is_edited = true`)
- Se actualiza el timestamp `edited_at`

---

### 14. Eliminar Comentario

Elimina un comentario (soft delete).

**Endpoint:** `DELETE /api/v1/posts/comments/{comment_id}`

**Parámetros URL:**
- `comment_id` (integer) - ID del comentario

**Permisos:**
- El creador del comentario
- El creador del post
- Admins del gimnasio

**Request Example:**

```bash
curl -X DELETE "https://api.tu-gym.com/api/v1/posts/comments/85" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

```javascript
const response = await fetch('/api/v1/posts/comments/85', {
  method: 'DELETE',
  headers: {
    'Authorization': `Bearer ${token}`
  }
});
// Response 204 No Content
```

**Response 204 No Content**

No hay body. Status 204 indica éxito.

**Errores:**

```json
// 403 - Sin permisos
{
  "detail": "No tienes permiso para eliminar este comentario"
}

// 404 - Comentario no encontrado
{
  "detail": "Comentario no encontrado"
}
```

**Notas:**
- Es soft delete: `is_deleted = true`
- El contador `comment_count` del post se decrementa automáticamente
- Los likes del comentario permanecen pero el comentario no es visible

---

### 15. Toggle Like en Comentario

Agrega o quita un like de un comentario.

**Endpoint:** `POST /api/v1/posts/comments/{comment_id}/like`

**Parámetros URL:**
- `comment_id` (integer) - ID del comentario

**Request Example:**

```bash
curl -X POST "https://api.tu-gym.com/api/v1/posts/comments/85/like" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

```javascript
const response = await fetch('/api/v1/posts/comments/85/like', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`
  }
});
const result = await response.json();
```

**Response 200 OK:**

```json
{
  "success": true,
  "action": "liked",
  "total_likes": 6,
  "message": "Comentario liked"
}
```

**Notas:**
- Funciona igual que el like de posts (toggle)
- El contador se actualiza atómicamente

---

## 🚨 Reportes

### 16. Reportar Post

Reporta un post como inapropiado para revisión de moderadores.

**Endpoint:** `POST /api/v1/posts/{post_id}/report`

**Parámetros URL:**
- `post_id` (integer) - ID del post

**Body (JSON):**

```json
{
  "reason": "spam",
  "description": "Este post es claramente spam promocional"
}
```

**Campos:**
- `reason` (string, requerido) - Razón del reporte
  - Valores válidos: `spam`, `inappropriate`, `harassment`, `violence`, `hate_speech`, `misinformation`, `other`
- `description` (string, opcional) - Descripción adicional (max 500 caracteres)

**Request Example:**

```bash
curl -X POST "https://api.tu-gym.com/api/v1/posts/42/report" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "inappropriate",
    "description": "Contenido inapropiado para el gym"
  }'
```

```javascript
const response = await fetch('/api/v1/posts/42/report', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    reason: 'inappropriate',
    description: 'Contenido inapropiado'
  })
});
const result = await response.json();
```

**Response 200 OK:**

```json
{
  "success": true,
  "report_id": 15
}
```

**Errores:**

```json
// 400 - Ya reportaste este post
{
  "detail": "Ya has reportado este post anteriormente"
}

// 400 - Razón inválida
{
  "detail": "Razón de reporte inválida. Valores permitidos: spam, inappropriate, harassment..."
}
```

**Razones de Reporte:**

| Razón | Descripción |
|-------|-------------|
| `spam` | Contenido spam o publicidad no deseada |
| `inappropriate` | Contenido inapropiado |
| `harassment` | Acoso o bullying |
| `violence` | Violencia o amenazas |
| `hate_speech` | Discurso de odio |
| `misinformation` | Información falsa o engañosa |
| `other` | Otra razón (explicar en description) |

**Notas:**
- Un usuario solo puede reportar un post una vez
- Los reportes se almacenan para revisión de admins
- El post NO se elimina automáticamente, requiere revisión manual

---

## 🏷️ Tags y Menciones

### 17. Posts por Evento

Obtiene posts etiquetados con un evento específico.

**Endpoint:** `GET /api/v1/posts/events/{event_id}`

**Parámetros URL:**
- `event_id` (integer) - ID del evento

**Query Parameters:**

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `limit` | integer | 20 | Posts por página |
| `offset` | integer | 0 | Posts a saltar |

**Request Example:**

```bash
curl -X GET "https://api.tu-gym.com/api/v1/posts/events/10?limit=20&offset=0" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

```javascript
const response = await fetch('/api/v1/posts/events/10?limit=20&offset=0', {
  headers: { 'Authorization': `Bearer ${token}` }
});
const posts = await response.json();
```

**Response 200 OK:**

```json
{
  "posts": [
    {
      "id": 48,
      "caption": "¡Torneo épico! 🏆",
      "created_at": "2025-11-10T18:00:00Z",
      "tags": [
        {
          "tag_type": "event",
          "tag_id": 10,
          "tagged_event": {
            "id": 10,
            "title": "Torneo CrossFit 2025",
            "start_date": "2025-11-15T10:00:00Z"
          }
        }
      ],
      // ... resto del post
    }
  ],
  "total": 15,
  "limit": 20,
  "offset": 0,
  "has_more": false,
  "next_offset": null
}
```

**Uso:**
- Ver todos los posts de un evento específico
- Crear galería del evento con fotos de participantes
- Útil para eventos, competencias, talleres

---

### 18. Posts por Sesión

Obtiene posts etiquetados con una sesión/clase específica.

**Endpoint:** `GET /api/v1/posts/sessions/{session_id}`

**Parámetros URL:**
- `session_id` (integer) - ID de la sesión/clase

**Query Parameters:**

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `limit` | integer | 20 | Posts por página |
| `offset` | integer | 0 | Posts a saltar |

**Request Example:**

```bash
curl -X GET "https://api.tu-gym.com/api/v1/posts/sessions/50?limit=20" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

```javascript
const response = await fetch('/api/v1/posts/sessions/50?limit=20', {
  headers: { 'Authorization': `Bearer ${token}` }
});
const posts = await response.json();
```

**Response 200 OK:**

```json
{
  "posts": [
    {
      "id": 52,
      "caption": "¡Clase de CrossFit increíble! 💪",
      "tags": [
        {
          "tag_type": "session",
          "tag_id": 50,
          "tagged_session": {
            "id": 50,
            "title": "CrossFit Avanzado",
            "start_time": "2025-11-10T17:00:00Z"
          }
        }
      ],
      // ...
    }
  ],
  "total": 8,
  "limit": 20,
  "offset": 0,
  "has_more": false
}
```

**Uso:**
- Ver posts de una clase específica
- Compartir experiencias de entrenamientos
- Crear comunidad alrededor de clases regulares

---

### 19. Mis Menciones

Obtiene posts donde el usuario actual fue mencionado.

**Endpoint:** `GET /api/v1/posts/mentions/me`

**Query Parameters:**

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `limit` | integer | 20 | Posts por página |
| `offset` | integer | 0 | Posts a saltar |

**Request Example:**

```bash
curl -X GET "https://api.tu-gym.com/api/v1/posts/mentions/me?limit=20&offset=0" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

```javascript
const response = await fetch('/api/v1/posts/mentions/me?limit=20&offset=0', {
  headers: { 'Authorization': `Bearer ${token}` }
});
const mentions = await response.json();
```

**Response 200 OK:**

```json
{
  "posts": [
    {
      "id": 55,
      "caption": "¡Gran entrenamiento con @user_789! 💪",
      "user_id": 123,
      "created_at": "2025-11-10T16:00:00Z",
      "tags": [
        {
          "tag_type": "mention",
          "tag_id": 789,
          "tagged_user": {
            "id": 789,
            "full_name": "María García",
            "profile_picture_url": "https://..."
          }
        }
      ],
      "user": {
        "id": 123,
        "full_name": "Carlos López",
        // ...
      }
    }
  ],
  "total": 5,
  "limit": 20,
  "offset": 0,
  "has_more": false
}
```

**Uso:**
- Ver en qué posts te han mencionado
- Recibir notificaciones de menciones
- Seguimiento de interacciones sociales

---

## 🔒 Seguridad y Permisos

### Niveles de Acceso

| Endpoint | Member | Trainer | Admin |
|----------|--------|---------|-------|
| Crear post | ✅ | ✅ | ✅ |
| Ver posts públicos | ✅ | ✅ | ✅ |
| Ver posts privados propios | ✅ | ✅ | ✅ |
| Editar post propio | ✅ | ✅ | ✅ |
| Eliminar post propio | ✅ | ✅ | ✅ |
| Eliminar post de otros | ❌ | ❌ | ✅ |
| Like/Unlike | ✅ | ✅ | ✅ |
| Comentar | ✅ | ✅ | ✅ |
| Editar comentario propio | ✅ | ✅ | ✅ |
| Eliminar comentario propio | ✅ | ✅ | ✅ |
| Eliminar comentario en post propio | ✅ | ✅ | ✅ |
| Eliminar comentario de otros | ❌ | ❌ | ✅ |
| Reportar post | ✅ | ✅ | ✅ |

### Validaciones de Seguridad

1. **Multi-tenancy:** Todos los endpoints validan `gym_id` del token
2. **Ownership:** Editar/eliminar requiere ser el creador o admin
3. **Privacidad:** Posts privados solo visibles por el creador
4. **Rate Limiting:** Límites configurados por endpoint (ver middleware)
5. **File Upload:** Validación de tipos MIME y tamaños

---

## 📊 Códigos de Estado HTTP

| Código | Significado | Cuándo ocurre |
|--------|-------------|---------------|
| 200 | OK | Operación exitosa (GET, PUT, POST con respuesta) |
| 201 | Created | Post creado exitosamente |
| 204 | No Content | Eliminación exitosa (DELETE) |
| 400 | Bad Request | Datos inválidos, archivo muy grande, etc. |
| 401 | Unauthorized | Token JWT faltante o inválido |
| 403 | Forbidden | Sin permisos para la operación |
| 404 | Not Found | Post, comentario o recurso no encontrado |
| 500 | Internal Server Error | Error del servidor |

---

## 🎨 Casos de Uso Completos

### Caso 1: Crear Post con Galería

```javascript
// 1. Usuario selecciona imágenes en el frontend
const files = document.getElementById('fileInput').files;

// 2. Crear FormData
const formData = new FormData();
formData.append('caption', '¡Increíble sesión de CrossFit! 💪 @user_123 @user_456');
formData.append('post_type', 'gallery');
formData.append('privacy', 'public');
formData.append('location', 'Gym Principal - Zona CrossFit');
formData.append('tagged_event_id', '10');
formData.append('mentioned_user_ids_json', JSON.stringify([123, 456]));

// Agregar archivos
Array.from(files).forEach(file => {
  formData.append('files', file);
});

// 3. Enviar request
const response = await fetch('/api/v1/posts', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`
  },
  body: formData
});

const { success, post } = await response.json();

if (success) {
  console.log('Post creado:', post.id);
  console.log('Galería:', post.media.length, 'imágenes');
}
```

### Caso 2: Feed Infinito con Scroll

```javascript
let offset = 0;
const limit = 20;
let isLoading = false;
let hasMore = true;

async function loadMorePosts() {
  if (isLoading || !hasMore) return;

  isLoading = true;

  const response = await fetch(
    `/api/v1/posts/feed/timeline?limit=${limit}&offset=${offset}`,
    {
      headers: { 'Authorization': `Bearer ${token}` }
    }
  );

  const data = await response.json();

  // Renderizar posts
  data.posts.forEach(post => renderPost(post));

  // Actualizar estado
  hasMore = data.has_more;
  offset = data.next_offset || offset;
  isLoading = false;
}

// Detectar scroll al final
window.addEventListener('scroll', () => {
  if (window.innerHeight + window.scrollY >= document.body.offsetHeight - 500) {
    loadMorePosts();
  }
});

// Carga inicial
loadMorePosts();
```

### Caso 3: Like con UI Optimista

```javascript
async function toggleLike(postId, currentLikeCount, hasLiked) {
  // 1. Actualizar UI inmediatamente (optimistic)
  const newLikeCount = hasLiked ? currentLikeCount - 1 : currentLikeCount + 1;
  const newHasLiked = !hasLiked;

  updatePostUI(postId, {
    like_count: newLikeCount,
    has_liked: newHasLiked
  });

  try {
    // 2. Enviar request al servidor
    const response = await fetch(`/api/v1/posts/${postId}/like`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` }
    });

    const result = await response.json();

    // 3. Confirmar con respuesta del servidor
    updatePostUI(postId, {
      like_count: result.total_likes,
      has_liked: result.action === 'liked'
    });

  } catch (error) {
    // 4. Revertir en caso de error
    updatePostUI(postId, {
      like_count: currentLikeCount,
      has_liked: hasLiked
    });

    console.error('Error toggling like:', error);
  }
}
```

### Caso 4: Comentarios en Tiempo Real

```javascript
async function loadComments(postId) {
  const response = await fetch(
    `/api/v1/posts/${postId}/comments?limit=50&offset=0`,
    {
      headers: { 'Authorization': `Bearer ${token}` }
    }
  );

  const { comments } = await response.json();
  renderComments(comments);
}

async function addComment(postId, text) {
  const response = await fetch(`/api/v1/posts/${postId}/comment`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ text })
  });

  const { success, comment } = await response.json();

  if (success) {
    // Agregar comentario a la UI
    appendComment(comment);

    // Limpiar input
    document.getElementById('commentInput').value = '';

    // Incrementar contador
    incrementCommentCount(postId);
  }
}
```

---

## 🐛 Troubleshooting

### Error: "Module not available"

**Causa:** El módulo de posts no está activado para el gimnasio.

**Solución:**
```sql
INSERT INTO gym_modules (gym_id, module_id, active, activated_at)
VALUES (1, 9, TRUE, NOW());
```

### Error: "File upload failed"

**Causas posibles:**
1. Bucket no creado en Supabase
2. Tamaño de archivo excede límite
3. Formato no soportado

**Solución:**
1. Crear bucket `gym-posts` en Supabase Storage
2. Reducir tamaño de imagen/video
3. Usar formatos soportados: JPEG, PNG, GIF, WebP, MP4, MOV

### Error: "Post not found" al intentar ver post

**Causas:**
1. Post eliminado (`is_deleted = true`)
2. Post privado de otro usuario
3. Post de otro gimnasio

**Solución:** Verificar que el post existe, es público o es tuyo.

### Performance: Feed lento

**Optimizaciones:**
1. Usar paginación con `limit=20`
2. Implementar infinite scroll en lugar de cargar todo
3. Cachear posts en frontend
4. Usar thumbnails en lugar de imágenes completas en feeds

---

## 📈 Mejores Prácticas

### Frontend

1. **Paginación:** Siempre usar límites razonables (10-20 posts)
2. **UI Optimista:** Actualizar UI antes de confirmar con servidor
3. **Lazy Loading:** Cargar imágenes solo cuando sean visibles
4. **Compresión:** Comprimir imágenes antes de subir
5. **Validación:** Validar archivos antes de enviar al servidor

### Backend

1. **Índices:** Ya implementados para queries frecuentes
2. **Contadores Atómicos:** Usados para likes y comments
3. **Soft Delete:** Posts y comentarios no se borran físicamente
4. **Eager Loading:** Usar `joinedload` para evitar N+1 queries
5. **Stream Feeds:** Fallback automático a BD si falla

---

## 📞 Soporte

Para reportar bugs o solicitar features:
- **GitHub Issues:** https://github.com/tu-repo/issues
- **Documentación Swagger:** http://localhost:8000/api/v1/docs

---

**Versión:** 1.0
**Última actualización:** 2025-11-10
**Endpoints totales:** 21
