# 🚀 Roadmap de Mejoras - Módulo de Nutrición

## 📊 Análisis del Estado Actual

### Fortalezas Actuales
- ✅ Sistema híbrido de planes (Template/Live/Archived)
- ✅ Generación con IA de ingredientes
- ✅ Multi-tenancy completo
- ✅ 40+ endpoints funcionales
- ✅ Sistema de tracking básico

### Áreas de Oportunidad
- ⚠️ Sin sistema de notificaciones activo
- ⚠️ Analytics básicas
- ⚠️ Sin tests automatizados
- ⚠️ Sin sistema de recomendaciones
- ⚠️ Sin integración con wearables
- ⚠️ Sin gamificación

---

## 🎯 PRIORIDAD ALTA - Quick Wins (1-2 semanas)

### 1. Sistema de Notificaciones Completo
**Impacto:** 📈 Alto | **Esfuerzo:** 💪 Medio

```python
# Nuevo endpoint para configuración de notificaciones
POST /api/v1/nutrition/notifications/settings
{
  "meal_reminders": true,
  "reminder_times": {
    "breakfast": "07:30",
    "lunch": "13:00",
    "dinner": "20:00"
  },
  "progress_updates": true,
  "challenge_updates": true,
  "new_plan_alerts": true,
  "achievement_notifications": true
}

# Implementar en services/nutrition.py
async def send_meal_reminder(self, user_id: int, meal_type: str):
    """Enviar recordatorio de comida vía OneSignal"""
    notification_service.send_push(
        user_id=user_id,
        title=f"🍽️ Hora de tu {meal_type}",
        body="Revisa tu plan nutricional para hoy",
        data={"type": "meal_reminder", "meal_type": meal_type}
    )

# Agregar job programado en app/main.py
scheduler.add_job(
    send_meal_reminders,
    'cron',
    hour='7,13,20',
    minute=30
)
```

### 2. Sistema de Logros y Gamificación
**Impacto:** 📈 Alto | **Esfuerzo:** 💪 Bajo

```python
# Nuevo modelo: NutritionAchievement
class NutritionAchievement(Base):
    __tablename__ = "nutrition_achievements"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    achievement_type = Column(Enum(AchievementType))
    unlocked_at = Column(DateTime)
    plan_id = Column(Integer, ForeignKey("nutrition_plans.id"))

class AchievementType(str, Enum):
    FIRST_MEAL = "first_meal"
    WEEK_STREAK = "week_streak"
    MONTH_STREAK = "month_streak"
    PERFECT_DAY = "perfect_day"
    CHALLENGE_COMPLETED = "challenge_completed"
    TOP_PERFORMER = "top_performer"
    PHOTO_WARRIOR = "photo_warrior"  # 50+ fotos
    EARLY_BIRD = "early_bird"  # Desayuno antes de 8am
    NIGHT_OWL = "night_owl"  # Cena después de 9pm

# Endpoint
GET /api/v1/nutrition/achievements
POST /api/v1/nutrition/achievements/{id}/share  # Compartir en redes
```

### 3. Shopping List Automática
**Impacto:** 📈 Alto | **Esfuerzo:** 💪 Bajo

```python
# Nuevo endpoint
GET /api/v1/nutrition/shopping-list?days=7
Response: {
  "period": "2025-01-20 to 2025-01-26",
  "grouped_ingredients": {
    "proteins": [
      {"name": "Pechuga de pollo", "total_quantity": 1.5, "unit": "kg"},
      {"name": "Huevos", "total_quantity": 14, "unit": "units"}
    ],
    "carbs": [...],
    "vegetables": [...],
    "fruits": [...],
    "dairy": [...],
    "pantry": [...]
  },
  "estimated_cost": {
    "economic": 45.50,
    "medium": 68.30,
    "premium": 95.20
  },
  "shopping_notes": "Comprar pollo y pescado frescos el día de compra",
  "export_formats": ["pdf", "whatsapp", "email"]
}

POST /api/v1/nutrition/shopping-list/share
{
  "format": "whatsapp",
  "phone": "+521234567890"
}
```

### 4. Sistema de Sustituciones Inteligentes
**Impacto:** 📈 Medio | **Esfuerzo:** 💪 Bajo

```python
# Nuevo endpoint con IA
POST /api/v1/nutrition/ingredients/{id}/smart-substitute
{
  "reason": "allergy",  # allergy, preference, unavailable, budget
  "restrictions": ["lactose_free"],
  "max_price_multiplier": 1.5
}

Response: {
  "original": {"name": "Leche", "quantity": 250, "unit": "ml"},
  "substitutes": [
    {
      "name": "Leche de almendras",
      "quantity": 250,
      "unit": "ml",
      "match_score": 0.95,
      "nutrition_diff": {
        "calories": -20,
        "protein": -6,
        "calcium": "+20%"
      },
      "price_diff": "+30%"
    }
  ]
}
```

### 5. Fotos con IA - Análisis Automático
**Impacto:** 📈 Alto | **Esfuerzo:** 💪 Medio

```python
# Mejorar endpoint de complete meal
POST /api/v1/nutrition/meals/{id}/complete
{
  "photo_url": "https://...",
  "analyze_photo": true  # NUEVO
}

# Proceso:
1. Usuario sube foto
2. IA analiza si corresponde a la comida esperada
3. Estima porción consumida
4. Sugiere ajustes nutricionales

Response: {
  "photo_analysis": {
    "meal_match": true,
    "confidence": 0.87,
    "estimated_portion": 0.85,  # 85% de la porción planeada
    "detected_ingredients": ["pollo", "arroz", "brócoli"],
    "missing_ingredients": ["aceite de oliva"],
    "nutrition_estimate": {
      "calories": 420,
      "vs_planned": -30
    },
    "suggestions": "Agregar una cucharada de aceite de oliva para completar grasas saludables"
  }
}
```

---

## 💎 PRIORIDAD MEDIA - Funcionalidades Premium (2-4 semanas)

### 6. Sistema de Recomendaciones Personalizadas
**Impacto:** 📈 Alto | **Esfuerzo:** 💪 Alto

```python
# Nuevo servicio: NutritionRecommendationService
class NutritionRecommendationService:
    async def get_personalized_plans(self, user_id: int):
        """Recomendar planes basados en historial y preferencias"""
        # Análisis de:
        # - Planes anteriores completados
        # - Satisfaction ratings
        # - Ingredientes preferidos/evitados
        # - Horarios de comida habituales
        # - Presupuesto histórico

        return {
            "recommended_plans": [...],
            "reasoning": "Basado en tu éxito con planes de 1800 cal...",
            "success_probability": 0.78
        }

# Endpoint
GET /api/v1/nutrition/recommendations
GET /api/v1/nutrition/recommendations/meals  # Comidas específicas
```

### 7. Modo Offline y Sincronización
**Impacto:** 📈 Alto | **Esfuerzo:** 💪 Alto

```python
# Nuevos endpoints para sincronización
GET /api/v1/nutrition/sync/download  # Descarga plan completo
Response: {
  "sync_token": "abc123",
  "data": {
    "plans": [...],
    "daily_plans": [...],
    "meals": [...],
    "ingredients": [...]
  },
  "cache_duration": 86400
}

POST /api/v1/nutrition/sync/upload  # Sube cambios offline
{
  "sync_token": "abc123",
  "completed_meals": [...],
  "photos": [...],
  "offline_duration": 3600
}
```

### 8. Integración con Wearables
**Impacto:** 📈 Alto | **Esfuerzo:** 💪 Alto

```python
# Nuevo modelo para tracking
class WearableData(Base):
    __tablename__ = "nutrition_wearable_data"

    user_id = Column(Integer)
    date = Column(Date)
    calories_burned = Column(Integer)
    steps = Column(Integer)
    active_minutes = Column(Integer)
    sleep_hours = Column(Float)
    heart_rate_avg = Column(Integer)
    source = Column(String)  # fitbit, garmin, apple_watch

# Ajuste automático de calorías
async def adjust_calories_by_activity(self, user_id: int, date: date):
    wearable_data = await self.get_wearable_data(user_id, date)
    base_calories = plan.target_calories

    # Ajuste basado en actividad
    if wearable_data.calories_burned > 500:
        adjusted = base_calories + (wearable_data.calories_burned * 0.3)

    return {
        "base_calories": base_calories,
        "activity_adjustment": adjustment,
        "recommended_calories": adjusted,
        "extra_meal_suggestion": "Agrega un snack post-entreno de 200 cal"
    }
```

### 9. Planificador de Meal Prep
**Impacto:** 📈 Medio | **Esfuerzo:** 💪 Medio

```python
# Nuevo endpoint
POST /api/v1/nutrition/meal-prep/generate
{
  "plan_id": 123,
  "days": [1, 2, 3, 4, 5],  # Días de la semana a preparar
  "prep_day": "sunday",
  "containers_available": 15,
  "cooking_time_available": 180  # minutos
}

Response: {
  "prep_schedule": {
    "sunday": {
      "cooking_blocks": [
        {
          "time": "10:00-11:00",
          "tasks": ["Cocinar 1kg pollo", "Preparar 2kg arroz"],
          "parallel_possible": true
        }
      ],
      "storage_plan": [
        {
          "meal": "Lunch día 1-3",
          "containers": 3,
          "storage": "refrigerador",
          "max_days": 3
        }
      ]
    }
  },
  "shopping_list_optimized": [...],
  "cooking_instructions_combined": [...],
  "savings_estimate": "$45 vs comprar preparado"
}
```

### 10. Coach Virtual con IA
**Impacto:** 📈 Alto | **Esfuerzo:** 💪 Alto

```python
# Nuevo endpoint para chat nutricional
POST /api/v1/nutrition/coach/chat
{
  "message": "No me gustó el desayuno de hoy, ¿qué puedo cambiar?",
  "context": {
    "meal_id": 789,
    "plan_id": 123
  }
}

Response: {
  "response": "Entiendo. El desayuno con avena puede cambiarse por estas opciones...",
  "suggestions": [
    {
      "alternative_meal": "Tostadas con huevo y aguacate",
      "maintains_macros": true,
      "prep_time": "10 min"
    }
  ],
  "action_buttons": [
    {"label": "Cambiar desayuno", "action": "substitute_meal"},
    {"label": "Ver más opciones", "action": "more_alternatives"}
  ]
}

# Sistema de preguntas frecuentes contextuales
GET /api/v1/nutrition/coach/faq?context=meal_completed&satisfaction=2
```

---

## 🚀 PRIORIDAD BAJA - Funcionalidades Avanzadas (1-2 meses)

### 11. Marketplace de Planes
**Impacto:** 📈 Alto | **Esfuerzo:** 💪 Muy Alto

```python
# Nuevos modelos
class PlanMarketplace(Base):
    plan_id = Column(Integer)
    price = Column(Decimal(10, 2))
    currency = Column(String)
    commission_percentage = Column(Integer)  # Para el gym
    sales_count = Column(Integer)
    revenue_total = Column(Decimal(10, 2))

class PlanPurchase(Base):
    buyer_id = Column(Integer)
    plan_id = Column(Integer)
    price_paid = Column(Decimal)
    payment_method = Column(String)
    stripe_payment_id = Column(String)

# Endpoints
POST /api/v1/nutrition/marketplace/publish
GET /api/v1/nutrition/marketplace/search
POST /api/v1/nutrition/marketplace/purchase/{plan_id}
GET /api/v1/nutrition/marketplace/earnings  # Para creadores
```

### 12. Análisis Predictivo y Machine Learning
**Impacto:** 📈 Alto | **Esfuerzo:** 💪 Muy Alto

```python
# Predicción de abandono
GET /api/v1/nutrition/analytics/churn-prediction/{user_id}
Response: {
  "churn_probability": 0.73,
  "risk_factors": [
    "Baja satisfacción últimos 3 días",
    "No ha subido fotos",
    "Saltó 2 comidas ayer"
  ],
  "recommendations": [
    "Enviar mensaje motivacional",
    "Ofrecer sesión con nutricionista",
    "Simplificar próximas comidas"
  ]
}

# Optimización automática de planes
POST /api/v1/nutrition/plans/{id}/auto-optimize
{
  "optimization_goal": "increase_adherence",
  "constraints": ["maintain_calories", "budget_limit"]
}
```

### 13. Integración con Delivery
**Impacto:** 📈 Medio | **Esfuerzo:** 💪 Alto

```python
# Integración con servicios de delivery
POST /api/v1/nutrition/meals/{id}/order-delivery
{
  "delivery_service": "uber_eats",
  "delivery_address": {...},
  "scheduled_time": "13:00"
}

# Encontrar restaurantes con comidas similares
GET /api/v1/nutrition/meals/{id}/restaurant-alternatives
Response: {
  "restaurants": [
    {
      "name": "Healthy Food Co",
      "dish": "Grilled Chicken Salad",
      "match_score": 0.89,
      "nutrition_comparison": {...},
      "price": 12.99,
      "delivery_time": "30-45 min"
    }
  ]
}
```

### 14. Video Recetas y Contenido Premium
**Impacto:** 📈 Medio | **Esfuerzo:** 💪 Medio

```python
# Nuevo modelo
class MealVideo(Base):
    meal_id = Column(Integer)
    video_url = Column(String)
    duration_seconds = Column(Integer)
    thumbnail_url = Column(String)
    is_premium = Column(Boolean)
    view_count = Column(Integer)
    chef_id = Column(Integer)

# Endpoints
POST /api/v1/nutrition/meals/{id}/video
GET /api/v1/nutrition/videos/trending
POST /api/v1/nutrition/videos/{id}/like
```

### 15. Sistema de Reviews y Social
**Impacto:** 📈 Medio | **Esfuerzo:** 💪 Medio

```python
# Reviews de planes y comidas
class PlanReview(Base):
    plan_id = Column(Integer)
    user_id = Column(Integer)
    rating = Column(Integer)  # 1-5
    title = Column(String)
    comment = Column(Text)
    would_recommend = Column(Boolean)
    verified_purchase = Column(Boolean)
    helpful_count = Column(Integer)

# Social features
class NutritionPost(Base):
    user_id = Column(Integer)
    meal_completion_id = Column(Integer)
    caption = Column(Text)
    likes_count = Column(Integer)
    comments_count = Column(Integer)
    is_public = Column(Boolean)
    hashtags = Column(JSON)

# Feed social
GET /api/v1/nutrition/social/feed
POST /api/v1/nutrition/social/posts
POST /api/v1/nutrition/social/posts/{id}/like
POST /api/v1/nutrition/social/posts/{id}/comment
```

---

## 🔧 OPTIMIZACIONES TÉCNICAS

### 16. Performance y Caché
```python
# Implementar caché más agresivo
class NutritionCacheService:
    async def cache_user_week_plan(self, user_id: int):
        """Pre-cachear plan completo de la semana"""

    async def cache_popular_meals(self):
        """Cachear top 100 comidas más usadas"""

    async def warm_cache_on_deploy(self):
        """Calentar caché después de deploy"""

# Índices adicionales en BD
- Index on user_meal_completions(user_id, completed_at)
- Index on nutrition_plans(gym_id, plan_type, is_active)
- Composite index on followers(user_id, plan_id, is_active)
```

### 17. Sistema de Tests Completo
```python
# tests/nutrition/
├── test_plan_creation.py
├── test_meal_completion.py
├── test_ai_generation.py
├── test_live_plans.py
├── test_shopping_list.py
├── test_notifications.py
└── test_analytics.py

# Fixtures específicos
@pytest.fixture
def nutrition_plan_factory():
    def create_plan(**kwargs):
        defaults = {
            "title": "Test Plan",
            "plan_type": "template",
            "duration_days": 7
        }
        return NutritionPlan(**{**defaults, **kwargs})
    return create_plan
```

### 18. Webhooks y Eventos
```python
# Sistema de eventos para integraciones
class NutritionEventService:
    events = [
        "plan.created",
        "plan.followed",
        "meal.completed",
        "goal.achieved",
        "streak.milestone",
        "challenge.completed"
    ]

    async def emit(self, event: str, data: dict):
        # Enviar a webhooks configurados
        # Enviar a sistema de analytics
        # Trigger automations

# Configuración de webhooks
POST /api/v1/nutrition/webhooks
{
  "url": "https://zapier.com/hooks/...",
  "events": ["meal.completed", "goal.achieved"],
  "secret": "webhook_secret"
}
```

### 19. Migración y Versionado de Datos
```python
# Sistema de versionado para planes
class PlanVersion(Base):
    plan_id = Column(Integer)
    version = Column(Integer)
    changes = Column(JSON)
    created_by = Column(Integer)
    created_at = Column(DateTime)

# Permitir rollback a versiones anteriores
POST /api/v1/nutrition/plans/{id}/restore-version/{version}
```

### 20. Monitoreo y Observabilidad
```python
# Métricas específicas del módulo
class NutritionMetrics:
    # Prometheus metrics
    meals_completed = Counter('nutrition_meals_completed_total')
    plans_created = Counter('nutrition_plans_created_total')
    ai_generations = Counter('nutrition_ai_generations_total')
    avg_satisfaction = Gauge('nutrition_avg_satisfaction')

    # Custom dashboards
    - Grafana dashboard para nutrition
    - Alertas para baja adherencia
    - Monitoreo de costos de OpenAI
```

---

## 📊 Métricas de Impacto Esperado

| Mejora | Impacto en Retención | Impacto en Engagement | ROI Estimado |
|--------|---------------------|----------------------|--------------|
| Notificaciones | +15% | +25% | 3x |
| Gamificación | +20% | +40% | 5x |
| Shopping List | +10% | +15% | 2x |
| Fotos con IA | +25% | +35% | 4x |
| Wearables | +30% | +20% | 3x |
| Marketplace | +5% | +10% | 10x |
| Social Features | +35% | +50% | 6x |

---

## 🗓️ Roadmap Sugerido

### Q1 2025 (Enero - Marzo)
- ✅ Documentación actual (COMPLETADO)
- 🔄 Sistema de notificaciones
- 🔄 Gamificación básica
- 🔄 Shopping list
- 🔄 Tests unitarios

### Q2 2025 (Abril - Junio)
- 📅 Fotos con IA
- 📅 Sistema de recomendaciones
- 📅 Meal prep planner
- 📅 Integración wearables básica

### Q3 2025 (Julio - Septiembre)
- 📅 Coach virtual
- 📅 Marketplace beta
- 📅 Social features
- 📅 Video recetas

### Q4 2025 (Octubre - Diciembre)
- 📅 ML y predicción
- 📅 Integraciones delivery
- 📅 Marketplace público
- 📅 Expansión internacional

---

## 💰 Presupuesto Estimado

| Componente | Costo Desarrollo | Costo Mensual Operación |
|------------|-----------------|-------------------------|
| Notificaciones | $2,000 | $50 (OneSignal) |
| IA Mejorada | $5,000 | $200 (OpenAI extra) |
| Wearables | $8,000 | $100 (APIs) |
| Marketplace | $15,000 | $500 (Stripe fees) |
| ML/Analytics | $10,000 | $300 (Compute) |
| **TOTAL** | **$40,000** | **$1,150/mes** |

---

## ✅ Próximos Pasos Inmediatos

1. **Implementar Sistema de Notificaciones** (1 semana)
   - Integrar con OneSignal existente
   - Agregar jobs programados
   - UI para configuración

2. **Agregar Gamificación Básica** (3 días)
   - Crear tabla de achievements
   - Lógica de desbloqueo
   - Endpoints de consulta

3. **Shopping List Automática** (3 días)
   - Endpoint de agregación
   - Agrupación inteligente
   - Export a WhatsApp

4. **Tests Básicos** (1 semana)
   - Tests de creación de planes
   - Tests de seguimiento
   - Tests de IA

5. **Documentar APIs Nuevas** (2 días)
   - Actualizar Swagger
   - Ejemplos de uso
   - Guías de integración