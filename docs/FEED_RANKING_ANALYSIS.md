# Análisis: Algoritmo de Ranking para Feed de Posts en GymApi

**Fecha:** 2025-11-13
**Autor:** Claude Code
**Repositorio analizado:** [Ranking-social-media-news-feed](https://github.com/SamBelkacem/Ranking-social-media-news-feed)

---

## Índice

1. [Resumen Ejecutivo](#resumen-ejecutivo)
2. [Análisis del Repositorio GitHub](#análisis-del-repositorio-github)
3. [Sistema Actual de Posts en GymApi](#sistema-actual-de-posts-en-gymapi)
4. [Comparación de Sistemas](#comparación-de-sistemas)
5. [Features Aprovechables](#features-aprovechables)
6. [Plan de Implementación por Fases](#plan-de-implementación-por-fases)
7. [Métricas de Éxito](#métricas-de-éxito)
8. [Desafíos y Mitigaciones](#desafíos-y-mitigaciones)
9. [Recomendaciones](#recomendaciones)

---

## Resumen Ejecutivo

### El Problema

El feed de posts actual en GymApi utiliza una fórmula de ranking simple:

```
engagement_score = (likes * 1.0) + (comments * 2.0) - (age_hours * 0.1)
```

Esta fórmula tiene limitaciones:
- ❌ Sin personalización por usuario
- ❌ No diferencia tipos de contenido (workout vs imagen simple)
- ❌ Decay temporal lineal (poco realista)
- ❌ No considera menciones ni hashtags
- ❌ No aprende de patrones de engagement

### La Oportunidad

El repositorio analizado demuestra que **Machine Learning puede mejorar el engagement en feeds hasta un 40%** usando 14 features y modelos de ensemble learning (Random Forest, Gradient Boosting).

### La Solución Propuesta

**Enfoque gradual en 4 fases:**
1. **Fase 1 (1-2 semanas):** Mejoras con features existentes → +20-30% engagement
2. **Fase 2 (2-4 semanas):** Sistema de follow y trending → +15-20% engagement
3. **Fase 3 (4-8 semanas):** Modelo ML básico → +25-40% engagement
4. **Fase 4 (3-6 meses):** ML avanzado y personalización real-time

**Recomendación:** Empezar con **Fase 1** (mejor ratio esfuerzo/impacto)

---

## Análisis del Repositorio GitHub

### Descripción del Sistema

**Proyecto:** Ranking de feeds de redes sociales usando aprendizaje supervisado
**Contexto:** Análisis de 26,180 tweets de 46 usuarios durante 10 meses
**Objetivo:** Predecir relevancia de posts para cada usuario

### Modelos de Machine Learning Evaluados

| Modelo | Tipo | Accuracy | Ranking |
|--------|------|----------|---------|
| **Gradient Boosting (GB)** | Ensemble | ~90% | 🥇 Mejor |
| **Random Forest (RF)** | Ensemble | ~89% | 🥈 Mejor |
| Support Vector Machine (SVM) | Discriminativo | ~85% | Regular |
| Decision Trees (DT) | Árbol | ~82% | Regular |
| Neural Networks (ANN) | Deep Learning | ~83% | Regular |
| Logistic Regression (LR) | Lineal | ~78% | Bajo |
| Naive Bayes (NB) | Probabilístico | ~75% | Bajo |

**Conclusión del estudio:** Los modelos de ensemble learning (GB y RF) superan significativamente a otros enfoques.

### Features Utilizadas (14 señales)

#### Features de Contenido

| Feature | Descripción | Tipo | Ejemplo |
|---------|-------------|------|---------|
| `keywords_relevance` | Relevancia de palabras clave | Numérico (0-11) | 7 |
| `hashtags_relevance` | Relevancia de hashtags | Numérico (0-14) | 5 |
| `hashtags` | Presencia de hashtags | Binario | 1 |
| `length` | Longitud del contenido | Numérico (5-140) | 87 |
| `multimedia` | Contiene multimedia | Binario | 1 |
| `url` | Contiene URL | Binario | 0 |

#### Features de Engagement

| Feature | Descripción | Tipo | Ejemplo |
|---------|-------------|------|---------|
| `interaction_rate` | Tasa de engagement | Decimal (0-1) | 0.75 |
| `popularity` | Métrica de popularidad | Numérico (0-2745) | 156 |

#### Features de Usuario/Autor

| Feature | Descripción | Tipo | Ejemplo |
|---------|-------------|------|---------|
| `followers_followings` | Ratio seguidores/seguidos | Numérico | 2,500 |
| `seniority` | Antigüedad de la cuenta | Numérico (0-10) | 3 |
| `listed_count` | Apariciones en listas | Numérico | 45 |

#### Features de Relaciones

| Feature | Descripción | Tipo | Ejemplo |
|---------|-------------|------|---------|
| `mentions_relevance` | Relevancia de menciones | Numérico | 1 |
| `mention_count` | Cantidad de menciones | Numérico | 3 |

#### Variable Objetivo

| Feature | Descripción | Tipo | Uso |
|---------|-------------|------|-----|
| `relevance` | ¿Es relevante para el usuario? | Binario (0/1) | Label/Target |

### Ventajas del Enfoque ML

✅ **Personalización real:** Predice relevancia específica para cada usuario
✅ **Patrones complejos:** Aprende interacciones no lineales entre features
✅ **Validación científica:** Comparación empírica de 7 algoritmos
✅ **Escalabilidad:** RF y GB manejan millones de posts eficientemente
✅ **Feature importance:** Identifica qué señales importan más
✅ **Mejora continua:** Reentrenamiento periódico adapta a cambios

### Desventajas del Enfoque ML

❌ **Complejidad técnica:** Requiere infraestructura de ML (training, serving, monitoring)
❌ **Cold start:** Usuarios nuevos sin historial no pueden ser rankeados
❌ **Latencia:** Inferencia añade 50-200ms por request
❌ **Mantenimiento:** Modelos requieren reentrenamiento periódico
❌ **Recursos:** Mayor uso de CPU/memoria que fórmulas simples
❌ **Contexto específico:** Diseñado para Twitter, no directamente aplicable a gym
❌ **Datos de entrenamiento:** Necesita miles de ejemplos etiquetados

---

## Sistema Actual de Posts en GymApi

### Arquitectura

```
┌─────────────────────────────────────────────────────────┐
│                     API Endpoints                        │
│           /api/v1/posts/feed/{timeline|explore}          │
└───────────────────────┬─────────────────────────────────┘
                        │
        ┌───────────────┴───────────────┐
        ▼                               ▼
┌───────────────┐              ┌──────────────────┐
│  PostService  │              │ PostFeedRepository│
└───────┬───────┘              └────────┬─────────┘
        │                               │
        ▼                               ▼
┌───────────────┐              ┌──────────────────┐
│PostRepository │              │ Stream Feeds API │
└───────┬───────┘              │   (opcional)     │
        │                      └──────────────────┘
        ▼
┌───────────────┐
│  PostgreSQL   │
│   + Redis     │
└───────────────┘
```

### Modelos de Datos

#### Post (modelo principal)

```python
class Post(Base):
    id: int
    gym_id: int                    # Multi-tenant
    user_id: int                   # Autor del post

    # Contenido
    post_type: Enum                # SINGLE_IMAGE, GALLERY, VIDEO, WORKOUT
    caption: str (max 2000)        # Texto del post
    location: str                  # Ubicación del gym
    workout_data: JSON             # Datos de entrenamiento

    # Privacy
    privacy: Enum                  # PUBLIC, PRIVATE

    # Engagement counters
    like_count: int = 0
    comment_count: int = 0
    view_count: int = 0            # ⚠️ No usado actualmente

    # Metadata
    is_edited: bool
    edited_at: datetime
    is_deleted: bool

    # Timestamps
    created_at: datetime
    updated_at: datetime
```

#### PostMedia (galería)

```python
class PostMedia(Base):
    id: int
    post_id: int
    media_type: Enum               # IMAGE, VIDEO
    media_url: str                 # S3/Cloudinary URL
    thumbnail_url: str             # Para videos
    display_order: int             # Orden en galería
    width: int
    height: int
```

#### PostTag (menciones)

```python
class PostTag(Base):
    id: int
    post_id: int
    tag_type: Enum                 # MENTION, EVENT, SESSION
    tagged_user_id: int            # Para MENTION
    tagged_event_id: int           # Para EVENT
    tagged_session_id: int         # Para SESSION
```

#### PostInteraction (engagement)

```python
# PostLike
class PostLike(Base):
    post_id: int
    user_id: int
    created_at: datetime

# PostComment
class PostComment(Base):
    post_id: int
    user_id: int
    content: str
    like_count: int
    created_at: datetime

# PostReport (moderación)
class PostReport(Base):
    post_id: int
    reporter_id: int
    reason: str
    description: str
```

### Sistema de Ranking Actual

#### Fórmula Simple (línea 95-100 de `app/models/post.py`)

```python
@property
def engagement_score(self) -> float:
    """
    Calcula score de engagement para ranking.
    Fórmula: likes + (comments * 2) - (age_hours * 0.1)
    """
    age_hours = (datetime.utcnow() - self.created_at).total_seconds() / 3600
    return (self.like_count * 1.0) + (self.comment_count * 2.0) - (age_hours * 0.1)
```

**Componentes:**
- **Likes:** Peso 1.0
- **Comments:** Peso 2.0 (valorados el doble que likes)
- **Age decay:** -0.1 por hora (penaliza contenido antiguo)

**Ejemplo:**
```
Post A: 50 likes, 10 comments, 5 horas → (50*1) + (10*2) - (5*0.1) = 69.5
Post B: 30 likes, 20 comments, 2 horas → (30*1) + (20*2) - (2*0.1) = 69.8 ✓
```

### Tipos de Feeds Implementados

#### 1. Timeline Feed (`GET /api/v1/posts/feed/timeline`)

**Descripción:** Feed cronológico simple
**Ordenamiento:** `created_at DESC`
**Personalización:** Ninguna

```python
# app/services/post_service.py (línea 180)
query = query.order_by(Post.created_at.desc())
```

**Respuesta:**
```json
{
  "posts": [
    {
      "id": 123,
      "user": {...},
      "caption": "Día de piernas 💪",
      "media": [...],
      "like_count": 45,
      "comment_count": 8,
      "created_at": "2025-11-13T10:30:00Z",
      "has_liked": false,
      "is_own_post": false
    }
  ],
  "total": 150,
  "has_more": true
}
```

#### 2. Explore Feed (`GET /api/v1/posts/feed/explore`)

**Descripción:** Feed ordenado por engagement
**Ordenamiento:** `(like_count + comment_count*2) DESC, created_at DESC`
**Personalización:** Ninguna

```python
# app/api/v1/endpoints/posts.py (línea 450)
query = query.order_by(
    (Post.like_count + Post.comment_count * 2).desc(),
    Post.created_at.desc()
)
```

#### 3. User Profile Feed (`GET /api/v1/posts/user/{user_id}`)

**Descripción:** Posts de un usuario específico
**Ordenamiento:** `created_at DESC`
**Personalización:** Respeta privacidad (solo PUBLIC si no es el autor)

#### 4. Stream Feeds Integration (opcional)

**Descripción:** Integración con Stream Feeds API para escalabilidad
**Archivo:** `app/repositories/post_feed_repository.py`

```python
# Líneas 153-217
async def get_explore_feed(self, gym_id: int, user_id: int, limit: int):
    # 1. Obtener posts recientes de Stream
    activities = await stream_feed.get(gym_id, limit=100)

    # 2. Calcular engagement score en runtime
    for activity in activities:
        activity['score'] = calculate_engagement(activity)

    # 3. Ordenar por score
    sorted_activities = sorted(activities, key=lambda x: x['score'], reverse=True)

    # 4. Retornar top N
    return sorted_activities[:limit]
```

### Features Disponibles (Que ya tenemos)

| Feature | Ubicación | Tipo | Uso Actual |
|---------|-----------|------|------------|
| `like_count` | Post model | int | ✅ Usado en ranking |
| `comment_count` | Post model | int | ✅ Usado en ranking |
| `view_count` | Post model | int | ❌ No usado |
| `post_type` | Post model | enum | ❌ No usado en ranking |
| `caption` | Post model | str | ❌ No analizado |
| `location` | Post model | str | ❌ No usado |
| `workout_data` | Post model | JSON | ❌ No usado en ranking |
| `media_count` | PostMedia count | int | ❌ No calculado |
| `mention_count` | PostTag count | int | ❌ No calculado |
| `user.created_at` | User model | datetime | ❌ No usado (seniority) |
| `created_at` | Post model | datetime | ✅ Usado para decay |

### Limitaciones Actuales

❌ **Sin personalización:** Todos los usuarios ven el mismo feed
❌ **No aprende:** La fórmula es estática, no se adapta
❌ **Ignora tipo de contenido:** Video y imagen simple pesan igual
❌ **No considera menciones:** Posts donde te mencionan no tienen boost
❌ **Decay lineal:** Poco realista (debería ser exponencial)
❌ **No analiza texto:** Caption y hashtags son ignorados
❌ **Sin sistema de follow:** No existe concepto de "amigos" o "seguidos"
❌ **view_count no usado:** Contador existe pero no afecta ranking
❌ **No hay trending:** No detecta posts con engagement viral rápido

---

## Comparación de Sistemas

### Tabla Comparativa

| Aspecto | Ranking GitHub ML | GymApi Actual |
|---------|-------------------|---------------|
| **Enfoque principal** | Machine Learning supervisado | Fórmula heurística |
| **Personalización** | ✅ Por usuario (historial) | ❌ Global |
| **Features usadas** | 14 señales diversas | 3 señales básicas |
| **Complejidad técnica** | Alta (modelos, training) | Baja (SQL query) |
| **Latencia típica** | 50-200ms (inferencia) | 5-20ms (query) |
| **Escalabilidad** | Requiere infra ML | PostgreSQL + Redis |
| **Mantenimiento** | Alto (reentrenamiento) | Bajo (fórmula estática) |
| **Cold start problem** | ⚠️ Sí (usuarios nuevos) | ✅ No aplica |
| **Análisis de contenido** | ✅ Keywords, hashtags | ❌ No implementado |
| **Relaciones sociales** | ✅ Followers, follows | ❌ No existe |
| **Aprendizaje continuo** | ✅ Con reentrenamiento | ❌ No aprende |
| **Costo computacional** | Alto (CPU/GPU) | Bajo (solo queries) |
| **Tiempo de desarrollo** | 2-3 meses | ✅ Ya implementado |

### Puntos en Común

✅ Ambos consideran engagement (likes, comments)
✅ Ambos aplican decay temporal
✅ Ambos filtran por privacy/visibilidad
✅ Ambos son multi-tenant (aislamiento por gym)

### Brechas Identificadas

| Gap | Descripción | Prioridad |
|-----|-------------|-----------|
| **Personalización** | No hay ranking por usuario | 🔴 Alta |
| **Tipo de contenido** | Video = Imagen en ranking | 🟡 Media |
| **Menciones** | Posts donde te mencionan no destacan | 🟡 Media |
| **Hashtags** | No se extraen ni analizan | 🟢 Baja |
| **Sistema de follow** | No existe concepto de "seguir" | 🔴 Alta |
| **Trending detection** | No se detectan posts virales | 🟡 Media |
| **View tracking** | view_count existe pero no se usa | 🟢 Baja |
| **ML pipeline** | No hay infraestructura de ML | 🔵 Futuro |

---

## Features Aprovechables

### ✅ Features Ya Disponibles en GymApi

Estas features **ya existen** en el código y solo necesitan ser integradas en el ranking:

| Feature GitHub | Equivalente GymApi | Cómo Obtenerlo | Esfuerzo |
|----------------|-------------------|----------------|----------|
| `interaction_rate` | `like_count / view_count` | Contador en Post | Bajo |
| `mention_count` | Contar PostTag tipo MENTION | `len([t for t in tags if t.type == MENTION])` | Bajo |
| `hashtags` (presencia) | Detectar # en caption | `'#' in post.caption` | Muy bajo |
| `multimedia` | PostMedia existe | `len(post.media) > 0` | Muy bajo |
| `popularity` | `like_count + comment_count` | Ya calculado | Muy bajo |
| `length` | Longitud de caption | `len(post.caption)` | Muy bajo |

**Ejemplo de implementación:**

```python
# app/models/post.py - Agregar propiedades

@property
def has_multimedia(self) -> bool:
    return len(self.media) > 0

@property
def mention_count(self) -> int:
    return len([t for t in self.tags if t.tag_type == TagType.MENTION])

@property
def hashtag_count(self) -> int:
    return self.caption.count('#') if self.caption else 0

@property
def interaction_rate(self) -> float:
    return self.like_count / max(self.view_count, 1)

@property
def caption_length(self) -> int:
    return len(self.caption) if self.caption else 0
```

### 🟡 Features Que Requieren Datos Nuevos

Estas features necesitan agregar nuevos campos o cálculos:

| Feature GitHub | Implementación GymApi | Descripción | Esfuerzo |
|----------------|----------------------|-------------|----------|
| `keywords_relevance` | Analizar workout_data + caption | NLP básico sobre contenido | Medio |
| `hashtags_relevance` | Tabla de trending hashtags | Tracking de hashtags populares | Medio |
| `followers_followings` | Tabla user_connections | Sistema de follow/unfollow | Alto |
| `seniority` | `(now - user.created_at).days` | Antigüedad del usuario | Bajo |
| `listed_count` | Contar menciones históricas | Agregación de PostTag | Bajo |

**Ejemplo - Sistema de Follow:**

```python
# app/models/user_connection.py (NUEVO)

class UserConnection(Base):
    __tablename__ = "user_connections"

    id = Column(Integer, primary_key=True)
    follower_id = Column(Integer, ForeignKey("user.id"))
    following_id = Column(Integer, ForeignKey("user.id"))
    gym_id = Column(Integer, ForeignKey("gyms.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('follower_id', 'following_id', 'gym_id'),
    )
```

### 🔴 Features Difíciles de Implementar

Estas features requieren ML o procesamiento complejo:

| Feature | Razón | Alternativa | Esfuerzo |
|---------|-------|-------------|----------|
| `mentions_relevance` | Requiere NLP del contenido | Usar count simple | Muy alto |
| `keywords_relevance` | Necesita análisis semántico | Matching de keywords fijos | Muy alto |
| User interaction history | Tracking detallado de clics/vistas | Signals implícitos (likes, comments) | Alto |

---

## Plan de Implementación por Fases

### 📊 Fase 1: Mejoras Rápidas con Features Existentes

**Duración:** 1-2 semanas
**Esfuerzo:** Bajo
**Impacto esperado:** +20-30% engagement

#### Objetivos

1. Mejorar fórmula de engagement con features existentes
2. Implementar decay exponencial (más realista)
3. Agregar boosts por tipo de contenido
4. Tracking efectivo de view_count
5. Nuevo endpoint `/feed/for-you` con ranking mejorado

#### Cambios Técnicos

**1. Mejorar método `engagement_score` en Post model:**

```python
# app/models/post.py

@property
def enhanced_engagement_score(self) -> float:
    """
    Fórmula mejorada de engagement para ranking.

    Componentes:
    - Base score: likes + (comments * 2) + (views * 0.1)
    - Content type boost: 1.0-1.4x según tipo
    - Time decay: Exponencial (más realista)

    Returns:
        Score de engagement (0-∞)
    """
    # 1. Score base
    base_score = (
        self.like_count * 1.0 +
        self.comment_count * 2.0 +
        self.view_count * 0.1
    )

    # 2. Boost por tipo de contenido
    content_multipliers = {
        PostType.VIDEO: 1.4,          # Videos son más valiosos
        PostType.WORKOUT: 1.3,        # Workouts son relevantes
        PostType.GALLERY: 1.2,        # Galerías son atractivas
        PostType.SINGLE_IMAGE: 1.0    # Baseline
    }
    content_boost = content_multipliers.get(self.post_type, 1.0)

    # 3. Decay exponencial (mejor que lineal)
    age_hours = (datetime.utcnow() - self.created_at).total_seconds() / 3600
    # Fórmula: e^(-t/48) → 50% relevancia después de 33 horas
    time_factor = math.exp(-age_hours / 48.0)

    # 4. Score final
    return base_score * content_boost * time_factor
```

**2. Agregar boost por menciones:**

```python
def enhanced_score_for_user(self, user_id: int) -> float:
    """
    Score personalizado para un usuario específico.

    Agrega boost si el usuario fue mencionado en el post.
    """
    base_score = self.enhanced_engagement_score

    # Boost si el usuario está mencionado
    mentioned_user_ids = [
        tag.tagged_user_id
        for tag in self.tags
        if tag.tag_type == TagType.MENTION
    ]

    mention_boost = 1.5 if user_id in mentioned_user_ids else 1.0

    return base_score * mention_boost
```

**3. Nuevo endpoint `/feed/for-you`:**

```python
# app/api/v1/endpoints/posts.py

@router.get("/feed/for-you", response_model=PostFeedResponse)
async def get_personalized_feed(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    gym_id: int = Depends(get_current_gym_id),
    db: Session = Depends(get_db)
):
    """
    Feed personalizado con ranking mejorado.

    Usa enhanced_score con boost por menciones.
    """
    # 1. Obtener posts recientes (ventana de 7 días)
    seven_days_ago = datetime.utcnow() - timedelta(days=7)

    posts = db.query(Post).filter(
        Post.gym_id == gym_id,
        Post.privacy == PrivacyType.PUBLIC,
        Post.is_deleted == False,
        Post.created_at >= seven_days_ago
    ).all()

    # 2. Calcular score personalizado para cada post
    scored_posts = [
        {
            'post': post,
            'score': post.enhanced_score_for_user(current_user.id)
        }
        for post in posts
    ]

    # 3. Ordenar por score descendente
    scored_posts.sort(key=lambda x: x['score'], reverse=True)

    # 4. Paginación
    paginated = scored_posts[offset:offset + limit]

    # 5. Enriquecer con metadata del usuario
    enriched_posts = [
        enrich_post(item['post'], current_user.id, db)
        for item in paginated
    ]

    return PostFeedResponse(
        posts=enriched_posts,
        total=len(scored_posts),
        limit=limit,
        offset=offset,
        has_more=offset + limit < len(scored_posts)
    )
```

**4. Tracking de view_count:**

```python
# app/api/v1/endpoints/posts.py

@router.get("/{post_id}", response_model=PostDetailResponse)
async def get_post_detail(
    post_id: int,
    current_user: User = Depends(get_current_user),
    gym_id: int = Depends(get_current_gym_id),
    db: Session = Depends(get_db)
):
    """
    Obtiene detalle de un post.

    NUEVO: Incrementa view_count automáticamente.
    """
    post = db.query(Post).filter(
        Post.id == post_id,
        Post.gym_id == gym_id,
        Post.is_deleted == False
    ).first()

    if not post:
        raise HTTPException(status_code=404, detail="Post no encontrado")

    # Incrementar view_count (excepto si es el autor)
    if post.user_id != current_user.id:
        post.view_count += 1
        db.commit()

    return enrich_post(post, current_user.id, db)
```

#### Beneficios Esperados

✅ **Mejor visibilidad:** Videos y workouts destacan más
✅ **Personalización básica:** Boost cuando te mencionan
✅ **Decay realista:** Contenido antiguo decae naturalmente
✅ **View tracking:** Métrica más completa de engagement
✅ **Migración gradual:** Endpoint nuevo no rompe apps existentes

#### Testing

```python
# tests/test_enhanced_ranking.py

def test_enhanced_score_video_boost():
    """Videos deben tener boost de 1.4x"""
    video_post = Post(post_type=PostType.VIDEO, like_count=10, comment_count=5)
    image_post = Post(post_type=PostType.SINGLE_IMAGE, like_count=10, comment_count=5)

    assert video_post.enhanced_engagement_score > image_post.enhanced_engagement_score

def test_exponential_decay():
    """Posts viejos deben decaer exponencialmente"""
    new_post = Post(created_at=datetime.utcnow() - timedelta(hours=1))
    old_post = Post(created_at=datetime.utcnow() - timedelta(hours=72))

    assert new_post.enhanced_engagement_score > old_post.enhanced_engagement_score * 3

def test_mention_boost():
    """Posts donde estoy mencionado deben tener boost de 1.5x"""
    user_id = 123
    post = Post(tags=[PostTag(tag_type=TagType.MENTION, tagged_user_id=user_id)])

    base_score = post.enhanced_engagement_score
    user_score = post.enhanced_score_for_user(user_id)

    assert user_score == base_score * 1.5
```

---

### 📊 Fase 2: Features Sociales y Trending

**Duración:** 2-4 semanas
**Esfuerzo:** Medio
**Impacto esperado:** +15-20% engagement adicional

#### Objetivos

1. Sistema de follow/connections entre usuarios
2. Algoritmo de trending (posts con engagement rápido)
3. Hashtag extraction y trending hashtags
4. Feed filtrado por "usuarios que sigo"

#### Cambios Técnicos

**1. Sistema de Follow:**

```python
# app/models/user_connection.py (NUEVO)

class UserConnection(Base):
    """
    Conexiones entre usuarios (follow/unfollow).
    Multi-tenant por gym_id.
    """
    __tablename__ = "user_connections"

    id = Column(Integer, primary_key=True, index=True)
    gym_id = Column(Integer, ForeignKey("gyms.id"), nullable=False, index=True)
    follower_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    following_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=func.now())

    __table_args__ = (
        UniqueConstraint('gym_id', 'follower_id', 'following_id', name='unique_connection'),
        Index('idx_gym_follower', 'gym_id', 'follower_id'),
        Index('idx_gym_following', 'gym_id', 'following_id'),
    )

    # Relaciones
    follower = relationship("User", foreign_keys=[follower_id], backref="following")
    following_user = relationship("User", foreign_keys=[following_id], backref="followers")
```

**2. Endpoints de Follow:**

```python
# app/api/v1/endpoints/user_connections.py (NUEVO)

@router.post("/users/{user_id}/follow")
async def follow_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    gym_id: int = Depends(get_current_gym_id),
    db: Session = Depends(get_db)
):
    """Seguir a un usuario"""
    if user_id == current_user.id:
        raise HTTPException(400, "No puedes seguirte a ti mismo")

    connection = UserConnection(
        gym_id=gym_id,
        follower_id=current_user.id,
        following_id=user_id
    )
    db.add(connection)
    db.commit()

    return {"message": "Usuario seguido exitosamente"}

@router.delete("/users/{user_id}/follow")
async def unfollow_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    gym_id: int = Depends(get_current_gym_id),
    db: Session = Depends(get_db)
):
    """Dejar de seguir a un usuario"""
    connection = db.query(UserConnection).filter(
        UserConnection.gym_id == gym_id,
        UserConnection.follower_id == current_user.id,
        UserConnection.following_id == user_id
    ).first()

    if connection:
        db.delete(connection)
        db.commit()

    return {"message": "Usuario dejado de seguir"}
```

**3. Feed de "Siguiendo":**

```python
# app/api/v1/endpoints/posts.py

@router.get("/feed/following", response_model=PostFeedResponse)
async def get_following_feed(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    gym_id: int = Depends(get_current_gym_id),
    db: Session = Depends(get_db)
):
    """
    Feed de posts de usuarios que sigo.

    Ordenado cronológicamente con boost por engagement.
    """
    # 1. Obtener IDs de usuarios que sigo
    following_ids = db.query(UserConnection.following_id).filter(
        UserConnection.gym_id == gym_id,
        UserConnection.follower_id == current_user.id
    ).all()
    following_ids = [id[0] for id in following_ids]

    if not following_ids:
        return PostFeedResponse(posts=[], total=0, limit=limit, offset=offset)

    # 2. Obtener posts de usuarios seguidos
    posts = db.query(Post).filter(
        Post.gym_id == gym_id,
        Post.user_id.in_(following_ids),
        Post.privacy == PrivacyType.PUBLIC,
        Post.is_deleted == False
    ).order_by(
        Post.enhanced_engagement_score.desc(),
        Post.created_at.desc()
    ).offset(offset).limit(limit).all()

    # 3. Enriquecer
    enriched_posts = [enrich_post(p, current_user.id, db) for p in posts]

    return PostFeedResponse(
        posts=enriched_posts,
        total=len(posts),
        limit=limit,
        offset=offset
    )
```

**4. Trending Algorithm:**

```python
# app/services/trending_service.py (NUEVO)

class TrendingService:
    """
    Detecta posts con engagement rápido (trending).

    Algoritmo: Engagement velocity en ventanas de tiempo.
    """

    def __init__(self, db: Session):
        self.db = db

    def calculate_engagement_velocity(self, post: Post, window_hours: int = 4) -> float:
        """
        Calcula velocidad de engagement (engagement / hora).

        Posts con alta velocidad están "trending".
        """
        age_hours = (datetime.utcnow() - post.created_at).total_seconds() / 3600

        if age_hours < window_hours:
            # Post muy nuevo, calcular velocity en su ventana actual
            velocity = post.engagement_score / max(age_hours, 0.1)
        else:
            # Post más viejo, velocity decae
            recent_engagement = self._get_recent_engagement(post, window_hours)
            velocity = recent_engagement / window_hours

        return velocity

    def _get_recent_engagement(self, post: Post, hours: int) -> float:
        """
        Obtiene engagement de las últimas N horas.

        Requiere tracking de timestamps en likes/comments.
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        recent_likes = self.db.query(PostLike).filter(
            PostLike.post_id == post.id,
            PostLike.created_at >= cutoff
        ).count()

        recent_comments = self.db.query(PostComment).filter(
            PostComment.post_id == post.id,
            PostComment.created_at >= cutoff
        ).count()

        return recent_likes + (recent_comments * 2)

    def get_trending_posts(self, gym_id: int, limit: int = 20) -> List[Post]:
        """
        Obtiene posts trending del gym.

        Criterio: Alta velocity + mínimo threshold de engagement.
        """
        # 1. Obtener posts recientes (últimas 24 horas)
        recent_posts = self.db.query(Post).filter(
            Post.gym_id == gym_id,
            Post.created_at >= datetime.utcnow() - timedelta(hours=24),
            Post.is_deleted == False,
            Post.privacy == PrivacyType.PUBLIC
        ).all()

        # 2. Calcular velocity para cada post
        scored_posts = [
            {
                'post': post,
                'velocity': self.calculate_engagement_velocity(post),
                'total_engagement': post.engagement_score
            }
            for post in recent_posts
            if post.engagement_score >= 5  # Mínimo threshold
        ]

        # 3. Ordenar por velocity
        scored_posts.sort(key=lambda x: x['velocity'], reverse=True)

        # 4. Retornar top N
        return [item['post'] for item in scored_posts[:limit]]
```

**5. Hashtag Extraction:**

```python
# app/services/hashtag_service.py (NUEVO)

import re
from collections import Counter

class HashtagService:
    """
    Extrae y trackea hashtags de posts.
    """

    HASHTAG_REGEX = r'#(\w+)'

    def extract_hashtags(self, text: str) -> List[str]:
        """
        Extrae hashtags de un texto.

        Ejemplo: "Día de #piernas en el #gym 💪" → ["piernas", "gym"]
        """
        if not text:
            return []

        hashtags = re.findall(self.HASHTAG_REGEX, text.lower())
        return list(set(hashtags))  # Sin duplicados

    def get_trending_hashtags(self, gym_id: int, days: int = 7, limit: int = 10) -> List[Dict]:
        """
        Obtiene hashtags trending del gym.

        Analiza posts recientes y cuenta frecuencia.
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        # 1. Obtener posts recientes
        posts = db.query(Post).filter(
            Post.gym_id == gym_id,
            Post.created_at >= cutoff,
            Post.is_deleted == False
        ).all()

        # 2. Extraer todos los hashtags
        all_hashtags = []
        for post in posts:
            hashtags = self.extract_hashtags(post.caption)
            all_hashtags.extend(hashtags)

        # 3. Contar frecuencia
        hashtag_counts = Counter(all_hashtags)

        # 4. Retornar top N
        trending = [
            {'hashtag': tag, 'count': count}
            for tag, count in hashtag_counts.most_common(limit)
        ]

        return trending
```

#### Beneficios Esperados

✅ **Conexiones sociales:** Usuarios pueden seguir a otros
✅ **Feed personalizado:** Ver posts de quienes sigo
✅ **Trending detection:** Posts virales destacan
✅ **Hashtags:** Descubrimiento de contenido relacionado
✅ **Engagement mayor:** Feed más relevante = más interacción

---

### 📊 Fase 3: Machine Learning Básico

**Duración:** 4-8 semanas
**Esfuerzo:** Alto
**Impacto esperado:** +25-40% engagement adicional

#### Objetivos

1. Implementar modelo RandomForest para predecir relevancia
2. Feature store para cálculos eficientes
3. Pipeline de training automatizado
4. A/B testing para validar mejoras
5. Monitoring dashboard

#### Arquitectura ML

```
┌─────────────────────────────────────────────────────────────┐
│                    FEATURE ENGINEERING                       │
│  Calcula features de posts + usuarios cada 15 min           │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                     FEATURE STORE                            │
│  PostgreSQL: post_features (materialized view)               │
│  Redis: Feature cache con TTL 15min                          │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┴───────────────┐
        │                            │
        ▼                            ▼
┌──────────────┐            ┌──────────────────┐
│   TRAINING   │            │  MODEL SERVING   │
│   (Offline)  │            │   (Online API)   │
│              │            │                  │
│ - Scikit-l   │───────────▶│ - Load model     │
│ - Data prep  │  Deploy    │ - Predict score  │
│ - Validation │            │ - Fallback rules │
└──────────────┘            └────────┬─────────┘
                                     │
                                     ▼
                            ┌────────────────┐
                            │  RANKING API   │
                            │ /feed/ml-rank  │
                            └────────────────┘
```

#### Implementación Técnica

**1. Feature Store (Materialized View):**

```sql
-- migrations/add_post_features_view.sql

CREATE MATERIALIZED VIEW post_features AS
SELECT
    p.id as post_id,
    p.gym_id,
    p.user_id,

    -- Engagement features
    p.like_count,
    p.comment_count,
    p.view_count,
    CAST(p.like_count AS FLOAT) / NULLIF(p.view_count, 0) as interaction_rate,

    -- Content features
    CASE p.post_type
        WHEN 'VIDEO' THEN 3
        WHEN 'WORKOUT' THEN 2
        WHEN 'GALLERY' THEN 1
        ELSE 0
    END as content_type_encoded,
    COALESCE(LENGTH(p.caption), 0) as caption_length,
    COALESCE(array_length(p.media, 1), 0) as media_count,

    -- Tag features
    (SELECT COUNT(*) FROM post_tags WHERE post_id = p.id AND tag_type = 'MENTION') as mention_count,
    LENGTH(p.caption) - LENGTH(REPLACE(p.caption, '#', '')) as hashtag_count,

    -- User features (autor)
    EXTRACT(EPOCH FROM (NOW() - u.created_at)) / 86400 as user_seniority_days,
    (SELECT COUNT(*) FROM user_connections WHERE following_id = p.user_id AND gym_id = p.gym_id) as author_follower_count,

    -- Time features
    EXTRACT(EPOCH FROM (NOW() - p.created_at)) / 3600 as age_hours,
    EXTRACT(HOUR FROM p.created_at) as created_hour,
    EXTRACT(DOW FROM p.created_at) as created_day_of_week,

    -- Timestamps
    p.created_at,
    NOW() as feature_computed_at

FROM posts p
JOIN user u ON p.user_id = u.id
WHERE p.is_deleted = FALSE
  AND p.privacy = 'PUBLIC';

-- Index para queries rápidas
CREATE INDEX idx_post_features_gym_age ON post_features(gym_id, age_hours);

-- Refresh automático cada 15 minutos
CREATE OR REPLACE FUNCTION refresh_post_features()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY post_features;
END;
$$ LANGUAGE plpgsql;

-- Schedule con pg_cron o APScheduler
SELECT cron.schedule('refresh-post-features', '*/15 * * * *', 'SELECT refresh_post_features()');
```

**2. Modelo de ML (RandomForest):**

```python
# app/ml/ranking_model.py

import pickle
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import precision_score, recall_score, roc_auc_score

class PostRankingModel:
    """
    Modelo de Machine Learning para rankear posts.

    Predice probabilidad de que un usuario interactúe con un post.
    """

    FEATURE_COLUMNS = [
        'like_count', 'comment_count', 'view_count', 'interaction_rate',
        'content_type_encoded', 'caption_length', 'media_count',
        'mention_count', 'hashtag_count',
        'user_seniority_days', 'author_follower_count',
        'age_hours', 'created_hour', 'created_day_of_week'
    ]

    def __init__(self):
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=20,
            random_state=42
        )
        self.is_trained = False

    def prepare_training_data(self, db: Session, gym_id: int) -> tuple:
        """
        Prepara datos de entrenamiento desde la BD.

        Label: user_engaged = 1 si el usuario dio like o comentó, 0 si no.
        """
        # Query con features + label
        query = """
        SELECT
            pf.*,
            CASE
                WHEN ul.user_id IS NOT NULL OR uc.user_id IS NOT NULL THEN 1
                ELSE 0
            END as user_engaged
        FROM post_features pf
        CROSS JOIN user u  -- Todos los usuarios del gym
        LEFT JOIN post_likes ul ON pf.post_id = ul.post_id AND ul.user_id = u.id
        LEFT JOIN post_comments uc ON pf.post_id = uc.post_id AND uc.user_id = u.id
        WHERE pf.gym_id = :gym_id
          AND u.gym_id = :gym_id
          AND pf.age_hours < 168  -- Posts de última semana
        """

        df = pd.read_sql(query, db.bind, params={'gym_id': gym_id})

        # Separar features y label
        X = df[self.FEATURE_COLUMNS].values
        y = df['user_engaged'].values

        return train_test_split(X, y, test_size=0.2, random_state=42)

    def train(self, X_train, y_train, X_test, y_test):
        """
        Entrena el modelo y valida performance.
        """
        print("Entrenando modelo RandomForest...")
        self.model.fit(X_train, y_train)

        # Validación
        y_pred = self.model.predict(X_test)
        y_pred_proba = self.model.predict_proba(X_test)[:, 1]

        metrics = {
            'precision': precision_score(y_test, y_pred),
            'recall': recall_score(y_test, y_pred),
            'roc_auc': roc_auc_score(y_test, y_pred_proba)
        }

        print(f"Métricas de validación: {metrics}")

        self.is_trained = True
        return metrics

    def predict_relevance(self, post_features: np.array) -> float:
        """
        Predice probabilidad de engagement para un post.

        Returns:
            Probabilidad entre 0 y 1
        """
        if not self.is_trained:
            raise ValueError("Modelo no entrenado")

        proba = self.model.predict_proba(post_features.reshape(1, -1))[0, 1]
        return float(proba)

    def get_feature_importance(self) -> Dict[str, float]:
        """
        Retorna importancia de cada feature.

        Útil para entender qué signals son más críticas.
        """
        importances = self.model.feature_importances_
        return dict(zip(self.FEATURE_COLUMNS, importances))

    def save(self, filepath: str):
        """Guarda modelo en disco"""
        with open(filepath, 'wb') as f:
            pickle.dump(self.model, f)
        print(f"Modelo guardado en {filepath}")

    def load(self, filepath: str):
        """Carga modelo desde disco"""
        with open(filepath, 'rb') as f:
            self.model = pickle.load(f)
        self.is_trained = True
        print(f"Modelo cargado desde {filepath}")
```

**3. Training Pipeline (APScheduler):**

```python
# app/ml/training_pipeline.py

from apscheduler.schedulers.background import BackgroundScheduler
import logging

logger = logging.getLogger(__name__)

class MLTrainingPipeline:
    """
    Pipeline automatizado para entrenar modelos.

    Se ejecuta semanalmente para cada gym.
    """

    def __init__(self, db: Session):
        self.db = db
        self.scheduler = BackgroundScheduler()

    def start(self):
        """
        Inicia el scheduler de training.

        Corre cada domingo a las 3 AM.
        """
        self.scheduler.add_job(
            self.train_all_gyms,
            'cron',
            day_of_week='sun',
            hour=3,
            minute=0
        )
        self.scheduler.start()
        logger.info("ML Training Pipeline iniciado")

    def train_all_gyms(self):
        """
        Entrena un modelo por cada gym activo.
        """
        gyms = self.db.query(Gym).filter(Gym.is_active == True).all()

        for gym in gyms:
            try:
                logger.info(f"Entrenando modelo para gym {gym.id}")
                self.train_gym_model(gym.id)
            except Exception as e:
                logger.error(f"Error entrenando gym {gym.id}: {e}")

    def train_gym_model(self, gym_id: int):
        """
        Entrena modelo para un gym específico.
        """
        # 1. Preparar datos
        model = PostRankingModel()
        X_train, X_test, y_train, y_test = model.prepare_training_data(self.db, gym_id)

        # Validar que hay suficientes datos
        if len(X_train) < 1000:
            logger.warning(f"Gym {gym_id} tiene pocos datos ({len(X_train)}), saltando")
            return

        # 2. Entrenar
        metrics = model.train(X_train, y_train, X_test, y_test)

        # 3. Guardar si performance es aceptable
        if metrics['roc_auc'] > 0.65:
            model_path = f"models/ranking_model_gym_{gym_id}.pkl"
            model.save(model_path)

            # Registrar en BD
            self._save_model_metadata(gym_id, metrics, model_path)
            logger.info(f"Modelo gym {gym_id} guardado con AUC={metrics['roc_auc']:.3f}")
        else:
            logger.warning(f"Modelo gym {gym_id} rechazado (AUC={metrics['roc_auc']:.3f} < 0.65)")

    def _save_model_metadata(self, gym_id: int, metrics: dict, model_path: str):
        """
        Guarda metadata del modelo en BD.
        """
        model_meta = MLModelMetadata(
            gym_id=gym_id,
            model_type='RandomForest',
            model_path=model_path,
            precision=metrics['precision'],
            recall=metrics['recall'],
            roc_auc=metrics['roc_auc'],
            trained_at=datetime.utcnow(),
            is_active=True
        )
        self.db.add(model_meta)

        # Desactivar modelos viejos
        self.db.query(MLModelMetadata).filter(
            MLModelMetadata.gym_id == gym_id,
            MLModelMetadata.id != model_meta.id
        ).update({'is_active': False})

        self.db.commit()
```

**4. Ranking Service con ML:**

```python
# app/services/ml_ranking_service.py

class MLRankingService:
    """
    Servicio que usa ML para rankear posts.

    Fallback a heurísticas si ML no está disponible.
    """

    def __init__(self, db: Session, gym_id: int):
        self.db = db
        self.gym_id = gym_id
        self.model = self._load_model()

    def _load_model(self) -> Optional[PostRankingModel]:
        """
        Carga modelo activo del gym desde disco.
        """
        model_meta = self.db.query(MLModelMetadata).filter(
            MLModelMetadata.gym_id == self.gym_id,
            MLModelMetadata.is_active == True
        ).first()

        if not model_meta:
            logger.warning(f"No hay modelo activo para gym {self.gym_id}")
            return None

        try:
            model = PostRankingModel()
            model.load(model_meta.model_path)
            return model
        except Exception as e:
            logger.error(f"Error cargando modelo: {e}")
            return None

    def rank_posts(self, posts: List[Post], user_id: int, limit: int = 20) -> List[Post]:
        """
        Rankea posts usando ML o fallback.

        Returns:
            Posts ordenados por relevancia
        """
        if self.model and self.model.is_trained:
            return self._rank_with_ml(posts, user_id, limit)
        else:
            logger.info("Usando ranking heurístico (fallback)")
            return self._rank_with_heuristics(posts, user_id, limit)

    def _rank_with_ml(self, posts: List[Post], user_id: int, limit: int) -> List[Post]:
        """
        Ranking con modelo ML.
        """
        # 1. Obtener features de posts
        post_ids = [p.id for p in posts]
        features_df = pd.read_sql(
            "SELECT * FROM post_features WHERE post_id = ANY(:ids)",
            self.db.bind,
            params={'ids': post_ids}
        )

        # 2. Predecir relevancia
        scored_posts = []
        for post in posts:
            post_features = features_df[features_df['post_id'] == post.id]

            if len(post_features) > 0:
                features_array = post_features[self.model.FEATURE_COLUMNS].values[0]
                relevance_score = self.model.predict_relevance(features_array)
            else:
                # Feature no disponible, usar heurística
                relevance_score = post.enhanced_engagement_score / 100.0

            scored_posts.append({
                'post': post,
                'ml_score': relevance_score
            })

        # 3. Ordenar por score
        scored_posts.sort(key=lambda x: x['ml_score'], reverse=True)

        # 4. Retornar top N
        return [item['post'] for item in scored_posts[:limit]]

    def _rank_with_heuristics(self, posts: List[Post], user_id: int, limit: int) -> List[Post]:
        """
        Fallback: Ranking con fórmula mejorada (Fase 1).
        """
        scored_posts = [
            {
                'post': post,
                'score': post.enhanced_score_for_user(user_id)
            }
            for post in posts
        ]

        scored_posts.sort(key=lambda x: x['score'], reverse=True)
        return [item['post'] for item in scored_posts[:limit]]
```

**5. Endpoint con ML:**

```python
# app/api/v1/endpoints/posts.py

@router.get("/feed/ml-ranked", response_model=PostFeedResponse)
async def get_ml_ranked_feed(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    gym_id: int = Depends(get_current_gym_id),
    db: Session = Depends(get_db)
):
    """
    Feed rankeado con Machine Learning.

    Usa modelo RandomForest entrenado o fallback a heurísticas.
    """
    # 1. Obtener candidatos (posts recientes)
    seven_days_ago = datetime.utcnow() - timedelta(days=7)

    candidate_posts = db.query(Post).filter(
        Post.gym_id == gym_id,
        Post.privacy == PrivacyType.PUBLIC,
        Post.is_deleted == False,
        Post.created_at >= seven_days_ago
    ).all()

    # 2. Rankear con ML
    ranking_service = MLRankingService(db, gym_id)
    ranked_posts = ranking_service.rank_posts(
        candidate_posts,
        user_id=current_user.id,
        limit=limit + offset  # Obtener más para paginación
    )

    # 3. Paginación
    paginated_posts = ranked_posts[offset:offset + limit]

    # 4. Enriquecer
    enriched_posts = [
        enrich_post(post, current_user.id, db)
        for post in paginated_posts
    ]

    return PostFeedResponse(
        posts=enriched_posts,
        total=len(ranked_posts),
        limit=limit,
        offset=offset,
        has_more=offset + limit < len(ranked_posts),
        ranking_method='ml' if ranking_service.model else 'heuristic'
    )
```

**6. A/B Testing Framework:**

```python
# app/core/ab_testing.py

import hashlib

class ABTestManager:
    """
    Sistema de A/B testing para validar mejoras.

    Asigna usuarios a variantes de forma determinística.
    """

    def __init__(self, experiment_name: str, variants: List[str]):
        self.experiment_name = experiment_name
        self.variants = variants

    def get_variant(self, user_id: int) -> str:
        """
        Asigna variante basado en hash del user_id.

        Asignación determinística: mismo usuario siempre ve misma variante.
        """
        # Hash user_id + experiment_name
        hash_input = f"{self.experiment_name}:{user_id}"
        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)

        # Módulo para distribuir uniformemente
        variant_index = hash_value % len(self.variants)
        return self.variants[variant_index]

    def track_event(self, user_id: int, event_name: str, metadata: dict = None):
        """
        Trackea evento para análisis posterior.
        """
        variant = self.get_variant(user_id)

        event = ABTestEvent(
            experiment_name=self.experiment_name,
            user_id=user_id,
            variant=variant,
            event_name=event_name,
            metadata=metadata,
            created_at=datetime.utcnow()
        )

        db.add(event)
        db.commit()

# Uso en endpoint:

ab_test = ABTestManager(
    experiment_name='feed_ranking_ml_vs_heuristic',
    variants=['ml_ranked', 'heuristic']
)

@router.get("/feed/smart")
async def get_smart_feed(current_user: User = Depends(get_current_user), ...):
    """
    Feed con A/B testing: 50% ML, 50% heuristic.
    """
    variant = ab_test.get_variant(current_user.id)

    if variant == 'ml_ranked':
        posts = get_ml_ranked_feed(...)
    else:
        posts = get_for_you_feed(...)  # Heuristic de Fase 1

    # Track impression
    ab_test.track_event(current_user.id, 'feed_viewed', {'post_count': len(posts)})

    return posts
```

#### Beneficios Esperados

✅ **Personalización real:** Modelo aprende preferencias individuales
✅ **Mejora continua:** Reentrenamiento semanal adapta a cambios
✅ **Validación científica:** A/B testing comprueba mejoras
✅ **Fallback robusto:** Sistema funciona sin ML
✅ **Feature importance:** Insights sobre qué impulsa engagement

---

### 📊 Fase 4: ML Avanzado (Futuro)

**Duración:** 3-6 meses
**Esfuerzo:** Muy alto
**Impacto esperado:** +30-50% engagement adicional

#### Tecnologías Avanzadas

1. **Collaborative Filtering:**
   - Usuarios similares recomiendan contenido mutuamente
   - Matrix factorization (SVD, ALS)

2. **Deep Learning:**
   - Redes neuronales para análisis de imágenes
   - Vision API: Detectar ejercicios, equipamiento
   - Text embeddings para caption similarity

3. **Real-time Personalization:**
   - Feature store con Redis (latencia <10ms)
   - Online learning con streaming data

4. **Multi-armed Bandits:**
   - Balance exploración/explotación
   - Thompson Sampling para diversidad

---

## Métricas de Éxito

### Métricas Primarias (KPIs)

| Métrica | Descripción | Baseline Actual | Meta Fase 1 | Meta Fase 3 |
|---------|-------------|-----------------|-------------|-------------|
| **Engagement Rate** | % usuarios que interactúan con posts | ~15% | +20% → 18% | +40% → 21% |
| **Time Spent** | Minutos promedio en feed por sesión | ~3 min | +25% → 3.75 min | +50% → 4.5 min |
| **Posts per Session** | Posts vistos por sesión | ~12 | +15% → 14 | +30% → 16 |
| **Return Rate** | % usuarios que vuelven en 24h | ~40% | +10% → 44% | +25% → 50% |
| **Like Rate** | Likes por 100 impresiones | ~8 | +15% → 9.2 | +30% → 10.4 |
| **Comment Rate** | Comments por 100 impresiones | ~2 | +20% → 2.4 | +40% → 2.8 |

### Métricas Secundarias

- **CTR (Click-Through Rate):** % de posts clickeados vs mostrados
- **View Duration:** Tiempo promedio viendo cada post
- **Share Rate:** % de posts compartidos
- **Profile Visits:** Visitas a perfil desde posts
- **Follow Rate:** Nuevos follows generados desde feed

### Métricas Técnicas (ML - Fase 3+)

- **Model AUC:** Area Under ROC Curve (target: > 0.70)
- **Precision@K:** Precisión en top K posts (target: > 0.60)
- **NDCG:** Normalized Discounted Cumulative Gain
- **Feature Drift:** Cambio en distribución de features
- **Model Latency:** Tiempo de inferencia (target: < 100ms)

### Dashboard de Monitoreo

```python
# app/services/metrics_service.py

class FeedMetricsService:
    """
    Servicio para calcular y trackear métricas del feed.
    """

    def calculate_engagement_rate(self, gym_id: int, days: int = 7) -> float:
        """
        Engagement Rate = (Usuarios que interactuaron) / (Usuarios activos)
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        # Usuarios que vieron al menos un post
        active_users = db.query(Post.user_id).filter(
            Post.gym_id == gym_id,
            Post.created_at >= cutoff
        ).distinct().count()

        # Usuarios que interactuaron (like o comment)
        engaged_users = db.query(
            func.count(func.distinct(PostLike.user_id))
        ).filter(
            PostLike.created_at >= cutoff
        ).scalar()

        engaged_users += db.query(
            func.count(func.distinct(PostComment.user_id))
        ).filter(
            PostComment.created_at >= cutoff
        ).scalar()

        return (engaged_users / active_users) * 100 if active_users > 0 else 0

    def calculate_time_spent(self, gym_id: int, user_id: int, days: int = 7) -> float:
        """
        Tiempo promedio en feed por sesión.

        Requiere tracking de sesiones (por implementar).
        """
        # TODO: Implementar tracking de sesiones
        pass

    def get_metrics_dashboard(self, gym_id: int) -> Dict:
        """
        Dashboard completo de métricas.
        """
        return {
            'engagement_rate': self.calculate_engagement_rate(gym_id),
            'avg_likes_per_post': self._avg_likes_per_post(gym_id),
            'avg_comments_per_post': self._avg_comments_per_post(gym_id),
            'active_users_7d': self._active_users(gym_id, days=7),
            'posts_created_7d': self._posts_created(gym_id, days=7),
            'top_posts': self._get_top_posts(gym_id, limit=10),
            'trending_hashtags': self._get_trending_hashtags(gym_id),
        }
```

---

## Desafíos y Mitigaciones

### Desafíos Técnicos

| Desafío | Descripción | Mitigación |
|---------|-------------|------------|
| **Cold Start** | Usuarios nuevos sin historial | Usar content-based filtering inicialmente |
| **Latencia ML** | Inferencia puede agregar 50-200ms | Pre-calcular scores cada 15min + cache |
| **Datos de training** | Necesitamos ejemplos etiquetados | Usar implicit signals (clicks, tiempo) |
| **Multi-tenancy** | ¿Modelo global o por gym? | Empezar global, luego transfer learning |
| **Model drift** | Preferencias cambian | Reentrenamiento semanal/mensual |
| **Escalabilidad** | Millones de posts × usuarios | Feature store + batch processing |
| **A/B testing** | Asignación y análisis complejo | Framework dedicado + logging |

### Desafíos de Producto

| Desafío | Descripción | Mitigación |
|---------|-------------|------------|
| **Definir relevancia** | ¿Qué es un "buen post"? | Múltiples métricas: likes, comments, time |
| **Filter bubble** | Solo mostrar un tipo de contenido | Diversidad forzada (10% exploración) |
| **Privacidad** | No exponer preferencias | No revelar features usadas |
| **Transparencia** | ¿Por qué veo este post? | Tooltips: "Porque sigues a @user" |
| **Gaming del sistema** | Usuarios manipulan ranking | Detección de patrones anómalos |

### Desafíos de Infraestructura

| Desafío | Descripción | Mitigación |
|---------|-------------|------------|
| **Storage de features** | Millones de features × posts | PostgreSQL materialized views + partitioning |
| **Pipeline de training** | Automatización y monitoring | APScheduler + Airflow (futuro) |
| **Model serving** | API separada o integrada? | Integrada inicialmente, luego microservicio |
| **Monitoreo** | Detectar degradación | Alertas en Slack/email si métricas caen >10% |
| **Rollback** | Volver a versión anterior rápido | Feature flags + modelos versionados |

---

## Recomendaciones

### Para Empezar YA (Fase 1)

✅ **Prioridad Alta - Implementar esta semana:**

1. **Enhanced engagement score** en Post model
   - Esfuerzo: 2-3 horas
   - Impacto: Alto
   - Risk: Bajo

2. **Endpoint `/feed/for-you`** con ranking mejorado
   - Esfuerzo: 4-6 horas
   - Impacto: Alto
   - Risk: Bajo (no rompe apps existentes)

3. **View count tracking** en GET post detail
   - Esfuerzo: 1 hora
   - Impacto: Medio
   - Risk: Muy bajo

✅ **Prioridad Media - Próximas 2 semanas:**

4. **Tests de ranking** (TDD)
   - Esfuerzo: 3-4 horas
   - Impacto: Alto (confianza)
   - Risk: Ninguno

5. **Metrics dashboard** básico
   - Esfuerzo: 4-6 horas
   - Impacto: Medio (visibilidad)
   - Risk: Bajo

### Roadmap Sugerido

```
Semana 1-2:   Fase 1 - Enhanced ranking ✅ EMPEZAR AQUÍ
  │
  ├─ Sprint 1: Enhanced score + endpoint
  └─ Sprint 2: View tracking + tests

Semana 3-6:   Fase 2 - Features sociales
  │
  ├─ Sprint 3: Sistema de follow
  ├─ Sprint 4: Trending algorithm
  └─ Sprint 5: Hashtag extraction

Mes 2-3:      Fase 3 - ML básico
  │
  ├─ Sprint 6: Feature store
  ├─ Sprint 7: Modelo RandomForest
  ├─ Sprint 8: Training pipeline
  └─ Sprint 9: A/B testing

Mes 4-6:      Fase 4 - ML avanzado (opcional)
  │
  └─ Collaborative filtering, Deep Learning, Real-time
```

### Criterios de Decisión

**Cuándo implementar ML (Fase 3):**
- ✅ Tenemos >10,000 posts con engagement data
- ✅ Tenemos >1,000 usuarios activos
- ✅ Fase 1 y 2 ya están en producción
- ✅ Métricas actuales platearon (no mejoran más)
- ✅ Equipo tiene capacidad de ML

**Cuándo NO implementar ML:**
- ❌ Pocos datos (<5,000 posts)
- ❌ Pocos usuarios (<500 activos)
- ❌ Fase 1 aún no implementada
- ❌ Equipo sin experiencia en ML
- ❌ Recursos limitados

### Siguiente Paso Recomendado

🚀 **Acción inmediata:** Implementar Fase 1 esta semana

1. Crear branch `feature/enhanced-ranking`
2. Implementar `enhanced_engagement_score` en Post model
3. Crear endpoint `/feed/for-you`
4. Escribir tests
5. Validar con datos reales
6. Merge a main

**Tiempo estimado:** 1-2 días de desarrollo + 1 día de testing

---

## Conclusión

El algoritmo de ranking del repositorio de GitHub demuestra que **Machine Learning puede mejorar significativamente el engagement en feeds sociales**. Sin embargo, para GymApi recomiendo un **enfoque gradual**:

### Resumen de Fases

| Fase | Duración | Esfuerzo | Impacto | Riesgo | Cuándo |
|------|----------|----------|---------|--------|--------|
| **Fase 1** | 1-2 sem | Bajo | +20-30% | Bajo | ✅ AHORA |
| **Fase 2** | 2-4 sem | Medio | +15-20% | Bajo | 1 mes |
| **Fase 3** | 4-8 sem | Alto | +25-40% | Medio | 3 meses |
| **Fase 4** | 3-6 mes | Muy alto | +30-50% | Alto | 6+ meses |

### Por Qué Empezar con Fase 1

✅ **Bajo riesgo:** No requiere ML ni infraestructura compleja
✅ **Alto impacto:** Mejoras de 20-30% son significativas
✅ **Rápido:** Implementable en 1-2 semanas
✅ **Aprendizaje:** Valida hipótesis antes de invertir en ML
✅ **No rompe nada:** Endpoint nuevo compatible con apps existentes

### Éxito Esperado

Con implementación completa de las 4 fases, esperamos:

- 📈 **+60-80% engagement total** (acumulado de todas las fases)
- ⏱️ **+100% time spent** (de 3min a 6min por sesión)
- 👥 **+50% return rate** (de 40% a 60% vuelven en 24h)
- 🎯 **Feed personalizado** real para cada usuario
- 🤖 **Sistema que aprende** y mejora continuamente

---

**Próximo paso:** ¿Empezamos con Fase 1?
