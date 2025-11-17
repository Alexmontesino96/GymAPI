# Plan de Implementación: Sistema de Perfilado de Usuarios y Feed Ranking

**Basado en:** `USER_PROFILING_AND_FEED_RANKING_ALGORITHM.md`
**Fecha de inicio:** 2025-11-16
**Rama:** `perfilado-de-user`
**Estado:** 🟡 En planificación

---

## Índice

1. [Visión General](#visión-general)
2. [Fase 1: Ranking Básico Heurístico](#fase-1-ranking-básico-heurístico) ⬅️ **EMPEZAMOS AQUÍ**
3. [Fase 2: Perfilado Completo de Usuario](#fase-2-perfilado-completo-de-usuario)
4. [Fase 3: Machine Learning Básico](#fase-3-machine-learning-básico)
5. [Fase 4: ML Avanzado y Optimización](#fase-4-ml-avanzado-y-optimización)
6. [Testing y Validación](#testing-y-validación)
7. [Deployment y Monitoreo](#deployment-y-monitoreo)

---

## Visión General

### Objetivo Final
Crear un sistema inteligente que personalice el feed de posts para cada usuario basándose en:
- Sus intereses fitness (categorías preferidas)
- Sus relaciones sociales (trainer, compañeros)
- Su historial de engagement (qué le gusta)
- El timing óptimo (cuándo está activo)
- La popularidad del contenido (trending)

### Métricas de Éxito

| Métrica | Baseline Actual | Meta Fase 1 | Meta Fase 2 | Meta Fase 3 | Meta Fase 4 |
|---------|----------------|-------------|-------------|-------------|-------------|
| Tiempo en feed | 3 min | 3.5 min | 4 min | 4.5 min | 5 min |
| Engagement rate | 15% | 18% | 21% | 24% | 27% |
| Like rate | 8% | 9% | 10% | 11% | 12% |
| Posts por sesión | 12 | 14 | 15 | 16 | 18 |
| Return rate (24h) | 40% | 43% | 47% | 52% | 55% |

### Stack Tecnológico
- **Backend:** FastAPI + SQLAlchemy + PostgreSQL
- **Cache:** Redis (TTL configurables)
- **ML (Fase 3+):** Scikit-learn → LightGBM
- **A/B Testing:** Custom middleware
- **Monitoreo:** Logs + métricas en DB

---

## Fase 1: Ranking Básico Heurístico

**Duración estimada:** 1-2 semanas
**Esfuerzo:** ~40 horas
**Objetivo:** Implementar ranking personalizado con 5 señales ponderadas, sin ML

### Alcance de Fase 1

Implementar endpoint `/api/v1/posts/feed/ranked` con scoring basado en:
1. **Content Affinity (25%)** - Match con intereses del usuario
2. **Social Affinity (25%)** - Relación con el autor del post
3. **Past Engagement (15%)** - Historial de interacciones
4. **Timing (15%)** - Recency + horarios activos del usuario
5. **Popularity (20%)** - Trending + engagement general

### Pasos Detallados

---

#### **Paso 1.1: Crear tabla `post_views` para tracking de deduplicación**

**Problema actual:** No tenemos forma de saber qué posts ya vio un usuario
**Solución:** Nueva tabla para tracking de vistas

**Archivos a crear/modificar:**
- `app/models/post.py` - Agregar modelo `PostView`
- `alembic/versions/XXXXX_add_post_views_table.py` - Migración

**Tareas:**
- [ ] 1.1.1 Definir modelo `PostView` en `app/models/post.py`
  ```python
  class PostView(Base):
      __tablename__ = "post_views"

      id = Column(Integer, primary_key=True)
      post_id = Column(Integer, ForeignKey("post.id"), nullable=False, index=True)
      user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
      gym_id = Column(Integer, ForeignKey("gym.id"), nullable=False, index=True)

      viewed_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
      view_duration_seconds = Column(Integer, nullable=True)  # Tiempo en vista (futuro)
      device_type = Column(String(50), nullable=True)  # iOS, Android, Web

      # Índices compuestos para queries eficientes
      __table_args__ = (
          Index('idx_post_views_user_post', 'user_id', 'post_id'),
          Index('idx_post_views_gym_user', 'gym_id', 'user_id'),
      )
  ```

- [ ] 1.1.2 Crear migración Alembic
  ```bash
  alembic revision --autogenerate -m "add post_views table for feed deduplication"
  ```

- [ ] 1.1.3 Revisar y ajustar migración generada
  - Verificar índices compuestos
  - Verificar foreign keys con `ondelete="CASCADE"`
  - Verificar timezone=True en DateTime

- [ ] 1.1.4 Aplicar migración en desarrollo
  ```bash
  alembic upgrade head
  ```

- [ ] 1.1.5 Actualizar modelo `Post` con relación
  ```python
  # En app/models/post.py
  class Post(Base):
      # ... campos existentes ...

      # Nueva relación
      views = relationship("PostView", back_populates="post", cascade="all, delete-orphan")
  ```

**Validación:**
- Ejecutar `pytest tests/models/test_post.py` (crear si no existe)
- Verificar que la tabla existe: `\d post_views` en psql
- Insertar registro de prueba y validar constraints

---

#### **Paso 1.2: Implementar función `content_affinity_score()`**

**Objetivo:** Calcular qué tan relevante es un post para un usuario basándose en categorías

**Archivos a crear/modificar:**
- `app/services/feed_ranking.py` - Nuevo servicio
- `app/repositories/feed_ranking.py` - Nuevo repositorio (queries SQL)

**Tareas:**
- [ ] 1.2.1 Crear `app/services/feed_ranking.py` con esqueleto básico
  ```python
  """
  Servicio para ranking inteligente del feed de posts.
  Implementa múltiples señales de scoring para personalización.
  """
  from typing import List, Dict, Optional
  from sqlalchemy.orm import Session
  from app.models.user import User
  from app.models.post import Post

  class FeedRankingService:
      """Servicio de ranking de feed con múltiples señales"""

      def __init__(self, db: Session):
          self.db = db

      def content_affinity_score(
          self,
          user_id: int,
          gym_id: int,
          post_id: int
      ) -> float:
          """
          Calcula content affinity (0.0 - 1.0) entre usuario y post.

          Basado en:
          - Categoría primaria del usuario (de clases asistidas)
          - Categorías del post (tags)
          - Match exacto = 1.0
          - Sin match = 0.2 (base para diversidad)
          """
          pass  # Implementar en 1.2.3
  ```

- [ ] 1.2.2 Crear `app/repositories/feed_ranking.py` para queries SQL
  ```python
  """
  Repositorio con queries SQL optimizadas para feed ranking.
  """
  from typing import Dict, List, Optional
  from sqlalchemy import text
  from sqlalchemy.orm import Session

  class FeedRankingRepository:
      """Queries SQL para componentes de ranking"""

      def __init__(self, db: Session):
          self.db = db

      def get_user_primary_category(self, user_id: int, gym_id: int) -> Optional[str]:
          """
          Obtiene la categoría fitness primaria del usuario.
          Basado en clases asistidas (últimos 30 días).
          """
          query = text("""
              SELECT c.category
              FROM class_sessions cs
              JOIN classes c ON cs.class_id = c.id
              WHERE cs.user_id = :user_id
                AND c.gym_id = :gym_id
                AND cs.created_at >= NOW() - INTERVAL '30 days'
              GROUP BY c.category
              ORDER BY COUNT(*) DESC
              LIMIT 1
          """)
          result = self.db.execute(query, {"user_id": user_id, "gym_id": gym_id})
          row = result.fetchone()
          return row[0] if row else None

      def get_post_categories(self, post_id: int) -> List[str]:
          """Obtiene categorías/tags del post"""
          query = text("""
              SELECT ARRAY_AGG(DISTINCT tag) as tags
              FROM post_tags pt
              WHERE pt.post_id = :post_id
          """)
          result = self.db.execute(query, {"post_id": post_id})
          row = result.fetchone()
          return row[0] if row and row[0] else []
  ```

- [ ] 1.2.3 Implementar lógica de `content_affinity_score()`
  ```python
  def content_affinity_score(self, user_id: int, gym_id: int, post_id: int) -> float:
      repo = FeedRankingRepository(self.db)

      # 1. Categoría primaria del usuario
      user_category = repo.get_user_primary_category(user_id, gym_id)

      # 2. Categorías del post
      post_categories = repo.get_post_categories(post_id)

      # 3. Calcular match
      if not user_category:
          return 0.5  # Sin datos, score neutral

      if user_category in post_categories:
          return 1.0  # Match exacto

      # Categorías relacionadas (futuro: usar grafo de similitud)
      related_categories = {
          "cardio": ["hiit", "running", "cycling"],
          "strength": ["powerlifting", "bodybuilding", "crossfit"],
          "flexibility": ["yoga", "pilates", "stretching"]
      }

      if user_category in related_categories:
          if any(cat in post_categories for cat in related_categories[user_category]):
              return 0.7  # Match parcial

      return 0.2  # Sin match, pero score base para diversidad
  ```

- [ ] 1.2.4 Agregar tests en `tests/services/test_feed_ranking.py`
  ```python
  import pytest
  from app.services.feed_ranking import FeedRankingService

  def test_content_affinity_exact_match(db_session, sample_user, sample_post):
      """Test: Match exacto categoría = 1.0"""
      service = FeedRankingService(db_session)
      score = service.content_affinity_score(
          user_id=sample_user.id,
          gym_id=sample_user.gym_id,
          post_id=sample_post.id
      )
      assert score == 1.0

  def test_content_affinity_no_match(db_session, sample_user, sample_post):
      """Test: Sin match = 0.2 (diversidad)"""
      # Setup: user con categoría "yoga", post con categoría "cardio"
      score = service.content_affinity_score(...)
      assert score == 0.2
  ```

**Validación:**
- Ejecutar `pytest tests/services/test_feed_ranking.py -v`
- Verificar que scores estén en rango [0.0, 1.0]
- Probar casos edge: usuario sin clases, post sin tags

---

#### **Paso 1.3: Implementar función `social_affinity_score()`**

**Objetivo:** Calcular relevancia basada en relación con el autor del post

**Archivos a modificar:**
- `app/repositories/feed_ranking.py` - Agregar queries sociales

**Tareas:**
- [ ] 1.3.1 Agregar query para detectar relación trainer-member
  ```python
  # En app/repositories/feed_ranking.py

  def get_user_relationship_type(
      self,
      user_id: int,
      author_id: int,
      gym_id: int
  ) -> Optional[str]:
      """
      Determina el tipo de relación entre usuario y autor.

      Returns:
          - "trainer" si el autor es trainer del usuario
          - "trainee" si el usuario es trainer del autor
          - "same_gym" si comparten gym
          - None si no hay relación
      """
      # 1. Verificar si author es trainer del user
      query_trainer = text("""
          SELECT 1 FROM trainer_members
          WHERE trainer_id = :author_id
            AND member_id = :user_id
            AND gym_id = :gym_id
            AND is_active = true
          LIMIT 1
      """)
      result = self.db.execute(query_trainer, {
          "author_id": author_id,
          "user_id": user_id,
          "gym_id": gym_id
      })
      if result.fetchone():
          return "trainer"

      # 2. Verificar si user es trainer del author
      query_trainee = text("""
          SELECT 1 FROM trainer_members
          WHERE trainer_id = :user_id
            AND member_id = :author_id
            AND gym_id = :gym_id
            AND is_active = true
          LIMIT 1
      """)
      result = self.db.execute(query_trainee, {
          "user_id": user_id,
          "author_id": author_id,
          "gym_id": gym_id
      })
      if result.fetchone():
          return "trainee"

      # 3. Verificar si comparten gym
      if gym_id:  # Ya sabemos que comparten gym por parámetro
          return "same_gym"

      return None
  ```

- [ ] 1.3.2 Agregar query para detectar interacciones previas
  ```python
  def get_past_interactions_count(
      self,
      user_id: int,
      author_id: int,
      days: int = 30
  ) -> int:
      """
      Cuenta interacciones previas del usuario con posts del autor.

      Incluye: likes, comentarios, shares (últimos N días)
      """
      query = text("""
          SELECT COUNT(*) as interaction_count
          FROM (
              -- Likes
              SELECT created_at FROM post_likes pl
              JOIN post p ON pl.post_id = p.id
              WHERE pl.user_id = :user_id
                AND p.user_id = :author_id
                AND pl.created_at >= NOW() - INTERVAL :days day

              UNION ALL

              -- Comentarios
              SELECT created_at FROM post_comments pc
              JOIN post p ON pc.post_id = p.id
              WHERE pc.user_id = :user_id
                AND p.user_id = :author_id
                AND pc.created_at >= NOW() - INTERVAL :days day
          ) interactions
      """)
      result = self.db.execute(query, {
          "user_id": user_id,
          "author_id": author_id,
          "days": days
      })
      row = result.fetchone()
      return row[0] if row else 0
  ```

- [ ] 1.3.3 Implementar `social_affinity_score()` en service
  ```python
  # En app/services/feed_ranking.py

  def social_affinity_score(
      self,
      user_id: int,
      author_id: int,
      gym_id: int
  ) -> float:
      """
      Calcula social affinity (0.0 - 1.0) entre usuario y autor.

      Ponderación:
      - Trainer del usuario: 1.0 (máxima relevancia)
      - Usuario entrena al autor: 0.8
      - Interacciones frecuentes (5+): 0.7
      - Interacciones ocasionales (1-4): 0.5
      - Mismo gym, sin interacción: 0.3
      - Sin relación: 0.1
      """
      if user_id == author_id:
          return 0.0  # Propio post, no rankear por social

      repo = FeedRankingRepository(self.db)

      # 1. Verificar relación directa
      relationship = repo.get_user_relationship_type(user_id, author_id, gym_id)

      if relationship == "trainer":
          return 1.0  # Trainer del usuario = máxima prioridad

      if relationship == "trainee":
          return 0.8  # Usuario es trainer del autor

      # 2. Verificar interacciones históricas
      interactions = repo.get_past_interactions_count(user_id, author_id, days=30)

      if interactions >= 5:
          return 0.7  # Alta interacción previa

      if interactions >= 1:
          return 0.5  # Interacción ocasional

      # 3. Mismo gym sin interacción
      if relationship == "same_gym":
          return 0.3

      # 4. Sin relación
      return 0.1
  ```

- [ ] 1.3.4 Agregar tests
  ```python
  def test_social_affinity_trainer_relationship(db_session):
      """Test: Trainer del usuario = 1.0"""
      # Setup: crear relación trainer-member
      service = FeedRankingService(db_session)
      score = service.social_affinity_score(
          user_id=member_id,
          author_id=trainer_id,
          gym_id=gym_id
      )
      assert score == 1.0

  def test_social_affinity_high_interaction(db_session):
      """Test: 5+ interacciones = 0.7"""
      # Setup: crear 5 likes del user a posts del author
      score = service.social_affinity_score(...)
      assert score == 0.7
  ```

**Validación:**
- Ejecutar tests
- Verificar performance de queries (< 50ms)
- Probar con usuarios sin relación

---

#### **Paso 1.4: Implementar función `past_engagement_score()`**

**Objetivo:** Ponderar posts similares a contenido con el que el usuario ha interactuado antes

**Tareas:**
- [ ] 1.4.1 Agregar query para detectar patrones de engagement
  ```python
  # En app/repositories/feed_ranking.py

  def get_user_engagement_patterns(
      self,
      user_id: int,
      gym_id: int,
      days: int = 30
  ) -> Dict[str, any]:
      """
      Analiza patrones de engagement del usuario.

      Returns:
          {
              "total_likes": int,
              "total_comments": int,
              "avg_likes_per_day": float,
              "preferred_post_types": List[str],  # text, image, video
              "preferred_categories": List[str]
          }
      """
      query = text("""
          WITH user_likes AS (
              SELECT
                  p.id as post_id,
                  p.post_type,
                  COALESCE(pt.tags, ARRAY[]::text[]) as tags,
                  pl.created_at
              FROM post_likes pl
              JOIN post p ON pl.post_id = p.id
              LEFT JOIN LATERAL (
                  SELECT ARRAY_AGG(tag) as tags
                  FROM post_tags
                  WHERE post_id = p.id
              ) pt ON true
              WHERE pl.user_id = :user_id
                AND p.gym_id = :gym_id
                AND pl.created_at >= NOW() - INTERVAL :days day
          )
          SELECT
              COUNT(*) as total_likes,
              COUNT(*) FILTER (WHERE post_type = 'text') as text_posts,
              COUNT(*) FILTER (WHERE post_type = 'image') as image_posts,
              COUNT(*) FILTER (WHERE post_type = 'video') as video_posts,
              ARRAY_AGG(DISTINCT tag) FILTER (WHERE tag IS NOT NULL) as all_tags
          FROM user_likes, UNNEST(tags) as tag
      """)
      result = self.db.execute(query, {
          "user_id": user_id,
          "gym_id": gym_id,
          "days": days
      })
      row = result.fetchone()

      if not row or row[0] == 0:  # No hay likes
          return {
              "total_likes": 0,
              "avg_likes_per_day": 0.0,
              "preferred_post_types": [],
              "preferred_categories": []
          }

      # Determinar tipo preferido
      type_counts = {
          "text": row[1] or 0,
          "image": row[2] or 0,
          "video": row[3] or 0
      }
      preferred_type = max(type_counts, key=type_counts.get)

      return {
          "total_likes": row[0],
          "avg_likes_per_day": row[0] / days,
          "preferred_post_types": [preferred_type],
          "preferred_categories": row[4] or []
      }
  ```

- [ ] 1.4.2 Implementar scoring en service
  ```python
  # En app/services/feed_ranking.py

  def past_engagement_score(
      self,
      user_id: int,
      gym_id: int,
      post_id: int,
      post_type: str,
      post_categories: List[str]
  ) -> float:
      """
      Calcula past engagement score (0.0 - 1.0).

      Basado en:
      - Match con tipo de post preferido
      - Match con categorías que le gustan
      - Frecuencia de engagement general
      """
      repo = FeedRankingRepository(self.db)
      patterns = repo.get_user_engagement_patterns(user_id, gym_id)

      # Usuario nuevo o sin engagement
      if patterns["total_likes"] == 0:
          return 0.5  # Score neutral

      score = 0.0

      # 1. Match con tipo de post preferido (40% del score)
      if post_type in patterns["preferred_post_types"]:
          score += 0.4

      # 2. Match con categorías preferidas (40% del score)
      if patterns["preferred_categories"]:
          matching_cats = set(post_categories) & set(patterns["preferred_categories"])
          category_match_ratio = len(matching_cats) / len(patterns["preferred_categories"])
          score += 0.4 * category_match_ratio

      # 3. Boost por engagement frecuente (20% del score)
      # Usuario muy activo (3+ likes/día) = boost completo
      if patterns["avg_likes_per_day"] >= 3.0:
          score += 0.2
      elif patterns["avg_likes_per_day"] >= 1.0:
          score += 0.1

      return min(score, 1.0)  # Cap en 1.0
  ```

- [ ] 1.4.3 Agregar tests
  ```python
  def test_past_engagement_new_user(db_session):
      """Test: Usuario nuevo sin likes = 0.5 (neutral)"""
      service = FeedRankingService(db_session)
      score = service.past_engagement_score(...)
      assert score == 0.5

  def test_past_engagement_perfect_match(db_session):
      """Test: Match perfecto tipo + categoría = 1.0"""
      # Setup: usuario que solo da like a posts de "yoga" tipo "image"
      # Post de prueba: tipo "image", categoría "yoga"
      score = service.past_engagement_score(...)
      assert score >= 0.8  # Esperamos alto score
  ```

**Validación:**
- Tests pasando
- Query performance < 100ms
- Verificar que score está normalizado [0.0, 1.0]

---

#### **Paso 1.5: Implementar función `timing_score()`**

**Objetivo:** Ponderar por recency + horarios activos del usuario

**Tareas:**
- [ ] 1.5.1 Agregar query para detectar horarios activos
  ```python
  # En app/repositories/feed_ranking.py

  def get_user_active_hours(
      self,
      user_id: int,
      gym_id: int,
      days: int = 30
  ) -> List[int]:
      """
      Detecta las horas del día en las que el usuario es más activo.

      Returns:
          Lista de horas (0-23) ordenadas por actividad.
          Ej: [19, 20, 18, 7, 8] significa que es más activo 19-20h
      """
      query = text("""
          WITH user_activity AS (
              -- Likes
              SELECT EXTRACT(HOUR FROM created_at) as hour
              FROM post_likes
              WHERE user_id = :user_id
                AND created_at >= NOW() - INTERVAL :days day

              UNION ALL

              -- Comentarios
              SELECT EXTRACT(HOUR FROM created_at) as hour
              FROM post_comments
              WHERE user_id = :user_id
                AND created_at >= NOW() - INTERVAL :days day

              UNION ALL

              -- Posts creados
              SELECT EXTRACT(HOUR FROM created_at) as hour
              FROM post
              WHERE user_id = :user_id
                AND gym_id = :gym_id
                AND created_at >= NOW() - INTERVAL :days day
          )
          SELECT hour, COUNT(*) as activity_count
          FROM user_activity
          GROUP BY hour
          ORDER BY activity_count DESC
          LIMIT 5
      """)
      result = self.db.execute(query, {
          "user_id": user_id,
          "gym_id": gym_id,
          "days": days
      })
      return [int(row[0]) for row in result.fetchall()]
  ```

- [ ] 1.5.2 Implementar scoring con decaimiento exponencial
  ```python
  # En app/services/feed_ranking.py

  import math
  from datetime import datetime, timezone

  def timing_score(
      self,
      user_id: int,
      gym_id: int,
      post_created_at: datetime,
      current_time: datetime = None
  ) -> float:
      """
      Calcula timing score (0.0 - 1.0).

      Componentes:
      - 70% recency (decaimiento exponencial, half-life 6h)
      - 30% match con horarios activos del usuario
      """
      if current_time is None:
          current_time = datetime.now(timezone.utc)

      # Asegurar timezone-aware
      if post_created_at.tzinfo is None:
          post_created_at = post_created_at.replace(tzinfo=timezone.utc)

      # 1. Recency score (70%)
      hours_ago = (current_time - post_created_at).total_seconds() / 3600

      # Decaimiento exponencial: score = e^(-lambda * t)
      # Half-life de 6 horas: lambda = ln(2) / 6
      decay_lambda = 0.1155  # ln(2) / 6
      recency_score = math.exp(-decay_lambda * hours_ago)

      # 2. Active hours match (30%)
      repo = FeedRankingRepository(self.db)
      active_hours = repo.get_user_active_hours(user_id, gym_id)

      post_hour = post_created_at.hour
      active_hours_score = 0.0

      if active_hours:
          if post_hour in active_hours[:2]:  # Top 2 horas más activas
              active_hours_score = 1.0
          elif post_hour in active_hours[:5]:  # Top 5
              active_hours_score = 0.5
      else:
          active_hours_score = 0.5  # Sin datos, neutral

      # Score final ponderado
      final_score = (recency_score * 0.7) + (active_hours_score * 0.3)

      return min(final_score, 1.0)
  ```

- [ ] 1.5.3 Agregar tests
  ```python
  from datetime import timedelta

  def test_timing_score_very_recent(db_session):
      """Test: Post de hace 1 hora = score alto (>0.9)"""
      service = FeedRankingService(db_session)
      now = datetime.now(timezone.utc)
      post_time = now - timedelta(hours=1)

      score = service.timing_score(
          user_id=1,
          gym_id=1,
          post_created_at=post_time,
          current_time=now
      )
      assert score > 0.9

  def test_timing_score_old_post(db_session):
      """Test: Post de hace 24 horas = score bajo (<0.3)"""
      now = datetime.now(timezone.utc)
      post_time = now - timedelta(hours=24)

      score = service.timing_score(...)
      assert score < 0.3

  def test_timing_score_active_hours_boost(db_session):
      """Test: Post en hora activa del usuario = boost adicional"""
      # Setup: usuario activo a las 19-20h
      # Post creado a las 19h hace 2 horas
      score = service.timing_score(...)
      # Debe tener boost adicional del 30%
  ```

**Validación:**
- Tests pasando
- Verificar curva de decaimiento: 1h=0.9, 6h=0.5, 12h=0.25, 24h=0.06
- Performance < 50ms

---

#### **Paso 1.6: Implementar función `popularity_score()`**

**Objetivo:** Ponderar posts trending con alto engagement

**Tareas:**
- [ ] 1.6.1 Agregar query para métricas de popularidad
  ```python
  # En app/repositories/feed_ranking.py

  def get_post_engagement_metrics(
      self,
      post_id: int,
      gym_id: int
  ) -> Dict[str, any]:
      """
      Obtiene métricas de engagement del post.

      Returns:
          {
              "likes_count": int,
              "comments_count": int,
              "views_count": int,
              "engagement_rate": float,  # (likes + comments) / views
              "velocity": float  # engagement / hours_since_creation
          }
      """
      query = text("""
          SELECT
              p.like_count as likes,
              p.comment_count as comments,
              COALESCE(v.view_count, 0) as views,
              EXTRACT(EPOCH FROM (NOW() - p.created_at)) / 3600.0 as hours_old
          FROM post p
          LEFT JOIN (
              SELECT post_id, COUNT(*) as view_count
              FROM post_views
              WHERE post_id = :post_id
              GROUP BY post_id
          ) v ON v.post_id = p.id
          WHERE p.id = :post_id
            AND p.gym_id = :gym_id
      """)
      result = self.db.execute(query, {"post_id": post_id, "gym_id": gym_id})
      row = result.fetchone()

      if not row:
          return {
              "likes_count": 0,
              "comments_count": 0,
              "views_count": 0,
              "engagement_rate": 0.0,
              "velocity": 0.0
          }

      likes = row[0] or 0
      comments = row[1] or 0
      views = row[2] or 0
      hours_old = max(row[3], 0.1)  # Evitar división por 0

      engagement_rate = (likes + comments * 2) / max(views, 1)  # Comentarios valen 2x
      velocity = (likes + comments * 2) / hours_old

      return {
          "likes_count": likes,
          "comments_count": comments,
          "views_count": views,
          "engagement_rate": engagement_rate,
          "velocity": velocity
      }
  ```

- [ ] 1.6.2 Agregar query para percentiles del gym
  ```python
  def get_gym_engagement_percentiles(
      self,
      gym_id: int,
      hours_lookback: int = 24
  ) -> Dict[str, float]:
      """
      Calcula percentiles de engagement para posts recientes del gym.

      Usado para determinar si un post es "trending" relativamente.

      Returns:
          {
              "likes_p50": float,  # Mediana
              "likes_p90": float,  # Top 10%
              "velocity_p50": float,
              "velocity_p90": float
          }
      """
      query = text("""
          WITH recent_posts AS (
              SELECT
                  p.id,
                  p.like_count as likes,
                  (p.like_count + p.comment_count * 2) /
                      GREATEST(EXTRACT(EPOCH FROM (NOW() - p.created_at)) / 3600.0, 0.1) as velocity
              FROM post p
              WHERE p.gym_id = :gym_id
                AND p.created_at >= NOW() - INTERVAL :hours_lookback hour
                AND p.deleted_at IS NULL
          )
          SELECT
              PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY likes) as likes_p50,
              PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY likes) as likes_p90,
              PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY velocity) as velocity_p50,
              PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY velocity) as velocity_p90
          FROM recent_posts
      """)
      result = self.db.execute(query, {
          "gym_id": gym_id,
          "hours_lookback": hours_lookback
      })
      row = result.fetchone()

      if not row:
          return {"likes_p50": 0, "likes_p90": 0, "velocity_p50": 0, "velocity_p90": 0}

      return {
          "likes_p50": float(row[0] or 0),
          "likes_p90": float(row[1] or 0),
          "velocity_p50": float(row[2] or 0),
          "velocity_p90": float(row[3] or 0)
      }
  ```

- [ ] 1.6.3 Implementar scoring
  ```python
  # En app/services/feed_ranking.py

  def popularity_score(
      self,
      post_id: int,
      gym_id: int
  ) -> float:
      """
      Calcula popularity score (0.0 - 1.0).

      Componentes:
      - 50% trending (velocity vs gym median)
      - 30% engagement absoluto (likes + comments)
      - 20% engagement rate (engagement / views)
      """
      repo = FeedRankingRepository(self.db)

      # Métricas del post
      metrics = repo.get_post_engagement_metrics(post_id, gym_id)

      # Percentiles del gym (últimas 24h)
      percentiles = repo.get_gym_engagement_percentiles(gym_id, hours_lookback=24)

      # 1. Trending score (50%) - basado en velocity
      velocity = metrics["velocity"]
      velocity_p90 = percentiles["velocity_p90"]

      if velocity_p90 > 0:
          trending_score = min(velocity / velocity_p90, 1.0)
      else:
          trending_score = 0.5  # Sin referencia, neutral

      # 2. Engagement absoluto (30%) - basado en likes totales
      likes = metrics["likes_count"]
      likes_p90 = percentiles["likes_p90"]

      if likes_p90 > 0:
          engagement_score = min(likes / likes_p90, 1.0)
      else:
          engagement_score = 0.0 if likes == 0 else 0.5

      # 3. Engagement rate (20%)
      engagement_rate = metrics["engagement_rate"]
      # Normalizar: rate > 0.3 (30%) es excelente
      rate_score = min(engagement_rate / 0.3, 1.0)

      # Score final ponderado
      final_score = (
          (trending_score * 0.5) +
          (engagement_score * 0.3) +
          (rate_score * 0.2)
      )

      return min(final_score, 1.0)
  ```

- [ ] 1.6.4 Agregar tests
  ```python
  def test_popularity_score_viral_post(db_session):
      """Test: Post viral (10x likes del p90) = score 1.0"""
      # Setup: crear post con likes muy altos
      score = service.popularity_score(...)
      assert score >= 0.9

  def test_popularity_score_low_engagement(db_session):
      """Test: Post sin engagement = score bajo"""
      # Post con 0 likes, 0 comments
      score = service.popularity_score(...)
      assert score <= 0.3
  ```

**Validación:**
- Tests pasando
- Performance < 100ms (cache percentiles si es necesario)

---

#### **Paso 1.7: Implementar función principal `calculate_feed_score()`**

**Objetivo:** Combinar las 5 señales con ponderación final

**Tareas:**
- [ ] 1.7.1 Implementar scoring combinado
  ```python
  # En app/services/feed_ranking.py

  from typing import NamedTuple

  class FeedScore(NamedTuple):
      """Resultado detallado del scoring"""
      post_id: int
      final_score: float
      content_affinity: float
      social_affinity: float
      past_engagement: float
      timing: float
      popularity: float

  def calculate_feed_score(
      self,
      user_id: int,
      gym_id: int,
      post: Post  # Modelo SQLAlchemy
  ) -> FeedScore:
      """
      Calcula el score final de ranking para un post.

      Ponderación:
      - Content Affinity: 25%
      - Social Affinity: 25%
      - Past Engagement: 15%
      - Timing: 15%
      - Popularity: 20%

      Returns:
          FeedScore con score final y componentes individuales
      """
      # 1. Calcular cada señal
      content = self.content_affinity_score(
          user_id=user_id,
          gym_id=gym_id,
          post_id=post.id
      )

      social = self.social_affinity_score(
          user_id=user_id,
          author_id=post.user_id,
          gym_id=gym_id
      )

      # Obtener categorías del post (asumir que Post tiene relación post_tags)
      post_categories = [tag.tag for tag in post.tags] if hasattr(post, 'tags') else []

      past_eng = self.past_engagement_score(
          user_id=user_id,
          gym_id=gym_id,
          post_id=post.id,
          post_type=post.post_type,
          post_categories=post_categories
      )

      timing = self.timing_score(
          user_id=user_id,
          gym_id=gym_id,
          post_created_at=post.created_at
      )

      popularity = self.popularity_score(
          post_id=post.id,
          gym_id=gym_id
      )

      # 2. Aplicar ponderación
      final = (
          (content * 0.25) +
          (social * 0.25) +
          (past_eng * 0.15) +
          (timing * 0.15) +
          (popularity * 0.20)
      )

      return FeedScore(
          post_id=post.id,
          final_score=final,
          content_affinity=content,
          social_affinity=social,
          past_engagement=past_eng,
          timing=timing,
          popularity=popularity
      )
  ```

- [ ] 1.7.2 Agregar método batch para múltiples posts
  ```python
  def calculate_feed_scores_batch(
      self,
      user_id: int,
      gym_id: int,
      posts: List[Post]
  ) -> List[FeedScore]:
      """
      Calcula scores para múltiples posts en batch.

      Optimización: cachea queries comunes (percentiles, user patterns)
      """
      # TODO: Agregar cache en Paso 1.9

      scores = []
      for post in posts:
          score = self.calculate_feed_score(user_id, gym_id, post)
          scores.append(score)

      # Ordenar por score final descendente
      scores.sort(key=lambda x: x.final_score, reverse=True)

      return scores
  ```

- [ ] 1.7.3 Agregar tests de integración
  ```python
  def test_calculate_feed_score_all_components(db_session, sample_user, sample_posts):
      """Test: Score final combina todas las señales correctamente"""
      service = FeedRankingService(db_session)

      # Post con todas las señales altas
      perfect_post = sample_posts[0]  # Trainer del user, categoría match, reciente
      score = service.calculate_feed_score(
          user_id=sample_user.id,
          gym_id=sample_user.gym_id,
          post=perfect_post
      )

      # Verificar componentes
      assert 0 <= score.content_affinity <= 1.0
      assert 0 <= score.social_affinity <= 1.0
      assert 0 <= score.past_engagement <= 1.0
      assert 0 <= score.timing <= 1.0
      assert 0 <= score.popularity <= 1.0

      # Score final debe ser suma ponderada
      expected = (
          score.content_affinity * 0.25 +
          score.social_affinity * 0.25 +
          score.past_engagement * 0.15 +
          score.timing * 0.15 +
          score.popularity * 0.20
      )
      assert abs(score.final_score - expected) < 0.001
  ```

**Validación:**
- Tests de integración pasando
- Verificar que ponderaciones suman 100%
- Performance total < 200ms por post

---

#### **Paso 1.8: Crear endpoint `/api/v1/posts/feed/ranked`**

**Objetivo:** Endpoint público que retorna feed personalizado rankeado

**Archivos a crear/modificar:**
- `app/api/v1/posts.py` - Agregar nuevo endpoint
- `app/schemas/post.py` - Agregar schemas de respuesta

**Tareas:**
- [ ] 1.8.1 Agregar schemas de respuesta
  ```python
  # En app/schemas/post.py

  from pydantic import BaseModel, Field
  from typing import Optional

  class FeedScoreDebug(BaseModel):
      """Información de debug del scoring (solo si debug=true)"""
      content_affinity: float = Field(..., ge=0.0, le=1.0)
      social_affinity: float = Field(..., ge=0.0, le=1.0)
      past_engagement: float = Field(..., ge=0.0, le=1.0)
      timing: float = Field(..., ge=0.0, le=1.0)
      popularity: float = Field(..., ge=0.0, le=1.0)
      final_score: float = Field(..., ge=0.0, le=1.0)

  class PostFeedRankedResponse(BaseModel):
      """Post en feed rankeado con score opcional"""
      id: int
      user_id: int
      user_name: str
      user_picture: Optional[str]
      content: str
      post_type: str
      media_urls: Optional[List[str]]
      like_count: int
      comment_count: int
      created_at: datetime

      # Score de ranking (opcional, solo si debug=true)
      score: Optional[FeedScoreDebug] = None

      class Config:
          from_attributes = True

  class FeedRankedListResponse(BaseModel):
      """Lista paginada de posts rankeados"""
      posts: List[PostFeedRankedResponse]
      total: int
      page: int
      page_size: int
      has_more: bool
  ```

- [ ] 1.8.2 Implementar endpoint
  ```python
  # En app/api/v1/posts.py

  from app.services.feed_ranking import FeedRankingService
  from app.schemas.post import FeedRankedListResponse, PostFeedRankedResponse, FeedScoreDebug

  @router.get("/feed/ranked", response_model=FeedRankedListResponse)
  async def get_ranked_feed(
      db: Session = Depends(get_db),
      current_user: User = Depends(get_current_user),
      gym_id: int = Depends(get_current_gym_id),
      page: int = Query(1, ge=1, description="Página (1-indexed)"),
      page_size: int = Query(20, ge=1, le=100, description="Posts por página"),
      debug: bool = Query(False, description="Incluir scores de debug"),
      exclude_seen: bool = Query(True, description="Excluir posts ya vistos")
  ):
      """
      Feed de posts personalizado con ranking inteligente.

      Algoritmo:
      - Content Affinity (25%): Match con intereses del usuario
      - Social Affinity (25%): Relación con autor
      - Past Engagement (15%): Historial de interacciones
      - Timing (15%): Recency + horarios activos
      - Popularity (20%): Trending + engagement

      Parámetros:
      - page: Número de página (default: 1)
      - page_size: Posts por página (max: 100, default: 20)
      - debug: Si true, incluye scores detallados (solo para testing)
      - exclude_seen: Si true, excluye posts ya vistos
      """
      # 1. Obtener posts candidatos (últimas 7 días, no borrados)
      offset = (page - 1) * page_size

      query = db.query(Post).filter(
          Post.gym_id == gym_id,
          Post.deleted_at.is_(None),
          Post.created_at >= datetime.now(timezone.utc) - timedelta(days=7)
      )

      # 2. Excluir posts ya vistos
      if exclude_seen:
          viewed_post_ids = db.query(PostView.post_id).filter(
              PostView.user_id == current_user.id,
              PostView.gym_id == gym_id
          ).subquery()

          query = query.filter(~Post.id.in_(viewed_post_ids))

      # 3. Obtener posts (tomamos más de los necesarios para rankear)
      # Ej: si pide 20, traemos 100 para rankear y quedarnos con top 20
      candidate_posts = query.order_by(Post.created_at.desc()).limit(page_size * 5).all()

      if not candidate_posts:
          return FeedRankedListResponse(
              posts=[],
              total=0,
              page=page,
              page_size=page_size,
              has_more=False
          )

      # 4. Calcular scores para todos los candidatos
      ranking_service = FeedRankingService(db)
      feed_scores = ranking_service.calculate_feed_scores_batch(
          user_id=current_user.id,
          gym_id=gym_id,
          posts=candidate_posts
      )

      # 5. Tomar top posts según paginación
      paginated_scores = feed_scores[offset:offset + page_size]

      # 6. Construir respuesta
      posts_response = []
      for feed_score in paginated_scores:
          # Obtener post original
          post = next(p for p in candidate_posts if p.id == feed_score.post_id)

          # Construir respuesta
          post_data = PostFeedRankedResponse(
              id=post.id,
              user_id=post.user_id,
              user_name=post.user.name if post.user else "Usuario",
              user_picture=post.user.picture if post.user else None,
              content=post.content,
              post_type=post.post_type,
              media_urls=post.media_urls,
              like_count=post.like_count,
              comment_count=post.comment_count,
              created_at=post.created_at,
              score=FeedScoreDebug(
                  content_affinity=feed_score.content_affinity,
                  social_affinity=feed_score.social_affinity,
                  past_engagement=feed_score.past_engagement,
                  timing=feed_score.timing,
                  popularity=feed_score.popularity,
                  final_score=feed_score.final_score
              ) if debug else None
          )

          posts_response.append(post_data)

      # 7. Registrar vistas (async en background)
      # TODO: Implementar en Paso 1.10

      return FeedRankedListResponse(
          posts=posts_response,
          total=len(feed_scores),
          page=page,
          page_size=page_size,
          has_more=(offset + page_size) < len(feed_scores)
      )
  ```

- [ ] 1.8.3 Agregar tests de endpoint
  ```python
  # En tests/api/test_posts_feed.py

  import pytest
  from httpx import AsyncClient

  @pytest.mark.asyncio
  async def test_ranked_feed_requires_auth(async_client: AsyncClient):
      """Test: Endpoint requiere autenticación"""
      response = await async_client.get("/api/v1/posts/feed/ranked")
      assert response.status_code == 401

  @pytest.mark.asyncio
  async def test_ranked_feed_returns_posts(
      async_client: AsyncClient,
      auth_headers: dict,
      sample_posts: List[Post]
  ):
      """Test: Retorna posts rankeados correctamente"""
      response = await async_client.get(
          "/api/v1/posts/feed/ranked",
          headers=auth_headers
      )
      assert response.status_code == 200

      data = response.json()
      assert "posts" in data
      assert "total" in data
      assert isinstance(data["posts"], list)

  @pytest.mark.asyncio
  async def test_ranked_feed_debug_mode(
      async_client: AsyncClient,
      auth_headers: dict
  ):
      """Test: Modo debug incluye scores detallados"""
      response = await async_client.get(
          "/api/v1/posts/feed/ranked?debug=true",
          headers=auth_headers
      )
      assert response.status_code == 200

      data = response.json()
      if data["posts"]:
          first_post = data["posts"][0]
          assert "score" in first_post
          assert "final_score" in first_post["score"]
          assert "content_affinity" in first_post["score"]

  @pytest.mark.asyncio
  async def test_ranked_feed_excludes_seen(
      async_client: AsyncClient,
      auth_headers: dict,
      db_session: Session,
      sample_user: User,
      sample_posts: List[Post]
  ):
      """Test: Excluye posts ya vistos cuando exclude_seen=true"""
      # Marcar primer post como visto
      db_session.add(PostView(
          post_id=sample_posts[0].id,
          user_id=sample_user.id,
          gym_id=sample_user.gym_id
      ))
      db_session.commit()

      response = await async_client.get(
          "/api/v1/posts/feed/ranked?exclude_seen=true",
          headers=auth_headers
      )

      data = response.json()
      post_ids = [p["id"] for p in data["posts"]]
      assert sample_posts[0].id not in post_ids
  ```

**Validación:**
- Tests de endpoint pasando
- Verificar autenticación funciona
- Verificar paginación correcta
- Verificar modo debug funciona

---

#### **Paso 1.9: Implementar cache Redis para queries pesadas**

**Objetivo:** Cachear percentiles y patrones de usuario para optimizar performance

**Archivos a modificar:**
- `app/services/feed_ranking.py` - Agregar cache
- `app/core/config.py` - Configurar TTLs

**Tareas:**
- [ ] 1.9.1 Definir TTLs de cache en config
  ```python
  # En app/core/config.py

  class Settings(BaseSettings):
      # ... campos existentes ...

      # Cache TTLs para feed ranking
      FEED_CACHE_USER_PATTERNS_TTL: int = 300  # 5 minutos
      FEED_CACHE_GYM_PERCENTILES_TTL: int = 600  # 10 minutos
      FEED_CACHE_POST_ENGAGEMENT_TTL: int = 60  # 1 minuto
  ```

- [ ] 1.9.2 Agregar helpers de cache en repository
  ```python
  # En app/repositories/feed_ranking.py

  from app.db.redis_client import get_redis
  import json

  class FeedRankingRepository:
      # ... métodos existentes ...

      def _get_cache_key(self, prefix: str, **kwargs) -> str:
          """Genera cache key consistente"""
          params = "_".join([f"{k}:{v}" for k, v in sorted(kwargs.items())])
          return f"feed:{prefix}:{params}"

      def get_user_engagement_patterns_cached(
          self,
          user_id: int,
          gym_id: int,
          days: int = 30
      ) -> Dict[str, any]:
          """Versión cacheada de get_user_engagement_patterns"""
          cache_key = self._get_cache_key(
              "user_patterns",
              user_id=user_id,
              gym_id=gym_id,
              days=days
          )

          # Intentar obtener de cache
          redis = get_redis()
          if redis:
              cached = redis.get(cache_key)
              if cached:
                  return json.loads(cached)

          # Cache miss: calcular y guardar
          patterns = self.get_user_engagement_patterns(user_id, gym_id, days)

          if redis:
              from app.core.config import get_settings
              settings = get_settings()
              redis.setex(
                  cache_key,
                  settings.FEED_CACHE_USER_PATTERNS_TTL,
                  json.dumps(patterns)
              )

          return patterns

      def get_gym_engagement_percentiles_cached(
          self,
          gym_id: int,
          hours_lookback: int = 24
      ) -> Dict[str, float]:
          """Versión cacheada de get_gym_engagement_percentiles"""
          cache_key = self._get_cache_key(
              "gym_percentiles",
              gym_id=gym_id,
              hours=hours_lookback
          )

          redis = get_redis()
          if redis:
              cached = redis.get(cache_key)
              if cached:
                  return json.loads(cached)

          percentiles = self.get_gym_engagement_percentiles(gym_id, hours_lookback)

          if redis:
              from app.core.config import get_settings
              settings = get_settings()
              redis.setex(
                  cache_key,
                  settings.FEED_CACHE_GYM_PERCENTILES_TTL,
                  json.dumps(percentiles)
              )

          return percentiles
  ```

- [ ] 1.9.3 Actualizar service para usar versiones cacheadas
  ```python
  # En app/services/feed_ranking.py

  def past_engagement_score(...):
      repo = FeedRankingRepository(self.db)

      # Usar versión cacheada
      patterns = repo.get_user_engagement_patterns_cached(user_id, gym_id)

      # ... resto del código ...

  def popularity_score(...):
      repo = FeedRankingRepository(self.db)

      # Usar versión cacheada
      percentiles = repo.get_gym_engagement_percentiles_cached(gym_id, hours_lookback=24)

      # ... resto del código ...
  ```

- [ ] 1.9.4 Agregar invalidación de cache al crear engagement
  ```python
  # En app/services/post.py (donde se crean likes/comments)

  async def create_post_like(...):
      # ... lógica existente ...

      # Invalidar cache de user patterns
      from app.db.redis_client import get_redis
      redis = get_redis()
      if redis:
          cache_key = f"feed:user_patterns:user_id:{user_id}:gym_id:{gym_id}:days:30"
          redis.delete(cache_key)

      return like
  ```

**Validación:**
- Verificar cache hit en segunda petición
- Medir mejora de performance (antes/después)
- Verificar invalidación funciona al crear like

---

#### **Paso 1.10: Implementar tracking de vistas automático**

**Objetivo:** Registrar automáticamente cuando un usuario ve posts en el feed

**Tareas:**
- [ ] 1.10.1 Crear función async para registrar vistas
  ```python
  # En app/services/post.py

  from fastapi import BackgroundTasks

  async def register_post_view(
      db: Session,
      post_id: int,
      user_id: int,
      gym_id: int,
      device_type: Optional[str] = None
  ):
      """
      Registra una vista de post.

      Se ejecuta en background para no bloquear respuesta.
      """
      try:
          # Verificar si ya existe vista (últimas 24h)
          existing_view = db.query(PostView).filter(
              PostView.post_id == post_id,
              PostView.user_id == user_id,
              PostView.viewed_at >= datetime.now(timezone.utc) - timedelta(hours=24)
          ).first()

          if existing_view:
              return  # Ya registrado

          # Crear nueva vista
          view = PostView(
              post_id=post_id,
              user_id=user_id,
              gym_id=gym_id,
              device_type=device_type
          )
          db.add(view)
          db.commit()

      except Exception as e:
          logger.error(f"Error registrando vista de post {post_id}: {e}")
          db.rollback()
  ```

- [ ] 1.10.2 Integrar en endpoint del feed
  ```python
  # En app/api/v1/posts.py

  @router.get("/feed/ranked", ...)
  async def get_ranked_feed(
      ...,
      background_tasks: BackgroundTasks,
      request: Request  # Para detectar device
  ):
      # ... código existente de ranking ...

      # Registrar vistas en background
      device_type = request.headers.get("User-Agent", "unknown")[:50]

      for post_response in posts_response:
          background_tasks.add_task(
              register_post_view,
              db=db,
              post_id=post_response.id,
              user_id=current_user.id,
              gym_id=gym_id,
              device_type=device_type
          )

      return FeedRankedListResponse(...)
  ```

**Validación:**
- Verificar que vistas se registran correctamente
- Verificar que no bloquea respuesta del endpoint
- Verificar deduplicación (no registra múltiples vistas en 24h)

---

#### **Paso 1.11: Documentación y validación final de Fase 1**

**Tareas:**
- [ ] 1.11.1 Actualizar documentación de API en Swagger
  - Verificar que endpoint aparece en `/api/v1/docs`
  - Agregar ejemplos de respuesta
  - Documentar parámetros

- [ ] 1.11.2 Crear guía de uso para frontend
  ```markdown
  # Guía: Integración de Feed Rankeado

  ## Endpoint
  `GET /api/v1/posts/feed/ranked`

  ## Parámetros
  - `page` (int): Número de página (default: 1)
  - `page_size` (int): Posts por página (max: 100, default: 20)
  - `exclude_seen` (bool): Excluir posts ya vistos (default: true)
  - `debug` (bool): Incluir scores detallados (default: false)

  ## Respuesta
  ```json
  {
    "posts": [
      {
        "id": 123,
        "user_id": 45,
        "user_name": "Juan Pérez",
        "user_picture": "https://...",
        "content": "Gran rutina de hoy! 💪",
        "post_type": "image",
        "media_urls": ["https://..."],
        "like_count": 15,
        "comment_count": 3,
        "created_at": "2025-11-16T10:30:00Z",
        "score": null  // Solo si debug=true
      }
    ],
    "total": 45,
    "page": 1,
    "page_size": 20,
    "has_more": true
  }
  ```

  ## Implementación Recomendada

  ### Infinite Scroll
  ```javascript
  let currentPage = 1;

  async function loadMorePosts() {
    const response = await fetch(
      `/api/v1/posts/feed/ranked?page=${currentPage}&page_size=20`,
      { headers: { Authorization: `Bearer ${token}` } }
    );

    const data = await response.json();

    // Agregar posts a UI
    appendPostsToFeed(data.posts);

    // Incrementar página si hay más
    if (data.has_more) {
      currentPage++;
    } else {
      hideLoadMoreButton();
    }
  }
  ```

  ### Pull to Refresh
  ```javascript
  async function refreshFeed() {
    currentPage = 1;
    clearFeed();
    await loadMorePosts();
  }
  ```
  ```

- [ ] 1.11.3 Ejecutar suite completa de tests
  ```bash
  pytest tests/services/test_feed_ranking.py -v
  pytest tests/api/test_posts_feed.py -v
  pytest tests/models/test_post.py -v
  ```

- [ ] 1.11.4 Pruebas manuales en desarrollo
  - Crear 20+ posts de prueba con variedad de:
    - Categorías (cardio, strength, yoga, etc.)
    - Autores (trainer, members, admin)
    - Engagement (0 likes, pocos likes, muchos likes)
    - Antigüedad (recientes, viejos)
  - Probar endpoint con diferentes usuarios:
    - Usuario nuevo sin historial
    - Usuario activo con muchas interacciones
    - Usuario con trainer asignado
  - Verificar que ranking hace sentido

- [ ] 1.11.5 Medición de performance
  ```python
  # Script de benchmark
  import time

  def benchmark_feed_ranking():
      start = time.time()

      # Llamar endpoint con 100 posts candidatos
      response = client.get("/api/v1/posts/feed/ranked?page_size=20")

      elapsed = time.time() - start
      print(f"Feed ranking tomó {elapsed:.2f}s")

      # Meta: < 500ms para 100 posts candidatos
      assert elapsed < 0.5, "Performance degradada"
  ```

- [ ] 1.11.6 Crear script de migración para producción
  ```bash
  # scripts/deploy_feed_ranking_phase1.sh

  #!/bin/bash
  set -e

  echo "🚀 Deploying Feed Ranking - Fase 1"

  # 1. Backup de BD
  echo "📦 Creando backup..."
  python scripts/backup_database.py

  # 2. Aplicar migración de post_views
  echo "🔄 Aplicando migraciones..."
  alembic upgrade head

  # 3. Verificar migración
  echo "✓ Verificando esquema..."
  python -c "from app.models.post import PostView; print('PostView OK')"

  # 4. Reiniciar servidor
  echo "♻️ Reiniciando servidor..."
  # (comando específico de tu hosting)

  echo "✅ Deploy completado!"
  ```

---

### Checklist Final Fase 1

Antes de dar por completada la Fase 1, verificar:

- [ ] ✅ Tabla `post_views` creada y funcionando
- [ ] ✅ 5 funciones de scoring implementadas y testeadas
- [ ] ✅ Función combinada `calculate_feed_score()` funcionando
- [ ] ✅ Endpoint `/api/v1/posts/feed/ranked` funcionando
- [ ] ✅ Cache Redis optimizando queries pesadas
- [ ] ✅ Tracking de vistas automático
- [ ] ✅ Tests unitarios pasando (cobertura > 80%)
- [ ] ✅ Tests de integración pasando
- [ ] ✅ Performance < 500ms para feed de 100 posts
- [ ] ✅ Documentación API actualizada
- [ ] ✅ Guía para frontend creada
- [ ] ✅ Script de deploy listo

---

## Fase 2: Perfilado Completo de Usuario

**Duración estimada:** 2-3 semanas
**Esfuerzo:** ~60 horas
**Objetivo:** Crear perfiles multi-dimensionales de usuarios almacenados en DB

### Alcance de Fase 2

1. Crear tabla `user_profiles` con 8 dimensiones
2. Implementar cálculo de perfiles en batch
3. Crear job programado para actualización diaria
4. Crear endpoint `/api/v1/users/{user_id}/profile` para consultar perfil
5. Mejorar scoring de Fase 1 usando datos de perfil pre-calculados

### Pasos Detallados

---

#### **Paso 2.1: Crear modelo `UserProfile`**

**Tareas:**
- [ ] 2.1.1 Definir modelo SQLAlchemy
  ```python
  # app/models/user_profile.py

  from sqlalchemy import Column, Integer, String, Float, JSON, DateTime, ForeignKey
  from sqlalchemy.orm import relationship
  from app.db.base_class import Base
  from datetime import datetime, timezone

  class UserProfile(Base):
      """
      Perfil multi-dimensional del usuario.

      Calculado periódicamente (diario) basándose en actividad,
      interacciones, asistencia a clases, etc.
      """
      __tablename__ = "user_profiles"

      id = Column(Integer, primary_key=True)
      user_id = Column(Integer, ForeignKey("user.id"), nullable=False, unique=True, index=True)
      gym_id = Column(Integer, ForeignKey("gym.id"), nullable=False, index=True)

      # 1. Fitness Interests
      primary_category = Column(String(50), nullable=True)  # cardio, strength, yoga, etc.
      category_distribution = Column(JSON, default={})  # {"cardio": 0.4, "strength": 0.6}

      # 2. Activity Level
      activity_classification = Column(String(20), nullable=True)  # very_active, active, moderate, low
      avg_sessions_per_week = Column(Float, default=0.0)
      total_sessions_30d = Column(Integer, default=0)
      consistency_score = Column(Float, default=0.0)  # 0.0 - 1.0

      # 3. Temporal Preferences
      preferred_hours = Column(JSON, default=[])  # [19, 20, 7, 8]
      preferred_days = Column(JSON, default=[])  # [1, 3, 5] (Mon, Wed, Fri)

      # 4. Goals
      primary_goal = Column(String(50), nullable=True)  # weight_loss, muscle_gain, maintenance
      nutrition_active = Column(Boolean, default=False)

      # 5. Social Profile
      social_level = Column(String(20), nullable=True)  # influencer, active, moderate, passive
      social_score = Column(Float, default=0.0)  # 0.0 - 1.0
      avg_engagement_per_post = Column(Float, default=0.0)

      # 6. Content Preferences
      preferred_post_types = Column(JSON, default=[])  # ["image", "video"]
      preferred_topics = Column(JSON, default=[])  # ["nutrition", "workouts"]

      # 7. Business Value
      business_tier = Column(String(20), nullable=True)  # vip, premium, standard, trial
      subscription_status = Column(String(20), nullable=True)  # active, cancelled, trial
      ltv_estimate = Column(Float, default=0.0)
      churn_risk = Column(Float, default=0.0)  # 0.0 - 1.0

      # 8. Aggregate Scores
      activity_score = Column(Float, default=0.0)  # 0.0 - 1.0
      social_engagement_score = Column(Float, default=0.0)  # 0.0 - 1.0
      commitment_score = Column(Float, default=0.0)  # 0.0 - 1.0

      # Metadata
      last_calculated_at = Column(DateTime(timezone=True), nullable=True)
      calculation_version = Column(String(10), default="1.0")

      # Relaciones
      user = relationship("User", back_populates="profile")

      def to_dict(self) -> dict:
          """Serializa perfil a dict"""
          return {
              "user_id": self.user_id,
              "gym_id": self.gym_id,
              "fitness_interests": {
                  "primary_category": self.primary_category,
                  "distribution": self.category_distribution
              },
              "activity_level": {
                  "classification": self.activity_classification,
                  "sessions_per_week": self.avg_sessions_per_week,
                  "total_sessions_30d": self.total_sessions_30d,
                  "consistency": self.consistency_score
              },
              "temporal_preferences": {
                  "hours": self.preferred_hours,
                  "days": self.preferred_days
              },
              "goals": {
                  "primary": self.primary_goal,
                  "nutrition_active": self.nutrition_active
              },
              "social_profile": {
                  "level": self.social_level,
                  "score": self.social_score,
                  "avg_engagement": self.avg_engagement_per_post
              },
              "content_preferences": {
                  "post_types": self.preferred_post_types,
                  "topics": self.preferred_topics
              },
              "business_value": {
                  "tier": self.business_tier,
                  "subscription": self.subscription_status,
                  "ltv": self.ltv_estimate,
                  "churn_risk": self.churn_risk
              },
              "scores": {
                  "activity": self.activity_score,
                  "social": self.social_engagement_score,
                  "commitment": self.commitment_score
              },
              "metadata": {
                  "last_calculated": self.last_calculated_at,
                  "version": self.calculation_version
              }
          }
  ```

- [ ] 2.1.2 Actualizar modelo User con relación
  ```python
  # En app/models/user.py

  class User(Base):
      # ... campos existentes ...

      # Nueva relación
      profile = relationship("UserProfile", back_populates="user", uselist=False)
  ```

- [ ] 2.1.3 Crear migración
  ```bash
  alembic revision --autogenerate -m "add user_profiles table"
  ```

- [ ] 2.1.4 Aplicar migración
  ```bash
  alembic upgrade head
  ```

---

#### **Paso 2.2: Implementar servicio de cálculo de perfiles**

**Tareas:**
- [ ] 2.2.1 Crear `app/services/user_profiling.py`
  ```python
  """
  Servicio para calcular perfiles multi-dimensionales de usuarios.

  Basado en:
  - Clases asistidas (categorías, frecuencia)
  - Interacciones sociales (posts, likes, comentarios)
  - Objetivos declarados
  - Suscripción y facturación
  """

  from typing import Dict, List, Optional
  from sqlalchemy.orm import Session
  from sqlalchemy import text, func
  from datetime import datetime, timedelta, timezone
  from app.models.user_profile import UserProfile
  from app.models.user import User
  import logging

  logger = logging.getLogger(__name__)

  class UserProfilingService:
      """Servicio para calcular y actualizar perfiles de usuario"""

      VERSION = "1.0"

      def __init__(self, db: Session):
          self.db = db

      def calculate_profile(self, user_id: int, gym_id: int) -> UserProfile:
          """
          Calcula perfil completo de un usuario.

          Returns:
              UserProfile calculado (no guardado en DB aún)
          """
          logger.info(f"Calculando perfil para user_id={user_id}, gym_id={gym_id}")

          # 1. Fitness Interests
          fitness_interests = self._calculate_fitness_interests(user_id, gym_id)

          # 2. Activity Level
          activity_level = self._calculate_activity_level(user_id, gym_id)

          # 3. Temporal Preferences
          temporal_prefs = self._calculate_temporal_preferences(user_id, gym_id)

          # 4. Goals
          goals = self._calculate_goals(user_id, gym_id)

          # 5. Social Profile
          social = self._calculate_social_profile(user_id, gym_id)

          # 6. Content Preferences
          content = self._calculate_content_preferences(user_id, gym_id)

          # 7. Business Value
          business = self._calculate_business_value(user_id, gym_id)

          # 8. Aggregate Scores
          scores = self._calculate_aggregate_scores(
              activity_level, social, business
          )

          # Crear o actualizar perfil
          profile = self.db.query(UserProfile).filter(
              UserProfile.user_id == user_id,
              UserProfile.gym_id == gym_id
          ).first()

          if not profile:
              profile = UserProfile(user_id=user_id, gym_id=gym_id)

          # Actualizar todos los campos
          profile.primary_category = fitness_interests["primary"]
          profile.category_distribution = fitness_interests["distribution"]

          profile.activity_classification = activity_level["classification"]
          profile.avg_sessions_per_week = activity_level["sessions_per_week"]
          profile.total_sessions_30d = activity_level["total_sessions_30d"]
          profile.consistency_score = activity_level["consistency"]

          profile.preferred_hours = temporal_prefs["hours"]
          profile.preferred_days = temporal_prefs["days"]

          profile.primary_goal = goals["primary"]
          profile.nutrition_active = goals["nutrition_active"]

          profile.social_level = social["level"]
          profile.social_score = social["score"]
          profile.avg_engagement_per_post = social["avg_engagement"]

          profile.preferred_post_types = content["post_types"]
          profile.preferred_topics = content["topics"]

          profile.business_tier = business["tier"]
          profile.subscription_status = business["subscription"]
          profile.ltv_estimate = business["ltv"]
          profile.churn_risk = business["churn_risk"]

          profile.activity_score = scores["activity"]
          profile.social_engagement_score = scores["social"]
          profile.commitment_score = scores["commitment"]

          profile.last_calculated_at = datetime.now(timezone.utc)
          profile.calculation_version = self.VERSION

          return profile

      # Implementar métodos auxiliares en pasos siguientes...
  ```

- [ ] 2.2.2 Implementar `_calculate_fitness_interests()`
  ```python
  def _calculate_fitness_interests(
      self,
      user_id: int,
      gym_id: int
  ) -> Dict[str, any]:
      """
      Calcula intereses fitness basándose en clases asistidas.

      Returns:
          {
              "primary": str,  # Categoría principal
              "distribution": dict  # {"cardio": 0.4, "strength": 0.6}
          }
      """
      query = text("""
          SELECT
              c.category,
              COUNT(*) as session_count
          FROM class_sessions cs
          JOIN classes c ON cs.class_id = c.id
          WHERE cs.user_id = :user_id
            AND c.gym_id = :gym_id
            AND cs.created_at >= NOW() - INTERVAL '90 days'
          GROUP BY c.category
          ORDER BY session_count DESC
      """)

      result = self.db.execute(query, {"user_id": user_id, "gym_id": gym_id})
      rows = result.fetchall()

      if not rows:
          return {"primary": None, "distribution": {}}

      # Calcular distribución
      total = sum(row[1] for row in rows)
      distribution = {
          row[0]: round(row[1] / total, 2)
          for row in rows
      }

      primary = rows[0][0]  # Categoría más frecuente

      return {
          "primary": primary,
          "distribution": distribution
      }
  ```

- [ ] 2.2.3 Implementar `_calculate_activity_level()`
  ```python
  def _calculate_activity_level(
      self,
      user_id: int,
      gym_id: int
  ) -> Dict[str, any]:
      """
      Calcula nivel de actividad del usuario.

      Returns:
          {
              "classification": str,  # very_active, active, moderate, low
              "sessions_per_week": float,
              "total_sessions_30d": int,
              "consistency": float  # 0.0 - 1.0
          }
      """
      # Total sesiones últimos 30 días
      query_total = text("""
          SELECT COUNT(*) as total
          FROM class_sessions cs
          JOIN classes c ON cs.class_id = c.id
          WHERE cs.user_id = :user_id
            AND c.gym_id = :gym_id
            AND cs.created_at >= NOW() - INTERVAL '30 days'
      """)
      result = self.db.execute(query_total, {"user_id": user_id, "gym_id": gym_id})
      total_30d = result.scalar() or 0

      # Promedio por semana
      sessions_per_week = total_30d / 4.3  # 4.3 semanas en 30 días

      # Clasificación
      if sessions_per_week >= 5:
          classification = "very_active"
      elif sessions_per_week >= 3:
          classification = "active"
      elif sessions_per_week >= 1:
          classification = "moderate"
      else:
          classification = "low"

      # Consistency: varianza semanal (bajo = consistente)
      query_consistency = text("""
          WITH weekly_counts AS (
              SELECT
                  DATE_TRUNC('week', cs.created_at) as week,
                  COUNT(*) as sessions
              FROM class_sessions cs
              JOIN classes c ON cs.class_id = c.id
              WHERE cs.user_id = :user_id
                AND c.gym_id = :gym_id
                AND cs.created_at >= NOW() - INTERVAL '90 days'
              GROUP BY week
          )
          SELECT
              AVG(sessions) as avg_sessions,
              STDDEV(sessions) as stddev_sessions
          FROM weekly_counts
      """)
      result = self.db.execute(query_consistency, {"user_id": user_id, "gym_id": gym_id})
      row = result.fetchone()

      consistency_score = 0.5  # Default
      if row and row[0]:
          avg = row[0]
          stddev = row[1] or 0
          # Consistency = 1 - (stddev / avg), normalizado
          if avg > 0:
              consistency_score = max(0, 1 - (stddev / avg))

      return {
          "classification": classification,
          "sessions_per_week": round(sessions_per_week, 1),
          "total_sessions_30d": total_30d,
          "consistency": round(consistency_score, 2)
      }
  ```

- [ ] 2.2.4 Implementar resto de métodos de cálculo
  - `_calculate_temporal_preferences()` - Horarios preferidos
  - `_calculate_goals()` - Objetivos del usuario
  - `_calculate_social_profile()` - Nivel social
  - `_calculate_content_preferences()` - Tipos de contenido
  - `_calculate_business_value()` - Tier de suscripción
  - `_calculate_aggregate_scores()` - Scores combinados

*(Detalles completos en siguiente paso para no sobrecargar este paso)*

---

#### **Paso 2.3: Implementar cálculo batch de perfiles**

**Tareas:**
- [ ] 2.3.1 Crear script `scripts/calculate_user_profiles.py`
  ```python
  """
  Script para calcular perfiles de usuarios en batch.

  Uso:
      python scripts/calculate_user_profiles.py [--gym-id GYM_ID] [--dry-run]
  """

  import sys
  from pathlib import Path
  sys.path.insert(0, str(Path(__file__).parent.parent))

  import argparse
  from sqlalchemy import select
  from app.db.session import SessionLocal
  from app.models.user import User
  from app.services.user_profiling import UserProfilingService
  import logging

  logging.basicConfig(level=logging.INFO)
  logger = logging.getLogger(__name__)

  def calculate_profiles(gym_id: int = None, dry_run: bool = False):
      """Calcula perfiles para todos los usuarios (o de un gym específico)"""
      db = SessionLocal()

      try:
          # Obtener usuarios
          query = select(User).where(User.is_active == True)
          if gym_id:
              query = query.join(User.user_gyms).where(UserGym.gym_id == gym_id)

          users = db.execute(query).scalars().all()
          logger.info(f"Calculando perfiles para {len(users)} usuarios")

          service = UserProfilingService(db)

          for idx, user in enumerate(users, 1):
              logger.info(f"[{idx}/{len(users)}] Procesando user_id={user.id}")

              # Calcular perfil
              profile = service.calculate_profile(user.id, user.gym_id)

              if not dry_run:
                  db.add(profile)
                  if idx % 100 == 0:
                      db.commit()  # Commit cada 100 usuarios

              logger.info(f"  ✓ Categoría: {profile.primary_category}, "
                        f"Actividad: {profile.activity_classification}")

          if not dry_run:
              db.commit()
              logger.info(f"✅ Perfiles guardados: {len(users)}")
          else:
              logger.info(f"🔍 DRY-RUN: {len(users)} perfiles calculados (no guardados)")

      finally:
          db.close()

  if __name__ == "__main__":
      parser = argparse.ArgumentParser()
      parser.add_argument("--gym-id", type=int, help="Calcular solo para un gym")
      parser.add_argument("--dry-run", action="store_true", help="No guardar en DB")

      args = parser.parse_args()
      calculate_profiles(gym_id=args.gym_id, dry_run=args.dry_run)
  ```

---

#### **Paso 2.4: Crear job programado para actualización diaria**

**Tareas:**
- [ ] 2.4.1 Agregar job en APScheduler
  ```python
  # En app/core/scheduler.py (o donde se configuran jobs)

  from app.services.user_profiling import UserProfilingService

  def update_user_profiles_job():
      """Job programado para actualizar perfiles de usuarios"""
      from app.db.session import SessionLocal

      db = SessionLocal()
      try:
          logger.info("Iniciando actualización de perfiles de usuarios")

          # Actualizar perfiles modificados hace más de 24h
          from sqlalchemy import select, or_
          from app.models.user_profile import UserProfile
          from datetime import timedelta

          cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

          query = select(UserProfile).where(
              or_(
                  UserProfile.last_calculated_at < cutoff,
                  UserProfile.last_calculated_at.is_(None)
              )
          )

          profiles_to_update = db.execute(query).scalars().all()

          service = UserProfilingService(db)

          for profile in profiles_to_update:
              updated_profile = service.calculate_profile(
                  profile.user_id,
                  profile.gym_id
              )
              db.add(updated_profile)

          db.commit()
          logger.info(f"✅ {len(profiles_to_update)} perfiles actualizados")

      except Exception as e:
          logger.error(f"Error en update_user_profiles_job: {e}", exc_info=True)
          db.rollback()
      finally:
          db.close()

  # Registrar job (ejecutar diariamente a las 3am)
  scheduler.add_job(
      update_user_profiles_job,
      trigger="cron",
      hour=3,
      minute=0,
      id="update_user_profiles",
      replace_existing=True
  )
  ```

---

#### **Paso 2.5: Crear endpoint de consulta de perfil**

**Tareas:**
- [ ] 2.5.1 Crear endpoint en `app/api/v1/users.py`
  ```python
  @router.get("/{user_id}/profile", response_model=UserProfileResponse)
  async def get_user_profile(
      user_id: int,
      db: Session = Depends(get_db),
      current_user: User = Depends(get_current_user),
      gym_id: int = Depends(get_current_gym_id)
  ):
      """
      Obtiene el perfil multi-dimensional de un usuario.

      Solo accesible para:
      - El propio usuario
      - Admins/trainers del gym
      """
      # Verificar permisos
      if current_user.id != user_id:
          if not has_permission(current_user, "view_member_profiles"):
              raise HTTPException(status_code=403, detail="Sin permisos")

      # Obtener perfil
      profile = db.query(UserProfile).filter(
          UserProfile.user_id == user_id,
          UserProfile.gym_id == gym_id
      ).first()

      if not profile:
          # Calcular perfil on-demand si no existe
          from app.services.user_profiling import UserProfilingService
          service = UserProfilingService(db)
          profile = service.calculate_profile(user_id, gym_id)
          db.add(profile)
          db.commit()

      return profile.to_dict()
  ```

---

#### **Paso 2.6: Optimizar ranking de Fase 1 usando perfiles**

**Tareas:**
- [ ] 2.6.1 Actualizar `content_affinity_score()` para usar perfil
  ```python
  # En app/services/feed_ranking.py

  def content_affinity_score(self, user_id: int, gym_id: int, post_id: int) -> float:
      # Obtener perfil del usuario
      profile = self.db.query(UserProfile).filter(
          UserProfile.user_id == user_id,
          UserProfile.gym_id == gym_id
      ).first()

      if not profile or not profile.primary_category:
          # Fallback a método original
          return self._content_affinity_score_legacy(user_id, gym_id, post_id)

      # Usar categoría del perfil (pre-calculado, más rápido)
      post_categories = self._get_post_categories(post_id)

      if profile.primary_category in post_categories:
          return 1.0

      # Check categorías secundarias con distribución
      for category, weight in profile.category_distribution.items():
          if category in post_categories and weight > 0.2:
              return 0.7

      return 0.2
  ```

---

### Checklist Final Fase 2

- [ ] ✅ Modelo `UserProfile` creado y migrado
- [ ] ✅ Servicio de cálculo implementado (8 dimensiones)
- [ ] ✅ Script batch funcionando
- [ ] ✅ Job programado configurado
- [ ] ✅ Endpoint de consulta funcionando
- [ ] ✅ Optimización de ranking integrada
- [ ] ✅ Tests de perfilado pasando
- [ ] ✅ Documentación actualizada

---

## Fase 3: Machine Learning Básico

**Duración estimada:** 1-2 meses
**Esfuerzo:** ~80 horas
**Objetivo:** Implementar modelo ML para predecir engagement

*(Pasos detallados de Fase 3 en siguiente sección...)*

---

## Fase 4: ML Avanzado y Optimización

**Duración estimada:** 3-6 meses
**Esfuerzo:** ~120 horas
**Objetivo:** Modelo avanzado con LightGBM, A/B testing, reentrenamiento automático

*(Pasos detallados de Fase 4 en siguiente sección...)*

---

## Testing y Validación

### Estrategia de Testing

1. **Tests Unitarios** (coverage > 80%)
   - Cada función de scoring aislada
   - Casos edge (usuarios nuevos, sin datos)
   - Normalización de scores

2. **Tests de Integración**
   - Endpoint completo con DB real
   - Cache Redis funcionando
   - Background tasks ejecutándose

3. **Tests de Performance**
   - Benchmark de latencia (< 500ms)
   - Benchmark de throughput (queries/segundo)
   - Test de carga con 1000+ posts

4. **Tests A/B** (Fase 1+)
   - Métrica: CTR (click-through rate)
   - Métrica: Time in feed
   - Métrica: Engagement rate
   - Duración mínima: 2 semanas
   - Sample size: 1000+ usuarios

### Scripts de Testing

```bash
# Tests unitarios
pytest tests/services/test_feed_ranking.py -v

# Tests de integración
pytest tests/api/test_posts_feed.py -v

# Performance
pytest tests/performance/test_feed_performance.py -v

# Coverage
pytest --cov=app/services/feed_ranking --cov-report=html
```

---

## Deployment y Monitoreo

### Checklist de Deploy

- [ ] Backup de BD antes de migración
- [ ] Aplicar migraciones en staging
- [ ] Validar migraciones con datos de producción clonados
- [ ] Deploy a producción con feature flag
- [ ] Activar feature flag para 10% de usuarios (canary)
- [ ] Monitorear métricas por 24h
- [ ] Incrementar a 50% si métricas OK
- [ ] Full rollout a 100%

### Métricas a Monitorear

1. **Performance**
   - Latencia p50, p95, p99 del endpoint
   - Cache hit rate
   - DB query time

2. **Engagement**
   - CTR en feed
   - Time in feed (promedio)
   - Likes per session
   - Comments per session
   - Return rate (24h, 7d)

3. **Errores**
   - Error rate del endpoint
   - Fallos en cálculo de scores
   - Timeouts de cache

### Dashboard de Monitoreo

Crear dashboard con:
- Gráfica de latencia en tiempo real
- Gráfica de engagement rate (comparado con baseline)
- Tabla de top posts por score
- Logs de errores en cálculo de perfiles

---

## Resumen de Entregables por Fase

### Fase 1 (1-2 semanas)
- ✅ Tabla `post_views`
- ✅ 5 funciones de scoring
- ✅ Endpoint `/feed/ranked`
- ✅ Cache Redis
- ✅ Tests + documentación

### Fase 2 (2-3 semanas)
- ✅ Tabla `user_profiles`
- ✅ Servicio de perfilado
- ✅ Job programado
- ✅ Endpoint de consulta
- ✅ Optimización de Fase 1

### Fase 3 (1-2 meses)
- ✅ Feature engineering
- ✅ Modelo RandomForest
- ✅ Pipeline de entrenamiento
- ✅ Endpoint ML-powered
- ✅ A/B testing framework

### Fase 4 (3-6 meses)
- ✅ Modelo LightGBM
- ✅ Reentrenamiento automático
- ✅ Feature store
- ✅ Optimización avanzada
- ✅ Monitoreo completo

---

## Anexo: Comandos Útiles

```bash
# Desarrollo
python app_wrapper.py  # Iniciar servidor
pytest -v  # Ejecutar tests

# Migraciones
alembic revision --autogenerate -m "descripción"
alembic upgrade head
alembic downgrade -1

# Perfilado
python scripts/calculate_user_profiles.py --gym-id 1 --dry-run
python scripts/calculate_user_profiles.py  # Todos los gyms

# Cache
redis-cli FLUSHDB  # Limpiar cache Redis
redis-cli KEYS "feed:*"  # Ver keys de feed

# Monitoring
tail -f logs/app.log | grep "feed_ranking"
```

---

**Última actualización:** 2025-11-16
**Versión:** 1.0
**Autor:** GymApi Team
