# Algoritmo de Perfilado de Usuarios y Ranking de Feed

**Fecha:** 2025-11-16
**Versión:** 1.0
**Autor:** Análisis técnico GymApi

---

## Índice

1. [Resumen Ejecutivo](#resumen-ejecutivo)
2. [Inventario Completo de Datos](#inventario-completo-de-datos)
3. [Algoritmo de Perfil de Usuario](#algoritmo-de-perfil-de-usuario)
4. [Algoritmo de Ranking de Feed](#algoritmo-de-ranking-de-feed)
5. [Features para Machine Learning](#features-para-machine-learning)
6. [Implementación Técnica](#implementación-técnica)
7. [Gaps y Oportunidades](#gaps-y-oportunidades)
8. [Roadmap de Implementación](#roadmap-de-implementación)
9. [Anexos](#anexos)

---

## Resumen Ejecutivo

### Objetivo

Crear un sistema inteligente de perfilado de usuarios y ranking de contenido que:

1. **Perfila cada usuario** basándose en su actividad, preferencias y comportamiento
2. **Rankea el feed de posts** mostrando contenido relevante y personalizado
3. **Maximiza el engagement** aumentando tiempo en app e interacciones
4. **Aprende continuamente** adaptándose a cambios en comportamiento

### Estado Actual

**Datos disponibles:** ✅ **Excelente cobertura**
- Actividad física (clases, asistencia, ejercicios)
- Salud y progreso (peso, grasa, músculo)
- Social (posts, stories, likes, comentarios)
- Nutrición (planes, comidas)
- Facturación (suscripciones)

**Algoritmo de ranking actual:** ⚠️ **Muy básico**
```python
score = (likes * 1.0) + (comments * 2.0) - (age_hours * 0.1)
```
- Sin personalización
- Solo 3 señales
- No considera relaciones sociales
- No aprende

### Oportunidad

Implementando los algoritmos propuestos en este documento:

| Métrica | Actual | Objetivo | Mejora |
|---------|--------|----------|--------|
| Tiempo en feed | 3 min/sesión | 5 min/sesión | +67% |
| Engagement rate | 15% | 25% | +67% |
| Posts por sesión | 12 | 18 | +50% |
| Return rate (24h) | 40% | 55% | +37% |
| Like rate | 8% | 12% | +50% |

---

## Inventario Completo de Datos

### 1. Perfil de Usuario Básico

**Tabla:** `user`

| Campo | Tipo | Insight |
|-------|------|---------|
| `birth_date` | date | Edad → segmentación demográfica |
| `height` | int | Contexto físico |
| `weight` | int | Objetivos inferidos |
| `goals` | JSON | Objetivos declarados explícitamente |
| `health_conditions` | JSON | Filtrado de contenido apropiado |
| `bio` | text | Intereses (extracción NLP) |
| `created_at` | timestamp | Antigüedad en plataforma |
| `role` | enum | Influencer (trainer/admin) vs miembro |

**Volumen:** 1 registro por usuario
**Granularidad:** Estático (actualización manual)

---

### 2. Relación Usuario-Gimnasio

**Tabla:** `user_gyms`

| Campo | Tipo | Insight |
|-------|------|---------|
| `created_at` | timestamp | Antigüedad en el gym |
| `is_active` | boolean | Usuario activo vs inactivo |
| `role` | enum | OWNER/ADMIN/TRAINER/MEMBER |
| `total_app_opens` | int | Engagement total |
| `monthly_app_opens` | int | Engagement reciente |
| `last_app_access` | timestamp | Días desde última actividad |
| `membership_type` | string | free/paid/trial → valor del usuario |
| `membership_expires_at` | timestamp | Riesgo de churn |

**Volumen:** 1-3 registros por usuario
**Granularidad:** Multi-tenant por gym

**Query ejemplo - Nivel de actividad:**
```sql
SELECT
    u.id,
    ug.monthly_app_opens,
    DATE_PART('day', NOW() - ug.last_app_access) as days_inactive,
    CASE
        WHEN ug.monthly_app_opens >= 40 THEN 'highly_active'
        WHEN ug.monthly_app_opens >= 15 THEN 'moderately_active'
        WHEN ug.monthly_app_opens >= 5 THEN 'lightly_active'
        ELSE 'inactive'
    END as activity_level
FROM user u
JOIN user_gyms ug ON ug.user_id = u.id
WHERE ug.gym_id = :gym_id AND ug.is_active = true;
```

---

### 3. Actividad Física

#### 3.1 Participación en Clases

**Tablas:** `class_participation` + `class_session` + `class`

| Campo | Tipo | Insight |
|-------|------|---------|
| `status` | enum | ATTENDED/NO_SHOW → consistencia |
| `attendance_time` | timestamp | Horarios preferidos |
| `session.start_time` | timestamp | Hora del día preferida |
| `session.trainer_id` | int | Instructor favorito |
| `class.category_enum` | enum | Tipo de ejercicio (cardio, fuerza, yoga) |
| `class.difficulty_level` | enum | Nivel fitness del usuario |
| `class.duration` | int | Duración preferida de entrenamientos |

**Volumen:** 8-20 registros/mes por usuario activo
**Granularidad:** Por clase asistida

**Query ejemplo - Preferencias de entrenamiento:**
```sql
WITH class_stats AS (
    SELECT
        cp.member_id,
        c.category_enum,
        c.difficulty_level,
        EXTRACT(HOUR FROM cs.start_time AT TIME ZONE g.timezone) as hour_local,
        COUNT(*) as count
    FROM class_participation cp
    JOIN class_session cs ON cs.id = cp.session_id
    JOIN class c ON c.id = cs.class_id
    JOIN gyms g ON g.id = cp.gym_id
    WHERE cp.status = 'ATTENDED'
      AND cp.gym_id = :gym_id
      AND cp.attendance_time >= NOW() - INTERVAL '90 days'
    GROUP BY cp.member_id, c.category_enum, c.difficulty_level, hour_local
)
SELECT
    member_id,
    -- Categoría favorita
    MODE() WITHIN GROUP (ORDER BY category_enum) as favorite_category,
    -- Porcentaje de cada categoría
    jsonb_object_agg(
        category_enum,
        ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY member_id), 2)
    ) as category_distribution,
    -- Nivel predominante
    MODE() WITHIN GROUP (ORDER BY difficulty_level) as typical_difficulty,
    -- Horario preferido
    CASE
        WHEN MODE() WITHIN GROUP (ORDER BY hour_local) BETWEEN 6 AND 11 THEN 'morning'
        WHEN MODE() WITHIN GROUP (ORDER BY hour_local) BETWEEN 12 AND 17 THEN 'afternoon'
        WHEN MODE() WITHIN GROUP (ORDER BY hour_local) BETWEEN 18 AND 21 THEN 'evening'
        ELSE 'night'
    END as preferred_time_slot,
    -- Frecuencia
    COUNT(DISTINCT DATE(attendance_time)) / 13.0 as avg_weekly_sessions
FROM class_stats
GROUP BY member_id;
```

**Insights extraíbles:**
- ✅ Tipos de entrenamiento favoritos (cardio: 40%, fuerza: 30%, yoga: 20%, HIIT: 10%)
- ✅ Nivel fitness (principiante vs avanzado)
- ✅ Frecuencia de entrenamiento (días/semana)
- ✅ Horarios preferidos (mañana/tarde/noche)
- ✅ Días activos (lunes, miércoles, viernes)
- ✅ Instructores favoritos
- ✅ Consistencia (racha de semanas consecutivas)
- ✅ Tasa de no-show (compromiso)

---

#### 3.2 Health Tracking

**Tabla:** `user_health_records`

| Campo | Tipo | Insight |
|-------|------|---------|
| `weight` | float | Progreso físico |
| `body_fat_percentage` | float | Objetivos (definición vs volumen) |
| `muscle_mass` | float | Ganancia muscular |
| `recorded_at` | timestamp | Frecuencia de tracking |
| `measurement_type` | enum | MANUAL/SCALE/TRAINER → compromiso |

**Volumen:** 1-4 registros/mes por usuario comprometido
**Granularidad:** Serie temporal

**Query ejemplo - Tendencias de progreso:**
```sql
WITH recent_measurements AS (
    SELECT
        user_id,
        weight,
        body_fat_percentage,
        muscle_mass,
        recorded_at,
        LAG(weight) OVER (PARTITION BY user_id ORDER BY recorded_at) as prev_weight,
        LAG(body_fat_percentage) OVER (PARTITION BY user_id ORDER BY recorded_at) as prev_bf,
        LAG(muscle_mass) OVER (PARTITION BY user_id ORDER BY recorded_at) as prev_muscle
    FROM user_health_records
    WHERE user_id = :user_id
      AND recorded_at >= NOW() - INTERVAL '90 days'
    ORDER BY recorded_at DESC
    LIMIT 1
)
SELECT
    user_id,
    weight,
    body_fat_percentage,
    muscle_mass,
    -- Tendencias
    CASE
        WHEN weight < prev_weight THEN 'losing_weight'
        WHEN weight > prev_weight THEN 'gaining_weight'
        ELSE 'maintaining_weight'
    END as weight_trend,
    CASE
        WHEN body_fat_percentage < prev_bf THEN 'cutting'
        WHEN body_fat_percentage > prev_bf THEN 'bulking'
        ELSE 'maintaining'
    END as body_composition_trend,
    CASE
        WHEN muscle_mass > prev_muscle THEN 'gaining_muscle'
        WHEN muscle_mass < prev_muscle THEN 'losing_muscle'
        ELSE 'maintaining_muscle'
    END as muscle_trend,
    -- Objetivos inferidos
    CASE
        WHEN weight < prev_weight AND body_fat_percentage < prev_bf THEN 'fat_loss'
        WHEN weight > prev_weight AND muscle_mass > prev_muscle THEN 'muscle_gain'
        WHEN body_fat_percentage < prev_bf AND muscle_mass > prev_muscle THEN 'recomposition'
        ELSE 'general_fitness'
    END as inferred_goal
FROM recent_measurements;
```

**Insights extraíbles:**
- ✅ Progreso físico (tendencia peso, grasa, músculo)
- ✅ Nivel de compromiso (frecuencia mediciones)
- ✅ Objetivos inferidos (pérdida peso vs ganancia músculo)
- ✅ Seguimiento profesional (TRAINER measurements)

---

#### 3.3 Objetivos y Metas

**Tabla:** `user_goals`

| Campo | Tipo | Insight |
|-------|------|---------|
| `goal_type` | enum | WEIGHT_LOSS, MUSCLE_GAIN, STRENGTH, ENDURANCE |
| `target_value` | float | Meta específica |
| `current_value` | float | Progreso actual |
| `status` | enum | ACTIVE, COMPLETED, PAUSED |
| `is_public` | boolean | Usuario social (comparte objetivos) |
| `target_date` | date | Urgencia / compromiso temporal |

**Volumen:** 1-3 objetivos activos por usuario comprometido
**Granularidad:** Múltiples objetivos por usuario

**Query ejemplo - Perfil de objetivos:**
```sql
SELECT
    u.id,
    ug.goal_type as primary_goal,
    ug.current_value / NULLIF(ug.target_value, 0) as progress_percentage,
    DATE_PART('day', ug.target_date - NOW()) as days_to_deadline,
    ug.is_public,
    -- Nivel de compromiso basado en objetivos
    CASE
        WHEN COUNT(ug.id) >= 3 AND AVG(ug.current_value / NULLIF(ug.target_value, 0)) > 0.5
            THEN 'highly_committed'
        WHEN COUNT(ug.id) >= 2 THEN 'committed'
        WHEN COUNT(ug.id) = 1 THEN 'casually_committed'
        ELSE 'no_goals'
    END as commitment_level
FROM user u
LEFT JOIN user_goals ug ON ug.user_id = u.id AND ug.status = 'ACTIVE'
WHERE u.id = :user_id
GROUP BY u.id, ug.goal_type, ug.current_value, ug.target_value, ug.target_date, ug.is_public;
```

**Insights extraíbles:**
- ✅ Motivación principal (peso, fuerza, resistencia)
- ✅ Nivel de compromiso (tiene objetivos vs no tiene)
- ✅ Progreso hacia metas (% completado)
- ✅ Usuario social (is_public = comparte públicamente)

---

### 4. Interacciones Sociales

#### 4.1 Posts Creados

**Tabla:** `posts`

| Campo | Tipo | Insight |
|-------|------|---------|
| `post_type` | enum | SINGLE_IMAGE, GALLERY, VIDEO, WORKOUT |
| `caption` | text | Temas de interés (NLP) |
| `location` | string | Ubicaciones frecuentadas |
| `workout_data` | JSON | Ejercicios específicos |
| `privacy` | enum | PUBLIC/PRIVATE → nivel de apertura |
| `like_count` | int | Engagement recibido |
| `comment_count` | int | Engagement profundo |
| `view_count` | int | Alcance |

**Volumen:** 0-10 posts/mes (usuarios muy activos), mayoría 0-2
**Granularidad:** Por post creado

**Query ejemplo - Perfil de creador:**
```sql
WITH post_stats AS (
    SELECT
        user_id,
        COUNT(*) as total_posts,
        COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '30 days') as posts_last_month,
        AVG(like_count) as avg_likes,
        AVG(comment_count) as avg_comments,
        AVG(view_count) as avg_views,
        -- Distribución de tipos
        COUNT(*) FILTER (WHERE post_type = 'WORKOUT') * 100.0 / COUNT(*) as pct_workout,
        COUNT(*) FILTER (WHERE post_type = 'GALLERY') * 100.0 / COUNT(*) as pct_gallery,
        COUNT(*) FILTER (WHERE post_type = 'VIDEO') * 100.0 / COUNT(*) as pct_video,
        -- Privacidad
        COUNT(*) FILTER (WHERE privacy = 'PUBLIC') * 100.0 / COUNT(*) as pct_public
    FROM posts
    WHERE gym_id = :gym_id
      AND is_deleted = false
      AND created_at >= NOW() - INTERVAL '180 days'
    GROUP BY user_id
)
SELECT
    user_id,
    total_posts,
    posts_last_month,
    ROUND(avg_likes::numeric, 2) as avg_likes_per_post,
    ROUND(avg_comments::numeric, 2) as avg_comments_per_post,
    ROUND(avg_views::numeric, 2) as avg_views_per_post,
    -- Clasificación como creador
    CASE
        WHEN posts_last_month >= 8 AND avg_likes >= 30 THEN 'influencer'
        WHEN posts_last_month >= 4 THEN 'active_creator'
        WHEN posts_last_month >= 1 THEN 'casual_creator'
        ELSE 'consumer'
    END as creator_type,
    -- Tipo de contenido preferido
    GREATEST(
        pct_workout,
        pct_gallery,
        pct_video
    ) as dominant_content_type_pct,
    CASE
        WHEN pct_workout >= pct_gallery AND pct_workout >= pct_video THEN 'workout'
        WHEN pct_gallery >= pct_video THEN 'gallery'
        ELSE 'video'
    END as dominant_content_type
FROM post_stats
WHERE user_id = :user_id;
```

**Insights extraíbles:**
- ✅ Usuario creador vs consumidor
- ✅ Tipo de contenido preferido (workout/gallery/video)
- ✅ Engagement generado (calidad contenido)
- ✅ Temas favoritos (NLP en captions)
- ✅ Nivel de privacidad (público vs privado)

---

#### 4.2 Likes en Posts

**Tabla:** `post_likes`

| Campo | Tipo | Insight |
|-------|------|---------|
| `post_id` | int | Qué tipo de posts le gustan |
| `user_id` | int | Quién interactúa |
| `created_at` | timestamp | Cuándo está activo |

**Volumen:** 10-50 likes/mes por usuario activo
**Granularidad:** Por like dado

**Query ejemplo - Preferencias de contenido:**
```sql
WITH like_patterns AS (
    SELECT
        pl.user_id,
        p.post_type,
        p.user_id as author_id,
        COUNT(*) as likes_count,
        EXTRACT(HOUR FROM pl.created_at AT TIME ZONE g.timezone) as hour_local
    FROM post_likes pl
    JOIN posts p ON p.id = pl.post_id
    JOIN gyms g ON g.id = p.gym_id
    WHERE pl.user_id = :user_id
      AND pl.created_at >= NOW() - INTERVAL '60 days'
    GROUP BY pl.user_id, p.post_type, p.user_id, hour_local
)
SELECT
    user_id,
    -- Tipo de posts favoritos
    jsonb_object_agg(
        post_type,
        likes_count
    ) FILTER (WHERE post_type IS NOT NULL) as post_type_preferences,
    -- Autores con los que más interactúa
    ARRAY_AGG(DISTINCT author_id ORDER BY likes_count DESC) FILTER (WHERE author_id IS NOT NULL)
        as top_interacted_authors,
    -- Horarios de actividad
    MODE() WITHIN GROUP (ORDER BY hour_local) as most_active_hour,
    CASE
        WHEN MODE() WITHIN GROUP (ORDER BY hour_local) BETWEEN 6 AND 11 THEN 'morning'
        WHEN MODE() WITHIN GROUP (ORDER BY hour_local) BETWEEN 12 AND 17 THEN 'afternoon'
        WHEN MODE() WITHIN GROUP (ORDER BY hour_local) BETWEEN 18 AND 21 THEN 'evening'
        ELSE 'night'
    END as preferred_browsing_time
FROM like_patterns
GROUP BY user_id;
```

**Insights extraíbles:**
- ✅ Preferencias de contenido (tipo de posts)
- ✅ Usuarios con los que interactúa
- ✅ Nivel de actividad social
- ✅ Timing de actividad (cuándo da likes)

---

#### 4.3 Comentarios en Posts

**Tabla:** `post_comments`

| Campo | Tipo | Insight |
|-------|------|---------|
| `post_id` | int | Posts que generan conversación |
| `comment_text` | text | Temas de interés (NLP) |
| `like_count` | int | Influencia (sus comentarios gustan) |
| `created_at` | timestamp | Timing de actividad |

**Volumen:** 2-20 comentarios/mes por usuario activo
**Granularidad:** Por comentario

**Insights extraíbles:**
- ✅ Engagement profundo (comentar > like)
- ✅ Temas de interés (análisis texto)
- ✅ Influencia (likes en comentarios)
- ✅ Conexiones sociales (con quién conversa)

---

#### 4.4 Stories

**Tablas:** `stories`, `story_views`, `story_reactions`

| Campo | Tipo | Insight |
|-------|------|---------|
| `story_type` | enum | IMAGE, VIDEO, WORKOUT, ACHIEVEMENT |
| `caption` | text | Contenido efímero compartido |
| `privacy` | enum | PUBLIC, FOLLOWERS, CLOSE_FRIENDS |
| `view_count` | int | Alcance |
| `reaction_count` | int | Engagement |
| `view_duration_seconds` | int | Tiempo de atención |
| `emoji` | string | Tipo de reacción emocional |

**Volumen stories creadas:** 0-20 stories/semana (muy activos), mayoría 0-3
**Volumen story views:** 20-100 views/semana por usuario activo
**Granularidad:** Por story / por view

**Query ejemplo - Perfil de stories:**
```sql
WITH story_engagement AS (
    SELECT
        s.user_id as creator_id,
        COUNT(DISTINCT s.id) as stories_created,
        AVG(s.view_count) as avg_views,
        AVG(s.reaction_count) as avg_reactions,
        -- Tipo de contenido
        COUNT(*) FILTER (WHERE s.story_type = 'WORKOUT') * 100.0 / COUNT(*) as pct_workout_stories
    FROM stories s
    WHERE s.gym_id = :gym_id
      AND s.created_at >= NOW() - INTERVAL '30 days'
      AND s.is_deleted = false
    GROUP BY s.user_id
),
story_consumption AS (
    SELECT
        sv.viewer_id,
        COUNT(DISTINCT sv.story_id) as stories_viewed,
        AVG(sv.view_duration_seconds) as avg_view_duration,
        COUNT(DISTINCT sr.id) as reactions_given,
        -- De quién ve stories
        ARRAY_AGG(DISTINCT s.user_id) as viewed_from_users
    FROM story_views sv
    JOIN stories s ON s.id = sv.story_id
    LEFT JOIN story_reactions sr ON sr.story_id = sv.story_id AND sr.user_id = sv.viewer_id
    WHERE sv.viewer_id = :user_id
      AND sv.viewed_at >= NOW() - INTERVAL '30 days'
    GROUP BY sv.viewer_id
)
SELECT
    :user_id as user_id,
    -- Creación
    COALESCE(se.stories_created, 0) as stories_created_monthly,
    COALESCE(se.avg_views, 0) as avg_story_views,
    COALESCE(se.avg_reactions, 0) as avg_story_reactions,
    -- Consumo
    COALESCE(sc.stories_viewed, 0) as stories_viewed_monthly,
    COALESCE(sc.avg_view_duration, 0) as avg_view_duration_seconds,
    COALESCE(sc.reactions_given, 0) as story_reactions_given,
    -- Perfil
    CASE
        WHEN COALESCE(se.stories_created, 0) >= 12 THEN 'prolific_story_creator'
        WHEN COALESCE(se.stories_created, 0) >= 4 THEN 'active_story_creator'
        WHEN COALESCE(se.stories_created, 0) >= 1 THEN 'casual_story_creator'
        WHEN COALESCE(sc.stories_viewed, 0) >= 50 THEN 'story_consumer'
        ELSE 'story_inactive'
    END as story_profile
FROM story_engagement se
FULL OUTER JOIN story_consumption sc ON se.creator_id = sc.viewer_id
WHERE se.creator_id = :user_id OR sc.viewer_id = :user_id;
```

**Insights extraíbles:**
- ✅ Frecuencia de compartir momentos
- ✅ Tipo de contenido efímero (workout, achievement)
- ✅ Nivel de privacidad (público vs close friends)
- ✅ Engagement emocional (emojis usados)
- ✅ Conexiones fuertes (con quién reacciona)
- ✅ Tiempo de atención (view_duration)

---

### 5. Nutrición

**Tablas:** `nutrition_plan_followers`, `nutrition_plans`, `user_daily_progress`, `user_meal_completion`

| Campo | Tipo | Insight |
|-------|------|---------|
| `plan.goal` | enum | BULK, CUT, MAINTENANCE, WEIGHT_LOSS |
| `plan.dietary_restrictions` | array | VEGAN, KETO, GLUTEN_FREE |
| `daily_progress.completion_percentage` | float | Adherencia al plan |
| `meal_completion.satisfaction_rating` | int | Satisfacción nutricional |
| `meal.meal_type` | enum | BREAKFAST, LUNCH, DINNER, POST_WORKOUT |

**Volumen:**
- Planes: 0-2 activos por usuario
- Daily progress: 7-30 registros/mes por usuario en plan
- Meal completions: 14-90 registros/mes (2-3 comidas/día)

**Query ejemplo - Perfil nutricional:**
```sql
WITH nutrition_adherence AS (
    SELECT
        npf.user_id,
        np.goal as nutrition_goal,
        np.dietary_restrictions,
        AVG(udp.completion_percentage) as avg_completion,
        AVG(udp.overall_satisfaction) as avg_satisfaction,
        COUNT(DISTINCT udp.date) as days_tracked
    FROM nutrition_plan_followers npf
    JOIN nutrition_plans np ON np.id = npf.plan_id
    LEFT JOIN user_daily_progress udp ON udp.user_id = npf.user_id
        AND udp.date >= npf.start_date
        AND udp.date >= NOW() - INTERVAL '30 days'
    WHERE npf.user_id = :user_id
      AND npf.is_active = true
    GROUP BY npf.user_id, np.goal, np.dietary_restrictions
)
SELECT
    user_id,
    nutrition_goal,
    dietary_restrictions,
    ROUND(avg_completion::numeric, 2) as avg_adherence_pct,
    ROUND(avg_satisfaction::numeric, 2) as avg_satisfaction,
    days_tracked,
    -- Clasificación
    CASE
        WHEN avg_completion >= 80 THEN 'highly_compliant'
        WHEN avg_completion >= 60 THEN 'moderately_compliant'
        WHEN avg_completion >= 30 THEN 'struggling'
        ELSE 'non_compliant'
    END as nutrition_compliance_level
FROM nutrition_adherence;
```

**Insights extraíbles:**
- ✅ Objetivo nutricional (volumen, definición)
- ✅ Restricciones dietéticas (vegano, keto)
- ✅ Adherencia al plan (% completado)
- ✅ Satisfacción con nutrición
- ✅ Horarios de comida preferidos

---

### 6. Participación en Eventos

**Tabla:** `event_participations` + `events`

| Campo | Tipo | Insight |
|-------|------|---------|
| `status` | enum | REGISTERED, CANCELLED, WAITING_LIST |
| `attended` | boolean | Asistencia real |
| `payment_status` | enum | Disposición a pagar |
| `event.title` | string | Tipos de eventos de interés |
| `event.is_paid` | boolean | Eventos pagos vs gratuitos |

**Volumen:** 0-5 registros/mes por usuario
**Granularidad:** Por participación en evento

**Query ejemplo - Perfil de eventos:**
```sql
WITH event_stats AS (
    SELECT
        ep.member_id,
        COUNT(DISTINCT ep.id) as events_registered,
        COUNT(DISTINCT ep.id) FILTER (WHERE ep.attended = true) as events_attended,
        COUNT(DISTINCT ep.id) FILTER (WHERE e.is_paid = true) as paid_events,
        COUNT(DISTINCT ep.id) FILTER (WHERE ep.attended = true) * 100.0 /
            NULLIF(COUNT(DISTINCT ep.id), 0) as attendance_rate
    FROM event_participations ep
    JOIN events e ON e.id = ep.event_id
    WHERE ep.member_id = :user_id
      AND ep.registered_at >= NOW() - INTERVAL '180 days'
    GROUP BY ep.member_id
)
SELECT
    member_id,
    events_registered,
    events_attended,
    paid_events,
    ROUND(attendance_rate::numeric, 2) as attendance_rate_pct,
    -- Perfil de participación
    CASE
        WHEN events_registered >= 5 AND attendance_rate >= 80 THEN 'event_enthusiast'
        WHEN events_registered >= 3 THEN 'event_participant'
        WHEN events_registered >= 1 THEN 'occasional_participant'
        ELSE 'event_inactive'
    END as event_participation_profile,
    -- Disposición a pagar
    CASE
        WHEN paid_events >= 2 THEN 'willing_to_pay'
        WHEN paid_events = 1 THEN 'occasionally_pays'
        ELSE 'free_only'
    END as payment_disposition
FROM event_stats;
```

**Insights extraíbles:**
- ✅ Nivel de participación social
- ✅ Disposición a pagar por eventos
- ✅ Tipos de eventos preferidos
- ✅ Tasa de asistencia (compromiso)

---

### 7. Facturación y Valor del Usuario

**Tablas:** `user_gym_stripe_profile`, `user_gym_subscriptions`, `membership_plans`

| Campo | Tipo | Insight |
|-------|------|---------|
| `subscription.status` | enum | active, canceled, past_due |
| `plan.price_cents` | int | Valor del usuario |
| `plan.billing_interval` | enum | MONTH, YEAR → compromiso temporal |
| `subscription.created_at` | timestamp | Lifetime del usuario |
| `subscription.canceled_at` | timestamp | Churn |

**Volumen:** 1-2 suscripciones activas por usuario de pago
**Granularidad:** Por suscripción

**Query ejemplo - Valor del usuario:**
```sql
WITH user_value AS (
    SELECT
        ugs.user_id,
        ugs.gym_id,
        s.status as subscription_status,
        mp.price_cents / 100.0 as monthly_price,
        mp.billing_interval,
        DATE_PART('day', NOW() - s.created_at) as subscription_age_days,
        -- Lifetime value estimado
        CASE
            WHEN mp.billing_interval = 'YEAR'
                THEN mp.price_cents * (subscription_age_days / 365.0)
            WHEN mp.billing_interval = 'MONTH'
                THEN mp.price_cents * (subscription_age_days / 30.0)
            ELSE 0
        END / 100.0 as estimated_ltv
    FROM user_gym_stripe_profile ugsp
    JOIN user_gym_subscriptions ugs ON ugs.stripe_customer_id = ugsp.stripe_customer_id
    LEFT JOIN membership_plans mp ON mp.id = ugs.plan_id
    LEFT JOIN (
        SELECT DISTINCT ON (subscription_id)
            subscription_id,
            status,
            created_at
        FROM user_gym_subscriptions
        ORDER BY subscription_id, created_at DESC
    ) s ON s.subscription_id = ugs.stripe_subscription_id
    WHERE ugs.user_id = :user_id
      AND ugs.gym_id = :gym_id
)
SELECT
    user_id,
    subscription_status,
    monthly_price,
    billing_interval,
    subscription_age_days,
    ROUND(estimated_ltv::numeric, 2) as estimated_lifetime_value,
    -- Clasificación de valor
    CASE
        WHEN estimated_ltv >= 500 THEN 'high_value'
        WHEN estimated_ltv >= 200 THEN 'medium_value'
        WHEN estimated_ltv >= 50 THEN 'low_value'
        ELSE 'trial_or_free'
    END as user_value_tier,
    -- Riesgo de churn
    CASE
        WHEN subscription_status = 'past_due' THEN 'high_churn_risk'
        WHEN subscription_status = 'canceled' THEN 'churned'
        WHEN billing_interval = 'MONTH' THEN 'medium_churn_risk'
        WHEN billing_interval = 'YEAR' THEN 'low_churn_risk'
        ELSE 'unknown'
    END as churn_risk
FROM user_value;
```

**Insights extraíbles:**
- ✅ Valor del usuario (LTV)
- ✅ Compromiso temporal (mensual vs anual)
- ✅ Riesgo de churn
- ✅ Estado de pago

---

### 8. Relaciones y Conexiones

#### 8.1 Relación Trainer-Member

**Tabla:** `trainer_member_relationship`

| Campo | Tipo | Insight |
|-------|------|---------|
| `trainer_id` | int | Trainer asignado |
| `status` | enum | ACTIVE, PAUSED, TERMINATED |
| `start_date` | date | Duración de la relación |

**Volumen:** 0-1 trainer por miembro
**Granularidad:** Por relación activa

**Insights extraíbles:**
- ✅ Seguimiento personalizado (tiene trainer)
- ✅ Nivel de servicio (premium)
- ✅ Conexión con trainer (para ranking)

---

#### 8.2 Conexiones de Chat

**Tabla:** `chat_members` + `chat_rooms`

| Campo | Tipo | Insight |
|-------|------|---------|
| `room_id` | int | Canales activos |
| `is_direct` | boolean | Chats 1-1 vs grupos |
| `event_id` | int | Participación en eventos |

**Volumen:** 3-15 canales por usuario activo
**Granularidad:** Por canal

**Insights extraíbles:**
- ✅ Nivel de socialización (cantidad canales)
- ✅ Tipo de comunicación (directo vs grupos)
- ✅ Participación en eventos

---

## Algoritmo de Perfil de Usuario

### Objetivo

Crear un **perfil multidimensional** de cada usuario que capture:
- Intereses fitness
- Nivel de actividad
- Preferencias temporales
- Objetivos
- Nivel social
- Valor para el negocio

### Dimensiones del Perfil

```python
user_profile = {
    "user_id": 123,
    "gym_id": 4,
    "profile_version": "1.0",
    "last_updated": "2025-11-16T10:30:00Z",

    # 1. Intereses Fitness
    "fitness_interests": {
        "primary_category": "strength",
        "category_distribution": {
            "strength": 0.45,
            "cardio": 0.30,
            "yoga": 0.15,
            "hiit": 0.10
        },
        "difficulty_level": "intermediate",
        "favorite_trainers": [trainer_67, trainer_89],
        "workout_types": ["push", "pull", "legs"]
    },

    # 2. Nivel de Actividad
    "activity_level": {
        "classification": "highly_active",
        "metrics": {
            "weekly_classes": 4.2,
            "app_opens_monthly": 48,
            "posts_per_month": 3,
            "stories_per_week": 5,
            "current_streak_days": 14,
            "longest_streak_days": 28
        },
        "consistency_score": 8.7  # 0-10
    },

    # 3. Preferencias Temporales
    "temporal_preferences": {
        "preferred_workout_time": "evening",  # morning/afternoon/evening/night
        "preferred_days": ["monday", "wednesday", "friday"],
        "app_usage_peak": "20:00-22:00",
        "content_browsing_time": "evening",
        "timezone": "America/Los_Angeles"
    },

    # 4. Objetivos y Progreso
    "goals": {
        "primary_goal": "muscle_gain",
        "secondary_goals": ["strength", "attendance"],
        "goal_progress": 0.67,
        "has_active_goals": true,
        "nutrition_goal": "bulk",
        "dietary_restrictions": ["vegetarian"],
        "inferred_from_progress": {
            "weight_trend": "gaining",
            "muscle_trend": "gaining",
            "body_fat_trend": "maintaining"
        }
    },

    # 5. Nivel Social
    "social_profile": {
        "level": "highly_social",  # antisocial/reserved/social/highly_social
        "score": 8.5,  # 0-10
        "creator_type": "active_creator",  # consumer/casual/active/influencer
        "engagement_given": {
            "posts_created_monthly": 3,
            "stories_created_weekly": 5,
            "comments_monthly": 12,
            "likes_monthly": 35,
            "reactions_weekly": 6
        },
        "engagement_received": {
            "avg_likes_per_post": 28,
            "avg_comments_per_post": 6,
            "avg_story_views": 85,
            "avg_story_reactions": 15
        },
        "connections": {
            "has_trainer": true,
            "chat_rooms": 8,
            "top_interacted_users": [user_234, user_567, user_890]
        }
    },

    # 6. Preferencias de Contenido
    "content_preferences": {
        "post_types": {
            "workout": 0.55,
            "gallery": 0.30,
            "video": 0.15
        },
        "story_types": {
            "workout": 0.40,
            "achievement": 0.35,
            "image": 0.25
        },
        "topics_of_interest": ["strength_training", "nutrition", "motivation"],
        "hashtags_followed": ["#legday", "#gains", "#pr"]
    },

    # 7. Valor del Usuario
    "business_value": {
        "tier": "high_value",
        "subscription_status": "active",
        "monthly_revenue": 79.99,
        "lifetime_value": 480.00,
        "subscription_age_days": 180,
        "churn_risk": "low",
        "commitment_level": "highly_committed"
    },

    # 8. Scores Agregados
    "aggregate_scores": {
        "activity_score": 8.7,      # 0-10
        "social_score": 8.5,         # 0-10
        "commitment_score": 9.1,     # 0-10
        "engagement_score": 7.8,     # 0-10
        "overall_user_quality": 8.5  # 0-10 (promedio ponderado)
    }
}
```

---

### Implementación SQL - Perfil Completo

```sql
-- Vista materializada para perfiles de usuario (refresh cada hora)
CREATE MATERIALIZED VIEW user_profiles AS

WITH
-- 1. Intereses fitness
fitness_interests AS (
    SELECT
        cp.member_id as user_id,
        c.category_enum,
        c.difficulty_level,
        cs.trainer_id,
        COUNT(*) as class_count,
        COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY cp.member_id) as category_pct
    FROM class_participation cp
    JOIN class_session cs ON cs.id = cp.session_id
    JOIN class c ON c.id = cs.class_id
    WHERE cp.status = 'ATTENDED'
      AND cp.attendance_time >= NOW() - INTERVAL '90 days'
    GROUP BY cp.member_id, c.category_enum, c.difficulty_level, cs.trainer_id
),

-- 2. Nivel de actividad
activity_metrics AS (
    SELECT
        u.id as user_id,
        ug.gym_id,
        ug.monthly_app_opens,
        COUNT(DISTINCT DATE(cp.attendance_time)) / 13.0 as avg_weekly_classes,
        COUNT(DISTINCT p.id) as posts_last_month,
        COUNT(DISTINCT s.id) / 4.0 as stories_per_week,
        COALESCE(MAX(uhs.current_streak), 0) as current_streak_days
    FROM user u
    JOIN user_gyms ug ON ug.user_id = u.id
    LEFT JOIN class_participation cp ON cp.member_id = u.id
        AND cp.status = 'ATTENDED'
        AND cp.attendance_time >= NOW() - INTERVAL '90 days'
    LEFT JOIN posts p ON p.user_id = u.id
        AND p.created_at >= NOW() - INTERVAL '30 days'
    LEFT JOIN stories s ON s.user_id = u.id
        AND s.created_at >= NOW() - INTERVAL '30 days'
    LEFT JOIN user_health_snapshots uhs ON uhs.user_id = u.id
        AND uhs.snapshot_date = (SELECT MAX(snapshot_date) FROM user_health_snapshots WHERE user_id = u.id)
    GROUP BY u.id, ug.gym_id, ug.monthly_app_opens, uhs.current_streak
),

-- 3. Social profile
social_metrics AS (
    SELECT
        u.id as user_id,
        COUNT(DISTINCT p.id) as posts_created,
        AVG(p.like_count) as avg_post_likes,
        AVG(p.comment_count) as avg_post_comments,
        COUNT(DISTINCT pl.id) as likes_given,
        COUNT(DISTINCT pc.id) as comments_given,
        COUNT(DISTINCT cm.room_id) as chat_rooms
    FROM user u
    LEFT JOIN posts p ON p.user_id = u.id
        AND p.created_at >= NOW() - INTERVAL '30 days'
    LEFT JOIN post_likes pl ON pl.user_id = u.id
        AND pl.created_at >= NOW() - INTERVAL '30 days'
    LEFT JOIN post_comments pc ON pc.user_id = u.id
        AND pc.created_at >= NOW() - INTERVAL '30 days'
    LEFT JOIN chat_members cm ON cm.user_id = u.id
    GROUP BY u.id
),

-- 4. Objetivos y progreso
goal_metrics AS (
    SELECT
        ug.user_id,
        ug.goal_type as primary_goal,
        AVG(ug.current_value / NULLIF(ug.target_value, 0)) as avg_goal_progress,
        COUNT(*) as active_goals_count,
        np.goal as nutrition_goal
    FROM user_goals ug
    LEFT JOIN nutrition_plan_followers npf ON npf.user_id = ug.user_id AND npf.is_active = true
    LEFT JOIN nutrition_plans np ON np.id = npf.plan_id
    WHERE ug.status = 'ACTIVE'
    GROUP BY ug.user_id, ug.goal_type, np.goal
),

-- 5. Valor del usuario
user_value AS (
    SELECT
        ugsp.user_id,
        ugsp.gym_id,
        mp.price_cents / 100.0 as monthly_price,
        s.status as subscription_status,
        DATE_PART('day', NOW() - s.created_at) as subscription_age_days
    FROM user_gym_stripe_profile ugsp
    LEFT JOIN user_gym_subscriptions ugs ON ugs.stripe_customer_id = ugsp.stripe_customer_id
    LEFT JOIN membership_plans mp ON mp.id = ugs.plan_id
    LEFT JOIN (
        SELECT DISTINCT ON (user_id, gym_id) *
        FROM user_gym_subscriptions
        ORDER BY user_id, gym_id, created_at DESC
    ) s ON s.user_id = ugsp.user_id AND s.gym_id = ugsp.gym_id
)

-- Combinar todo en un perfil unificado
SELECT
    u.id as user_id,
    am.gym_id,

    -- Intereses fitness (JSON)
    jsonb_build_object(
        'primary_category', (
            SELECT category_enum
            FROM fitness_interests
            WHERE user_id = u.id
            ORDER BY category_pct DESC
            LIMIT 1
        ),
        'category_distribution', (
            SELECT jsonb_object_agg(category_enum, ROUND(category_pct::numeric, 2))
            FROM fitness_interests
            WHERE user_id = u.id
        )
    ) as fitness_interests,

    -- Nivel de actividad
    jsonb_build_object(
        'classification',
            CASE
                WHEN am.avg_weekly_classes >= 4 AND am.monthly_app_opens >= 40 THEN 'highly_active'
                WHEN am.avg_weekly_classes >= 2 AND am.monthly_app_opens >= 15 THEN 'moderately_active'
                WHEN am.avg_weekly_classes >= 1 OR am.monthly_app_opens >= 5 THEN 'lightly_active'
                ELSE 'inactive'
            END,
        'metrics', jsonb_build_object(
            'weekly_classes', ROUND(am.avg_weekly_classes::numeric, 2),
            'app_opens_monthly', am.monthly_app_opens,
            'posts_per_month', am.posts_last_month,
            'stories_per_week', ROUND(am.stories_per_week::numeric, 2),
            'current_streak_days', am.current_streak_days
        ),
        'consistency_score', LEAST(10, (
            (am.avg_weekly_classes * 2) +
            (am.monthly_app_opens / 10.0) +
            (am.current_streak_days / 5.0)
        ))
    ) as activity_level,

    -- Nivel social
    jsonb_build_object(
        'level',
            CASE
                WHEN social_score >= 8 THEN 'highly_social'
                WHEN social_score >= 5 THEN 'social'
                WHEN social_score >= 2 THEN 'reserved'
                ELSE 'antisocial'
            END,
        'score', ROUND(social_score::numeric, 2),
        'engagement_given', jsonb_build_object(
            'posts_created_monthly', sm.posts_created,
            'comments_monthly', sm.comments_given,
            'likes_monthly', sm.likes_given
        ),
        'engagement_received', jsonb_build_object(
            'avg_likes_per_post', ROUND(COALESCE(sm.avg_post_likes, 0)::numeric, 2),
            'avg_comments_per_post', ROUND(COALESCE(sm.avg_post_comments, 0)::numeric, 2)
        )
    ) as social_profile,

    -- Objetivos
    jsonb_build_object(
        'primary_goal', gm.primary_goal,
        'goal_progress', ROUND(COALESCE(gm.avg_goal_progress, 0)::numeric, 2),
        'active_goals_count', COALESCE(gm.active_goals_count, 0),
        'nutrition_goal', gm.nutrition_goal
    ) as goals,

    -- Valor del usuario
    jsonb_build_object(
        'subscription_status', uv.subscription_status,
        'monthly_revenue', uv.monthly_price,
        'subscription_age_days', uv.subscription_age_days,
        'tier',
            CASE
                WHEN uv.monthly_price >= 100 THEN 'premium'
                WHEN uv.monthly_price >= 50 THEN 'standard'
                ELSE 'basic'
            END
    ) as business_value,

    -- Scores agregados
    jsonb_build_object(
        'activity_score', ROUND(activity_score::numeric, 2),
        'social_score', ROUND(social_score::numeric, 2),
        'commitment_score', ROUND(commitment_score::numeric, 2),
        'overall_quality', ROUND(
            ((activity_score * 0.35) + (social_score * 0.25) + (commitment_score * 0.40))::numeric,
            2
        )
    ) as aggregate_scores,

    -- Metadata
    NOW() as profile_generated_at

FROM user u
LEFT JOIN activity_metrics am ON am.user_id = u.id
LEFT JOIN social_metrics sm ON sm.user_id = u.id
LEFT JOIN goal_metrics gm ON gm.user_id = u.id
LEFT JOIN user_value uv ON uv.user_id = u.id

-- Calcular scores intermedios
CROSS JOIN LATERAL (
    SELECT
        LEAST(10, (
            (COALESCE(am.avg_weekly_classes, 0) * 2) +
            (COALESCE(am.monthly_app_opens, 0) / 10.0) +
            (COALESCE(am.current_streak_days, 0) / 5.0)
        )) as activity_score,

        LEAST(10, (
            (COALESCE(sm.posts_created, 0) * 0.5) +
            (COALESCE(sm.likes_given, 0) * 0.05) +
            (COALESCE(sm.comments_given, 0) * 0.2) +
            (COALESCE(sm.avg_post_likes, 0) * 0.3) +
            (COALESCE(sm.avg_post_comments, 0) * 0.5) +
            (COALESCE(sm.chat_rooms, 0) * 0.2)
        )) as social_score,

        LEAST(10, (
            (COALESCE(gm.active_goals_count, 0) * 2) +
            (COALESCE(gm.avg_goal_progress, 0) * 5) +
            CASE WHEN gm.nutrition_goal IS NOT NULL THEN 3 ELSE 0 END
        )) as commitment_score
) scores;

-- Índices para queries rápidas
CREATE INDEX idx_user_profiles_user_gym ON user_profiles(user_id, gym_id);
CREATE INDEX idx_user_profiles_activity ON user_profiles((aggregate_scores->>'activity_score'));
CREATE INDEX idx_user_profiles_social ON user_profiles((aggregate_scores->>'social_score'));

-- Refresh automático cada hora
CREATE OR REPLACE FUNCTION refresh_user_profiles()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY user_profiles;
END;
$$ LANGUAGE plpgsql;

-- Programar refresh (con pg_cron o APScheduler)
-- SELECT cron.schedule('refresh-user-profiles', '0 * * * *', 'SELECT refresh_user_profiles()');
```

---

### Uso del Perfil

```python
# app/services/user_profile_service.py

class UserProfileService:
    """
    Servicio para obtener y usar perfiles de usuario.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_user_profile(self, user_id: int, gym_id: int) -> Dict:
        """
        Obtiene el perfil completo de un usuario.
        """
        query = """
        SELECT
            user_id,
            gym_id,
            fitness_interests,
            activity_level,
            social_profile,
            goals,
            business_value,
            aggregate_scores,
            profile_generated_at
        FROM user_profiles
        WHERE user_id = :user_id AND gym_id = :gym_id
        """

        result = self.db.execute(text(query), {
            "user_id": user_id,
            "gym_id": gym_id
        }).fetchone()

        if not result:
            return self._generate_profile_on_demand(user_id, gym_id)

        return {
            "user_id": result[0],
            "gym_id": result[1],
            "fitness_interests": result[2],
            "activity_level": result[3],
            "social_profile": result[4],
            "goals": result[5],
            "business_value": result[6],
            "aggregate_scores": result[7],
            "profile_generated_at": result[8]
        }

    def is_user_interested_in(self, user_id: int, gym_id: int, interest: str) -> bool:
        """
        Verifica si un usuario tiene interés en una categoría específica.

        Args:
            interest: 'strength', 'cardio', 'yoga', etc.
        """
        profile = self.get_user_profile(user_id, gym_id)

        if not profile or not profile.get("fitness_interests"):
            return False

        category_dist = profile["fitness_interests"].get("category_distribution", {})
        return category_dist.get(interest, 0) >= 0.20  # 20% o más

    def get_user_activity_level(self, user_id: int, gym_id: int) -> str:
        """
        Retorna el nivel de actividad: highly_active, moderately_active, etc.
        """
        profile = self.get_user_profile(user_id, gym_id)

        if not profile:
            return "inactive"

        return profile.get("activity_level", {}).get("classification", "inactive")

    def get_similar_users(self, user_id: int, gym_id: int, limit: int = 10) -> List[int]:
        """
        Encuentra usuarios similares basándose en perfiles.

        Usa distancia coseno entre vectores de features.
        """
        # TODO: Implementar similarity search con embeddings
        pass
```

---

## Algoritmo de Ranking de Feed

### Objetivo

Ordenar posts en el feed de cada usuario mostrando primero el contenido **más relevante** basándose en:

1. **Content Affinity:** Qué tanto le gusta este tipo de contenido
2. **Social Affinity:** Relación con el autor
3. **Past Engagement:** Historial de engagement similar
4. **Timing:** Recency y hora del día
5. **Popularity:** Trending y engagement general

### Fórmula Final de Ranking

```python
final_score = (
    (content_affinity * 0.25) +
    (social_affinity * 0.25) +
    (past_engagement * 0.15) +
    (timing * 0.15) +
    (popularity * 0.20)
)
```

**Pesos justificados:**
- **Content affinity (25%):** Lo más importante es mostrar contenido que le interesa
- **Social affinity (25%):** Conexiones sociales impulsan engagement
- **Popularity (20%):** Posts populares tienen calidad verificada
- **Past engagement (15%):** Predictor de comportamiento futuro
- **Timing (15%):** Recency matters, pero no más que relevancia

---

### 1. Content Affinity Score

**Objetivo:** Medir qué tanto coincide el post con los intereses del usuario

```sql
-- app/services/feed_ranking/content_affinity.sql

WITH user_preferences AS (
    -- Tipos de posts que le gustan al usuario
    SELECT
        pl.user_id,
        p.post_type,
        COUNT(*) as likes_count,
        COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY pl.user_id) as preference_pct
    FROM post_likes pl
    JOIN posts p ON p.id = pl.post_id
    WHERE pl.user_id = :user_id
      AND pl.created_at >= NOW() - INTERVAL '60 days'
    GROUP BY pl.user_id, p.post_type
),
user_class_categories AS (
    -- Categorías de clases que asiste
    SELECT
        cp.member_id,
        c.category_enum,
        COUNT(*) as attendance_count,
        COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY cp.member_id) as category_pct
    FROM class_participation cp
    JOIN class_session cs ON cs.id = cp.session_id
    JOIN class c ON c.id = cs.class_id
    WHERE cp.member_id = :user_id
      AND cp.status = 'ATTENDED'
      AND cp.attendance_time >= NOW() - INTERVAL '90 days'
    GROUP BY cp.member_id, c.category_enum
)
SELECT
    p.id as post_id,

    -- 1. Type match (tipo de post preferido)
    COALESCE(
        up.preference_pct / 100.0,
        0.5  -- Default si no hay datos
    ) as type_match_score,

    -- 2. Category match (si post está taggeado con sesión/evento de categoría favorita)
    CASE
        WHEN EXISTS (
            SELECT 1 FROM post_tags pt
            JOIN class_session cs ON cs.id = pt.tagged_session_id
            JOIN class c ON c.id = cs.class_id
            WHERE pt.post_id = p.id
              AND pt.tag_type = 'SESSION'
              AND c.category_enum = (
                  SELECT category_enum
                  FROM user_class_categories
                  WHERE member_id = :user_id
                  ORDER BY category_pct DESC
                  LIMIT 1
              )
        ) THEN 1.0
        WHEN EXISTS (
            SELECT 1 FROM post_tags pt
            JOIN class_session cs ON cs.id = pt.tagged_session_id
            JOIN class c ON c.id = cs.class_id
            WHERE pt.post_id = p.id
              AND pt.tag_type = 'SESSION'
              AND c.category_enum IN (
                  SELECT category_enum
                  FROM user_class_categories
                  WHERE member_id = :user_id AND category_pct >= 20
              )
        ) THEN 0.7
        ELSE 0.3
    END as category_match_score,

    -- 3. Location match (post en ubicación que usuario frecuenta)
    CASE
        WHEN p.location IS NOT NULL AND p.location IN (
            SELECT DISTINCT location
            FROM posts
            WHERE user_id = :user_id AND location IS NOT NULL
        ) THEN 0.8
        WHEN p.location IS NULL THEN 0.5
        ELSE 0.3
    END as location_match_score,

    -- 4. Workout data match (si es WORKOUT post con ejercicios que hace)
    CASE
        WHEN p.post_type = 'WORKOUT' AND p.workout_data IS NOT NULL THEN 0.8
        WHEN p.post_type = 'WORKOUT' THEN 0.6
        ELSE 0.5
    END as workout_match_score,

    -- Content Affinity Score Final
    (
        (COALESCE(up.preference_pct / 100.0, 0.5) * 0.25) +
        (category_match_score * 0.35) +
        (location_match_score * 0.15) +
        (workout_match_score * 0.25)
    ) as content_affinity_score

FROM posts p
LEFT JOIN user_preferences up ON up.post_type = p.post_type AND up.user_id = :user_id
WHERE p.gym_id = :gym_id
  AND p.is_deleted = false
  AND p.privacy = 'PUBLIC'
  AND p.created_at >= NOW() - INTERVAL '7 days';
```

**Interpretación:**
- `1.0` → Perfecta coincidencia con intereses
- `0.7-0.9` → Muy relevante
- `0.5-0.7` → Moderadamente relevante
- `<0.5` → Poco relevante

---

### 2. Social Affinity Score

**Objetivo:** Medir la relación social entre el usuario y el autor del post

```sql
-- app/services/feed_ranking/social_affinity.sql

WITH user_interactions AS (
    -- Historial de interacciones usuario → autor
    SELECT
        p.user_id as author_id,
        COUNT(DISTINCT pl.post_id) as liked_posts,
        COUNT(DISTINCT pc.post_id) as commented_posts,
        COUNT(DISTINCT p.id) as total_author_posts
    FROM posts p
    LEFT JOIN post_likes pl ON pl.post_id = p.id AND pl.user_id = :user_id
    LEFT JOIN post_comments pc ON pc.post_id = p.id AND pc.user_id = :user_id
    WHERE p.gym_id = :gym_id
      AND p.created_at >= NOW() - INTERVAL '90 days'
    GROUP BY p.user_id
),
shared_context AS (
    -- Contextos compartidos entre usuario y autores
    SELECT DISTINCT
        cp2.member_id as author_id,

        -- Asisten a las mismas clases
        COUNT(DISTINCT cp1.session_id) > 0 as same_classes,

        -- Tienen el mismo trainer
        EXISTS (
            SELECT 1 FROM trainer_member_relationship tmr1
            JOIN trainer_member_relationship tmr2 ON tmr2.trainer_id = tmr1.trainer_id
            WHERE tmr1.member_id = :user_id
              AND tmr2.member_id = cp2.member_id
              AND tmr1.status = 'ACTIVE'
              AND tmr2.status = 'ACTIVE'
        ) as same_trainer
    FROM class_participation cp1
    JOIN class_participation cp2 ON cp2.session_id = cp1.session_id
    WHERE cp1.member_id = :user_id
      AND cp2.member_id != :user_id
      AND cp1.status = 'ATTENDED'
      AND cp2.status = 'ATTENDED'
      AND cp1.attendance_time >= NOW() - INTERVAL '90 days'
    GROUP BY cp2.member_id
),
chat_connections AS (
    -- Usuarios con los que ha chateado
    SELECT DISTINCT
        cm2.user_id as author_id
    FROM chat_members cm1
    JOIN chat_members cm2 ON cm2.room_id = cm1.room_id
    WHERE cm1.user_id = :user_id
      AND cm2.user_id != :user_id
)
SELECT
    p.id as post_id,
    p.user_id as author_id,

    -- 1. Ha interactuado con este autor antes
    (COALESCE(ui.liked_posts, 0) + COALESCE(ui.commented_posts, 0)) > 0 as has_interacted,

    -- 2. Frecuencia de interacción con autor
    CASE
        WHEN ui.total_author_posts > 0
        THEN (COALESCE(ui.liked_posts, 0) + COALESCE(ui.commented_posts, 0)) * 1.0 / ui.total_author_posts
        ELSE 0
    END as interaction_frequency,

    -- 3. Mismo trainer
    COALESCE(sc.same_trainer, false) as same_trainer,

    -- 4. Mismas clases
    COALESCE(sc.same_classes, false) as same_classes,

    -- 5. Chat history
    EXISTS (SELECT 1 FROM chat_connections WHERE author_id = p.user_id) as chat_history,

    -- 6. Author role (trainers/admins tienen más autoridad)
    ug.role as author_role,

    -- Social Affinity Score Final
    (
        (((COALESCE(ui.liked_posts, 0) + COALESCE(ui.commented_posts, 0)) > 0)::int * 2.0) +
        (COALESCE(sc.same_trainer, false)::int * 1.5) +
        (COALESCE(sc.same_classes, false)::int * 1.2) +
        ((EXISTS (SELECT 1 FROM chat_connections WHERE author_id = p.user_id))::int * 1.0) +
        (CASE
            WHEN ui.total_author_posts > 0
            THEN (COALESCE(ui.liked_posts, 0) + COALESCE(ui.commented_posts, 0)) * 1.0 / ui.total_author_posts
            ELSE 0
        END * 3.0) +
        ((ug.role = 'TRAINER')::int * 1.5) +
        ((ug.role IN ('ADMIN', 'OWNER'))::int * 2.0)
    ) / 12.2 as social_affinity_score

FROM posts p
JOIN user_gyms ug ON ug.user_id = p.user_id AND ug.gym_id = p.gym_id
LEFT JOIN user_interactions ui ON ui.author_id = p.user_id
LEFT JOIN shared_context sc ON sc.author_id = p.user_id
WHERE p.gym_id = :gym_id
  AND p.is_deleted = false
  AND p.privacy = 'PUBLIC';
```

**Interpretación:**
- `1.0` → Conexión muy fuerte (amigo cercano, mismo trainer, interacción frecuente)
- `0.7-0.9` → Conexión fuerte
- `0.4-0.7` → Conocido
- `<0.4` → Desconocido

---

### 3. Past Engagement Score

**Objetivo:** Predecir engagement basándose en comportamiento histórico con contenido similar

```sql
-- app/services/feed_ranking/past_engagement.sql

WITH similar_posts AS (
    -- Posts similares al actual (mismo tipo, categoría)
    SELECT DISTINCT
        p2.id as similar_post_id,
        p2.post_type,
        p2.created_at
    FROM posts p1
    CROSS JOIN posts p2
    WHERE p1.id = :current_post_id
      AND p2.id != p1.id
      AND p2.post_type = p1.post_type
      AND p2.gym_id = p1.gym_id
      AND p2.created_at >= NOW() - INTERVAL '60 days'
      AND p2.is_deleted = false
),
user_engagement_on_similar AS (
    SELECT
        sp.similar_post_id,
        COUNT(DISTINCT pl.post_id) as user_liked_count,
        COUNT(DISTINCT pc.post_id) as user_commented_count,
        COUNT(DISTINCT sp.similar_post_id) as total_similar_posts
    FROM similar_posts sp
    LEFT JOIN post_likes pl ON pl.post_id = sp.similar_post_id AND pl.user_id = :user_id
    LEFT JOIN post_comments pc ON pc.post_id = sp.similar_post_id AND pc.user_id = :user_id
    GROUP BY sp.similar_post_id
)
SELECT
    :current_post_id as post_id,

    -- Engagement histórico en posts similares
    SUM(user_liked_count) > 0 as has_liked_similar,
    SUM(user_commented_count) > 0 as has_commented_similar,

    -- Tasa de engagement en contenido similar
    CASE
        WHEN SUM(total_similar_posts) > 0
        THEN (SUM(user_liked_count) + SUM(user_commented_count)) * 1.0 / SUM(total_similar_posts)
        ELSE 0
    END as similar_content_engagement_rate,

    -- Past Engagement Score
    (
        ((SUM(user_liked_count) > 0)::int * 0.5) +
        ((SUM(user_commented_count) > 0)::int * 1.0) +
        (CASE
            WHEN SUM(total_similar_posts) > 0
            THEN (SUM(user_liked_count) + SUM(user_commented_count)) * 1.0 / SUM(total_similar_posts)
            ELSE 0
        END * 5.0)
    ) / 6.5 as past_engagement_score

FROM user_engagement_on_similar;
```

**Interpretación:**
- `1.0` → Siempre interactúa con este tipo de contenido
- `0.7-0.9` → Frecuentemente interactúa
- `0.3-0.7` → A veces interactúa
- `<0.3` → Raramente interactúa

---

### 4. Timing Score

**Objetivo:** Dar prioridad a contenido reciente y mostrar en horarios activos del usuario

```sql
-- app/services/feed_ranking/timing.sql

WITH user_active_hours AS (
    -- Horarios en los que el usuario típicamente interactúa
    SELECT
        EXTRACT(HOUR FROM created_at AT TIME ZONE g.timezone) as hour,
        COUNT(*) as interactions
    FROM (
        SELECT pl.created_at, pl.gym_id
        FROM post_likes pl
        WHERE pl.user_id = :user_id

        UNION ALL

        SELECT pc.created_at, pc.gym_id
        FROM post_comments pc
        WHERE pc.user_id = :user_id

        UNION ALL

        SELECT sv.viewed_at as created_at, s.gym_id
        FROM story_views sv
        JOIN stories s ON s.id = sv.story_id
        WHERE sv.viewer_id = :user_id
    ) all_interactions
    JOIN gyms g ON g.id = all_interactions.gym_id
    WHERE all_interactions.created_at >= NOW() - INTERVAL '60 days'
    GROUP BY hour
    ORDER BY interactions DESC
    LIMIT 5
)
SELECT
    p.id as post_id,
    p.created_at,

    -- Edad del post en horas
    EXTRACT(EPOCH FROM (NOW() - p.created_at)) / 3600.0 as age_hours,

    -- Recency score con exponential decay
    -- Fórmula: e^(-decay_rate * age_hours)
    -- decay_rate = 0.1 → 50% de score a las 6.9 horas
    EXP(-0.1 * (EXTRACT(EPOCH FROM (NOW() - p.created_at)) / 3600.0)) as recency_score,

    -- Hora actual del usuario
    EXTRACT(HOUR FROM NOW() AT TIME ZONE g.timezone) as current_hour_local,

    -- ¿Es hora activa del usuario?
    EXTRACT(HOUR FROM NOW() AT TIME ZONE g.timezone) IN (
        SELECT hour FROM user_active_hours
    ) as is_user_active_hour,

    -- Timing Score Final
    (
        -- Recency (70% del peso)
        (EXP(-0.1 * (EXTRACT(EPOCH FROM (NOW() - p.created_at)) / 3600.0)) * 0.70) +

        -- Active hour boost (30% del peso)
        (CASE
            WHEN EXTRACT(HOUR FROM NOW() AT TIME ZONE g.timezone) IN (
                SELECT hour FROM user_active_hours
            ) THEN 0.30
            ELSE 0.15
        END)
    ) as timing_score

FROM posts p
JOIN gyms g ON g.id = p.gym_id
WHERE p.gym_id = :gym_id
  AND p.is_deleted = false
  AND p.created_at >= NOW() - INTERVAL '7 days';  -- Solo posts de última semana
```

**Interpretación:**
- `1.0` → Post muy reciente (<1 hora) en horario activo del usuario
- `0.7-0.9` → Post reciente (1-6 horas)
- `0.4-0.7` → Post de hoy (6-24 horas)
- `<0.4` → Post de días anteriores

**Curva de decay:**
```
Age (horas) | Recency Score
0           | 1.00
1           | 0.90
6           | 0.55
12          | 0.30
24          | 0.09
48          | 0.01
```

---

### 5. Popularity Score

**Objetivo:** Medir popularidad absoluta y trending (velocity de engagement)

```sql
-- app/services/feed_ranking/popularity.sql

WITH user_connections AS (
    -- Usuarios con conexión (mismo trainer, mismas clases, chats)
    SELECT DISTINCT connected_user_id
    FROM (
        -- Mismas clases
        SELECT DISTINCT cp2.member_id as connected_user_id
        FROM class_participation cp1
        JOIN class_participation cp2 ON cp2.session_id = cp1.session_id
        WHERE cp1.member_id = :user_id
          AND cp2.member_id != :user_id
          AND cp1.status = 'ATTENDED'
          AND cp1.attendance_time >= NOW() - INTERVAL '90 days'

        UNION

        -- Mismo trainer
        SELECT DISTINCT tmr2.member_id
        FROM trainer_member_relationship tmr1
        JOIN trainer_member_relationship tmr2 ON tmr2.trainer_id = tmr1.trainer_id
        WHERE tmr1.member_id = :user_id
          AND tmr2.member_id != :user_id
          AND tmr1.status = 'ACTIVE'

        UNION

        -- Chats compartidos
        SELECT DISTINCT cm2.user_id
        FROM chat_members cm1
        JOIN chat_members cm2 ON cm2.room_id = cm1.room_id
        WHERE cm1.user_id = :user_id
          AND cm2.user_id != :user_id
    ) all_connections
),
post_stats AS (
    SELECT
        p.id,
        p.like_count,
        p.comment_count,
        p.view_count,
        p.created_at,
        EXTRACT(EPOCH FROM (NOW() - p.created_at)) / 3600.0 as age_hours,

        -- Engagement de conexiones del usuario
        COUNT(DISTINCT pl.user_id) FILTER (
            WHERE pl.user_id IN (SELECT connected_user_id FROM user_connections)
        ) as likes_from_connections,
        COUNT(DISTINCT pc.user_id) FILTER (
            WHERE pc.user_id IN (SELECT connected_user_id FROM user_connections)
        ) as comments_from_connections

    FROM posts p
    LEFT JOIN post_likes pl ON pl.post_id = p.id
    LEFT JOIN post_comments pc ON pc.post_id = p.id
    WHERE p.gym_id = :gym_id
      AND p.is_deleted = false
      AND p.privacy = 'PUBLIC'
      AND p.created_at >= NOW() - INTERVAL '7 days'
    GROUP BY p.id, p.like_count, p.comment_count, p.view_count, p.created_at
)
SELECT
    id as post_id,
    like_count,
    comment_count,
    view_count,
    age_hours,

    -- Engagement rate
    (like_count + comment_count) * 1.0 / NULLIF(view_count, 1) as engagement_rate,

    -- Velocity (trending) - solo para posts <6 horas
    CASE
        WHEN age_hours <= 6 AND age_hours > 0.1
        THEN (like_count * 1.0) / age_hours
        ELSE 0
    END as likes_per_hour,
    CASE
        WHEN age_hours <= 6 AND age_hours > 0.1
        THEN (comment_count * 1.0) / age_hours
        ELSE 0
    END as comments_per_hour,

    -- Engagement de círculo del usuario
    likes_from_connections,
    comments_from_connections,
    (likes_from_connections + comments_from_connections) * 1.0 /
    NULLIF((SELECT COUNT(*) FROM user_connections), 1) as connection_engagement_rate,

    -- Popularity Score Final
    LEAST(1.0, (
        -- Engagement absoluto (normalizado)
        ((like_count * 0.5) + (comment_count * 1.0) + (view_count * 0.1)) / 100.0 * 0.30 +

        -- Engagement rate
        ((like_count + comment_count) * 1.0 / NULLIF(view_count, 1)) * 0.20 +

        -- Velocity (trending)
        (
            (CASE
                WHEN age_hours <= 6 AND age_hours > 0.1
                THEN (like_count * 1.0) / age_hours
                ELSE 0
            END * 0.5) +
            (CASE
                WHEN age_hours <= 6 AND age_hours > 0.1
                THEN (comment_count * 1.0) / age_hours
                ELSE 0
            END * 1.0)
        ) / 20.0 * 0.25 +

        -- Engagement de conexiones (MUY IMPORTANTE)
        (
            (likes_from_connections * 1.5) +
            (comments_from_connections * 2.0) +
            ((likes_from_connections + comments_from_connections) * 1.0 /
             NULLIF((SELECT COUNT(*) FROM user_connections), 1) * 10)
        ) / 30.0 * 0.25
    )) as popularity_score

FROM post_stats
ORDER BY popularity_score DESC;
```

**Interpretación:**
- `1.0` → Extremadamente popular y viral
- `0.7-0.9` → Muy popular
- `0.4-0.7` → Popularidad moderada
- `<0.4` → Poco popular

---

### Query Final - Ranking Completo

```sql
-- app/services/feed_ranking/final_ranking.sql

WITH
-- 1. Content Affinity
content_affinity AS (
    -- [Query de content_affinity.sql]
    SELECT post_id, content_affinity_score FROM ...
),

-- 2. Social Affinity
social_affinity AS (
    -- [Query de social_affinity.sql]
    SELECT post_id, social_affinity_score FROM ...
),

-- 3. Past Engagement
past_engagement AS (
    -- [Query de past_engagement.sql]
    SELECT post_id, past_engagement_score FROM ...
),

-- 4. Timing
timing AS (
    -- [Query de timing.sql]
    SELECT post_id, timing_score FROM ...
),

-- 5. Popularity
popularity AS (
    -- [Query de popularity.sql]
    SELECT post_id, popularity_score FROM ...
),

-- Combinar todos los scores
ranked_feed AS (
    SELECT
        p.id as post_id,
        p.user_id as author_id,
        p.post_type,
        p.caption,
        p.created_at,

        -- Scores individuales
        COALESCE(ca.content_affinity_score, 0.5) as content_affinity,
        COALESCE(sa.social_affinity_score, 0.3) as social_affinity,
        COALESCE(pe.past_engagement_score, 0.4) as past_engagement,
        COALESCE(t.timing_score, 0.5) as timing,
        COALESCE(pop.popularity_score, 0.3) as popularity,

        -- Score final ponderado
        (
            (COALESCE(ca.content_affinity_score, 0.5) * 0.25) +
            (COALESCE(sa.social_affinity_score, 0.3) * 0.25) +
            (COALESCE(pe.past_engagement_score, 0.4) * 0.15) +
            (COALESCE(t.timing_score, 0.5) * 0.15) +
            (COALESCE(pop.popularity_score, 0.3) * 0.20)
        ) as final_ranking_score

    FROM posts p
    LEFT JOIN content_affinity ca ON ca.post_id = p.id
    LEFT JOIN social_affinity sa ON sa.post_id = p.id
    LEFT JOIN past_engagement pe ON pe.post_id = p.id
    LEFT JOIN timing t ON t.post_id = p.id
    LEFT JOIN popularity pop ON pop.post_id = p.id

    WHERE p.gym_id = :gym_id
      AND p.is_deleted = false
      AND p.privacy = 'PUBLIC'
      AND p.created_at >= NOW() - INTERVAL '7 days'

      -- Excluir posts ya vistos por el usuario
      AND NOT EXISTS (
          SELECT 1 FROM post_views pv
          WHERE pv.post_id = p.id AND pv.user_id = :user_id
      )

      -- Excluir posts del propio usuario (opcional)
      AND p.user_id != :user_id
)

SELECT
    post_id,
    author_id,
    post_type,
    caption,
    created_at,

    -- Scores (útil para debugging)
    content_affinity,
    social_affinity,
    past_engagement,
    timing,
    popularity,
    final_ranking_score,

    -- Ranking position
    ROW_NUMBER() OVER (ORDER BY final_ranking_score DESC) as rank_position

FROM ranked_feed
ORDER BY final_ranking_score DESC
LIMIT :limit
OFFSET :offset;
```

---

### Implementación Python

```python
# app/services/feed_ranking_service.py

from typing import List, Dict
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.models.post import Post
from app.models.user import User

class FeedRankingService:
    """
    Servicio para rankear el feed de posts usando algoritmo multi-señal.
    """

    # Pesos del algoritmo (configurables)
    WEIGHTS = {
        "content_affinity": 0.25,
        "social_affinity": 0.25,
        "past_engagement": 0.15,
        "timing": 0.15,
        "popularity": 0.20
    }

    def __init__(self, db: Session):
        self.db = db

    async def get_ranked_feed(
        self,
        user_id: int,
        gym_id: int,
        limit: int = 20,
        offset: int = 0
    ) -> List[Dict]:
        """
        Obtiene feed rankeado para un usuario.

        Returns:
            Lista de posts con scores de ranking
        """
        # Query SQL completo (ver arriba)
        query = text("""
            -- [Query completo de final_ranking.sql]
        """)

        result = self.db.execute(query, {
            "user_id": user_id,
            "gym_id": gym_id,
            "limit": limit,
            "offset": offset
        }).fetchall()

        return [
            {
                "post_id": row[0],
                "author_id": row[1],
                "post_type": row[2],
                "caption": row[3],
                "created_at": row[4],
                "scores": {
                    "content_affinity": row[5],
                    "social_affinity": row[6],
                    "past_engagement": row[7],
                    "timing": row[8],
                    "popularity": row[9],
                    "final_score": row[10]
                },
                "rank_position": row[11]
            }
            for row in result
        ]

    def explain_ranking(self, post_id: int, user_id: int, gym_id: int) -> Dict:
        """
        Explica por qué un post fue rankeado de cierta manera.

        Útil para debugging y transparencia.
        """
        # Ejecutar queries individuales
        content_score = self._get_content_affinity(post_id, user_id, gym_id)
        social_score = self._get_social_affinity(post_id, user_id, gym_id)
        past_score = self._get_past_engagement(post_id, user_id, gym_id)
        timing_score = self._get_timing(post_id, user_id, gym_id)
        popularity_score = self._get_popularity(post_id, user_id, gym_id)

        final_score = (
            (content_score * self.WEIGHTS["content_affinity"]) +
            (social_score * self.WEIGHTS["social_affinity"]) +
            (past_score * self.WEIGHTS["past_engagement"]) +
            (timing_score * self.WEIGHTS["timing"]) +
            (popularity_score * self.WEIGHTS["popularity"])
        )

        return {
            "post_id": post_id,
            "final_score": round(final_score, 3),
            "breakdown": {
                "content_affinity": {
                    "score": round(content_score, 3),
                    "weight": self.WEIGHTS["content_affinity"],
                    "contribution": round(content_score * self.WEIGHTS["content_affinity"], 3),
                    "explanation": "Qué tanto coincide con tus intereses fitness"
                },
                "social_affinity": {
                    "score": round(social_score, 3),
                    "weight": self.WEIGHTS["social_affinity"],
                    "contribution": round(social_score * self.WEIGHTS["social_affinity"], 3),
                    "explanation": "Tu relación con el autor del post"
                },
                "past_engagement": {
                    "score": round(past_score, 3),
                    "weight": self.WEIGHTS["past_engagement"],
                    "contribution": round(past_score * self.WEIGHTS["past_engagement"], 3),
                    "explanation": "Tu historial con contenido similar"
                },
                "timing": {
                    "score": round(timing_score, 3),
                    "weight": self.WEIGHTS["timing"],
                    "contribution": round(timing_score * self.WEIGHTS["timing"], 3),
                    "explanation": "Qué tan reciente es el post"
                },
                "popularity": {
                    "score": round(popularity_score, 3),
                    "weight": self.WEIGHTS["popularity"],
                    "contribution": round(popularity_score * self.WEIGHTS["popularity"], 3),
                    "explanation": "Qué tan popular es el post"
                }
            }
        }
```

---

### Endpoint de API

```python
# app/api/v1/endpoints/posts.py

@router.get("/feed/ranked", response_model=PostFeedResponse)
async def get_ranked_feed(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    gym_id: int = Depends(get_current_gym_id),
    db: Session = Depends(get_db)
):
    """
    Feed de posts rankeado con algoritmo multi-señal.

    Muestra posts ordenados por relevancia personalizada usando:
    - Content affinity: Qué tanto coincide con tus intereses
    - Social affinity: Relación con el autor
    - Past engagement: Tu historial de engagement
    - Timing: Recency del post
    - Popularity: Qué tan popular es
    """
    ranking_service = FeedRankingService(db)

    ranked_posts = await ranking_service.get_ranked_feed(
        user_id=current_user.id,
        gym_id=gym_id,
        limit=limit,
        offset=offset
    )

    # Enriquecer con datos completos del post
    post_ids = [p["post_id"] for p in ranked_posts]
    posts = db.query(Post).filter(Post.id.in_(post_ids)).all()

    # Mantener orden del ranking
    posts_map = {p.id: p for p in posts}
    ordered_posts = [posts_map[p["post_id"]] for p in ranked_posts if p["post_id"] in posts_map]

    # Enriquecer posts con metadata del usuario
    enriched_posts = [
        enrich_post(post, current_user.id, db)
        for post in ordered_posts
    ]

    return PostFeedResponse(
        posts=enriched_posts,
        total=len(ranked_posts),
        limit=limit,
        offset=offset,
        has_more=len(ranked_posts) == limit,
        ranking_method="multi_signal_v1"
    )


@router.get("/feed/ranked/{post_id}/explain", response_model=RankingExplanation)
async def explain_post_ranking(
    post_id: int,
    current_user: User = Depends(get_current_user),
    gym_id: int = Depends(get_current_gym_id),
    db: Session = Depends(get_db)
):
    """
    Explica por qué un post fue rankeado de cierta manera.

    Útil para debugging y transparencia con usuarios.
    """
    ranking_service = FeedRankingService(db)

    explanation = ranking_service.explain_ranking(
        post_id=post_id,
        user_id=current_user.id,
        gym_id=gym_id
    )

    return explanation
```

---

## Features para Machine Learning

Si queremos avanzar hacia un modelo de ML más sofisticado, necesitamos preparar features estructuradas.

### Feature Vector Completo

```python
# app/ml/feature_engineering.py

class FeatureEngineering:
    """
    Genera features para modelos de ML de ranking de feed.
    """

    @staticmethod
    def extract_features(
        user_id: int,
        post_id: int,
        gym_id: int,
        db: Session
    ) -> np.array:
        """
        Extrae vector de features para par (usuario, post).

        Returns:
            Array de 50+ features numéricas
        """
        features = []

        # 1. USUARIO FEATURES (20 features)
        user_profile = get_user_profile(user_id, gym_id, db)

        features.extend([
            user_profile["activity_level"]["metrics"]["weekly_classes"],
            user_profile["activity_level"]["metrics"]["app_opens_monthly"],
            user_profile["activity_level"]["metrics"]["current_streak_days"],
            user_profile["social_profile"]["score"],
            user_profile["aggregate_scores"]["activity_score"],
            user_profile["aggregate_scores"]["social_score"],
            user_profile["aggregate_scores"]["commitment_score"],
            # ... más features de usuario
        ])

        # 2. POST FEATURES (15 features)
        post = db.query(Post).filter(Post.id == post_id).first()

        features.extend([
            post.like_count,
            post.comment_count,
            post.view_count,
            (post.like_count + post.comment_count) / max(post.view_count, 1),  # engagement_rate
            (datetime.utcnow() - post.created_at).total_seconds() / 3600.0,  # age_hours
            len(post.caption) if post.caption else 0,
            len(post.media) if post.media else 0,
            post.post_type == PostType.WORKOUT,  # one-hot encoded
            post.post_type == PostType.GALLERY,
            post.post_type == PostType.VIDEO,
            # ... más features de post
        ])

        # 3. USER-POST INTERACTION FEATURES (10 features)
        author_id = post.user_id

        # ¿Ha interactuado con este autor antes?
        has_interacted = db.query(PostLike).filter(
            PostLike.user_id == user_id,
            PostLike.post_id.in_(
                db.query(Post.id).filter(Post.user_id == author_id)
            )
        ).count() > 0

        # ¿Mismo trainer?
        same_trainer = db.query(TrainerMemberRelationship).filter(
            TrainerMemberRelationship.trainer_id.in_(
                db.query(TrainerMemberRelationship.trainer_id).filter(
                    TrainerMemberRelationship.member_id == user_id
                )
            ),
            TrainerMemberRelationship.member_id == author_id
        ).count() > 0

        features.extend([
            int(has_interacted),
            int(same_trainer),
            # ... más interaction features
        ])

        # 4. TEMPORAL FEATURES (5 features)
        now = datetime.utcnow()

        features.extend([
            now.hour,
            now.weekday(),
            int(now.weekday() >= 5),  # is_weekend
            # ... más temporal features
        ])

        return np.array(features, dtype=np.float32)
```

---

### Dataset para Training

```sql
-- Crear dataset de training

CREATE TABLE ml_feed_training_data AS

WITH user_post_pairs AS (
    -- Generar pares (user, post) con label
    SELECT
        u.id as user_id,
        p.id as post_id,
        p.gym_id,

        -- LABEL: ¿El usuario interactuó con este post?
        CASE
            WHEN pl.id IS NOT NULL OR pc.id IS NOT NULL THEN 1
            ELSE 0
        END as label_engaged,

        -- Timestamp de cuando el post fue mostrado/disponible
        p.created_at as post_created_at

    FROM user u
    CROSS JOIN posts p  -- Todos los pares posibles
    LEFT JOIN post_likes pl ON pl.post_id = p.id AND pl.user_id = u.id
    LEFT JOIN post_comments pc ON pc.post_id = p.id AND pc.user_id = u.id

    WHERE p.gym_id = u.gym_id  -- Mismo gym
      AND p.created_at >= NOW() - INTERVAL '90 days'  -- Posts recientes
      AND p.created_at <= u.created_at  -- Post creado después de que usuario se unió
      AND p.privacy = 'PUBLIC'
      AND p.is_deleted = false
      AND p.user_id != u.id  -- No incluir posts propios
)

SELECT
    user_id,
    post_id,
    gym_id,
    label_engaged,
    post_created_at,

    -- Features se calcularán en Python usando FeatureEngineering

FROM user_post_pairs

-- Balance de clases (1:10 ratio negativo:positivo)
-- Tomar todos los positivos + sample de negativos
WHERE label_engaged = 1
   OR (label_engaged = 0 AND RANDOM() < 0.1);
```

---

### Modelo de ML (RandomForest)

```python
# app/ml/ranking_model.py

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
import pickle

class FeedRankingModel:
    """
    Modelo de ML para predecir probabilidad de engagement.
    """

    FEATURE_NAMES = [
        # Usuario (20)
        "user_weekly_classes",
        "user_app_opens_monthly",
        "user_current_streak",
        "user_social_score",
        "user_activity_score",
        # ... etc

        # Post (15)
        "post_like_count",
        "post_comment_count",
        "post_view_count",
        "post_engagement_rate",
        "post_age_hours",
        # ... etc

        # Interaction (10)
        "has_interacted_with_author",
        "same_trainer",
        # ... etc

        # Temporal (5)
        "hour_of_day",
        "day_of_week",
        # ... etc
    ]

    def __init__(self):
        self.model = RandomForestClassifier(
            n_estimators=200,
            max_depth=15,
            min_samples_split=50,
            min_samples_leaf=20,
            random_state=42,
            n_jobs=-1
        )
        self.is_trained = False

    def train(self, X_train, y_train, X_test, y_test):
        """
        Entrena el modelo.
        """
        print(f"Training RandomForest with {len(X_train)} samples...")

        self.model.fit(X_train, y_train)

        # Validación
        y_pred = self.model.predict(X_test)
        y_pred_proba = self.model.predict_proba(X_test)[:, 1]

        from sklearn.metrics import precision_score, recall_score, roc_auc_score

        metrics = {
            "precision": precision_score(y_test, y_pred),
            "recall": recall_score(y_test, y_pred),
            "roc_auc": roc_auc_score(y_test, y_pred_proba)
        }

        print(f"Validation metrics: {metrics}")

        self.is_trained = True
        return metrics

    def predict_engagement_probability(self, features: np.array) -> float:
        """
        Predice probabilidad de que usuario interactúe con post.

        Returns:
            Probabilidad 0-1
        """
        if not self.is_trained:
            raise ValueError("Model not trained")

        proba = self.model.predict_proba(features.reshape(1, -1))[0, 1]
        return float(proba)

    def get_feature_importance(self) -> Dict[str, float]:
        """
        Retorna importancia de cada feature.
        """
        importances = self.model.feature_importances_
        return dict(zip(self.FEATURE_NAMES, importances))

    def save(self, filepath: str):
        """Guarda modelo en disco"""
        with open(filepath, "wb") as f:
            pickle.dump(self.model, f)

    def load(self, filepath: str):
        """Carga modelo desde disco"""
        with open(filepath, "rb") as f:
            self.model = pickle.load(f)
        self.is_trained = True
```

---

## Gaps y Oportunidades

### Datos Faltantes Críticos

#### 1. Post Views Tracking

**CRÍTICO:** No sabemos qué posts ya vio cada usuario.

```sql
CREATE TABLE post_views (
    id SERIAL PRIMARY KEY,
    post_id INTEGER REFERENCES posts(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES user(id),
    gym_id INTEGER REFERENCES gyms(id),

    -- Engagement metrics
    view_duration_seconds INTEGER,
    scroll_depth FLOAT,  -- 0-1 (% del post visto)
    clicked_media BOOLEAN DEFAULT false,
    clicked_profile BOOLEAN DEFAULT false,

    -- Context
    device_type VARCHAR(20),
    referrer VARCHAR(50),  -- feed, profile, hashtag, notification

    viewed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE (post_id, user_id),
    INDEX idx_post_views_user (user_id, viewed_at),
    INDEX idx_post_views_post (post_id, viewed_at)
);
```

**Uso:**
- ✅ No repetir posts en el feed
- ✅ Medir view_duration (engagement real)
- ✅ A/B testing (qué posts generan más clicks)

---

#### 2. Sistema de Follows/Followers

**ALTO IMPACTO:** Priorizar posts de usuarios que sigue.

```sql
CREATE TABLE user_follows (
    id SERIAL PRIMARY KEY,
    follower_id INTEGER REFERENCES user(id),
    followed_id INTEGER REFERENCES user(id),
    gym_id INTEGER REFERENCES gyms(id),

    is_active BOOLEAN DEFAULT true,
    is_close_friend BOOLEAN DEFAULT false,

    notify_posts BOOLEAN DEFAULT true,
    notify_stories BOOLEAN DEFAULT true,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    unfollowed_at TIMESTAMP WITH TIME ZONE,

    UNIQUE (follower_id, followed_id, gym_id),
    INDEX idx_follows_follower (follower_id),
    INDEX idx_follows_followed (followed_id)
);
```

**Uso:**
- ✅ Boost posts de usuarios que sigo
- ✅ Stories de close friends
- ✅ Notificaciones personalizadas
- ✅ Social affinity score mejorado

---

#### 3. Exercise Tracking Granular

**MEDIO IMPACTO:** Matching preciso de posts WORKOUT.

```sql
CREATE TABLE user_exercise_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES user(id),
    gym_id INTEGER REFERENCES gyms(id),

    exercise_name VARCHAR(100) NOT NULL,
    exercise_category VARCHAR(50),  -- strength, cardio, flexibility

    weight_kg FLOAT,
    reps INTEGER,
    sets INTEGER,
    duration_minutes INTEGER,
    distance_km FLOAT,

    session_id INTEGER REFERENCES class_session(id),
    is_personal_record BOOLEAN DEFAULT false,

    logged_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    INDEX idx_exercise_user_date (user_id, logged_at),
    INDEX idx_exercise_name (exercise_name)
);
```

**Uso:**
- ✅ Recomendar posts sobre ejercicios que hace
- ✅ Detectar PRs automáticamente
- ✅ Content affinity más preciso

---

#### 4. Search History

**BAJO IMPACTO:** Recomendar basado en búsquedas.

```sql
CREATE TABLE user_search_history (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES user(id),
    gym_id INTEGER REFERENCES gyms(id),

    query VARCHAR(200),
    search_type VARCHAR(50),  -- users, posts, classes, hashtags

    results_count INTEGER,
    clicked_result_id INTEGER,
    clicked_result_type VARCHAR(50),

    searched_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    INDEX idx_search_user_date (user_id, searched_at)
);
```

**Uso:**
- ✅ Recomendar contenido basado en búsquedas
- ✅ Trending searches

---

#### 5. Saved Posts/Bookmarks

**MEDIO IMPACTO:** Señal fuerte de interés.

```sql
CREATE TABLE user_saved_posts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES user(id),
    post_id INTEGER REFERENCES posts(id) ON DELETE CASCADE,

    collection_name VARCHAR(100),  -- "Workout Ideas", "Recipes"

    saved_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE (user_id, post_id),
    INDEX idx_saved_user (user_id, saved_at)
);
```

**Uso:**
- ✅ Señal MUY fuerte de interés en ese contenido
- ✅ Recomendar posts similares a los guardados

---

### Mejoras en Datos Existentes

#### 1. Enriquecer `workout_data` en Posts

```python
# Estructura JSON mejorada
workout_data = {
    "exercises": [
        {
            "name": "Bench Press",
            "category": "strength",
            "muscle_groups": ["chest", "triceps", "shoulders"],
            "sets": 4,
            "reps": 8,
            "weight_kg": 100,
            "rest_seconds": 90,
            "notes": "Felt strong"
        }
    ],
    "total_duration_minutes": 60,
    "total_volume_kg": 4200,
    "workout_type": "push",  # push, pull, legs, upper, lower
    "difficulty_felt": 7,  # 1-10
    "personal_records": [
        {"exercise": "Bench Press", "new_record": 100}
    ]
}
```

---

#### 2. Sentiment Analysis

```sql
-- Agregar a tablas existentes
ALTER TABLE post_comments ADD COLUMN sentiment_score FLOAT;  -- -1 a 1
ALTER TABLE survey_answers ADD COLUMN sentiment_score FLOAT;
```

---

## Roadmap de Implementación

### Fase 1: Mejoras Rápidas (1-2 semanas) ✅ RECOMENDADO

**Objetivo:** Mejorar ranking con features existentes

1. ✅ Implementar `content_affinity_score`
2. ✅ Implementar `social_affinity_score`
3. ✅ Implementar `timing_score` mejorado
4. ✅ Nuevo endpoint `/feed/ranked`
5. ✅ A/B testing framework básico

**Esfuerzo:** Bajo | **Impacto:** Alto

---

### Fase 2: Post Views + Follows (2-3 semanas)

**Objetivo:** Agregar tracking crítico

1. ✅ Crear tabla `post_views`
2. ✅ Implementar tracking en endpoints
3. ✅ Crear tabla `user_follows`
4. ✅ Endpoints de follow/unfollow
5. ✅ Actualizar `social_affinity` con follows

**Esfuerzo:** Medio | **Impacto:** Muy Alto

---

### Fase 3: User Profiles + ML Básico (4-6 semanas)

**Objetivo:** Perfilado completo + ML

1. ✅ Crear vista materializada `user_profiles`
2. ✅ Feature engineering completo
3. ✅ Dataset de training
4. ✅ Modelo RandomForest inicial
5. ✅ A/B testing ML vs heurístico

**Esfuerzo:** Alto | **Impacto:** Alto

---

### Fase 4: ML Avanzado (3-6 meses) 🚀

**Objetivo:** Sistema de recomendación de última generación

1. ✅ Collaborative filtering
2. ✅ Deep learning (opcional)
3. ✅ Real-time personalization
4. ✅ Multi-armed bandits
5. ✅ Feature store dedicado

**Esfuerzo:** Muy Alto | **Impacto:** Muy Alto

---

## Anexos

### A. Ejemplo de Uso Completo

```python
# Ejemplo de flujo completo

# 1. Usuario abre la app
user_id = 123
gym_id = 4

# 2. Obtener perfil del usuario
profile_service = UserProfileService(db)
user_profile = profile_service.get_user_profile(user_id, gym_id)

print(f"Usuario: {user_id}")
print(f"Nivel de actividad: {user_profile['activity_level']['classification']}")
print(f"Interés principal: {user_profile['fitness_interests']['primary_category']}")
print(f"Social score: {user_profile['social_profile']['score']}")

# 3. Obtener feed rankeado
ranking_service = FeedRankingService(db)
ranked_posts = await ranking_service.get_ranked_feed(
    user_id=user_id,
    gym_id=gym_id,
    limit=20
)

print(f"\nFeed rankeado (top 5):")
for i, post in enumerate(ranked_posts[:5], 1):
    print(f"{i}. Post #{post['post_id']} - Score: {post['scores']['final_score']:.3f}")
    print(f"   Content: {post['scores']['content_affinity']:.2f} | "
          f"Social: {post['scores']['social_affinity']:.2f} | "
          f"Timing: {post['scores']['timing']:.2f}")

# 4. Explicar ranking de un post específico
explanation = ranking_service.explain_ranking(
    post_id=ranked_posts[0]['post_id'],
    user_id=user_id,
    gym_id=gym_id
)

print(f"\n¿Por qué veo este post primero?")
for component, data in explanation['breakdown'].items():
    print(f"- {data['explanation']}: {data['score']:.2f} "
          f"(contribución: {data['contribution']:.3f})")
```

---

### B. Configuración de Pesos

Los pesos del algoritmo son configurables según las prioridades del negocio:

```python
# config/ranking_weights.py

RANKING_WEIGHTS = {
    # DEFAULT: Balance entre relevancia y social
    "default": {
        "content_affinity": 0.25,
        "social_affinity": 0.25,
        "past_engagement": 0.15,
        "timing": 0.15,
        "popularity": 0.20
    },

    # SOCIAL_FIRST: Priorizar conexiones sociales
    "social_first": {
        "content_affinity": 0.20,
        "social_affinity": 0.35,
        "past_engagement": 0.15,
        "timing": 0.10,
        "popularity": 0.20
    },

    # CONTENT_FIRST: Priorizar relevancia de contenido
    "content_first": {
        "content_affinity": 0.35,
        "social_affinity": 0.20,
        "past_engagement": 0.20,
        "timing": 0.10,
        "popularity": 0.15
    },

    # TRENDING: Priorizar contenido viral
    "trending": {
        "content_affinity": 0.20,
        "social_affinity": 0.15,
        "past_engagement": 0.10,
        "timing": 0.20,
        "popularity": 0.35
    },

    # FRESH: Priorizar contenido reciente
    "fresh": {
        "content_affinity": 0.20,
        "social_affinity": 0.20,
        "past_engagement": 0.10,
        "timing": 0.35,
        "popularity": 0.15
    }
}

# Usar en el servicio
ranking_service = FeedRankingService(
    db=db,
    weights=RANKING_WEIGHTS["social_first"]
)
```

---

### C. Métricas de Éxito

```python
# app/services/metrics_service.py

class FeedMetricsService:
    """
    Calcula métricas de éxito del feed.
    """

    def calculate_feed_engagement(self, gym_id: int, days: int = 7) -> Dict:
        """
        Calcula métricas agregadas del feed.
        """
        query = text("""
        WITH feed_stats AS (
            SELECT
                COUNT(DISTINCT pv.user_id) as active_users,
                COUNT(DISTINCT pv.post_id) as posts_viewed,
                AVG(pv.view_duration_seconds) as avg_view_duration,

                COUNT(DISTINCT pl.user_id) as users_who_liked,
                COUNT(DISTINCT pc.user_id) as users_who_commented,

                COUNT(DISTINCT pl.id) as total_likes,
                COUNT(DISTINCT pc.id) as total_comments

            FROM post_views pv
            LEFT JOIN post_likes pl ON pl.post_id = pv.post_id AND pl.user_id = pv.user_id
            LEFT JOIN post_comments pc ON pc.post_id = pv.post_id AND pc.user_id = pv.user_id
            WHERE pv.gym_id = :gym_id
              AND pv.viewed_at >= NOW() - INTERVAL ':days days'
        )
        SELECT
            active_users,
            posts_viewed,
            ROUND(avg_view_duration::numeric, 2) as avg_view_duration_seconds,

            -- Engagement rate
            ROUND((users_who_liked * 100.0 / active_users)::numeric, 2) as like_rate_pct,
            ROUND((users_who_commented * 100.0 / active_users)::numeric, 2) as comment_rate_pct,

            -- Averages
            ROUND((total_likes * 1.0 / posts_viewed)::numeric, 2) as avg_likes_per_post,
            ROUND((total_comments * 1.0 / posts_viewed)::numeric, 2) as avg_comments_per_post

        FROM feed_stats
        """)

        result = db.execute(query, {"gym_id": gym_id, "days": days}).fetchone()

        return {
            "active_users": result[0],
            "posts_viewed": result[1],
            "avg_view_duration_seconds": result[2],
            "like_rate_pct": result[3],
            "comment_rate_pct": result[4],
            "avg_likes_per_post": result[5],
            "avg_comments_per_post": result[6]
        }
```

---

## Conclusión

Este documento presenta un sistema completo de perfilado de usuarios y ranking de feed que:

✅ **Utiliza todos los datos disponibles** en GymApi
✅ **Personaliza el feed** para cada usuario
✅ **Maximiza el engagement** con algoritmo multi-señal
✅ **Es escalable** (puede evolucionar a ML)
✅ **Es explicable** (sabemos por qué cada post está rankeado)

**Próximo paso recomendado:** Implementar **Fase 1** (mejoras rápidas con features existentes) para validar el enfoque antes de invertir en ML.

---

**Fin del documento**
