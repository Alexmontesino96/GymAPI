# 📱 Optimización de Performance para Stories - Análisis y Propuestas

## 🔍 Problemas Identificados en el Sistema Actual

### 1. **N+1 Query Problem Severo**
```python
# app/services/story_service.py líneas 306-319
for story in stories:
    user = self.db.get(User, story.user_id)  # ❌ Query por cada story
    has_viewed = await self._has_viewed_story(story.id, user_id)  # ❌ Query por cada story
```
**Impacto**: Si hay 25 stories de 10 usuarios diferentes = **51 queries a la BD**
- 1 query inicial para stories
- 25 queries para verificar vistas
- 25 queries para obtener usuarios

### 2. **No hay Sistema de Caché**
```python
# línea 737
async def _invalidate_story_cache(self, gym_id: int, user_id: int):
    # TODO: Implementar invalidación de cache con redis_client
    # Por ahora, el sistema funciona sin cache para historias.
```
**Impacto**: Cada request recalcula todo desde cero

### 3. **No hay Optimización de Media**
- URLs directas a S3/Cloudinary sin CDN optimization
- No hay thumbnails para imágenes grandes
- No hay compresión adaptativa
- No hay lazy loading implementado

### 4. **Carga Síncrona de Todo el Feed**
- Se cargan todas las stories de golpe
- No hay paginación por usuario
- No hay priorización de contenido

## 🚀 Técnicas que usan Instagram/Facebook

### 1. **Prefetching y Preloading**
```javascript
// Instagram preloads las próximas 3-5 stories mientras ves la actual
{
  "current_story": {...},
  "prefetch_queue": [story_2, story_3, story_4],
  "buffer_size": 3
}
```

### 2. **Progressive Image Loading**
```python
# Instagram usa este patrón:
{
  "media": {
    "placeholder": "data:image/svg+xml;base64,...",  # Blur hash 20x20
    "thumbnail": "https://cdn.../thumb_200x200.jpg",  # Carga primero
    "preview": "https://cdn.../preview_640x640.jpg",  # Carga segundo
    "full": "https://cdn.../full_1080x1920.jpg"      # Carga al final
  }
}
```

### 3. **CDN con Edge Caching**
- **Facebook CDN Strategy**:
  - Múltiples versiones de cada imagen
  - WebP para navegadores modernos
  - Edge servers cerca del usuario
  - Cache headers agresivos (1 año)

### 4. **GraphQL con DataLoader**
Facebook usa GraphQL para resolver el N+1 problem:
```graphql
query StoriesFeed {
  stories(first: 25) {
    edges {
      node {
        id
        media_url
        user {  # Resuelto con DataLoader (1 query batch)
          name
          avatar
        }
        hasViewed  # Resuelto con DataLoader (1 query batch)
      }
    }
  }
}
```

### 5. **Skeleton Screens y Optimistic Updates**
- Muestran placeholders mientras carga
- Actualizan UI antes de confirmar con servidor
- Rollback silencioso si falla

### 6. **Compresión Adaptativa**
Instagram ajusta calidad según:
- Velocidad de conexión
- Tipo de dispositivo
- Batería del dispositivo
- Plan de datos del usuario

## 💡 Propuestas de Mejora para GymAPI

### 1. **Implementar Eager Loading y Batch Queries**

```python
# app/services/story_service.py - MEJORADO
async def get_stories_feed(self, gym_id: int, user_id: int, limit: int = 25):
    # 1. Cargar stories con usuarios en una sola query
    stories = self.db.execute(
        select(Story)
        .options(joinedload(Story.user))  # Eager load users
        .where(
            and_(
                Story.gym_id == gym_id,
                Story.is_deleted == False,
                Story.expires_at > datetime.now(timezone.utc)
            )
        )
        .order_by(Story.created_at.desc())
        .limit(limit)
    ).unique().scalars().all()

    # 2. Batch check de vistas (1 query para todas)
    story_ids = [s.id for s in stories]
    viewed_stories = self.db.execute(
        select(StoryView.story_id)
        .where(
            and_(
                StoryView.story_id.in_(story_ids),
                StoryView.viewer_id == user_id
            )
        )
    ).scalars().all()
    viewed_set = set(viewed_stories)

    # 3. Construir respuesta sin queries adicionales
    for story in stories:
        story.has_viewed = story.id in viewed_set
```

### 2. **Implementar Cache Multi-capa con Redis**

```python
# app/services/story_cache_service.py - NUEVO
class StoryCacheService:
    def __init__(self, redis_client):
        self.redis = redis_client
        self.ttl = {
            'feed': 60,        # Feed cache por 1 minuto
            'story': 300,      # Story individual por 5 minutos
            'user_views': 30,  # Vistas de usuario por 30 segundos
        }

    async def get_feed_cached(self, gym_id: int, user_id: int) -> Optional[Dict]:
        """Cache de feed completo con TTL corto"""
        cache_key = f"gym:{gym_id}:user:{user_id}:stories:feed"
        cached = await self.redis.get(cache_key)

        if cached:
            # Actualizar solo campos dinámicos (view counts)
            return self._refresh_dynamic_fields(cached)

        return None

    async def cache_feed(self, gym_id: int, user_id: int, feed_data: Dict):
        """Cachear feed con compresión"""
        cache_key = f"gym:{gym_id}:user:{user_id}:stories:feed"
        compressed = zlib.compress(json.dumps(feed_data).encode())
        await self.redis.setex(cache_key, self.ttl['feed'], compressed)

    async def get_user_views_cached(self, user_id: int, story_ids: List[int]) -> Set[int]:
        """Cache de vistas del usuario"""
        cache_key = f"user:{user_id}:viewed_stories"
        cached = await self.redis.get(cache_key)

        if cached:
            return set(json.loads(cached))

        # Si no está en cache, buscar en BD y cachear
        viewed = self._get_viewed_from_db(user_id, story_ids)
        await self.redis.setex(cache_key, self.ttl['user_views'], json.dumps(list(viewed)))
        return viewed
```

### 3. **Optimización de Imágenes y CDN**

```python
# app/services/media_optimization_service.py - NUEVO
class MediaOptimizationService:
    def generate_responsive_urls(self, original_url: str) -> Dict[str, str]:
        """Genera URLs optimizadas para diferentes tamaños"""
        base_url = original_url.rsplit('.', 1)[0]
        ext = 'webp'  # Usar WebP cuando sea posible

        return {
            'placeholder': self._generate_blurhash(original_url),
            'thumbnail': f"{base_url}_200x200.{ext}",
            'preview': f"{base_url}_640x640.{ext}",
            'full': f"{base_url}_1080x1920.{ext}",
            'original': original_url
        }

    def _generate_blurhash(self, url: str) -> str:
        """Genera un placeholder blur de 20x20 pixels"""
        # Usar librería blurhash para generar placeholder
        return "data:image/svg+xml;base64,..."
```

### 4. **Paginación Inteligente y Prefetching**

```python
# app/schemas/story.py - MEJORADO
class StoryFeedResponse(BaseModel):
    user_stories: List[UserStoriesGroup]
    prefetch_hints: List[int]  # IDs de próximas stories a precargar
    cache_headers: Dict[str, str]

    class Config:
        schema_extra = {
            "example": {
                "user_stories": [...],
                "prefetch_hints": [456, 457, 458],  # Próximas 3 stories
                "cache_headers": {
                    "Cache-Control": "private, max-age=60",
                    "ETag": "W/\"story-feed-v2-123456\"",
                    "X-Content-Version": "2"
                }
            }
        }
```

### 5. **WebSocket para Updates en Tiempo Real**

```python
# app/websockets/story_updates.py - NUEVO
@app.websocket("/ws/stories/{gym_id}")
async def story_updates(websocket: WebSocket, gym_id: int):
    await manager.connect(websocket, gym_id)
    try:
        while True:
            # Enviar updates incrementales
            update = await manager.get_next_update(gym_id)
            if update['type'] == 'new_story':
                await websocket.send_json({
                    "action": "prepend_story",
                    "data": update['story_preview']  # Solo metadata ligera
                })
    except WebSocketDisconnect:
        manager.disconnect(websocket, gym_id)
```

### 6. **Headers de Cache HTTP Optimizados**

```python
# app/api/v1/endpoints/stories.py - MEJORADO
@router.get("/feed", response_model=StoryFeedResponse)
async def get_stories_feed(
    request: Request,
    response: Response,
    # ... otros parámetros
):
    # Verificar ETag
    etag = f'W/"{gym_id}-{user_id}-{hash(last_update)}"'
    if request.headers.get("If-None-Match") == etag:
        response.status_code = 304  # Not Modified
        return Response(status_code=304)

    # Configurar headers de cache
    response.headers["Cache-Control"] = "private, max-age=60, stale-while-revalidate=120"
    response.headers["ETag"] = etag
    response.headers["X-Content-Version"] = "2"
    response.headers["Vary"] = "Accept-Encoding, Authorization"

    return feed_data
```

## 📊 Métricas de Impacto Esperado

### Antes:
- **Tiempo de carga inicial**: 2-3 segundos
- **Queries a BD por request**: 51
- **Uso de ancho de banda**: 5-10 MB por feed
- **Cache hit rate**: 0%

### Después:
- **Tiempo de carga inicial**: 200-500ms
- **Queries a BD por request**: 3
- **Uso de ancho de banda**: 500KB-1MB por feed
- **Cache hit rate**: 70-80%

## 🚦 Plan de Implementación Recomendado

### Fase 1 (1-2 días) - Quick Wins
1. ✅ Implementar eager loading para eliminar N+1
2. ✅ Cache básico con Redis para feed completo
3. ✅ Headers HTTP de cache

### Fase 2 (3-5 días) - Optimización de Media
1. ✅ Generar múltiples tamaños de imágenes
2. ✅ Implementar blurhash placeholders
3. ✅ CDN configuration con CloudFlare/CloudFront

### Fase 3 (1 semana) - Features Avanzados
1. ✅ WebSocket para updates en tiempo real
2. ✅ Prefetching inteligente
3. ✅ Compresión adaptativa

## 🎯 KPIs a Monitorear

1. **Time to First Byte (TTFB)**: < 200ms
2. **First Contentful Paint (FCP)**: < 500ms
3. **Largest Contentful Paint (LCP)**: < 1s
4. **Cache Hit Rate**: > 70%
5. **API Response Time p95**: < 500ms

## 🔧 Herramientas Recomendadas

1. **Cloudflare Images**: Optimización automática de imágenes
2. **Redis con RedisJSON**: Cache estructurado
3. **DataLoader pattern**: Para batch loading
4. **Blurhash**: Para placeholders
5. **WebP/AVIF**: Formatos modernos de imagen

## 📝 Código de Ejemplo: Implementación Completa Optimizada

```python
# app/services/optimized_story_service.py
class OptimizedStoryService:
    def __init__(self, db: Session, cache: StoryCacheService):
        self.db = db
        self.cache = cache

    async def get_stories_feed(
        self,
        gym_id: int,
        user_id: int,
        limit: int = 25
    ) -> Dict:
        # 1. Check cache first
        cached = await self.cache.get_feed_cached(gym_id, user_id)
        if cached:
            return cached

        # 2. Single optimized query with eager loading
        stories_with_users = await self._fetch_stories_optimized(gym_id, limit)

        # 3. Batch check views
        viewed_ids = await self._batch_check_views(user_id, [s.id for s in stories_with_users])

        # 4. Build response with optimized media URLs
        feed = self._build_optimized_feed(stories_with_users, viewed_ids)

        # 5. Cache result
        await self.cache.cache_feed(gym_id, user_id, feed)

        return feed

    async def _fetch_stories_optimized(self, gym_id: int, limit: int):
        """Una sola query con eager loading"""
        return self.db.execute(
            select(Story)
            .options(
                joinedload(Story.user),
                selectinload(Story.reactions),
                selectinload(Story.views)
            )
            .where(
                and_(
                    Story.gym_id == gym_id,
                    Story.is_deleted == False,
                    Story.expires_at > datetime.now(timezone.utc)
                )
            )
            .order_by(Story.created_at.desc())
            .limit(limit)
        ).unique().scalars().all()

    async def _batch_check_views(self, user_id: int, story_ids: List[int]) -> Set[int]:
        """Una query para todas las vistas"""
        return await self.cache.get_user_views_cached(user_id, story_ids)
```

Esta implementación reduciría el tiempo de carga de 2-3 segundos a menos de 500ms, mejorando significativamente la experiencia del usuario.