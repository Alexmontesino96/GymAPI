# Sistema de Logros (Achievements)

## Índice
- [Descripción General](#descripción-general)
- [Modelo de Datos](#modelo-de-datos)
- [Tipos de Logros](#tipos-de-logros)
- [Sistema de Rareza](#sistema-de-rareza)
- [Cálculo Automático](#cálculo-automático)
- [Integración con Activity Feed](#integración-con-activity-feed)
- [Ejemplos de Uso](#ejemplos-de-uso)

---

## Descripción General

El **Sistema de Achievements** es un mecanismo de **gamificación** que recompensa automáticamente a los usuarios por:
- ✅ Asistencia consistente al gimnasio
- 💪 Completar metas de salud
- 📈 Alcanzar hitos de clases
- 🔥 Mantener rachas de entrenamiento
- 🏆 Logros sociales y de rendimiento

### Características Principales

- **Automático**: Los logros se otorgan sin intervención manual
- **Multi-tenant**: Cada gimnasio tiene sus propios logros
- **Niveles de Rareza**: Common, Rare, Epic, Legendary
- **Puntos**: Sistema de puntos para ranking
- **Iconos**: Cada logro tiene un emoji/icono visual

---

## Modelo de Datos

### Tabla: `user_achievements`

```python
class UserAchievement(Base):
    __tablename__ = "user_achievements"

    # Identificación
    id: int                          # PK
    user_id: int                     # FK a user
    gym_id: int                      # FK a gyms (multi-tenant)

    # Definición del logro
    achievement_type: AchievementType  # Tipo de logro
    title: str                         # "🔥 Racha de 7 Días"
    description: str                   # "Has entrenado 7 días seguidos"
    icon: str                          # "🔥" (emoji o código)

    # Datos del logro
    value: float                       # Valor numérico (7 días, 10kg, etc.)
    unit: str                          # "días", "kg", "clases"
    rarity: str                        # "common", "rare", "epic", "legendary"

    # Metadata
    earned_at: datetime                # Cuándo se obtuvo
    is_milestone: bool                 # Si es un hito importante
    points_awarded: int                # Puntos otorgados (10-100)

    created_at: datetime
```

### Relaciones

```python
# En User model
user.achievements → List[UserAchievement]

# En Gym model (implícito)
gym.id → user_achievements.gym_id
```

---

## Tipos de Logros

### Enum: `AchievementType`

```python
class AchievementType(str, enum.Enum):
    # 1. Rachas de Asistencia
    ATTENDANCE_STREAK = "attendance_streak"
    # Ejemplos: 3, 7, 14, 30, 60, 90, 180, 365 días consecutivos

    # 2. Metas de Peso
    WEIGHT_GOAL = "weight_goal"
    # Se otorga automáticamente al completar un UserGoal de tipo peso

    # 3. Hitos de Clases
    CLASS_MILESTONE = "class_milestone"
    # Ejemplos: 10, 25, 50, 100, 250, 500 clases completadas

    # 4. Participación Social
    SOCIAL_ENGAGEMENT = "social_engagement"
    # Interacciones en posts, stories, comentarios

    # 5. Ganancia de Fuerza
    STRENGTH_GAIN = "strength_gain"
    # Basado en progreso en ejercicios de fuerza

    # 6. Hitos de Resistencia
    ENDURANCE_MILESTONE = "endurance_milestone"
    # Basado en ejercicios cardiovasculares

    # 7. Consistencia General
    CONSISTENCY = "consistency"
    # Asistencia regular durante periodos largos
```

---

## Sistema de Rareza

### Niveles de Rareza

| Nivel | Descripción | Puntos | Color | Icono |
|-------|-------------|--------|-------|-------|
| **Common** | Logros básicos y frecuentes | 10 | Gris | ⚪ |
| **Rare** | Logros que requieren esfuerzo | 25 | Azul | 🔵 |
| **Epic** | Logros difíciles de conseguir | 50 | Morado | 🟣 |
| **Legendary** | Logros extremadamente raros | 100 | Dorado | 🟡 |

### Ejemplos por Rareza

```python
# Common (10 puntos)
"Primera Clase Completada"        # CLASS_MILESTONE: 1 clase
"Racha de 3 Días"                 # ATTENDANCE_STREAK: 3 días

# Rare (25 puntos)
"Guerrero de 10 Clases"           # CLASS_MILESTONE: 10 clases
"Semana Perfecta"                 # ATTENDANCE_STREAK: 7 días
"Meta de Peso Alcanzada"          # WEIGHT_GOAL: completó objetivo

# Epic (50 puntos)
"Atleta de 100 Clases"            # CLASS_MILESTONE: 100 clases
"Mes Imparable"                   # ATTENDANCE_STREAK: 30 días
"Transformación Completa"         # WEIGHT_GOAL: objetivo > 10kg

# Legendary (100 puntos)
"Leyenda de 500 Clases"           # CLASS_MILESTONE: 500 clases
"Año Inquebrantable"              # ATTENDANCE_STREAK: 365 días
"Campeón de Consistencia"         # CONSISTENCY: 90% asistencia 6 meses
```

---

## Cálculo Automático

### 1. Racha de Asistencia (`ATTENDANCE_STREAK`)

**Método:** `_check_attendance_streak_achievements()`

**Lógica:**
```python
# 1. Obtiene asistencias de últimos 30 días
# 2. Calcula racha actual (días consecutivos)
# 3. Verifica hitos: [3, 7, 14, 30, 60, 90, 180, 365]
# 4. Crea logro si alcanza hito y no existe

# Ejemplo de racha actual:
today = 2025-12-20
attendance_dates = [
    2025-12-20,  # Hoy
    2025-12-19,  # Ayer
    2025-12-18,  # Anteayer
    # ... días consecutivos
]

current_streak = 7  # 7 días seguidos
→ Se otorga "🔥 Racha de 7 Días" (Rare, 25 puntos)
```

**Hitos Configurados:**
```python
streak_milestones = [3, 7, 14, 30, 60, 90, 180, 365]

# 3 días    → Common    (10 pts)  "🔥 Racha de 3 Días"
# 7 días    → Rare      (25 pts)  "🔥 Racha de 7 Días"
# 14 días   → Rare      (25 pts)  "🔥 Racha de 14 Días"
# 30 días   → Epic      (50 pts)  "🔥 Mes Imparable"
# 60 días   → Epic      (50 pts)  "🔥 Dos Meses Consecutivos"
# 90 días   → Epic      (50 pts)  "🔥 Trimestre Perfecto"
# 180 días  → Legendary (100 pts) "🔥 Medio Año de Fuego"
# 365 días  → Legendary (100 pts) "🔥 Año Inquebrantable"
```

**Creación del Logro:**
```python
achievement = UserAchievement(
    user_id=user_id,
    gym_id=gym_id,
    achievement_type=AchievementType.ATTENDANCE_STREAK,
    title=f"🔥 Racha de {current_streak} Días",
    description=f"Has entrenado {current_streak} días consecutivos. ¡Imparable!",
    icon="🔥",
    value=current_streak,
    unit="días",
    rarity="rare",              # Basado en el hito
    is_milestone=True,
    points_awarded=25           # Basado en rareza
)
```

---

### 2. Hitos de Clases (`CLASS_MILESTONE`)

**Método:** `_check_class_milestone_achievements()`

**Lógica:**
```python
# 1. Cuenta total de clases asistidas del usuario
# 2. Verifica hitos: [10, 25, 50, 100, 250, 500]
# 3. Crea logro si alcanza hito y no existe

total_classes = 50  # Usuario ha asistido a 50 clases

→ Se otorgan 3 logros:
   - "🎯 10 Clases Completadas" (Common)
   - "🎯 25 Clases Completadas" (Rare)
   - "🎯 50 Clases Completadas" (Epic)
```

**Hitos Configurados:**
```python
class_milestones = [10, 25, 50, 100, 250, 500]

# 10 clases   → Common    (10 pts)  "🎯 Guerrero de 10 Clases"
# 25 clases   → Rare      (25 pts)  "🎯 Atleta de 25 Clases"
# 50 clases   → Epic      (50 pts)  "🎯 Profesional de 50 Clases"
# 100 clases  → Epic      (50 pts)  "🏆 Centurión de las Clases"
# 250 clases  → Legendary (100 pts) "🏆 Maestro de 250 Clases"
# 500 clases  → Legendary (100 pts) "🏆 Leyenda de 500 Clases"
```

---

### 3. Metas de Peso (`WEIGHT_GOAL`)

**Método:** `_create_goal_achievement()` (se llama desde `update_goal_progress()`)

**Lógica:**
```python
# Se dispara automáticamente cuando:
# 1. Un UserGoal se marca como completado
# 2. El tipo de goal es de peso (WEIGHT_LOSS o WEIGHT_GAIN)

# Ejemplo: Meta de perder 10kg
goal = UserGoal(
    goal_type=GoalType.WEIGHT_LOSS,
    start_value=90.0,  # kg
    target_value=80.0,  # kg
    current_value=80.0  # Alcanzado!
)

→ Se otorga logro automático:
achievement = UserAchievement(
    achievement_type=AchievementType.WEIGHT_GOAL,
    title="Meta Alcanzada: Perder 10kg",
    description="¡Has perdido 10.0 kg!",
    icon="⚖️",
    value=10.0,
    unit="kg",
    rarity="epic",        # Epic si > 5kg
    is_milestone=True,
    points_awarded=50
)
```

**Rareza basada en magnitud:**
```python
weight_change = abs(goal.current_value - goal.start_value)

if weight_change >= 20:
    rarity = "legendary"  # 100 puntos
elif weight_change >= 10:
    rarity = "epic"       # 50 puntos
elif weight_change >= 5:
    rarity = "rare"       # 25 puntos
else:
    rarity = "common"     # 10 puntos
```

---

## Cómo se Disparan los Logros

### 1. **Manualmente (API Call)**

```python
from app.services.health import UserHealthService

health_service = UserHealthService()

# Verificar y crear achievements
new_achievements = health_service.check_and_create_achievements(
    db=db,
    user_id=user_id,
    gym_id=gym_id
)

# Devuelve lista de nuevos achievements creados
for achievement in new_achievements:
    print(f"🎉 Nuevo logro: {achievement.title}")
```

**Endpoints que deberían llamar esto:**
- `POST /api/v1/schedule/participation/checkin` - Después de check-in
- `POST /api/v1/schedule/participation/{id}/attendance` - Al marcar asistencia
- Cualquier operación que afecte la racha de asistencia

---

### 2. **Automáticamente (al completar Goals)**

```python
# En: update_goal_progress()
if is_completed:
    goal.status = GoalStatus.COMPLETED
    goal.completed_at = datetime.utcnow()

    # Crear achievement automáticamente
    self._create_goal_achievement(db, goal)

    db.commit()
```

**Endpoints que disparan esto:**
- `PUT /api/v1/health/goals/{goal_id}/progress` - Actualizar progreso de meta
- `POST /api/v1/health/records` - Al registrar nueva medición de peso

---

### 3. **Scheduled Jobs (Futuros)**

```python
# Job diario: Verificar achievements para todos los usuarios activos
@scheduler.scheduled_job('cron', hour=23, minute=50)
async def daily_achievement_check():
    """Verifica achievements para usuarios activos del día."""

    active_users = get_active_users_today()

    for user in active_users:
        new_achievements = health_service.check_and_create_achievements(
            db=db,
            user_id=user.id,
            gym_id=user.gym_id
        )

        # Notificar al usuario de nuevos achievements
        if new_achievements:
            send_achievement_notification(user, new_achievements)
```

---

## Integración con Activity Feed

Cuando se otorga un achievement, se puede publicar en el Activity Feed **de forma anónima**:

```python
# En el endpoint después de crear achievement
from app.services.activity_aggregator import ActivityAggregator

aggregator = ActivityAggregator(feed_service, db)

await aggregator.on_achievement_unlocked({
    "gym_id": gym_id,
    "achievement_type": achievement.achievement_type.value,
    "achievement_level": achievement.rarity
})

# Esto incrementa contadores:
# - gym:{gym_id}:daily:achievements_count
# - gym:{gym_id}:daily:achievements:{type}

# Y publica al feed cada 3 logros:
# "⭐ 3 logros desbloqueados hoy"
# "⭐ 6 logros desbloqueados hoy"
# etc.
```

**Importante:** El Activity Feed **NO expone nombres de usuarios**. Solo muestra:
- ✅ "⭐ 12 logros desbloqueados hoy" (cantidad agregada)
- ❌ "Juan Pérez desbloqueó un logro" (nombre individual)

---

## Ejemplos de Uso

### Ejemplo 1: Check-in a Clase + Verificar Achievements

```python
@router.post("/schedule/participation/checkin")
async def checkin_to_class(
    session_id: int,
    db: Session = Depends(get_db),
    gym_id: int = Depends(get_tenant_id),
    user_id: int = Depends(get_current_user_id),
    redis: Redis = Depends(get_redis_client)
):
    # 1. Procesar check-in normal
    participation = create_participation(db, session_id, user_id)

    # 2. Verificar achievements
    from app.services.health import UserHealthService
    health_service = UserHealthService()

    new_achievements = health_service.check_and_create_achievements(
        db=db,
        user_id=user_id,
        gym_id=gym_id
    )

    # 3. Publicar en Activity Feed si hay nuevos achievements
    if new_achievements:
        from app.services.activity_aggregator import ActivityAggregator
        from app.services.activity_feed_service import ActivityFeedService

        feed_service = ActivityFeedService(redis)
        aggregator = ActivityAggregator(feed_service, db)

        for achievement in new_achievements:
            await aggregator.on_achievement_unlocked({
                "gym_id": gym_id,
                "achievement_type": achievement.achievement_type.value,
                "achievement_level": achievement.rarity
            })

    return {
        "participation": participation,
        "new_achievements": [
            {
                "title": a.title,
                "description": a.description,
                "icon": a.icon,
                "points": a.points_awarded,
                "rarity": a.rarity
            }
            for a in new_achievements
        ]
    }
```

**Response:**
```json
{
  "participation": {...},
  "new_achievements": [
    {
      "title": "🔥 Racha de 7 Días",
      "description": "Has entrenado 7 días consecutivos. ¡Imparable!",
      "icon": "🔥",
      "points": 25,
      "rarity": "rare"
    }
  ]
}
```

---

### Ejemplo 2: Completar Meta de Peso

```python
@router.post("/health/records")
async def record_weight(
    weight: float,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
    gym_id: int = Depends(get_tenant_id)
):
    from app.services.health import UserHealthService
    health_service = UserHealthService()

    # 1. Registrar medición
    record = health_service.record_measurement(
        db=db,
        user_id=user_id,
        gym_id=gym_id,
        weight=weight
    )

    # 2. Actualizar progreso de goals activos
    active_goals = health_service.get_active_goals(db, user_id, gym_id)

    completed_goals = []
    for goal in active_goals:
        if goal.goal_type in [GoalType.WEIGHT_LOSS, GoalType.WEIGHT_GAIN]:
            # Actualiza y verifica si se completó
            updated_goal = health_service.update_goal_progress(
                db=db,
                goal_id=goal.id,
                current_value=weight
            )

            if updated_goal.status == GoalStatus.COMPLETED:
                completed_goals.append(updated_goal)
                # ✅ Achievement automático ya creado en update_goal_progress()

    return {
        "record": record,
        "completed_goals": completed_goals
    }
```

---

### Ejemplo 3: Obtener Achievements del Usuario

```python
@router.get("/users/me/achievements")
async def get_my_achievements(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
    gym_id: int = Depends(get_tenant_id)
):
    # Obtener todos los achievements del usuario
    achievements = db.query(UserAchievement).filter(
        UserAchievement.user_id == user_id,
        UserAchievement.gym_id == gym_id
    ).order_by(UserAchievement.earned_at.desc()).all()

    # Calcular total de puntos
    total_points = sum(a.points_awarded for a in achievements)

    # Agrupar por rareza
    by_rarity = {
        "common": [],
        "rare": [],
        "epic": [],
        "legendary": []
    }

    for achievement in achievements:
        by_rarity[achievement.rarity].append({
            "id": achievement.id,
            "title": achievement.title,
            "description": achievement.description,
            "icon": achievement.icon,
            "value": achievement.value,
            "unit": achievement.unit,
            "earned_at": achievement.earned_at,
            "points": achievement.points_awarded
        })

    return {
        "total_achievements": len(achievements),
        "total_points": total_points,
        "by_rarity": by_rarity,
        "recent": [
            {
                "title": a.title,
                "icon": a.icon,
                "earned_at": a.earned_at
            }
            for a in achievements[:5]  # Últimos 5
        ]
    }
```

**Response:**
```json
{
  "total_achievements": 12,
  "total_points": 375,
  "by_rarity": {
    "common": [
      {
        "title": "Primera Clase Completada",
        "icon": "🎯",
        "points": 10
      }
    ],
    "rare": [
      {
        "title": "🔥 Racha de 7 Días",
        "icon": "🔥",
        "points": 25
      },
      {
        "title": "🎯 Guerrero de 10 Clases",
        "icon": "🎯",
        "points": 25
      }
    ],
    "epic": [
      {
        "title": "⚖️ Meta Alcanzada: Perder 10kg",
        "icon": "⚖️",
        "points": 50
      }
    ],
    "legendary": []
  },
  "recent": [
    {
      "title": "🔥 Racha de 7 Días",
      "icon": "🔥",
      "earned_at": "2025-12-20T10:30:00Z"
    }
  ]
}
```

---

## Resumen Rápido

### ¿Cuándo se Crean Achievements?

| Trigger | Método | Achievement Type |
|---------|--------|------------------|
| **Check-in a clase** | `check_and_create_achievements()` | ATTENDANCE_STREAK, CLASS_MILESTONE |
| **Completar meta de peso** | `_create_goal_achievement()` | WEIGHT_GOAL |
| **Job diario** (futuro) | `check_and_create_achievements()` | Todos |

### ¿Qué Necesitas Implementar?

1. **Llamar a `check_and_create_achievements()` después de check-ins**
   ```python
   # En POST /schedule/participation/checkin
   new_achievements = health_service.check_and_create_achievements(db, user_id, gym_id)
   ```

2. **Publicar en Activity Feed cuando se crean achievements**
   ```python
   if new_achievements:
       await aggregator.on_achievement_unlocked({
           "gym_id": gym_id,
           "achievement_type": achievement.achievement_type.value,
           "achievement_level": achievement.rarity
       })
   ```

3. **Crear endpoint para listar achievements del usuario**
   ```python
   GET /api/v1/users/me/achievements
   ```

4. **(Opcional) Job nocturno para verificar achievements pendientes**
   ```python
   @scheduler.scheduled_job('cron', hour=23, minute=50)
   async def daily_achievement_check():
       ...
   ```

---

## Estado Actual vs Pendiente

### ✅ Implementado
- Modelo de datos `UserAchievement`
- Tipos de logros `AchievementType`
- Cálculo de racha de asistencia
- Cálculo de hitos de clases
- Achievements automáticos al completar goals
- Sistema de rareza y puntos

### ⚠️ Parcialmente Implementado
- Integración con Activity Feed (código existe pero no se llama)
- Endpoints de achievements (no existen aún)

### ❌ Pendiente
- Llamar a `check_and_create_achievements()` desde endpoints de check-in
- Endpoint `GET /users/me/achievements`
- Job nocturno para verificación automática
- Notificaciones push cuando se obtienen achievements
- Achievements de `SOCIAL_ENGAGEMENT`, `STRENGTH_GAIN`, `ENDURANCE_MILESTONE`

---

**Última Actualización:** 2025-12-20
**Versión:** 1.0
