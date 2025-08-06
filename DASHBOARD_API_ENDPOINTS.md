# Dashboard API - Especificación Completa de Endpoints

## 📊 Situación Actual de la API

### ✅ Endpoints Existentes Listos para Dashboard

La API actual ya cuenta con endpoints robustos que pueden alimentar un dashboard comprehensivo:

#### **Datos de Participación y Actividad**
- `GET /api/v1/schedule/participation/my-attendance-history` - Historial completo de asistencia
- `GET /api/v1/schedule/participation/my-classes` - Clases próximas del usuario  
- `GET /api/v1/events/participation/me` - Participaciones en eventos
- `GET /api/v1/events/me` - Eventos creados por el usuario

#### **Datos de Membresía y Estado**
- `GET /api/v1/memberships/my-status` - Estado completo de membresía actual
- `GET /api/v1/memberships/summary` - Resumen de membresías del gimnasio

#### **Datos de Perfil y Métricas**
- `GET /api/v1/users/profile/me` - Perfil completo con métricas físicas

#### **Datos de Chat y Social**
- `GET /api/v1/chat/analytics/user-activity` - Actividad de chat del usuario
- `GET /api/v1/chat/analytics/popular-times` - Horarios más activos de chat

#### **Datos de Nutrición** (si módulo activo)
- `GET /api/v1/nutrition/dashboard` - Dashboard nutricional completo
- `GET /api/v1/nutrition/today` - Plan de comidas del día actual

---

## ❌ Endpoints Faltantes - Especificación Detallada

### 1. Estadísticas Comprehensivas del Usuario

#### `GET /api/v1/users/stats/comprehensive`

**Descripción:** Endpoint principal que agrega estadísticas de todas las fuentes disponibles.

**Permisos:** `resource:read` (usuario propio)

**Parámetros de Query:**
- `period` (opcional): `week|month|quarter|year` - Período de análisis (default: month)
- `include_goals` (opcional): `boolean` - Incluir progreso de metas (default: true)

**Respuesta:**
```json
{
  "user_id": 10,
  "period": "month",
  "period_start": "2025-01-01T00:00:00Z",
  "period_end": "2025-01-31T23:59:59Z",
  "fitness_metrics": {
    "classes_attended": 12,
    "classes_scheduled": 15,
    "attendance_rate": 80.0,
    "total_workout_hours": 18.5,
    "average_session_duration": 92.5,
    "streak_current": 5,
    "streak_longest": 8,
    "favorite_class_types": ["Yoga", "CrossFit", "Spinning"],
    "peak_workout_times": ["18:00-20:00", "07:00-09:00"],
    "calories_burned_estimate": 2400
  },
  "events_metrics": {
    "events_attended": 3,
    "events_registered": 4,
    "events_created": 0,
    "attendance_rate": 75.0,
    "favorite_event_types": ["Workshop", "Competition"]
  },
  "social_metrics": {
    "chat_messages_sent": 45,
    "chat_rooms_active": 8,
    "social_score": 7.2,
    "trainer_interactions": 12
  },
  "health_metrics": {
    "current_weight": 75.5,
    "current_height": 175,
    "bmi": 24.6,
    "bmi_category": "normal",
    "weight_change": -2.1,
    "goals_progress": [
      {
        "goal_id": 1,
        "goal_type": "weight_loss",
        "target_value": 70,
        "current_value": 75.5,
        "progress_percentage": 45.0,
        "status": "on_track"
      }
    ]
  },
  "membership_utilization": {
    "plan_name": "Premium",
    "utilization_rate": 78.5,
    "value_score": 8.4,
    "days_until_renewal": 15,
    "recommended_actions": ["Attend 2 more classes to reach 90% utilization"]
  },
  "achievements": [
    {
      "id": 5,
      "type": "attendance_streak",
      "name": "5 Day Streak",
      "description": "Attended classes 5 days in a row",
      "earned_at": "2025-01-15T10:30:00Z",
      "badge_icon": "🔥"
    }
  ],
  "trends": {
    "attendance_trend": "increasing",
    "workout_intensity_trend": "stable", 
    "social_engagement_trend": "increasing"
  },
  "recommendations": [
    "Try a new class type to improve variety score",
    "Schedule morning workouts for better consistency",
    "Join the CrossFit community chat for tips"
  ]
}
```

### 2. Resumen Semanal

#### `GET /api/v1/users/stats/weekly-summary`

**Descripción:** Resumen optimizado para vista semanal con datos día por día.

**Permisos:** `resource:read`

**Parámetros de Query:**
- `week_offset` (opcional): `integer` - Semanas atrás desde ahora (default: 0)

**Respuesta:**
```json
{
  "user_id": 10,
  "week_start": "2025-01-20T00:00:00Z",
  "week_end": "2025-01-26T23:59:59Z",
  "week_number": 4,
  "summary": {
    "total_workouts": 4,
    "total_hours": 6.5,
    "days_active": 4,
    "rest_days": 3,
    "streak_maintained": true
  },
  "daily_breakdown": [
    {
      "date": "2025-01-20",
      "day_name": "Monday", 
      "workouts": 1,
      "duration_minutes": 90,
      "classes": ["Morning Yoga"],
      "events": [],
      "chat_activity": 5,
      "energy_level": 8
    },
    {
      "date": "2025-01-21",
      "day_name": "Tuesday",
      "workouts": 0,
      "duration_minutes": 0,
      "classes": [],
      "events": [],
      "chat_activity": 2,
      "energy_level": null
    }
  ],
  "week_goals": [
    {
      "goal_type": "workouts_per_week",
      "target": 5,
      "achieved": 4,
      "status": "behind"
    },
    {
      "goal_type": "workout_hours",
      "target": 7.5,
      "achieved": 6.5,
      "status": "close"
    }
  ],
  "compared_to_average": {
    "workouts_vs_avg": 0.2,
    "hours_vs_avg": -0.8,
    "consistency_vs_avg": 0.1
  }
}
```

### 3. Tendencias Mensuales

#### `GET /api/v1/users/stats/monthly-trends`

**Descripción:** Análisis de tendencias y patrones a lo largo de varios meses.

**Permisos:** `resource:read`

**Parámetros de Query:**
- `months_back` (opcional): `integer` - Número de meses hacia atrás (default: 6, max: 12)

**Respuesta:**
```json
{
  "user_id": 10,
  "analysis_period": {
    "start_date": "2024-08-01T00:00:00Z",
    "end_date": "2025-01-31T23:59:59Z",
    "months_analyzed": 6
  },
  "monthly_data": [
    {
      "month": "2024-08",
      "workouts": 18,
      "hours": 27.0,
      "attendance_rate": 85.7,
      "weight": 77.8,
      "avg_session_duration": 90
    },
    {
      "month": "2024-09", 
      "workouts": 16,
      "hours": 24.5,
      "attendance_rate": 80.0,
      "weight": 77.2,
      "avg_session_duration": 92
    }
  ],
  "trends": {
    "workout_frequency": {
      "direction": "increasing",
      "rate": 0.15,
      "confidence": 85.2
    },
    "workout_duration": {
      "direction": "stable",
      "rate": 0.02,
      "confidence": 92.1
    },
    "weight_change": {
      "direction": "decreasing",
      "rate": -0.3,
      "confidence": 78.9
    },
    "attendance_consistency": {
      "direction": "improving",
      "rate": 0.08,
      "confidence": 80.5
    }
  },
  "seasonal_patterns": {
    "best_month": "October",
    "worst_month": "December",
    "peak_days": ["Monday", "Wednesday", "Friday"],
    "preferred_times": ["07:00-09:00", "18:00-20:00"]
  },
  "forecasting": {
    "next_month_prediction": {
      "expected_workouts": 17,
      "confidence_range": [15, 20],
      "recommended_goals": {
        "workouts": 18,
        "hours": 27
      }
    }
  }
}
```

### 4. Progreso de Objetivos

#### `GET /api/v1/users/goals-progress`

**Descripción:** Estado detallado de todas las metas personales del usuario.

**Permisos:** `resource:read`

**Respuesta:**
```json
{
  "user_id": 10,
  "active_goals": [
    {
      "goal_id": 1,
      "type": "weight_loss",
      "name": "Perder 5kg",
      "description": "Alcanzar 70kg para el verano",
      "created_at": "2024-12-01T00:00:00Z",
      "target_date": "2025-06-01T00:00:00Z", 
      "current_value": 75.5,
      "target_value": 70.0,
      "starting_value": 80.0,
      "progress_percentage": 45.0,
      "status": "on_track",
      "weekly_progress": -0.3,
      "milestones": [
        {
          "value": 78,
          "achieved": true,
          "date_achieved": "2024-12-15T00:00:00Z"
        },
        {
          "value": 75,
          "achieved": false,
          "estimated_date": "2025-02-10T00:00:00Z"
        }
      ]
    },
    {
      "goal_id": 2,
      "type": "workout_frequency",
      "name": "Entrenar 5 veces por semana",
      "description": "Mantener consistencia de entrenamiento",
      "created_at": "2025-01-01T00:00:00Z",
      "target_date": null,
      "current_value": 4.2,
      "target_value": 5.0,
      "starting_value": 3.1,
      "progress_percentage": 57.9,
      "status": "behind",
      "weekly_progress": 0.1,
      "streak_current": 2,
      "streak_best": 4
    }
  ],
  "completed_goals": [
    {
      "goal_id": 3,
      "type": "strength_gain",
      "name": "Aumentar peso en press banca",
      "completed_at": "2024-11-20T00:00:00Z",
      "final_value": 80,
      "target_value": 75,
      "completion_rate": 106.7
    }
  ],
  "goal_categories": {
    "fitness": 2,
    "weight": 1,
    "strength": 1,
    "endurance": 0,
    "nutrition": 0
  },
  "overall_progress": {
    "goals_completed": 1,
    "goals_on_track": 1,
    "goals_behind": 1,
    "average_completion_rate": 67.3
  }
}
```

### 5. Sistema de Logros

#### `GET /api/v1/users/achievements`

**Descripción:** Sistema completo de logros y badges del usuario.

**Permisos:** `resource:read`

**Parámetros de Query:**
- `category` (opcional): `fitness|social|consistency|milestones` - Filtrar por categoría
- `status` (opcional): `earned|available|locked` - Filtrar por estado

**Respuesta:**
```json
{
  "user_id": 10,
  "achievements_summary": {
    "total_earned": 12,
    "total_available": 45,
    "total_points": 340,
    "level": 3,
    "next_level_points": 160
  },
  "recent_achievements": [
    {
      "id": 15,
      "type": "streak",
      "category": "consistency",
      "name": "Five Day Fire",
      "description": "Attended workouts 5 consecutive days",
      "badge_icon": "🔥",
      "points": 50,
      "rarity": "common",
      "earned_at": "2025-01-15T18:30:00Z",
      "requirements_met": {
        "consecutive_days": 5
      }
    }
  ],
  "earned_achievements": [
    {
      "id": 1,
      "type": "first_class",
      "category": "milestones",
      "name": "First Step",
      "description": "Attended your first class",
      "badge_icon": "👶",
      "points": 10,
      "rarity": "common",
      "earned_at": "2024-08-15T09:00:00Z"
    },
    {
      "id": 8,
      "type": "weight_milestone",
      "category": "fitness",
      "name": "Progress Tracker",
      "description": "Lost 5kg from starting weight",
      "badge_icon": "📉",
      "points": 75,
      "rarity": "rare",
      "earned_at": "2024-12-20T14:20:00Z"
    }
  ],
  "available_achievements": [
    {
      "id": 23,
      "type": "social",
      "category": "social",
      "name": "Chat Champion", 
      "description": "Send 100 messages in community chats",
      "badge_icon": "💬",
      "points": 30,
      "rarity": "uncommon",
      "progress": {
        "current": 67,
        "required": 100,
        "percentage": 67.0
      },
      "estimated_unlock": "2025-02-05T00:00:00Z"
    }
  ],
  "locked_achievements": [
    {
      "id": 45,
      "type": "elite_streak",
      "category": "consistency",
      "name": "Century Club",
      "description": "Maintain 100 day workout streak",
      "badge_icon": "💯",
      "points": 500,
      "rarity": "legendary",
      "unlock_requirements": [
        "Earn 'Monthly Warrior' achievement first",
        "Reach level 5"
      ]
    }
  ],
  "leaderboards": {
    "gym_ranking": 8,
    "total_participants": 156,
    "category_rankings": {
      "consistency": 3,
      "fitness": 12,
      "social": 15
    }
  }
}
```

### 6. Metas Personales - CRUD

#### `GET /api/v1/users/goals`

**Descripción:** Lista todas las metas del usuario.

**Permisos:** `resource:read`

#### `POST /api/v1/users/goals`

**Descripción:** Crear nueva meta personal.

**Permisos:** `resource:write`

**Body:**
```json
{
  "type": "weight_loss|weight_gain|workout_frequency|strength_gain|endurance|custom",
  "name": "Mi meta personalizada",
  "description": "Descripción detallada de la meta",
  "target_value": 70.0,
  "current_value": 75.5,
  "target_date": "2025-06-01T00:00:00Z",
  "unit": "kg",
  "tracking_frequency": "daily|weekly|monthly",
  "reminders_enabled": true,
  "public": false
}
```

#### `PUT /api/v1/users/goals/{goal_id}`

**Descripción:** Actualizar meta existente.

**Permisos:** `resource:write`

#### `DELETE /api/v1/users/goals/{goal_id}`

**Descripción:** Eliminar meta.

**Permisos:** `resource:write`

### 7. Análisis de Rendimiento

#### `GET /api/v1/users/stats/performance-analysis`

**Descripción:** Análisis avanzado de rendimiento y recomendaciones personalizadas.

**Permisos:** `resource:read`

**Respuesta:**
```json
{
  "user_id": 10,
  "performance_score": 78.5,
  "analysis_date": "2025-01-31T12:00:00Z",
  "strengths": [
    {
      "area": "consistency",
      "score": 85.2,
      "description": "Excellent workout consistency over the past month"
    },
    {
      "area": "variety",
      "score": 72.1, 
      "description": "Good variety in workout types"
    }
  ],
  "improvement_areas": [
    {
      "area": "intensity",
      "score": 65.3,
      "description": "Consider increasing workout intensity",
      "recommendations": [
        "Try advanced CrossFit classes",
        "Increase weight in strength training",
        "Add HIIT sessions to routine"
      ]
    }
  ],
  "optimal_schedule": {
    "best_workout_days": ["Monday", "Wednesday", "Friday"],
    "best_workout_times": ["07:00", "18:00"],
    "recommended_rest_pattern": "2 days on, 1 day off"
  },
  "predicted_outcomes": {
    "next_month_fitness_level": 82.1,
    "goal_achievement_probability": {
      "weight_goal": 75.2,
      "frequency_goal": 88.9
    }
  }
}
```

---

## 🏗️ Estructura de Datos - Nuevos Modelos

### UserComprehensiveStats
```python
class UserComprehensiveStats(BaseModel):
    user_id: int
    period: str
    period_start: datetime
    period_end: datetime
    fitness_metrics: FitnessMetrics
    events_metrics: EventsMetrics
    social_metrics: SocialMetrics
    health_metrics: HealthMetrics
    membership_utilization: MembershipUtilization
    achievements: List[Achievement]
    trends: TrendAnalysis
    recommendations: List[str]
```

### UserGoal
```python
class UserGoal(BaseModel):
    goal_id: int
    user_id: int
    type: GoalType
    name: str
    description: Optional[str]
    target_value: float
    current_value: float
    starting_value: float
    target_date: Optional[datetime]
    created_at: datetime
    status: GoalStatus
    progress_percentage: float
    unit: Optional[str]
    tracking_frequency: TrackingFrequency
    reminders_enabled: bool
    public: bool
```

### Achievement
```python
class Achievement(BaseModel):
    id: int
    type: str
    category: AchievementCategory
    name: str
    description: str
    badge_icon: str
    points: int
    rarity: AchievementRarity
    earned_at: Optional[datetime]
    requirements: Dict[str, Any]
    progress: Optional[AchievementProgress]
```

---

## 📋 Plan de Implementación

### Fase 1: Backend Base (1-2 semanas)
1. **Crear servicio `UserStatsService`**
   - Agregación de datos de múltiples fuentes
   - Cálculos de tendencias y métricas
   - Sistema de caché optimizado

2. **Implementar endpoints básicos**
   - `/users/stats/comprehensive`
   - `/users/stats/weekly-summary` 
   - `/users/stats/monthly-trends`

3. **Base de datos**
   - Nuevas tablas para goals y achievements
   - Índices optimizados para consultas de estadísticas

### Fase 2: Sistema de Metas y Logros (2-3 semanas)  
1. **Sistema de Goals**
   - CRUD completo para metas personales
   - Tracking automático de progreso
   - Notificaciones y recordatorios

2. **Sistema de Achievements**
   - Motor de logros automático
   - Sistema de puntos y niveles
   - Badges y ranking

### Fase 3: Análisis Avanzado (2-3 semanas)
1. **Performance Analysis**
   - Algoritmos de análisis de rendimiento
   - Recomendaciones personalizadas
   - Predicciones basadas en patrones

2. **Optimización y Testing**
   - Tests comprehensivos
   - Optimización de performance
   - Documentación completa

### Consideraciones Técnicas

**Caching Strategy:**
- Redis para datos frecuentemente accedidos
- TTL diferenciado según tipo de dato
- Invalidación inteligente en actualizaciones

**Performance:**
- Consultas optimizadas con índices apropiados  
- Paginación en endpoints con grandes datasets
- Cálculos asyncronos para métricas complejas

**Seguridad:**
- Validación estricta de acceso a datos propios
- Rate limiting en endpoints computacionalmente intensivos
- Sanitización de parámetros de entrada

Este sistema proporcionará un dashboard comprehensivo que aprovecha toda la riqueza de datos disponible en la API existente, añadiendo las capas de análisis y gamificación necesarias para una experiencia de usuario excepcional.