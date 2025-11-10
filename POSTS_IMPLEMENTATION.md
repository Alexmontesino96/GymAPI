# 📝 Implementación del Sistema de Posts

**Fecha inicio:** 2025-11-09
**Fecha finalización:** 2025-11-09
**Progreso general:** 95% (Implementación completa, faltan testing y docs)

---

## 🎉 RESUMEN DE LO COMPLETADO

### Archivos Creados (2,823 líneas de código)
1. **app/models/post.py** (153 líneas) - Modelos Post, PostMedia, PostTag
2. **app/models/post_interaction.py** (169 líneas) - PostLike, PostComment, PostCommentLike, PostReport
3. **app/schemas/post.py** (170 líneas) - Schemas de posts y media
4. **app/schemas/post_interaction.py** (155 líneas) - Schemas de interacciones
5. **app/services/post_media_service.py** (333 líneas) - Upload de galería
6. **app/services/post_service.py** (418 líneas) - Lógica de negocio principal
7. **app/services/post_interaction_service.py** (432 líneas) - Likes y comentarios
8. **app/repositories/post_repository.py** (159 líneas) - Queries especializadas
9. **app/repositories/post_feed_repository.py** (228 líneas) - Stream Feeds
10. **app/api/v1/endpoints/posts.py** (529 líneas) - 21 endpoints REST
11. **migrations/versions/f546b56de5bb_*.py** (226 líneas) - Migración de BD

### Configuración
- ✅ Router registrado en `/api/v1/posts`
- ✅ Módulo "posts" creado en BD (ID: 9)
- ✅ 7 tablas de BD creadas y verificadas
- ✅ Relaciones en User y Gym actualizadas

### Funcionalidades Implementadas
- ✅ CRUD completo de posts
- ✅ Upload de galería (hasta 10 archivos)
- ✅ Generación automática de thumbnails
- ✅ Sistema de likes con contadores atómicos
- ✅ Sistema de comentarios simples
- ✅ Likes en comentarios
- ✅ Sistema de reportes
- ✅ Feed timeline cronológico
- ✅ Feed explorar con ranking por engagement
- ✅ Filtros por ubicación
- ✅ Tags a eventos y sesiones
- ✅ Menciones de usuarios
- ✅ Integración con Stream Feeds
- ✅ Multi-tenancy completo
- ✅ Privacidad (PUBLIC/PRIVATE)

---

## ✅ COMPLETADO

### Fase 1: Modelos y Base de Datos ✅
- [x] Crear modelo `Post` con todos los campos
- [x] Crear modelo `PostMedia` para galería
- [x] Crear modelo `PostTag` para menciones y etiquetas
- [x] Crear modelo `PostLike` con constraint de unicidad
- [x] Crear modelo `PostComment` para comentarios simples
- [x] Crear modelo `PostCommentLike` para likes en comentarios
- [x] Crear modelo `PostReport` para sistema de moderación
- [x] Crear enums: `PostType`, `PostPrivacy`, `TagType`, `ReportReason`
- [x] Agregar relaciones en modelo `User`
- [x] Agregar relaciones en modelo `Gym`
- [x] Actualizar imports en `app/db/base.py`
- [x] Crear migración de Alembic
- [x] Aplicar migración a la base de datos
- [x] Verificar tablas creadas (7 tablas)

**Archivos creados:**
- `app/models/post.py` (153 líneas)
- `app/models/post_interaction.py` (169 líneas)
- `migrations/versions/f546b56de5bb_add_posts_system_with_gallery_support.py` (226 líneas)
- `apply_posts_migration.py` (script auxiliar)

### Fase 2: Schemas Pydantic ✅
- [x] Crear `PostBase` schema
- [x] Crear `PostCreate` con validaciones
- [x] Crear `PostUpdate` (solo caption y location)
- [x] Crear `PostMediaCreate` y `PostMediaResponse`
- [x] Crear `PostTagResponse`
- [x] Crear `PostInDBBase` y `Post` (respuesta completa)
- [x] Crear `PostResponse` y `PostListResponse`
- [x] Crear `PostFeedResponse` para feeds
- [x] Crear `PostStatsResponse` para estadísticas
- [x] Crear `PostCreateMultipart` para form-data
- [x] Crear `CommentCreate` y `CommentUpdate`
- [x] Crear `CommentResponse` y `CommentsListResponse`
- [x] Crear `PostLikeResponse` y `LikeToggleResponse`
- [x] Crear `PostReportCreate` y `PostReportResponse`
- [x] Crear schemas de estadísticas

**Archivos creados:**
- `app/schemas/post.py` (170 líneas)
- `app/schemas/post_interaction.py` (155 líneas)

---

## 🔄 EN PROGRESO

### Fase 3: Servicios de Media y Upload
**Prioridad:** ALTA | **Estimación:** 1-2 horas

#### PostMediaService
- [ ] Crear clase `PostMediaService` extendiendo `MediaService`
- [ ] Implementar `upload_post_media()` para múltiples archivos
  - [ ] Validar tipos de archivo (imagen/video)
  - [ ] Validar tamaño (10MB imágenes, 100MB videos)
  - [ ] Generar nombres únicos con UUID
  - [ ] Subir a Supabase bucket `POSTS_BUCKET`
  - [ ] Generar thumbnails para imágenes
  - [ ] Generar thumbnails para videos (opcional)
  - [ ] Retornar URLs y metadata
- [ ] Implementar `upload_gallery()` para múltiples archivos
  - [ ] Validar máximo 10 archivos
  - [ ] Subir archivos en paralelo
  - [ ] Mantener orden (display_order)
  - [ ] Crear registros en `post_media`
- [ ] Implementar `delete_post_media()` para limpiar archivos
- [ ] Implementar `get_media_by_post_id()`
- [ ] Agregar manejo de errores robusto

**Archivo a crear:**
- `app/services/post_media_service.py` (~200 líneas)

---

## ⏳ PENDIENTE

### Fase 4: Servicios Core
**Prioridad:** ALTA | **Estimación:** 2-3 horas

#### PostService
- [ ] Crear clase `PostService` con dependencia de DB
- [ ] Implementar `create_post()`
  - [ ] Validar usuario pertenece al gym
  - [ ] Crear registro en BD
  - [ ] Procesar archivos de media (llamar MediaService)
  - [ ] Procesar tags (menciones, eventos, sesiones)
  - [ ] Publicar en Stream Feeds
  - [ ] Enviar notificaciones a mencionados
  - [ ] Invalidar cache
- [ ] Implementar `get_post_by_id()`
  - [ ] Verificar privacidad
  - [ ] Eager load media y tags
  - [ ] Calcular campos: has_liked, is_own_post
  - [ ] Incluir user_info
- [ ] Implementar `get_user_posts()`
  - [ ] Filtrar por gym_id
  - [ ] Paginación
  - [ ] Ordenar por created_at DESC
- [ ] Implementar `update_post()`
  - [ ] Solo caption y location editables
  - [ ] Marcar is_edited = true
  - [ ] Actualizar edited_at
  - [ ] Invalidar cache
- [ ] Implementar `delete_post()`
  - [ ] Soft delete (is_deleted = true)
  - [ ] Eliminar de Stream Feeds
  - [ ] Eliminar archivos de media
  - [ ] Invalidar cache
- [ ] Implementar métodos auxiliares privados
  - [ ] `_can_view_post()` - verificar privacidad
  - [ ] `_process_mentions()` - extraer @menciones del caption
  - [ ] `_create_tags()` - crear registros en post_tags
  - [ ] `_invalidate_post_cache()` - limpiar cache

**Archivo a crear:**
- `app/services/post_service.py` (~400 líneas)

#### PostInteractionService
- [ ] Crear clase `PostInteractionService`
- [ ] Implementar `toggle_like()`
  - [ ] Verificar si ya existe like
  - [ ] Si existe: eliminar (unlike)
  - [ ] Si no existe: crear (like)
  - [ ] Actualizar contador con SQL atómico
  - [ ] Invalidar cache
  - [ ] Retornar action ('liked' o 'unliked')
- [ ] Implementar `get_post_likes()`
  - [ ] Paginación
  - [ ] Incluir user_info
- [ ] Implementar `add_comment()`
  - [ ] Validar longitud texto
  - [ ] Crear registro
  - [ ] Actualizar contador de comentarios
  - [ ] Notificar al dueño del post
  - [ ] Notificar usuarios mencionados en comentario
  - [ ] Invalidar cache
- [ ] Implementar `update_comment()`
  - [ ] Verificar ownership
  - [ ] Solo texto editable
  - [ ] Marcar is_edited = true
- [ ] Implementar `delete_comment()`
  - [ ] Verificar ownership o admin
  - [ ] Soft delete
  - [ ] Actualizar contador
- [ ] Implementar `get_post_comments()`
  - [ ] Paginación
  - [ ] Ordenar por created_at
  - [ ] Incluir user_info
  - [ ] Calcular has_liked
- [ ] Implementar `toggle_comment_like()`
  - [ ] Similar a toggle_like de posts
- [ ] Implementar `report_post()`
  - [ ] Crear reporte
  - [ ] Notificar admins
  - [ ] Validar no duplicados

**Archivo a crear:**
- `app/services/post_interaction_service.py` (~350 líneas)

---

### Fase 5: Repositorios
**Prioridad:** MEDIA | **Estimación:** 2 horas

#### PostRepository
- [ ] Crear clase extendiendo `BaseRepository`
- [ ] Implementar `get_by_location()`
- [ ] Implementar `get_by_tag()`
- [ ] Implementar `get_trending()`
  - [ ] Query con engagement_score calculado
  - [ ] Filtrar últimas 24-48 horas
  - [ ] Ordenar por score DESC
- [ ] Implementar `get_by_event_id()`
- [ ] Implementar `get_by_session_id()`

**Archivo a crear:**
- `app/repositories/post_repository.py` (~150 líneas)

#### PostFeedRepository
- [ ] Crear clase para integración con Stream Feeds
- [ ] Implementar `create_post_activity()`
  - [ ] Formato: verb="post", actor, object
  - [ ] Incluir metadata completa
  - [ ] Publicar en feed "user"
- [ ] Implementar `get_gym_feed()`
  - [ ] Obtener de feed global del gym
  - [ ] Fallback a BD si Stream falla
  - [ ] Aplicar ranking/scoring
- [ ] Implementar `get_explore_feed()`
  - [ ] Feed de posts populares
  - [ ] Cálculo de engagement score
  - [ ] Cache de 5 minutos
- [ ] Implementar `delete_post_activity()`
- [ ] Implementar métodos auxiliares
  - [ ] `_calculate_engagement_score()`
  - [ ] `_sanitize_user_id()`

**Archivo a crear:**
- `app/repositories/post_feed_repository.py` (~250 líneas)

---

### Fase 6: Endpoints API
**Prioridad:** ALTA | **Estimación:** 3-4 horas

#### Posts CRUD
- [ ] Crear router con prefix `/posts`
- [ ] Agregar dependency `module_enabled("posts")`
- [ ] Implementar `POST /posts`
  - [ ] Multipart form-data
  - [ ] Recibir múltiples archivos (hasta 10)
  - [ ] Validar post_type
  - [ ] Llamar PostService.create_post()
  - [ ] Retornar PostResponse
- [ ] Implementar `GET /posts/{post_id}`
  - [ ] Verificar privacidad
  - [ ] Incluir media y tags
  - [ ] Incluir has_liked
- [ ] Implementar `GET /posts/user/{user_id}`
  - [ ] Paginación (limit, offset)
  - [ ] Filtrar por gym_id
- [ ] Implementar `PUT /posts/{post_id}`
  - [ ] Verificar ownership
  - [ ] Solo caption y location
- [ ] Implementar `DELETE /posts/{post_id}`
  - [ ] Verificar ownership o admin

#### Feeds
- [ ] Implementar `GET /posts/feed`
  - [ ] Query param: feed_type (timeline, explore, all)
  - [ ] Paginación
  - [ ] Ordenar por created_at o engagement
- [ ] Implementar `GET /posts/feed/explore`
  - [ ] Posts más populares del gym
  - [ ] Algoritmo de ranking
- [ ] Implementar `GET /posts/feed/location/{location}`
  - [ ] Posts por ubicación

#### Interacciones
- [ ] Implementar `POST /posts/{post_id}/like`
  - [ ] Toggle like/unlike
  - [ ] Retornar action y total
- [ ] Implementar `GET /posts/{post_id}/likes`
  - [ ] Lista paginada con user_info
- [ ] Implementar `POST /posts/{post_id}/comment`
  - [ ] Crear comentario
  - [ ] Notificar
- [ ] Implementar `GET /posts/{post_id}/comments`
  - [ ] Paginación
  - [ ] Incluir user_info
- [ ] Implementar `PUT /posts/comments/{comment_id}`
  - [ ] Editar comentario
- [ ] Implementar `DELETE /posts/comments/{comment_id}`
  - [ ] Eliminar comentario
- [ ] Implementar `POST /posts/comments/{comment_id}/like`
  - [ ] Toggle like en comentario
- [ ] Implementar `POST /posts/{post_id}/report`
  - [ ] Crear reporte

**Archivo a crear:**
- `app/api/v1/endpoints/posts.py` (~600 líneas)

---

### Fase 7: Features Avanzadas
**Prioridad:** MEDIA | **Estimación:** 2 horas

#### Menciones
- [ ] Implementar parser de menciones en `PostService`
  - [ ] Regex para detectar @username o @user_id
  - [ ] Validar usuarios existen en el gym
  - [ ] Crear registros en post_tags
- [ ] Implementar notificaciones para mencionados
  - [ ] Usar OneSignal
  - [ ] Template: "Te mencionaron en un post"
- [ ] Implementar endpoint `GET /posts/mentions/me`
  - [ ] Posts donde fui mencionado

#### Etiquetas a Eventos/Sesiones
- [ ] Validar evento existe y pertenece al gym
- [ ] Validar sesión existe y pertenece al gym
- [ ] Crear registros en post_tags
- [ ] Implementar endpoints:
  - [ ] `GET /events/{event_id}/posts`
  - [ ] `GET /sessions/{session_id}/posts`

#### Feed Explorar
- [ ] Implementar algoritmo de ranking
  - [ ] Formula: `(likes * 1.0 + comments * 2.0) / sqrt(age_hours + 1)`
- [ ] Cachear resultados en Redis (5 min)
- [ ] Implementar paginación eficiente
- [ ] Filtros opcionales:
  - [ ] Por tipo de post
  - [ ] Por rango de fechas

---

### Fase 8: Optimizaciones
**Prioridad:** BAJA | **Estimación:** 1-2 horas

#### Cache Redis
- [ ] Implementar `_invalidate_post_cache()`
- [ ] Cache keys:
  - [ ] `gym:{gym_id}:post:{post_id}`
  - [ ] `gym:{gym_id}:post:{post_id}:likes`
  - [ ] `gym:{gym_id}:post:{post_id}:comments`
  - [ ] `gym:{gym_id}:user:{user_id}:posts`
  - [ ] `gym:{gym_id}:feed:explore`
- [ ] TTLs:
  - [ ] Post individual: 5 min
  - [ ] Contadores: 1 min
  - [ ] Feed: 2 min
- [ ] Invalidación en updates/deletes

#### Contadores Atómicos
- [ ] Refactorizar incremento de like_count con SQL
  - [ ] `UPDATE posts SET like_count = like_count + 1`
- [ ] Refactorizar incremento de comment_count
- [ ] Refactorizar like_count en comentarios

#### Índices y Performance
- [ ] Verificar todos los índices están creados
- [ ] Analizar queries lentas
- [ ] Agregar índices adicionales si necesario
- [ ] Configurar EXPLAIN ANALYZE en queries críticas

---

### Fase 9: Configuración y Módulo
**Prioridad:** ALTA | **Estimación:** 30 min

#### Módulo "posts"
- [ ] Insertar registro en tabla `modules`
  - [ ] code: "posts"
  - [ ] name: "Publicaciones"
  - [ ] description: "Sistema de posts permanentes tipo Instagram"
  - [ ] is_premium: false
- [ ] Script de migración de datos si necesario
- [ ] Documentar activación del módulo

#### Configuración
- [ ] Agregar variables de entorno en `.env.example`:
  - [ ] `POSTS_BUCKET=gym-posts`
  - [ ] `MAX_POST_IMAGES=10`
  - [ ] `MAX_POST_IMAGE_SIZE_MB=10`
  - [ ] `MAX_POST_VIDEO_SIZE_MB=100`
- [ ] Actualizar `app/core/config.py` con nuevas settings
- [ ] Crear bucket en Supabase Storage

#### Registro en API
- [ ] Importar router en `app/api/v1/api.py`
- [ ] Registrar con prefijo `/posts`
- [ ] Verificar tags en OpenAPI

---

### Fase 10: Testing y Documentación
**Prioridad:** MEDIA | **Estimación:** 2 horas

#### Tests Unitarios
- [ ] Tests de `PostService`
  - [ ] `test_create_post()`
  - [ ] `test_update_post()`
  - [ ] `test_delete_post()`
- [ ] Tests de `PostInteractionService`
  - [ ] `test_toggle_like()`
  - [ ] `test_add_comment()`
- [ ] Tests de `PostMediaService`
  - [ ] `test_upload_single_image()`
  - [ ] `test_upload_gallery()`

#### Tests de Integración
- [ ] Test completo de creación de post con galería
- [ ] Test de feed con posts
- [ ] Test de menciones y notificaciones
- [ ] Test de reportes

#### Documentación
- [ ] Actualizar README con sección de Posts
- [ ] Documentar API endpoints en CLAUDE.md
- [ ] Ejemplos de uso en Swagger/OpenAPI
- [ ] Guía de activación del módulo

---

## 📊 Resumen de Progreso

### Tareas Principales
- ✅ Completadas: 6/19 (32%)
- 🔄 En progreso: 1/19 (5%)
- ⏳ Pendientes: 12/19 (63%)

### Estimación de Tiempo Restante
- **Fase 3 (Media):** 1-2 horas
- **Fase 4 (Servicios):** 2-3 horas
- **Fase 5 (Repositorios):** 2 horas
- **Fase 6 (Endpoints):** 3-4 horas
- **Fase 7 (Features):** 2 horas
- **Fase 8 (Optimizaciones):** 1-2 horas
- **Fase 9 (Configuración):** 30 min
- **Fase 10 (Testing):** 2 horas

**TOTAL ESTIMADO:** 14-18 horas

### Líneas de Código
- ✅ Completado: ~1,000 líneas
- ⏳ Pendiente: ~2,500 líneas
- **TOTAL ESTIMADO:** ~3,500 líneas

---

## 🎯 Próximos Pasos Inmediatos

1. **Implementar PostMediaService** (1 hora)
2. **Implementar PostService básico** (1.5 horas)
3. **Implementar endpoints CRUD básicos** (1.5 horas)
4. **Testing básico** (30 min)

**= 4.5 horas para MVP funcional**

---

## 📝 Notas y Decisiones

- **Galería:** Hasta 10 imágenes/videos por post
- **Comentarios:** Sin anidamiento en v1 (solo comentarios de primer nivel)
- **Follows:** NO implementado - feed global del gym
- **Privacidad:** Solo PUBLIC y PRIVATE (sin FOLLOWERS)
- **Cache:** Redis con fallback si no disponible
- **Stream Feeds:** Con fallback a BD si falla

---

**Última actualización:** 2025-11-09 21:30
