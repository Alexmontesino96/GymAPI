# Documentación Completa del Módulo de Nutrición - GymApi

## 📋 Índice
1. [Introducción](#introducción)
2. [Arquitectura del Sistema](#arquitectura-del-sistema)
3. [Tipos de Planes (Sistema Híbrido)](#tipos-de-planes-sistema-híbrido)
4. [Guía de Uso para Entrenadores](#guía-de-uso-para-entrenadores)
5. [Guía de Uso para Miembros](#guía-de-uso-para-miembros)
6. [Referencia de API - Endpoints](#referencia-de-api---endpoints)
7. [Integración con IA (OpenAI)](#integración-con-ia-openai)
8. [Modelos de Datos](#modelos-de-datos)
9. [Casos de Uso Reales](#casos-de-uso-reales)
10. [Preguntas Frecuentes](#preguntas-frecuentes)

---

## 🎯 Introducción

### ¿Qué es el Módulo de Nutrición?

El módulo de nutrición es un sistema integral diseñado para gimnasios y centros fitness que permite:

- **Creación de Planes Nutricionales Profesionales**: Los entrenadores pueden diseñar planes completos con días, comidas e ingredientes específicos.
- **Seguimiento y Tracking de Usuarios**: Los miembros pueden seguir planes, marcar comidas completadas y ver su progreso.
- **Sistema Híbrido de Planes**: Soporte para planes individuales (Template), challenges grupales (Live) y planes históricos reutilizables (Archived).
- **Inteligencia Artificial Integrada**: Generación automática de ingredientes con valores nutricionales usando OpenAI GPT-4o-mini.
- **Multi-tenancy Completo**: Cada gimnasio tiene sus propios planes aislados y seguros.

### Beneficios Clave

**Para el Gimnasio:**
- 📈 Valor agregado para miembros con planes nutricionales profesionales
- 🏆 Capacidad de crear challenges grupales para aumentar engagement
- 📊 Analytics detalladas sobre adherencia y satisfacción
- 💰 Potencial fuente de ingresos adicionales (venta de planes premium)

**Para Entrenadores:**
- 🚀 Creación rápida de planes con IA
- 📱 Gestión digital de múltiples clientes
- 📈 Seguimiento del progreso de sus miembros
- ♻️ Reutilización de planes exitosos

**Para Miembros:**
- 🎯 Planes personalizados según sus objetivos
- 📱 Acceso móvil a sus comidas del día
- 📸 Registro visual de comidas con fotos
- 🏆 Participación en challenges grupales
- 📊 Tracking de progreso y adherencia

---

## 🏗️ Arquitectura del Sistema

### Flujo de Datos

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Frontend  │────▶│   FastAPI   │────▶│  PostgreSQL │
│    (App)    │     │   Routers   │     │   Database  │
└─────────────┘     └─────────────┘     └─────────────┘
                            │
                            ▼
                    ┌─────────────┐
                    │   Services  │
                    │  (Business  │
                    │    Logic)   │
                    └─────────────┘
                            │
                    ┌───────┴────────┐
                    ▼                ▼
            ┌─────────────┐  ┌─────────────┐
            │   OpenAI    │  │    Redis    │
            │     API     │  │    Cache    │
            └─────────────┘  └─────────────┘
```

### Capas del Sistema

1. **API Layer** (`app/api/v1/endpoints/nutrition.py`)
   - 40+ endpoints REST
   - Validación con Pydantic
   - Autenticación con Auth0
   - Documentación automática (Swagger)

2. **Service Layer** (`app/services/nutrition*.py`)
   - Lógica de negocio
   - Integración con IA
   - Cálculos de progreso
   - Validaciones complejas

3. **Data Layer** (`app/models/nutrition.py`)
   - Modelos SQLAlchemy
   - Relaciones ORM
   - Índices optimizados

4. **Schema Layer** (`app/schemas/nutrition*.py`)
   - DTOs y validación
   - Serialización JSON
   - Type hints

---

## 🔄 Tipos de Planes (Sistema Híbrido)

### 1. Plans Template (Individuales)

**Características:**
- Cada usuario inicia cuando quiere
- Progreso individual e independiente
- Ideal para planes personalizados
- Sin fecha de inicio global

**Ejemplo de Uso:**
```json
POST /api/v1/nutrition/plans
{
  "title": "Plan Pérdida de Grasa - 30 días",
  "description": "Plan personalizado para perder grasa",
  "plan_type": "template",
  "duration_days": 30,
  "goal": "weight_loss",
  "target_calories": 1800,
  "is_recurring": false
}
```

### 2. Plans Live (Challenges Grupales)

**Características:**
- Todos los participantes en el mismo día
- Fecha de inicio global sincronizada
- Crea comunidad y competencia sana
- Se archiva automáticamente al terminar

**Ejemplo de Uso:**
```json
POST /api/v1/nutrition/plans
{
  "title": "Detox Challenge - 21 días",
  "description": "Challenge grupal de detox que inicia el 1 de febrero",
  "plan_type": "live",
  "live_start_date": "2025-02-01T00:00:00Z",
  "duration_days": 21,
  "goal": "weight_loss",
  "target_calories": 1600,
  "is_recurring": false
}
```

**Estados Automáticos:**
- **NOT_STARTED**: Antes del 1 de febrero
- **RUNNING**: Del 1 al 21 de febrero
- **FINISHED**: Después del 21 de febrero
- **ARCHIVED**: Convertido a template para reutilización

### 3. Plans Archived (Históricos Reutilizables)

**Características:**
- Plans Live terminados convertidos a Template
- Preservan información del challenge original
- Pueden ser reutilizados como templates individuales
- Mantienen referencia al plan live original

---

## 👨‍🏫 Guía de Uso para Entrenadores

### Flujo Completo: Crear un Plan Nutricional

#### Paso 1: Crear el Plan Base

```bash
POST /api/v1/nutrition/plans
Authorization: Bearer {token}
Content-Type: application/json

{
  "title": "Ganancia Muscular - Intermedio",
  "description": "Plan de 8 semanas para ganancia muscular limpia",
  "plan_type": "template",
  "goal": "muscle_gain",
  "difficulty_level": "intermediate",
  "budget_level": "medium",
  "dietary_restrictions": ["gluten_free"],
  "duration_days": 56,
  "is_recurring": false,
  "target_calories": 2800,
  "target_protein_g": 180,
  "target_carbs_g": 350,
  "target_fat_g": 90,
  "is_public": true,
  "tags": ["muscle", "bulk", "gym"]
}
```

**Respuesta:**
```json
{
  "id": 123,
  "title": "Ganancia Muscular - Intermedio",
  "gym_id": 1,
  "creator_id": 45,
  "creator_name": "Juan Pérez",
  "plan_type": "template",
  "duration_days": 56,
  "created_at": "2025-01-15T10:00:00Z",
  ...
}
```

#### Paso 2: Agregar Días al Plan

```bash
POST /api/v1/nutrition/plans/123/days
Authorization: Bearer {token}

{
  "nutrition_plan_id": 123,
  "day_number": 1,
  "total_calories": 2800,
  "total_protein_g": 180,
  "total_carbs_g": 350,
  "total_fat_g": 90,
  "notes": "Día de entrenamiento pesado - piernas",
  "is_published": false
}
```

#### Paso 3: Agregar Comidas a Cada Día

```bash
POST /api/v1/nutrition/days/456/meals
Authorization: Bearer {token}

{
  "daily_plan_id": 456,
  "meal_type": "breakfast",
  "name": "Power Breakfast",
  "description": "Desayuno alto en proteínas para empezar el día con energía",
  "calories": 650,
  "protein_g": 45,
  "carbs_g": 75,
  "fat_g": 18,
  "fiber_g": 8,
  "preparation_time_minutes": 15,
  "cooking_instructions": "1. Cocinar avena en agua\n2. Agregar claras de huevo\n3. Mezclar con frutos rojos\n4. Añadir almendras",
  "order_in_day": 1,
  "image_url": "https://example.com/breakfast.jpg"
}
```

#### Paso 4A: Agregar Ingredientes Manualmente

```bash
POST /api/v1/nutrition/meals/789/ingredients
Authorization: Bearer {token}

{
  "meal_id": 789,
  "name": "Avena integral",
  "quantity": 80,
  "unit": "gr",
  "alternatives": "Quinoa, Amaranto",
  "is_optional": false,
  "calories_per_serving": 304,
  "protein_per_serving": 10.4,
  "carbs_per_serving": 54.4,
  "fat_per_serving": 4.8
}
```

#### Paso 4B: Generar Ingredientes con IA

```bash
# Primero, generar con IA
POST /api/v1/nutrition/meals/789/ingredients/ai-generate
Authorization: Bearer {token}

{
  "recipe_name": "Power Breakfast",
  "servings": 1,
  "dietary_restrictions": ["gluten_free"],
  "target_calories": 650,
  "target_protein": 45,
  "exclude_ingredients": ["soya", "lactosa"],
  "cuisine_type": "mediterranean",
  "preparation_complexity": "simple"
}
```

**Respuesta de IA:**
```json
{
  "success": true,
  "ingredients": [
    {
      "name": "Avena sin gluten",
      "quantity": 80,
      "unit": "gr",
      "alternatives": "Quinoa cocida",
      "calories_per_unit": 3.8,
      "protein_per_unit": 0.13,
      "carbs_per_unit": 0.68,
      "fat_per_unit": 0.06,
      "fiber_per_unit": 0.1,
      "confidence_score": 0.9
    },
    {
      "name": "Claras de huevo",
      "quantity": 150,
      "unit": "ml",
      "alternatives": "Tofu sedoso",
      "calories_per_unit": 0.52,
      "protein_per_unit": 0.11,
      "carbs_per_unit": 0.007,
      "fat_per_unit": 0.002,
      "confidence_score": 0.95
    },
    ...
  ],
  "total_calories": 645,
  "total_protein": 44.5,
  "total_carbs": 73.2,
  "total_fat": 17.8,
  "confidence_score": 0.88
}
```

```bash
# Luego, aplicar los ingredientes generados
POST /api/v1/nutrition/meals/789/ingredients/apply
Authorization: Bearer {token}

{
  "ingredients": [...], // Los ingredientes generados
  "replace_existing": true,
  "update_meal_nutrition": true
}
```

#### Paso 5: Publicar el Plan

```bash
POST /api/v1/nutrition/days/456/publish
Authorization: Bearer {token}

{
  "notify_followers": true
}
```

### Crear un Challenge Grupal (Plan Live)

```bash
POST /api/v1/nutrition/plans
Authorization: Bearer {token}

{
  "title": "🔥 Reto Verano 2025 - 30 días",
  "description": "Challenge grupal para llegar en forma al verano. ¡Iniciamos todos juntos el 1 de marzo!",
  "plan_type": "live",
  "live_start_date": "2025-03-01T00:00:00Z",
  "duration_days": 30,
  "goal": "weight_loss",
  "difficulty_level": "intermediate",
  "budget_level": "medium",
  "dietary_restrictions": [],
  "target_calories": 1800,
  "target_protein_g": 140,
  "target_carbs_g": 180,
  "target_fat_g": 60,
  "is_public": true,
  "tags": ["challenge", "verano", "grupal", "comunidad"]
}
```

**Características del Challenge:**
- Todos los participantes empiezan el 1 de marzo
- Contador de participantes visible: `live_participants_count`
- Estado automático: NOT_STARTED → RUNNING → FINISHED → ARCHIVED
- Al terminar, se convierte en template para reutilización futura

---

## 👤 Guía de Uso para Miembros

### Flujo del Usuario

#### 1. Buscar Planes Disponibles

```bash
GET /api/v1/nutrition/plans?goal=weight_loss&difficulty_level=beginner&page=1&per_page=10
Authorization: Bearer {token}
```

**Respuesta:**
```json
{
  "items": [
    {
      "id": 123,
      "title": "Plan Principiante - Pérdida de Peso",
      "description": "Plan de 30 días para perder peso de forma saludable",
      "plan_type": "template",
      "creator_name": "Coach María",
      "duration_days": 30,
      "target_calories": 1600,
      "followers_count": 45,
      "avg_satisfaction": 4.5,
      "current_day": null,
      "status": "not_started",
      "is_followed_by_user": false
    },
    {
      "id": 124,
      "title": "🔥 Detox Challenge Febrero",
      "plan_type": "live",
      "live_start_date": "2025-02-01T00:00:00Z",
      "live_participants_count": 28,
      "days_until_start": 7,
      "status": "not_started",
      "is_followed_by_user": false
    }
  ],
  "total": 15,
  "page": 1,
  "per_page": 10
}
```

#### 2. Ver Detalles de un Plan

```bash
GET /api/v1/nutrition/plans/123
Authorization: Bearer {token}
```

**Respuesta Detallada:**
```json
{
  "id": 123,
  "title": "Plan Principiante - Pérdida de Peso",
  "description": "Plan completo con 3 comidas principales y 2 snacks",
  "plan_type": "template",
  "creator_name": "Coach María",
  "duration_days": 30,
  "is_recurring": false,
  "goal": "weight_loss",
  "difficulty_level": "beginner",
  "budget_level": "economic",
  "dietary_restrictions": [],
  "target_calories": 1600,
  "target_protein_g": 120,
  "target_carbs_g": 160,
  "target_fat_g": 53,
  "tags": ["pérdida peso", "principiante", "económico"],
  "followers_count": 45,
  "is_followed_by_user": false,
  "daily_plans": [
    {
      "id": 456,
      "day_number": 1,
      "total_calories": 1580,
      "notes": "Día de inicio - hidratación importante",
      "meals": [
        {
          "id": 789,
          "meal_type": "breakfast",
          "name": "Desayuno Energético",
          "description": "Perfecto para empezar el día",
          "calories": 380,
          "protein_g": 25,
          "preparation_time_minutes": 10,
          "image_url": "https://...",
          "ingredients": [
            {
              "name": "Avena",
              "quantity": 50,
              "unit": "gr",
              "alternatives": "Quinoa"
            },
            ...
          ]
        },
        ...
      ]
    },
    ...
  ]
}
```

#### 3. Seguir un Plan

```bash
POST /api/v1/nutrition/plans/123/follow
Authorization: Bearer {token}

{
  "notifications_enabled": true,
  "notification_time_breakfast": "07:30",
  "notification_time_lunch": "13:00",
  "notification_time_dinner": "20:00"
}
```

**Respuesta:**
```json
{
  "id": 567,
  "user_id": 89,
  "plan_id": 123,
  "is_active": true,
  "start_date": "2025-01-20T00:00:00Z",
  "notifications_enabled": true,
  "notification_time_breakfast": "07:30",
  "notification_time_lunch": "13:00",
  "notification_time_dinner": "20:00"
}
```

#### 4. Ver Plan del Día (Today)

```bash
GET /api/v1/nutrition/today
Authorization: Bearer {token}
```

**Respuesta:**
```json
{
  "plan_id": 123,
  "plan_title": "Plan Principiante - Pérdida de Peso",
  "current_day": 5,
  "total_days": 30,
  "status": "running",
  "meals": [
    {
      "id": 801,
      "meal_type": "breakfast",
      "name": "Tostadas Integrales con Aguacate",
      "calories": 420,
      "protein_g": 18,
      "preparation_time_minutes": 10,
      "is_completed": false,
      "completion_id": null,
      "ingredients": [...]
    },
    {
      "id": 802,
      "meal_type": "mid_morning",
      "name": "Snack de Frutas y Nueces",
      "calories": 180,
      "is_completed": true,
      "completion_id": 999,
      "completed_at": "2025-01-20T10:30:00Z",
      "satisfaction_rating": 5
    },
    ...
  ],
  "progress": {
    "meals_completed": 2,
    "total_meals": 5,
    "percentage": 40,
    "calories_consumed": 600,
    "calories_target": 1600,
    "protein_consumed": 45,
    "protein_target": 120
  },
  "days_until_start": null  // Para planes live no iniciados
}
```

#### 5. Marcar Comida Completada

```bash
POST /api/v1/nutrition/meals/801/complete
Authorization: Bearer {token}

{
  "satisfaction_rating": 4,
  "photo_url": "https://storage.example.com/meals/user89/breakfast_20250120.jpg",
  "notes": "Cambié el pan integral por pan de centeno",
  "portion_size_modifier": 0.8  // Comí 80% de la porción
}
```

**Respuesta:**
```json
{
  "id": 1000,
  "user_id": 89,
  "meal_id": 801,
  "completed_at": "2025-01-20T08:45:00Z",
  "satisfaction_rating": 4,
  "photo_url": "https://storage.example.com/meals/user89/breakfast_20250120.jpg",
  "notes": "Cambié el pan integral por pan de centeno",
  "portion_size_modifier": 0.8
}
```

#### 6. Ver Dashboard Personal

```bash
GET /api/v1/nutrition/dashboard
Authorization: Bearer {token}
```

**Respuesta:**
```json
{
  "template_plans": [
    {
      "id": 123,
      "title": "Plan Principiante - Pérdida de Peso",
      "plan_type": "template",
      "current_day": 5,
      "total_days": 30,
      "status": "running",
      "progress_percentage": 16.7,
      "today_completed": 2,
      "today_total": 5
    }
  ],
  "live_plans": [
    {
      "id": 124,
      "title": "🔥 Detox Challenge Febrero",
      "plan_type": "live",
      "live_start_date": "2025-02-01T00:00:00Z",
      "live_participants_count": 45,
      "days_until_start": 12,
      "status": "not_started",
      "is_live_active": false
    }
  ],
  "available_plans": [
    {
      "id": 125,
      "title": "Plan Vegano - Mantenimiento",
      "creator_name": "Nutricionista Ana",
      "followers_count": 23
    }
  ],
  "today_plan": {
    "meals": [...],
    "progress": {...}
  },
  "stats": {
    "completion_streak": 4,
    "weekly_average": 85,
    "total_plans_followed": 3,
    "total_meals_completed": 67
  }
}
```

---

## 📚 Referencia de API - Endpoints

### Endpoints Públicos (Sin Autenticación)

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/v1/nutrition/enums/nutrition-goals` | Lista de objetivos disponibles |
| GET | `/api/v1/nutrition/enums/difficulty-levels` | Niveles de dificultad |
| GET | `/api/v1/nutrition/enums/budget-levels` | Niveles de presupuesto |
| GET | `/api/v1/nutrition/enums/dietary-restrictions` | Restricciones dietéticas |
| GET | `/api/v1/nutrition/enums/meal-types` | Tipos de comidas |

### Endpoints de Planes

| Método | Endpoint | Descripción | Permisos |
|--------|----------|-------------|----------|
| GET | `/api/v1/nutrition/plans` | Listar planes disponibles | Member+ |
| POST | `/api/v1/nutrition/plans` | Crear nuevo plan | Trainer+ |
| GET | `/api/v1/nutrition/plans/{id}` | Ver detalles de plan | Member+ |
| PUT | `/api/v1/nutrition/plans/{id}` | Actualizar plan | Owner |
| DELETE | `/api/v1/nutrition/plans/{id}` | Eliminar plan (soft) | Owner |
| POST | `/api/v1/nutrition/plans/{id}/follow` | Seguir plan | Member+ |
| DELETE | `/api/v1/nutrition/plans/{id}/follow` | Dejar de seguir | Member+ |
| POST | `/api/v1/nutrition/plans/{id}/archive` | Archivar plan live | Owner |
| GET | `/api/v1/nutrition/plans/{id}/analytics` | Ver analytics | Owner |

### Endpoints de Días

| Método | Endpoint | Descripción | Permisos |
|--------|----------|-------------|----------|
| POST | `/api/v1/nutrition/plans/{id}/days` | Agregar día a plan | Owner |
| GET | `/api/v1/nutrition/days/{id}` | Ver día específico | Member+ |
| PUT | `/api/v1/nutrition/days/{id}` | Actualizar día | Owner |
| DELETE | `/api/v1/nutrition/days/{id}` | Eliminar día | Owner |
| POST | `/api/v1/nutrition/days/{id}/publish` | Publicar día | Owner |

### Endpoints de Comidas

| Método | Endpoint | Descripción | Permisos |
|--------|----------|-------------|----------|
| POST | `/api/v1/nutrition/days/{id}/meals` | Agregar comida a día | Owner |
| GET | `/api/v1/nutrition/meals/{id}` | Ver comida | Member+ |
| PUT | `/api/v1/nutrition/meals/{id}` | Actualizar comida | Owner |
| DELETE | `/api/v1/nutrition/meals/{id}` | Eliminar comida | Owner |
| POST | `/api/v1/nutrition/meals/{id}/complete` | Marcar completada | Member+ |

### Endpoints de Ingredientes

| Método | Endpoint | Descripción | Permisos |
|--------|----------|-------------|----------|
| POST | `/api/v1/nutrition/meals/{id}/ingredients` | Agregar ingrediente | Owner |
| PUT | `/api/v1/nutrition/ingredients/{id}` | Actualizar ingrediente | Owner |
| DELETE | `/api/v1/nutrition/ingredients/{id}` | Eliminar ingrediente | Owner |

### Endpoints de IA

| Método | Endpoint | Descripción | Permisos |
|--------|----------|-------------|----------|
| POST | `/api/v1/nutrition/meals/{id}/ingredients/ai-generate` | Generar con IA | Owner |
| POST | `/api/v1/nutrition/meals/{id}/ingredients/apply` | Aplicar generados | Owner |
| GET | `/api/v1/nutrition/ai/test-connection` | Test conexión OpenAI | Admin |

### Endpoints de Usuario

| Método | Endpoint | Descripción | Permisos |
|--------|----------|-------------|----------|
| GET | `/api/v1/nutrition/today` | Plan de hoy | Member+ |
| GET | `/api/v1/nutrition/dashboard` | Dashboard personal | Member+ |
| GET | `/api/v1/nutrition/my-progress` | Mi progreso | Member+ |
| GET | `/api/v1/nutrition/followed-plans` | Planes que sigo | Member+ |

### Parámetros de Query Comunes

#### Listado de Planes (`GET /plans`)
```
?page=1                         # Número de página
&per_page=20                    # Items por página (max 100)
&goal=weight_loss               # Filtrar por objetivo
&difficulty_level=beginner      # Filtrar por dificultad
&budget_level=economic          # Filtrar por presupuesto
&dietary_restrictions=vegan     # Filtrar por restricción
&search_query=detox             # Búsqueda en título/descripción
&creator_id=45                  # Filtrar por creador
&plan_type=live                 # Filtrar por tipo (template/live/archived)
&status=running                 # Filtrar por estado
&is_live_active=true           # Solo planes live activos
```

---

## 🤖 Integración con IA (OpenAI)

### Configuración Requerida

```bash
# En archivo .env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini  # Modelo por defecto
OPENAI_MAX_TOKENS=2000
OPENAI_TEMPERATURE=0.7
```

### Proceso de Generación de Ingredientes

1. **Request del Usuario**
```json
{
  "recipe_name": "Ensalada Mediterránea",
  "servings": 2,
  "dietary_restrictions": ["vegetarian"],
  "target_calories": 450,
  "target_protein": 15,
  "exclude_ingredients": ["tomate"],
  "cuisine_type": "mediterranean"
}
```

2. **Prompt al Modelo**
```
Sistema: Eres un nutricionista experto. Genera ingredientes con valores nutricionales precisos.
- Límites realistas: máximo 9 kcal/g
- Unidades válidas: gr, ml, units, cups, tbsp, tsp
- Coherencia nutricional obligatoria

Usuario: Genera ingredientes para "Ensalada Mediterránea" para 2 porciones...
```

3. **Respuesta de OpenAI**
```json
{
  "ingredients": [
    {
      "name": "Lechuga mixta",
      "quantity": 150,
      "unit": "gr",
      "alternatives": "Espinacas, Rúcula",
      "calories_per_unit": 0.15,
      "protein_per_unit": 0.013,
      "carbs_per_unit": 0.029,
      "fat_per_unit": 0.002,
      "fiber_per_unit": 0.013
    },
    {
      "name": "Pepino",
      "quantity": 100,
      "unit": "gr",
      "alternatives": "Apio",
      "calories_per_unit": 0.16,
      "protein_per_unit": 0.007,
      "carbs_per_unit": 0.036,
      "fat_per_unit": 0.001
    },
    ...
  ],
  "total_calories": 445,
  "confidence_score": 0.92
}
```

4. **Validación y Limpieza**
- Verificar límites realistas
- Coherencia calórica
- Ajuste proporcional si necesario
- Aplicación a la comida

### Manejo de Errores

| Error | Código | Solución |
|-------|--------|----------|
| Rate Limit | 429 | Reintentar en 60 segundos |
| Timeout | 500 | Request tomó >30s, reintentar |
| Invalid Key | 403 | Verificar OPENAI_API_KEY |
| Model Error | 500 | Cambiar modelo o reducir complejidad |

---

## 📊 Modelos de Datos

### Jerarquía Principal

```
NutritionPlan (Plan Nutricional)
│
├── plan_type: TEMPLATE | LIVE | ARCHIVED
├── duration_days: 1-365
├── goal: weight_loss | muscle_gain | maintenance...
├── target_calories, protein, carbs, fat
│
└── DailyNutritionPlan (Día del Plan)
    ├── day_number: 1, 2, 3...
    ├── total_calories, protein, carbs, fat
    │
    └── Meal (Comida)
        ├── meal_type: breakfast | lunch | dinner...
        ├── calories, protein, carbs, fat
        │
        └── MealIngredient (Ingrediente)
            ├── name, quantity, unit
            └── calories_per_serving, protein_per_serving...

NutritionPlanFollower (Seguidor del Plan)
├── user_id, plan_id
├── start_date, end_date
└── notifications_enabled, times

UserMealCompletion (Comida Completada)
├── user_id, meal_id
├── completed_at
├── satisfaction_rating: 1-5
└── photo_url, notes

UserDailyProgress (Progreso Diario)
├── user_id, daily_plan_id
├── date
├── meals_completed / total_meals
└── completion_percentage
```

### Enums y Tipos

```python
# Objetivos Nutricionales
NutritionGoal = {
    BULK: "Volumen muscular",
    CUT: "Definición muscular",
    MAINTENANCE: "Mantenimiento",
    WEIGHT_LOSS: "Pérdida de peso",
    MUSCLE_GAIN: "Ganancia muscular",
    PERFORMANCE: "Rendimiento deportivo"
}

# Niveles de Dificultad
DifficultyLevel = {
    BEGINNER: "Principiante",
    INTERMEDIATE: "Intermedio",
    ADVANCED: "Avanzado"
}

# Niveles de Presupuesto
BudgetLevel = {
    ECONOMIC: "Económico",
    MEDIUM: "Medio",
    PREMIUM: "Premium"
}

# Restricciones Dietéticas
DietaryRestriction = {
    NONE: "Sin restricciones",
    VEGETARIAN: "Vegetariano",
    VEGAN: "Vegano",
    GLUTEN_FREE: "Sin gluten",
    LACTOSE_FREE: "Sin lactosa",
    KETO: "Cetogénico",
    PALEO: "Paleo",
    MEDITERRANEAN: "Mediterráneo"
}

# Tipos de Plan
PlanType = {
    TEMPLATE: "Individual",
    LIVE: "Challenge grupal",
    ARCHIVED: "Histórico"
}

# Tipos de Comida
MealType = {
    BREAKFAST: "Desayuno",
    MID_MORNING: "Media mañana",
    LUNCH: "Almuerzo",
    AFTERNOON: "Merienda",
    DINNER: "Cena",
    POST_WORKOUT: "Post-entreno",
    LATE_SNACK: "Snack nocturno"
}

# Estados del Plan
PlanStatus = {
    NOT_STARTED: "No iniciado",
    RUNNING: "En progreso",
    FINISHED: "Finalizado",
    ARCHIVED: "Archivado"
}

# Unidades de Medida
Units = {
    gr: "Gramos",
    ml: "Mililitros",
    units: "Unidades",
    cups: "Tazas",
    tbsp: "Cucharadas",
    tsp: "Cucharaditas",
    oz: "Onzas",
    kg: "Kilogramos",
    l: "Litros"
}
```

---

## 💡 Casos de Uso Reales

### Caso 1: Gimnasio con Nutricionista

**Escenario:** Gimnasio premium con nutricionista en staff

**Implementación:**
1. Nutricionista crea planes template personalizados para cada cliente
2. Planes privados (is_public=false) solo para sus clientes
3. Seguimiento semanal del progreso con analytics
4. Ajustes basados en feedback (satisfaction_rating)

**Beneficios:**
- Digitalización del servicio de nutrición
- Mejor adherencia con app móvil
- Métricas para demostrar resultados

### Caso 2: Challenge de Transformación

**Escenario:** Gimnasio organiza "Reto Verano 90 días"

**Implementación:**
1. Crear plan live con fecha de inicio específica
2. Promoción del challenge (mostrar contador de participantes)
3. Todos los participantes en el mismo día del plan
4. Premios basados en adherencia y progreso

**Código:**
```json
{
  "title": "🏖️ Reto Verano 90 Días",
  "plan_type": "live",
  "live_start_date": "2025-03-01",
  "duration_days": 90,
  "is_public": true,
  "tags": ["challenge", "verano", "transformación"]
}
```

**Métricas del Challenge:**
- Participantes activos: `live_participants_count`
- Adherencia promedio: Analytics endpoint
- Comidas más populares
- Satisfacción general

### Caso 3: Planes para Equipos Deportivos

**Escenario:** Entrenador de equipo de fútbol

**Implementación:**
1. Plan live sincronizado para todo el equipo
2. Diferentes variantes según posición (defensa, mediocampo, delantero)
3. Ajustes según calendario de partidos
4. Tracking de hidratación y suplementación

**Características Especiales:**
- is_recurring=true para temporada completa
- Notificaciones sincronizadas para todo el equipo
- Reportes semanales al cuerpo técnico

### Caso 4: Nutrición Post-Cirugía Bariátrica

**Escenario:** Centro médico con programa post-bariátrica

**Implementación:**
1. Planes template con progresión específica
2. Fases: líquidos → purés → sólidos
3. Control estricto de porciones (portion_size_modifier)
4. Fotografías obligatorias para supervisión médica

**Validaciones Especiales:**
- Calorías muy bajas (600-800 inicial)
- Proteína prioritaria
- Volúmenes pequeños
- Progresión gradual

---

## ❓ Preguntas Frecuentes

### General

**P: ¿Necesito tener conocimientos de nutrición para crear planes?**
R: Es recomendable tener conocimientos básicos. La IA puede ayudar con ingredientes, pero el diseño del plan requiere conocimiento profesional.

**P: ¿Puedo vender mis planes nutricionales?**
R: Sí, el sistema soporta planes públicos y privados. Puedes monetizar tus planes premium.

**P: ¿Los usuarios pueden seguir múltiples planes?**
R: Sí, un usuario puede seguir varios planes simultáneamente.

### Planes Live (Challenges)

**P: ¿Qué pasa si un usuario se une a un challenge ya iniciado?**
R: El usuario entrará en el día actual del challenge, no desde el día 1. Esto mantiene la sincronización grupal.

**P: ¿Puedo modificar un plan live mientras está en progreso?**
R: Sí, puedes modificar días futuros, pero no días pasados para mantener la consistencia.

**P: ¿Qué sucede cuando termina un plan live?**
R: Se convierte automáticamente en plan archived (template) para que pueda ser reutilizado.

### Inteligencia Artificial

**P: ¿Qué modelo de IA se usa?**
R: GPT-4o-mini por defecto, configurable a otros modelos de OpenAI.

**P: ¿Hay límite de generaciones con IA?**
R: Depende de tu plan de OpenAI. El sistema maneja rate limits automáticamente.

**P: ¿La IA puede generar planes completos?**
R: Actualmente solo genera ingredientes. La estructura del plan debe crearla el entrenador.

### Tracking y Progreso

**P: ¿Las fotos de comidas son obligatorias?**
R: No, son opcionales. Sirven para evidencia visual y motivación.

**P: ¿Qué pasa si olvido marcar una comida como completada?**
R: Puedes marcarla retrospectivamente, pero se registra la hora real de marcado.

**P: ¿Cómo se calcula el streak de días?**
R: Días consecutivos con al menos 80% de comidas completadas.

### Técnico

**P: ¿El módulo funciona sin conexión?**
R: No, requiere conexión para sincronizar con el servidor.

**P: ¿Hay límite de ingredientes por comida?**
R: Técnicamente no, pero se recomienda máximo 15-20 para usabilidad.

**P: ¿Se pueden importar planes desde Excel/CSV?**
R: No directamente, pero puedes crear un script usando los endpoints de API.

### Seguridad y Privacidad

**P: ¿Los planes son privados por defecto?**
R: Sí, is_public=false por defecto. Debes explícitamente hacerlos públicos.

**P: ¿Otros gimnasios pueden ver mis planes?**
R: No, el sistema es multi-tenant. Cada gimnasio está completamente aislado.

**P: ¿Se guardan las fotos de comidas de forma segura?**
R: Las URLs de fotos se guardan, el almacenamiento real depende de tu configuración (S3, etc).

---

## 📈 Métricas y Analytics

### Para Entrenadores

```bash
GET /api/v1/nutrition/plans/{id}/analytics
```

**Métricas Disponibles:**
- Total de seguidores (histórico)
- Seguidores activos actuales
- Tasa promedio de completación
- Satisfacción promedio (1-5)
- Comidas más/menos populares
- Tendencias de adherencia por día de la semana
- Distribución de abandonos por día del plan

### Para Gimnasios

**Métricas Agregadas:**
- Plans más populares
- Entrenadores más activos
- Participación en challenges
- Retención de usuarios con nutrición vs sin nutrición
- Ingresos adicionales por planes premium

### KPIs Recomendados

| KPI | Fórmula | Meta Sugerida |
|-----|---------|---------------|
| Adherencia | Comidas completadas / Total | >70% |
| Satisfacción | Promedio ratings | >4.0/5 |
| Retención | Usuarios activos día 30 / Total | >60% |
| Engagement | Fotos subidas / Comidas | >30% |
| Conversión | Seguidores / Vistas | >10% |

---

## 🚀 Mejores Prácticas

### Para Crear Plans Exitosos

1. **Progresión Gradual**
   - No cambios drásticos de calorías
   - Introducir alimentos nuevos gradualmente
   - Aumentar dificultad progresivamente

2. **Variedad**
   - Rotar proteínas, carbohidratos y vegetales
   - Diferentes métodos de cocción
   - Opciones de temporada

3. **Flexibilidad**
   - Siempre ofrecer alternativas
   - Contemplar diferentes presupuestos
   - Adaptable a diferentes horarios

4. **Educación**
   - Explicar el "por qué" de cada comida
   - Tips de preparación
   - Información nutricional clara

5. **Comunidad**
   - Fomentar compartir fotos
   - Challenges grupales periódicos
   - Celebrar logros

### Para Maximizar Adherencia

1. **Preparación Simple**
   - Meal prep dominical
   - Recetas de <30 minutos
   - Ingredientes fáciles de conseguir

2. **Personalización**
   - Ajustar a gustos personales
   - Respetar restricciones culturales
   - Adaptable a rutina diaria

3. **Soporte Continuo**
   - Check-ins semanales
   - Ajustes según feedback
   - Motivación constante

4. **Medición de Resultados**
   - Fotos de progreso
   - Medidas corporales
   - Energía y bienestar

---

## 🔧 Configuración Avanzada

### Variables de Entorno

```bash
# Nutrición
NUTRITION_MODULE_ENABLED=true
NUTRITION_AI_ENABLED=true
NUTRITION_MAX_PLANS_PER_USER=10
NUTRITION_MAX_FOLLOWERS_PER_PLAN=500
NUTRITION_DEFAULT_NOTIFICATION_TIMES="07:30,13:00,20:00"

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
OPENAI_MAX_TOKENS=2000
OPENAI_TEMPERATURE=0.7
OPENAI_TIMEOUT=30

# Límites
NUTRITION_MAX_INGREDIENTS_PER_MEAL=25
NUTRITION_MAX_MEALS_PER_DAY=8
NUTRITION_MAX_DAYS_PER_PLAN=365
NUTRITION_PHOTO_MAX_SIZE_MB=10
```

### Webhooks y Eventos

El sistema puede emitir eventos para integraciones:

```python
# Eventos disponibles
NUTRITION_PLAN_CREATED
NUTRITION_PLAN_FOLLOWED
NUTRITION_MEAL_COMPLETED
NUTRITION_CHALLENGE_STARTED
NUTRITION_CHALLENGE_COMPLETED
NUTRITION_STREAK_MILESTONE  # 7, 14, 30 días
```

### Integraciones Posibles

- **MyFitnessPal**: Sincronización de calorías
- **Fitbit/Garmin**: Ajuste por actividad física
- **Instagram**: Compartir logros automáticamente
- **WhatsApp Business**: Recordatorios de comidas
- **Google Calendar**: Agregar comidas al calendario
- **Slack**: Notificaciones de equipo

---

## 📝 Conclusión

El módulo de nutrición es una herramienta poderosa y completa que transforma la manera en que los gimnasios ofrecen servicios nutricionales. Con su sistema híbrido de planes, integración con IA, y capacidades de tracking detalladas, proporciona valor tanto a entrenadores como a usuarios finales.

### Características Clave Resumidas

✅ **Sistema Híbrido**: Template, Live y Archived plans
✅ **IA Integrada**: Generación automática de ingredientes
✅ **Multi-tenant**: Aislamiento completo por gimnasio
✅ **Tracking Completo**: Fotos, satisfacción, progreso
✅ **Analytics**: Métricas para optimización continua
✅ **API RESTful**: 40+ endpoints documentados
✅ **Escalable**: Arquitectura preparada para crecimiento

### Soporte y Contacto

- **Documentación API**: `/api/v1/nutrition/docs`
- **Swagger UI**: `/api/v1/docs#/nutrition`
- **GitHub Issues**: Para reportar bugs
- **Email Soporte**: soporte@gymapi.com

---

*Última actualización: Enero 2025*
*Versión del módulo: 2.0 (Sistema Híbrido)*