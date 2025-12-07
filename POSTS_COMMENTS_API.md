# API de Comentarios de Posts - Documentación Completa

Documentación detallada de todos los endpoints relacionados con comentarios en posts del sistema GymAPI.

**Base URL**: `/api/v1/posts`

**Autenticación**: Todos los endpoints requieren token JWT de Auth0 en el header `Authorization`.

**Headers requeridos**:
```
Authorization: Bearer {token}
x-gym-id: {gym_id}
Content-Type: application/json
```

---

## Índice de Endpoints

1. [POST /{post_id}/comment](#1-crear-comentario-en-post) - Crear comentario
2. [GET /{post_id}/comments](#2-obtener-comentarios-de-post) - Listar comentarios
3. [PUT /comments/{comment_id}](#3-actualizar-comentario) - Actualizar comentario
4. [DELETE /comments/{comment_id}](#4-eliminar-comentario) - Eliminar comentario
5. [POST /comments/{comment_id}/like](#5-toggle-like-en-comentario) - Like/Unlike comentario

---

## 1. Crear Comentario en Post

Agrega un nuevo comentario a un post específico.

### Request

**Endpoint**: `POST /api/v1/posts/{post_id}/comment`

**Parámetros de Path**:
- `post_id` (int, requerido): ID del post al que se agregará el comentario

**Request Body**:
```json
{
  "comment_text": "¡Excelente post! Sigue así 💪"
}
```

**Schema - CommentCreate**:
| Campo | Tipo | Requerido | Validación | Descripción |
|-------|------|-----------|------------|-------------|
| comment_text | string | Sí | min: 1, max: 2000 | Texto del comentario |

**⚠️ IMPORTANTE**: El frontend actualmente envía `text` en lugar de `comment_text`. Necesita ajustarse para usar `comment_text`.

### Response Exitosa - 200 OK

```json
{
  "success": true,
  "comment": {
    "id": 123,
    "post_id": 14,
    "user_id": 10,
    "gym_id": 4,
    "comment_text": "¡Excelente post! Sigue así 💪",
    "is_edited": false,
    "edited_at": null,
    "like_count": 0,
    "created_at": "2025-12-07T05:53:36.123Z",
    "updated_at": null,
    "user_info": {
      "id": 10,
      "first_name": "Juan",
      "last_name": "Pérez",
      "picture": "https://example.com/avatar.jpg"
    },
    "has_liked": false
  },
  "message": "Comentario agregado exitosamente"
}
```

**Schema - CommentCreateResponse**:
| Campo | Tipo | Descripción |
|-------|------|-------------|
| success | boolean | Indica si la operación fue exitosa |
| comment | CommentResponse | Objeto del comentario creado |
| message | string | Mensaje de confirmación |

**Schema - CommentResponse** (objeto anidado):
| Campo | Tipo | Nullable | Descripción |
|-------|------|----------|-------------|
| id | integer | No | ID único del comentario |
| post_id | integer | No | ID del post comentado |
| user_id | integer | No | ID del usuario que comentó |
| gym_id | integer | No | ID del gimnasio |
| comment_text | string | No | Texto del comentario |
| is_edited | boolean | No | Si el comentario fue editado |
| edited_at | datetime | Sí | Fecha/hora de última edición |
| like_count | integer | No | Cantidad de likes en el comentario |
| created_at | datetime | No | Fecha/hora de creación |
| updated_at | datetime | Sí | Fecha/hora de última actualización |
| user_info | object | Sí | Información del usuario que comentó |
| has_liked | boolean | No | Si el usuario actual dio like al comentario |

### Errores Posibles

**404 Not Found** - Post no encontrado:
```json
{
  "detail": "Post no encontrado"
}
```

**422 Unprocessable Entity** - Validación fallida:
```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "comment_text"],
      "msg": "Field required",
      "input": {"text": "Ggg"}
    }
  ]
}
```

**401 Unauthorized** - Token inválido o faltante

**403 Forbidden** - Usuario sin permisos para comentar en este gym

### Ejemplo cURL

```bash
curl -X POST "https://gymapi-eh6m.onrender.com/api/v1/posts/14/comment" \
  -H "Authorization: Bearer eyJhbGc..." \
  -H "x-gym-id: 4" \
  -H "Content-Type: application/json" \
  -d '{
    "comment_text": "¡Excelente post! Sigue así 💪"
  }'
```

### Notas Técnicas

- **Incremento atómico**: El contador `comment_count` del post se incrementa automáticamente
- **Transaccional**: Si falla la creación del comentario, el contador no se incrementa
- **TODO**: Notificar al dueño del post (no implementado)
- **TODO**: Notificar usuarios mencionados (@usuario) (no implementado)

---

## 2. Obtener Comentarios de Post

Obtiene la lista de comentarios de un post con paginación.

### Request

**Endpoint**: `GET /api/v1/posts/{post_id}/comments`

**Parámetros de Path**:
- `post_id` (int, requerido): ID del post

**Parámetros Query**:
| Parámetro | Tipo | Requerido | Default | Validación | Descripción |
|-----------|------|-----------|---------|------------|-------------|
| limit | integer | No | 20 | min: 1, max: 100 | Cantidad de comentarios por página |
| offset | integer | No | 0 | min: 0 | Número de comentarios a saltar |

### Response Exitosa - 200 OK

```json
{
  "comments": [
    {
      "id": 125,
      "post_id": 14,
      "user_id": 12,
      "gym_id": 4,
      "comment_text": "¡Increíble transformación! 🔥",
      "is_edited": false,
      "edited_at": null,
      "like_count": 5,
      "created_at": "2025-12-07T06:30:00.000Z",
      "updated_at": null,
      "user_info": {
        "id": 12,
        "first_name": "María",
        "last_name": "González",
        "picture": "https://example.com/maria.jpg"
      },
      "has_liked": true
    },
    {
      "id": 123,
      "post_id": 14,
      "user_id": 10,
      "gym_id": 4,
      "comment_text": "¡Excelente post! Sigue así 💪",
      "is_edited": false,
      "edited_at": null,
      "like_count": 0,
      "created_at": "2025-12-07T05:53:36.123Z",
      "updated_at": null,
      "user_info": {
        "id": 10,
        "first_name": "Juan",
        "last_name": "Pérez",
        "picture": "https://example.com/avatar.jpg"
      },
      "has_liked": false
    }
  ],
  "total": 2,
  "limit": 20,
  "offset": 0,
  "has_more": false
}
```

**Schema - CommentsListResponse**:
| Campo | Tipo | Descripción |
|-------|------|-------------|
| comments | CommentResponse[] | Array de comentarios |
| total | integer | Número de comentarios en esta página |
| limit | integer | Límite solicitado |
| offset | integer | Offset utilizado |
| has_more | boolean | Si hay más comentarios disponibles (true si total == limit) |

### Errores Posibles

**404 Not Found** - Post no encontrado o eliminado:
```json
{
  "detail": "Post no encontrado"
}
```

**401 Unauthorized** - Token inválido o faltante

### Ejemplo cURL

```bash
curl -X GET "https://gymapi-eh6m.onrender.com/api/v1/posts/14/comments?limit=20&offset=0" \
  -H "Authorization: Bearer eyJhbGc..." \
  -H "x-gym-id: 4"
```

### Notas Técnicas

- **Ordenamiento**: Comentarios ordenados por `created_at DESC` (más recientes primero)
- **Soft delete**: Solo retorna comentarios con `is_deleted = False`
- **Paginación**: Usa `has_more` para saber si hay más páginas
- **Multi-tenant**: Solo retorna comentarios del gimnasio especificado en `x-gym-id`

---

## 3. Actualizar Comentario

Actualiza el texto de un comentario existente. Solo el autor del comentario puede editarlo.

### Request

**Endpoint**: `PUT /api/v1/posts/comments/{comment_id}`

**Parámetros de Path**:
- `comment_id` (int, requerido): ID del comentario a actualizar

**Request Body**:
```json
{
  "comment_text": "¡Excelente post! Sigue así 💪 [EDITADO]"
}
```

**Schema - CommentUpdate**:
| Campo | Tipo | Requerido | Validación | Descripción |
|-------|------|-----------|------------|-------------|
| comment_text | string | Sí | min: 1, max: 2000 | Nuevo texto del comentario |

### Response Exitosa - 200 OK

```json
{
  "id": 123,
  "post_id": 14,
  "user_id": 10,
  "gym_id": 4,
  "comment_text": "¡Excelente post! Sigue así 💪 [EDITADO]",
  "is_edited": true,
  "edited_at": "2025-12-07T06:45:23.456Z",
  "like_count": 3,
  "created_at": "2025-12-07T05:53:36.123Z",
  "updated_at": "2025-12-07T06:45:23.456Z",
  "user_info": {
    "id": 10,
    "first_name": "Juan",
    "last_name": "Pérez",
    "picture": "https://example.com/avatar.jpg"
  },
  "has_liked": false
}
```

**Schema - CommentResponse** (mismo que en crear comentario)

### Errores Posibles

**404 Not Found** - Comentario no encontrado:
```json
{
  "detail": "Comentario no encontrado"
}
```

**403 Forbidden** - Usuario no es el autor del comentario:
```json
{
  "detail": "No tienes permiso para editar este comentario"
}
```

**422 Unprocessable Entity** - Texto inválido (vacío o muy largo)

**401 Unauthorized** - Token inválido o faltante

### Ejemplo cURL

```bash
curl -X PUT "https://gymapi-eh6m.onrender.com/api/v1/posts/comments/123" \
  -H "Authorization: Bearer eyJhbGc..." \
  -H "x-gym-id: 4" \
  -H "Content-Type: application/json" \
  -d '{
    "comment_text": "¡Excelente post! Sigue así 💪 [EDITADO]"
  }'
```

### Notas Técnicas

- **Ownership**: Solo el autor (`user_id`) puede editar su propio comentario
- **Marcado automático**: `is_edited` se pone en `true` automáticamente
- **Timestamp**: `edited_at` se actualiza con la hora UTC actual
- **Likes preservados**: Los likes del comentario NO se pierden al editar
- **Sin límite de ediciones**: Se puede editar múltiples veces

---

## 4. Eliminar Comentario

Elimina un comentario (soft delete). El autor del comentario o un administrador pueden eliminarlo.

### Request

**Endpoint**: `DELETE /api/v1/posts/comments/{comment_id}`

**Parámetros de Path**:
- `comment_id` (int, requerido): ID del comentario a eliminar

**Request Body**: Ninguno

### Response Exitosa - 204 No Content

**Sin contenido en el body de la respuesta**

### Errores Posibles

**404 Not Found** - Comentario no encontrado:
```json
{
  "detail": "Comentario no encontrado"
}
```

**403 Forbidden** - Usuario sin permisos para eliminar:
```json
{
  "detail": "No tienes permiso para eliminar este comentario"
}
```

**401 Unauthorized** - Token inválido o faltante

### Ejemplo cURL

```bash
curl -X DELETE "https://gymapi-eh6m.onrender.com/api/v1/posts/comments/123" \
  -H "Authorization: Bearer eyJhbGc..." \
  -H "x-gym-id: 4"
```

### Notas Técnicas

- **Soft delete**: El comentario se marca con `is_deleted = True` y `deleted_at = UTC_NOW`
- **Permisos**: Puede eliminar el autor (`user_id`) o un admin del gimnasio
- **Contador decrementado**: `comment_count` del post se decrementa automáticamente
- **Transaccional**: Si falla, el contador no se decrementa
- **Permanencia de datos**: El comentario NO se elimina físicamente de la BD
- **Likes preservados**: Los likes del comentario eliminado se mantienen en BD pero no son visibles

---

## 5. Toggle Like en Comentario

Da o quita like a un comentario. Si ya tiene like, lo quita. Si no tiene like, lo agrega.

### Request

**Endpoint**: `POST /api/v1/posts/comments/{comment_id}/like`

**Parámetros de Path**:
- `comment_id` (int, requerido): ID del comentario

**Request Body**: Ninguno (vacío)

### Response Exitosa - 200 OK

**Caso 1: Like agregado (unliked → liked)**
```json
{
  "success": true,
  "action": "liked",
  "total_likes": 6,
  "message": "Comentario liked"
}
```

**Caso 2: Like removido (liked → unliked)**
```json
{
  "success": true,
  "action": "unliked",
  "total_likes": 5,
  "message": "Comentario unliked"
}
```

**Schema - LikeToggleResponse**:
| Campo | Tipo | Descripción |
|-------|------|-------------|
| success | boolean | Siempre true en respuesta exitosa |
| action | string | "liked" o "unliked" según la acción realizada |
| total_likes | integer | Nuevo total de likes del comentario |
| message | string | Mensaje descriptivo de la acción |

### Errores Posibles

**404 Not Found** - Comentario no encontrado o eliminado:
```json
{
  "detail": "Comentario no encontrado"
}
```

**401 Unauthorized** - Token inválido o faltante

**403 Forbidden** - Usuario sin acceso al gimnasio

### Ejemplo cURL

```bash
curl -X POST "https://gymapi-eh6m.onrender.com/api/v1/posts/comments/123/like" \
  -H "Authorization: Bearer eyJhbGc..." \
  -H "x-gym-id: 4" \
  -H "Content-Type: application/json"
```

### Notas Técnicas

- **Idempotente**: Se puede llamar múltiples veces sin efectos negativos
- **Toggle automático**: Detecta automáticamente si ya existe like del usuario
- **Contador atómico**: `like_count` se incrementa/decrementa atómicamente con SQL
- **Constraint único**: `(comment_id, user_id)` previene likes duplicados en BD
- **Race condition safe**: Usa `IntegrityError` para manejar condiciones de carrera
- **Rollback automático**: Si falla por constraint, hace rollback automático
- **Multi-tenant**: El like incluye `gym_id` para aislamiento

---

## Diagramas de Flujo

### Flujo: Crear Comentario

```
Usuario → POST /posts/{post_id}/comment
    ↓
Validar token JWT (Auth0)
    ↓
Validar x-gym-id header
    ↓
Validar schema (comment_text)
    ↓
Verificar que post existe y no está eliminado
    ↓
Verificar que post pertenece al gym_id
    ↓
Crear CommentInteraction
    ↓
Incrementar post.comment_count atómicamente
    ↓
Commit transacción
    ↓
Retornar CommentCreateResponse
```

### Flujo: Toggle Like en Comentario

```
Usuario → POST /comments/{comment_id}/like
    ↓
Validar token JWT
    ↓
Validar x-gym-id
    ↓
Verificar que comentario existe
    ↓
¿Ya existe like del usuario?
    ├─ SÍ → Eliminar like
    │        ├─ Decrementar like_count
    │        ├─ Commit
    │        └─ Retornar action: "unliked"
    │
    └─ NO → Crear like
             ├─ Incrementar like_count
             ├─ Commit (con manejo de IntegrityError)
             └─ Retornar action: "liked"
```

---

## Códigos de Estado HTTP

| Código | Significado | Uso |
|--------|-------------|-----|
| 200 | OK | Operación exitosa (GET, PUT, POST like) |
| 204 | No Content | Eliminación exitosa |
| 401 | Unauthorized | Token JWT faltante o inválido |
| 403 | Forbidden | Usuario sin permisos para la operación |
| 404 | Not Found | Recurso no encontrado (post o comentario) |
| 422 | Unprocessable Entity | Validación de datos fallida |
| 500 | Internal Server Error | Error del servidor |

---

## Modelos de Base de Datos

### Tabla: post_comment

```sql
CREATE TABLE post_comment (
    id SERIAL PRIMARY KEY,
    post_id INTEGER NOT NULL REFERENCES posts(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    gym_id INTEGER NOT NULL REFERENCES gyms(id),
    comment_text TEXT NOT NULL CHECK (length(comment_text) <= 2000),
    is_edited BOOLEAN DEFAULT FALSE,
    edited_at TIMESTAMP,
    like_count INTEGER DEFAULT 0,
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP,

    INDEX idx_post_comment_post_id (post_id),
    INDEX idx_post_comment_user_id (user_id),
    INDEX idx_post_comment_gym_id (gym_id),
    INDEX idx_post_comment_created_at (created_at DESC)
);
```

### Tabla: post_comment_like

```sql
CREATE TABLE post_comment_like (
    id SERIAL PRIMARY KEY,
    comment_id INTEGER NOT NULL REFERENCES post_comment(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    gym_id INTEGER NOT NULL REFERENCES gyms(id),
    created_at TIMESTAMP DEFAULT NOW(),

    UNIQUE (comment_id, user_id),
    INDEX idx_comment_like_comment_id (comment_id),
    INDEX idx_comment_like_user_id (user_id)
);
```

---

## Consideraciones de Seguridad

### Multi-tenancy
- ✅ Todos los endpoints validan `gym_id` del header vs `gym_id` del recurso
- ✅ Imposible acceder/modificar comentarios de otros gimnasios
- ✅ Validación automática en `TenantAuthMiddleware`

### Autenticación
- ✅ JWT de Auth0 obligatorio en todos los endpoints
- ✅ Token incluye `gym_id` en claims custom
- ✅ Permisos validados a nivel de scopes

### Autorización
- ✅ Solo el autor puede editar su comentario
- ✅ Solo el autor o admin puede eliminar comentario
- ✅ Cualquier usuario autenticado puede comentar/dar like

### Validación de Datos
- ✅ Pydantic valida tipos y longitudes automáticamente
- ✅ `comment_text` limitado a 2000 caracteres
- ✅ SQL injection protegido por SQLAlchemy ORM

### Rate Limiting
- ⚠️ Implementar rate limiting para prevenir spam de comentarios
- ⚠️ Implementar rate limiting para likes (actualmente ilimitado)

---

## Performance y Optimización

### Índices de Base de Datos
```sql
-- Índice compuesto para obtener comentarios de un post
CREATE INDEX idx_post_comment_post_deleted
ON post_comment(post_id, is_deleted, created_at DESC);

-- Índice para verificar likes existentes
CREATE INDEX idx_comment_like_user_comment
ON post_comment_like(user_id, comment_id);
```

### Caching
- ❌ Actualmente NO hay caching de comentarios
- 💡 Considerar cachear lista de comentarios por post_id (TTL: 60s)
- 💡 Invalidar cache al crear/editar/eliminar comentario

### Paginación
- ✅ Implementada con `limit` y `offset`
- ✅ `has_more` indica si hay más páginas
- 💡 Considerar cursor-based pagination para mejor performance en listas largas

### N+1 Queries
- ⚠️ `user_info` puede causar N+1 si no está eager-loaded
- 💡 Implementar `joinedload` en query de comentarios:
```python
query = select(PostComment).options(
    joinedload(PostComment.user)
).where(...)
```

---

## Testing

### Casos de Prueba Recomendados

**Crear Comentario**:
- ✅ Crear comentario exitoso con datos válidos
- ✅ Fallar con `comment_text` vacío
- ✅ Fallar con `comment_text` > 2000 caracteres
- ✅ Fallar con `post_id` inexistente
- ✅ Fallar con post de otro gimnasio
- ✅ Verificar incremento de `comment_count`

**Listar Comentarios**:
- ✅ Obtener lista vacía si no hay comentarios
- ✅ Obtener comentarios ordenados por fecha descendente
- ✅ Paginación correcta con `limit` y `offset`
- ✅ `has_more` correcto en última página
- ✅ No mostrar comentarios eliminados

**Actualizar Comentario**:
- ✅ Actualización exitosa por el autor
- ✅ Fallar si usuario no es el autor
- ✅ Verificar `is_edited = true` y `edited_at` actualizado
- ✅ Preservar `like_count` después de editar

**Eliminar Comentario**:
- ✅ Eliminación exitosa por el autor
- ✅ Eliminación exitosa por admin
- ✅ Fallar si usuario no es autor ni admin
- ✅ Verificar soft delete (`is_deleted = true`)
- ✅ Verificar decremento de `comment_count`

**Toggle Like Comentario**:
- ✅ Agregar like si no existe
- ✅ Quitar like si ya existe
- ✅ Incremento/decremento correcto de `like_count`
- ✅ Prevenir likes duplicados (constraint unique)
- ✅ Manejar race conditions correctamente

---

## Changelog

### v1.0.0 (2025-12-07)
- ✅ Implementación inicial de todos los endpoints
- ✅ Migración completa a async/await con AsyncSession
- ✅ Soft delete en comentarios
- ✅ Sistema de likes en comentarios
- ⚠️ **Issue conocido**: Frontend envía `text` en lugar de `comment_text`

### TODOs Pendientes
- [ ] Agregar alias `text` en `CommentCreate` schema para compatibilidad con mobile
- [ ] Implementar notificaciones al dueño del post cuando recibe comentario
- [ ] Implementar sistema de menciones (@usuario) en comentarios
- [ ] Agregar rate limiting para comentarios (max 10/min)
- [ ] Agregar rate limiting para likes (max 60/min)
- [ ] Implementar caching de lista de comentarios
- [ ] Agregar eager loading de `user_info` para evitar N+1
- [ ] Agregar cursor-based pagination
- [ ] Implementar reportes de comentarios
- [ ] Agregar moderación automática (filtro de palabras ofensivas)

---

## Contacto y Soporte

Para reportar bugs o solicitar features relacionados con comentarios de posts:
- **GitHub Issues**: https://github.com/Alexmontesino96/GymAPI/issues
- **Documentación API**: https://gymapi-eh6m.onrender.com/api/v1/docs

---

**Última actualización**: 2025-12-07
**Versión del documento**: 1.0.0
**Autor**: Claude Code (AI Assistant)
