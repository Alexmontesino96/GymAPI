# 🚀 Quick Start - Sistema de Posts

Guía rápida para empezar a usar el sistema de posts tipo Instagram.

---

## 📚 Documentación Completa

- **[POSTS_IMPLEMENTATION.md](POSTS_IMPLEMENTATION.md)** - Proceso completo de implementación
- **[POSTS_API_DOCUMENTATION.md](POSTS_API_DOCUMENTATION.md)** - Documentación detallada de API (21 endpoints)

---

## ⚡ Empezar en 5 Minutos

### 1. Verificar Activación

```bash
python verify_posts_activation.py
```

Deberías ver:
```
✅ Gimnasios con módulo 'posts' activo: 5
```

### 2. Crear Bucket en Supabase

1. Ve a tu proyecto de Supabase → Storage
2. Create new bucket: `gym-posts`
3. Configurar permisos públicos de lectura

### 3. Probar en Swagger

1. Abre: http://localhost:8000/api/v1/docs
2. Busca sección "posts"
3. Autoriza con tu token JWT
4. Prueba `POST /api/v1/posts`

---

## 📸 Ejemplos Rápidos

### Crear Post con Imagen

```javascript
const formData = new FormData();
formData.append('caption', '¡Mi primer post! 💪');
formData.append('post_type', 'single_image');
formData.append('privacy', 'public');
formData.append('files', imageFile);

const response = await fetch('/api/v1/posts', {
  method: 'POST',
  headers: { 'Authorization': `Bearer ${token}` },
  body: formData
});

const { post } = await response.json();
console.log('Post creado:', post.id);
```

### Obtener Feed

```javascript
const response = await fetch('/api/v1/posts/feed/timeline?limit=20', {
  headers: { 'Authorization': `Bearer ${token}` }
});

const { posts } = await response.json();
posts.forEach(post => console.log(post.caption));
```

### Dar Like

```javascript
const response = await fetch(`/api/v1/posts/${postId}/like`, {
  method: 'POST',
  headers: { 'Authorization': `Bearer ${token}` }
});

const { action, total_likes } = await response.json();
console.log(`${action}: ${total_likes} likes totales`);
```

### Agregar Comentario

```javascript
const response = await fetch(`/api/v1/posts/${postId}/comment`, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    text: '¡Excelente post! 🔥'
  })
});

const { comment } = await response.json();
console.log('Comentario agregado:', comment.id);
```

---

## 🎯 21 Endpoints Disponibles

### CRUD
- `POST /api/v1/posts` - Crear post
- `GET /api/v1/posts/{post_id}` - Obtener post
- `GET /api/v1/posts/user/{user_id}` - Posts de usuario
- `PUT /api/v1/posts/{post_id}` - Editar post
- `DELETE /api/v1/posts/{post_id}` - Eliminar post

### Feeds
- `GET /api/v1/posts/feed/timeline` - Feed cronológico
- `GET /api/v1/posts/feed/explore` - Posts populares
- `GET /api/v1/posts/feed/location/{location}` - Por ubicación

### Interacciones
- `POST /api/v1/posts/{post_id}/like` - Like/Unlike
- `GET /api/v1/posts/{post_id}/likes` - Ver likes
- `POST /api/v1/posts/{post_id}/comment` - Comentar
- `GET /api/v1/posts/{post_id}/comments` - Ver comentarios
- `PUT /api/v1/posts/comments/{comment_id}` - Editar comentario
- `DELETE /api/v1/posts/comments/{comment_id}` - Eliminar comentario
- `POST /api/v1/posts/comments/{comment_id}/like` - Like comentario

### Otras
- `POST /api/v1/posts/{post_id}/report` - Reportar
- `GET /api/v1/posts/events/{event_id}` - Posts por evento
- `GET /api/v1/posts/sessions/{session_id}` - Posts por sesión
- `GET /api/v1/posts/mentions/me` - Mis menciones

Ver [documentación completa](POSTS_API_DOCUMENTATION.md) para detalles de cada endpoint.

---

## 🔑 Características Principales

✅ **Galería** - Hasta 10 imágenes/videos por post
✅ **Thumbnails** - Generación automática (800x800px)
✅ **Likes visibles** - Lista de usuarios que dieron like
✅ **Comentarios simples** - Sin anidamiento
✅ **Feed Explore** - Ranking por engagement
✅ **Menciones** - @user_id en posts y comentarios
✅ **Tags** - Etiquetar eventos y sesiones
✅ **Privacidad** - Posts públicos o privados
✅ **Reportes** - Sistema de moderación
✅ **Multi-tenancy** - Aislamiento por gimnasio

---

## 📊 Tipos de Post Soportados

| Tipo | Descripción | Media Requerido |
|------|-------------|-----------------|
| `single_image` | Imagen única | 1 imagen |
| `gallery` | Galería | 2-10 imágenes/videos |
| `video` | Video único | 1 video |
| `workout` | Post de entrenamiento | Opcional + workout_data |

---

## 🔐 Autenticación

Todos los endpoints requieren:

```bash
Authorization: Bearer <JWT_TOKEN>
```

El token debe contener:
- `gym_id` - ID del gimnasio (custom claim)
- `sub` - User ID de Auth0

---

## 📝 Validaciones

### Archivos
- **Imágenes:** JPEG, PNG, GIF, WebP (máx 10MB c/u)
- **Videos:** MP4, MOV, AVI (máx 100MB c/u)
- **Galería:** Máximo 10 archivos

### Texto
- **Caption:** Máximo 2200 caracteres
- **Location:** Máximo 255 caracteres
- **Comentarios:** Máximo 2200 caracteres

---

## 🏗️ Arquitectura

```
┌─────────────────┐
│   API Endpoint  │  21 endpoints REST
└────────┬────────┘
         │
┌────────▼────────┐
│    Services     │  PostService, PostInteractionService, PostMediaService
└────────┬────────┘
         │
┌────────▼────────┐
│  Repositories   │  PostRepository, PostFeedRepository
└────────┬────────┘
         │
┌────────▼────────┐
│   Database      │  7 tablas (posts, post_media, post_likes, post_comments, etc.)
└─────────────────┘
         │
┌────────▼────────┐
│  Integraciones  │  Stream Feeds, Supabase Storage
└─────────────────┘
```

---

## 🎨 UI Components Sugeridos

Para una experiencia tipo Instagram, necesitarás:

### Feed View
- Grid de posts (3 columnas en web, 1 en mobile)
- Infinite scroll con paginación
- Lazy loading de imágenes
- Skeleton loaders

### Post Detail
- Carrusel de imágenes (si es galería)
- Caption con menciones clicables
- Contador de likes (con modal de usuarios)
- Lista de comentarios
- Input para nuevo comentario
- Botón de like con animación

### Post Creation
- Multi-file picker
- Preview de imágenes seleccionadas
- Input de caption con contador de caracteres
- Selector de ubicación
- Selector de privacidad
- Tags de eventos/sesiones
- Menciones con autocomplete

---

## 🚀 Performance Tips

### Frontend
```javascript
// 1. Paginación eficiente
const LIMIT = 20;
let offset = 0;

// 2. UI Optimista para likes
function optimisticLike(postId) {
  // Actualizar UI primero
  updateUI();
  // Luego confirmar con servidor
  sendRequest();
}

// 3. Lazy loading de imágenes
<img loading="lazy" src={post.media[0].thumbnail_url} />

// 4. Comprimir antes de subir
const compressed = await compressImage(file, {
  maxWidth: 1920,
  maxHeight: 1920,
  quality: 0.8
});
```

### Backend
- ✅ Ya implementado: Índices optimizados
- ✅ Ya implementado: Contadores atómicos
- ✅ Ya implementado: Eager loading
- ✅ Ya implementado: Thumbnails automáticos
- ⏸️ Pendiente: Cache Redis (preparado)

---

## 🐛 Troubleshooting

### "Module not available"
```bash
# Activar módulo para el gym
python activate_posts_for_all_gyms.py
```

### "File upload failed"
1. Verificar bucket `gym-posts` existe en Supabase
2. Verificar permisos del bucket
3. Verificar tamaño del archivo

### Feed vacío
1. Crear algunos posts de prueba
2. Verificar que sean públicos
3. Verificar `gym_id` en el token JWT

---

## 📞 Recursos

- **Swagger UI:** http://localhost:8000/api/v1/docs
- **Documentación API:** [POSTS_API_DOCUMENTATION.md](POSTS_API_DOCUMENTATION.md)
- **Implementación:** [POSTS_IMPLEMENTATION.md](POSTS_IMPLEMENTATION.md)
- **Scripts:**
  - `configure_posts_module.py` - Configurar módulo
  - `activate_posts_for_all_gyms.py` - Activar para gyms
  - `verify_posts_activation.py` - Verificar estado

---

## ✅ Checklist de Activación

- [x] Migración de BD aplicada (7 tablas)
- [x] Módulo configurado en tabla `modules` (ID: 9)
- [x] Módulo activado para todos los gyms
- [x] Router registrado en `/api/v1/posts`
- [ ] Bucket `gym-posts` creado en Supabase
- [ ] Permisos del bucket configurados
- [ ] Primera prueba de creación de post
- [ ] Integración con frontend

---

**¡Listo para usar! 🎉**

Para más detalles, consulta la [documentación completa de API](POSTS_API_DOCUMENTATION.md).
