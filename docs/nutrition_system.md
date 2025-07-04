# 🍎 Sistema de Planes Nutricionales

## Descripción General

El sistema de planes nutricionales permite a entrenadores crear planes de dieta personalizados que los usuarios pueden seguir, con funcionalidades de tracking, notificaciones y analytics.

## 🎯 Características Principales

### Para Entrenadores (Creadores de Contenido)
- **Creación de planes**: Planes nutricionales con objetivos específicos (volumen, definición, etc.)
- **Planificación diaria**: Definir comidas para cada día del plan
- **Gestión de ingredientes**: Añadir ingredientes con cantidades y alternativas
- **Publicación programada**: Publicar planes con 1 día de antelación
- **Analytics**: Ver estadísticas de seguimiento y satisfacción

### Para Usuarios (Seguidores)
- **Seguimiento de planes**: Suscribirse a planes de entrenadores
- **Plan diario**: Ver comidas del día actual
- **Check-in de comidas**: Marcar comidas como completadas
- **Feedback**: Calificar comidas y añadir notas
- **Progreso**: Ver estadísticas de adherencia

## 📊 Arquitectura del Sistema

### Modelos de Datos

```
NutritionPlan (Plan principal)
├── DailyNutritionPlan (Días del plan)
│   └── Meal (Comidas del día)
│       └── MealIngredient (Ingredientes)
├── NutritionPlanFollower (Seguidores)
└── UserDailyProgress (Progreso diario)
    └── UserMealCompletion (Comidas completadas)
```

### Enums Disponibles

- **NutritionGoal**: bulk, cut, maintenance, weight_loss, muscle_gain, performance
- **DifficultyLevel**: beginner, intermediate, advanced
- **BudgetLevel**: economic, medium, premium
- **DietaryRestriction**: none, vegetarian, vegan, gluten_free, lactose_free, keto, paleo, mediterranean
- **MealType**: breakfast, mid_morning, lunch, afternoon, dinner, post_workout, late_snack

## 🔧 API Endpoints

### Planes Nutricionales

```http
# Listar planes
GET /api/v1/nutrition/plans
Query params: page, per_page, goal, difficulty_level, search_query

# Crear plan
POST /api/v1/nutrition/plans
Body: NutritionPlanCreate

# Obtener plan específico
GET /api/v1/nutrition/plans/{plan_id}

# Seguir plan
POST /api/v1/nutrition/plans/{plan_id}/follow

# Dejar de seguir
DELETE /api/v1/nutrition/plans/{plan_id}/follow
```

### Gestión de Contenido (Solo Creadores)

```http
# Crear día del plan
POST /api/v1/nutrition/plans/{plan_id}/days
Body: DailyNutritionPlanCreate

# Crear comida
POST /api/v1/nutrition/days/{daily_plan_id}/meals
Body: MealCreate

# Añadir ingrediente
POST /api/v1/nutrition/meals/{meal_id}/ingredients
Body: MealIngredientCreate
```

### Usuario Final

```http
# Plan de hoy
GET /api/v1/nutrition/today

# Completar comida
POST /api/v1/nutrition/meals/{meal_id}/complete
Body: UserMealCompletionCreate

# Dashboard nutricional
GET /api/v1/nutrition/dashboard
```

### Utilidades

```http
# Obtener enums
GET /api/v1/nutrition/enums/goals
GET /api/v1/nutrition/enums/difficulty-levels
GET /api/v1/nutrition/enums/budget-levels
GET /api/v1/nutrition/enums/dietary-restrictions
GET /api/v1/nutrition/enums/meal-types
```

## 🚀 Flujo de Trabajo

### 1. Creación de Plan (Entrenador)

```python
# 1. Crear plan base
plan_data = {
    "title": "Plan de Volumen",
    "goal": "bulk",
    "duration_days": 7,
    "target_calories": 3000,
    # ... más campos
}

# 2. Crear días del plan
for day in range(1, 8):
    daily_plan = {
        "nutrition_plan_id": plan_id,
        "day_number": day,
        "total_calories": 3000
    }
    
    # 3. Crear comidas para cada día
    meals = ["breakfast", "lunch", "dinner"]
    for meal_type in meals:
        meal = {
            "daily_plan_id": daily_plan_id,
            "meal_type": meal_type,
            "name": f"{meal_type.title()} Day {day}",
            # ... más campos
        }
        
        # 4. Añadir ingredientes
        ingredients = [...]
```

### 2. Seguimiento de Plan (Usuario)

```python
# 1. Seguir plan
POST /nutrition/plans/{plan_id}/follow

# 2. Ver plan de hoy
today_plan = GET /nutrition/today

# 3. Completar comidas
for meal in today_plan.meals:
    POST /nutrition/meals/{meal.id}/complete
    {
        "satisfaction_rating": 5,
        "photo_url": "...",
        "notes": "Delicioso!"
    }
```

## 📱 Casos de Uso

### Caso 1: Entrenador Personal
- Crea planes personalizados para clientes específicos
- Publica nuevos días con 24h de antelación
- Monitorea adherencia y ajusta según feedback

### Caso 2: Influencer Fitness
- Crea planes públicos para su audiencia
- Genera contenido regular (7 días de volumen, 14 días de definición)
- Analiza qué comidas son más populares

### Caso 3: Usuario Casual
- Sigue planes de entrenadores que admira
- Recibe notificaciones de nuevas comidas
- Trackea su progreso y mantiene motivación

## 🔔 Sistema de Notificaciones

### Tipos de Notificaciones
- **Nueva comida publicada**: Cuando el entrenador publica el plan del día siguiente
- **Recordatorio de comida**: Basado en horarios configurados por el usuario
- **Logro desbloqueado**: Rachas de adherencia, metas alcanzadas

### Configuración
```python
# Usuario puede configurar horarios
{
    "notifications_enabled": true,
    "notification_time_breakfast": "08:00",
    "notification_time_lunch": "13:00", 
    "notification_time_dinner": "20:00"
}
```

## 📈 Analytics y Métricas

### Para Entrenadores
- Total de seguidores (activos/inactivos)
- Tasa de adherencia promedio
- Satisfacción promedio por comida
- Comidas más populares
- Tendencias de completación

### Para Usuarios
- Racha de días completados
- Porcentaje de adherencia semanal/mensual
- Progreso hacia objetivos nutricionales
- Evolución de peso/medidas (opcional)

## 🔧 Configuración Técnica

### Variables de Entorno
```bash
# Base de datos
DATABASE_URL=postgresql://user:pass@localhost/gymapi

# Notificaciones (futuro)
ONESIGNAL_APP_ID=your_app_id
ONESIGNAL_API_KEY=your_api_key

# Cloudinary para imágenes (futuro)
CLOUDINARY_CLOUD_NAME=your_cloud
CLOUDINARY_API_KEY=your_key
CLOUDINARY_API_SECRET=your_secret
```

### Dependencias Nuevas
```bash
pip install sqlalchemy-utils  # Para JSON fields
pip install pillow  # Para procesamiento de imágenes
pip install celery  # Para tareas en background (futuro)
```

## 🧪 Testing

### Ejecutar Script de Pruebas
```bash
cd scripts
python test_nutrition_system.py
```

### Tests Unitarios
```bash
pytest tests/nutrition/ -v
```

## 🚧 Roadmap Futuro

### Fase 2: Integraciones
- [ ] API de Spoonacular para base de datos de alimentos
- [ ] Integración con MyFitnessPal
- [ ] Cloudinary para upload de imágenes
- [ ] OneSignal para notificaciones push

### Fase 3: IA y Personalización
- [ ] Sugerencias automáticas de comidas
- [ ] Análisis de patrones alimentarios
- [ ] Recomendaciones personalizadas
- [ ] Chatbot nutricional

### Fase 4: Gamificación
- [ ] Sistema de logros y badges
- [ ] Leaderboards de adherencia
- [ ] Challenges entre usuarios
- [ ] Recompensas por consistencia

### Fase 5: Marketplace
- [ ] Planes premium de pago
- [ ] Comisiones para entrenadores
- [ ] Integración con tiendas de suplementos
- [ ] Subscripciones a entrenadores

## 🔒 Consideraciones de Seguridad

### Validaciones
- Todos los inputs son validados con Pydantic
- Verificación de permisos en cada endpoint
- Sanitización de contenido generado por usuarios

### Privacidad
- Planes pueden ser públicos o privados
- Datos de progreso solo visibles para el usuario
- Anonimización en analytics agregados

## 📞 Soporte y Contacto

Para dudas sobre la implementación:
- Revisar documentación de API en `/docs`
- Consultar logs en `logs/nutrition.log`
- Contactar al equipo de desarrollo

---

*Documentación actualizada: Enero 2025* 