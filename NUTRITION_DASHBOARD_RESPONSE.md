# Estructura de Respuesta del Dashboard de Nutrición

**Endpoint:** `GET /api/v1/nutrition/dashboard`
**Response Model:** `NutritionDashboardHybrid`

---

## 📋 Estructura Completa

```typescript
{
  // PLANES TEMPLATE (individuales que el usuario sigue)
  template_plans: [
    {
      // Información básica
      id: number,
      title: string,
      description: string | null,
      goal: string | null,
      duration_weeks: number | null,
      is_public: boolean,
      tags: string[] | null,

      // Identificadores
      creator_id: number,
      gym_id: number,

      // Estado del plan
      is_active: boolean,
      created_at: string,  // ISO datetime
      updated_at: string | null,

      // === CAMPOS HÍBRIDOS ===
      plan_type: "template",  // SIEMPRE "template" aquí
      live_start_date: null,
      live_end_date: null,
      is_live_active: false,
      live_participants_count: 0,
      original_live_plan_id: null,
      archived_at: null,
      original_participants_count: null,

      // === CAMPOS CALCULADOS (importantes!) ===
      current_day: number,  // Día actual según start_date del follower
      status: "not_started" | "running" | "finished",
      days_until_start: number | null,

      // === ESTADÍSTICAS OPCIONALES ===
      total_followers: number | null,
      avg_satisfaction: number | null  // 0.0 - 5.0
    }
  ],

  // PLANES LIVE (challenges grupales activos/próximos)
  live_plans: [
    {
      // Información básica (igual que template)
      id: number,
      title: string,
      description: string | null,
      goal: string | null,
      duration_weeks: number | null,
      is_public: boolean,
      tags: string[] | null,

      creator_id: number,
      gym_id: number,
      is_active: boolean,
      created_at: string,
      updated_at: string | null,

      // === CAMPOS HÍBRIDOS (DIFERENTES para LIVE) ===
      plan_type: "live",  // SIEMPRE "live" aquí
      live_start_date: string,  // ISO datetime - IMPORTANTE
      live_end_date: string,    // ISO datetime - IMPORTANTE
      is_live_active: boolean,  // true si está en curso ahora
      live_participants_count: number,  // Contador en tiempo real
      original_live_plan_id: null,
      archived_at: null,
      original_participants_count: null,

      // === CAMPOS CALCULADOS (para LIVE) ===
      current_day: number,  // Basado en live_start_date GLOBAL
      status: "not_started" | "running" | "finished",  // IGUAL para todos
      days_until_start: number | null,  // Días hasta que inicie

      // === ESTADÍSTICAS ===
      total_followers: number | null,
      avg_satisfaction: number | null
    }
  ],

  // PLANES DISPONIBLES (públicos que el usuario NO sigue)
  available_plans: [
    {
      // Estructura igual a template_plans
      // Diferencia: el usuario NO está siguiendo estos planes
      // Útil para mostrar "Planes Recomendados" o "Únete a"
      id: number,
      title: string,
      // ... resto de campos igual que arriba ...

      // IMPORTANTE: Estos NO tienen current_day ni status personal
      // porque el usuario no los sigue
      current_day: null,
      status: null
    }
  ],

  // PLAN DE HOY (comidas para el día actual)
  today_plan: {
    // Fecha actual
    date: string,  // ISO datetime

    // Plan diario específico
    daily_plan: {
      id: number,
      nutrition_plan_id: number,
      day_number: number,
      planned_date: string | null,
      total_calories: number | null,
      total_protein_g: number | null,
      total_carbs_g: number | null,
      total_fat_g: number | null,
      notes: string | null,
      is_published: boolean,
      published_at: string | null,
      created_at: string,
      updated_at: string | null
    } | null,

    // Comidas del día (array)
    meals: [
      {
        id: number,
        daily_plan_id: number,
        meal_type: "breakfast" | "mid_morning" | "lunch" | "afternoon" | "dinner" | "post_workout" | "late_snack",
        name: string,
        description: string | null,
        preparation_instructions: string | null,

        // Información nutricional
        calories: number | null,
        protein_g: number | null,
        carbs_g: number | null,
        fat_g: number | null,
        fiber_g: number | null,

        // Media
        image_url: string | null,
        video_url: string | null,

        order_in_day: number,
        created_at: string,
        updated_at: string | null,

        // Ingredientes (array)
        ingredients: [
          {
            id: number,
            meal_id: number,
            name: string,
            quantity: number,
            unit: string,  // "gr", "ml", "units", "cups", etc.
            alternatives: string | null,  // JSON string
            is_optional: boolean,
            calories_per_serving: number | null,
            protein_per_serving: number | null,
            carbs_per_serving: number | null,
            fat_per_serving: number | null,
            created_at: string
          }
        ]
      }
    ],

    // Progreso del día
    progress: {
      id: number,
      user_id: number,
      daily_plan_id: number,
      date: string,
      meals_completed: number,
      total_meals: number,
      completion_percentage: number,  // 0.0 - 100.0
      overall_satisfaction: number | null,  // 1-5 rating
      difficulty_rating: number | null,     // 1-5 rating
      notes: string | null,
      weight_kg: number | null,
      body_fat_percentage: number | null,
      created_at: string,
      updated_at: string | null
    } | null,

    // Porcentaje de completación (calculado)
    completion_percentage: number,  // 0.0 - 100.0

    // === INFORMACIÓN DEL PLAN ACTUAL ===
    plan: {
      // Objeto NutritionPlan completo del plan que se está siguiendo hoy
      id: number,
      title: string,
      plan_type: "template" | "live",
      // ... resto de campos de NutritionPlan
    } | null,

    // === ESTADO DEL PLAN HOY ===
    current_day: number,  // Día actual del plan
    status: "not_started" | "running" | "finished",
    days_until_start: number | null
  } | null,  // null si no hay plan activo hoy

  // RACHA DE COMPLETACIÓN (días consecutivos)
  completion_streak: number,  // Ejemplo: 7 = 7 días seguidos cumpliendo

  // PROGRESO SEMANAL (últimos 7 días)
  weekly_progress: [
    {
      id: number,
      user_id: number,
      daily_plan_id: number,
      date: string,  // ISO datetime
      meals_completed: number,
      total_meals: number,
      completion_percentage: number,
      overall_satisfaction: number | null,
      difficulty_rating: number | null,
      notes: string | null,
      weight_kg: number | null,
      body_fat_percentage: number | null,
      created_at: string,
      updated_at: string | null
    }
  ]
}
```

---

## 🎯 Ejemplo Real de Respuesta

```json
{
  "template_plans": [
    {
      "id": 123,
      "title": "Mi Plan de Pérdida de Grasa",
      "description": "Plan personalizado de 8 semanas",
      "goal": "Perder 5kg de forma saludable",
      "duration_weeks": 8,
      "is_public": false,
      "tags": ["perdida_grasa", "deficit_calorico"],
      "creator_id": 5,
      "gym_id": 4,
      "is_active": true,
      "created_at": "2025-01-01T00:00:00Z",
      "updated_at": "2025-01-15T10:30:00Z",

      "plan_type": "template",
      "live_start_date": null,
      "live_end_date": null,
      "is_live_active": false,
      "live_participants_count": 0,
      "original_live_plan_id": null,
      "archived_at": null,
      "original_participants_count": null,

      "current_day": 24,
      "status": "running",
      "days_until_start": null,

      "total_followers": 1,
      "avg_satisfaction": 4.5
    }
  ],

  "live_plans": [
    {
      "id": 456,
      "title": "Challenge Detox 2025",
      "description": "Challenge grupal de 21 días para desintoxicar el cuerpo",
      "goal": "Eliminar toxinas y mejorar energía",
      "duration_weeks": 3,
      "is_public": true,
      "tags": ["detox", "challenge", "2025"],
      "creator_id": 5,
      "gym_id": 4,
      "is_active": true,
      "created_at": "2024-12-15T00:00:00Z",
      "updated_at": "2025-01-20T15:00:00Z",

      "plan_type": "live",
      "live_start_date": "2025-01-20T00:00:00Z",
      "live_end_date": "2025-02-10T23:59:59Z",
      "is_live_active": true,
      "live_participants_count": 87,
      "original_live_plan_id": null,
      "archived_at": null,
      "original_participants_count": null,

      "current_day": 5,
      "status": "running",
      "days_until_start": 0,

      "total_followers": 87,
      "avg_satisfaction": 4.8
    }
  ],

  "available_plans": [
    {
      "id": 789,
      "title": "Plan Masa Muscular",
      "description": "Gana músculo con este plan de 12 semanas",
      "goal": "Ganar 3-5kg de músculo magro",
      "duration_weeks": 12,
      "is_public": true,
      "tags": ["ganancia_muscular", "hipertrofia"],
      "creator_id": 10,
      "gym_id": 4,
      "is_active": true,
      "created_at": "2024-11-01T00:00:00Z",
      "updated_at": "2025-01-10T08:00:00Z",

      "plan_type": "template",
      "live_start_date": null,
      "live_end_date": null,
      "is_live_active": false,
      "live_participants_count": 0,
      "original_live_plan_id": null,
      "archived_at": null,
      "original_participants_count": null,

      "current_day": null,
      "status": null,
      "days_until_start": null,

      "total_followers": 150,
      "avg_satisfaction": 4.7
    }
  ],

  "today_plan": {
    "date": "2025-12-24T00:00:00Z",
    "daily_plan": {
      "id": 2401,
      "nutrition_plan_id": 123,
      "day_number": 24,
      "planned_date": null,
      "total_calories": 1800,
      "total_protein_g": 140.0,
      "total_carbs_g": 180.0,
      "total_fat_g": 50.0,
      "notes": "Día de entrenamiento moderado",
      "is_published": true,
      "published_at": "2025-01-01T00:00:00Z",
      "created_at": "2025-01-01T00:00:00Z",
      "updated_at": null
    },
    "meals": [
      {
        "id": 12001,
        "daily_plan_id": 2401,
        "meal_type": "breakfast",
        "name": "Power Breakfast",
        "description": "Desayuno alto en proteínas para empezar el día",
        "preparation_instructions": "1. Cocinar huevos revueltos...",
        "calories": 540,
        "protein_g": 35.0,
        "carbs_g": 45.0,
        "fat_g": 18.0,
        "fiber_g": 8.0,
        "image_url": "https://example.com/power-breakfast.jpg",
        "video_url": null,
        "order_in_day": 0,
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": null,
        "ingredients": [
          {
            "id": 50001,
            "meal_id": 12001,
            "name": "Huevos",
            "quantity": 3.0,
            "unit": "units",
            "alternatives": null,
            "is_optional": false,
            "calories_per_serving": 70,
            "protein_per_serving": 6.0,
            "carbs_per_serving": 0.5,
            "fat_per_serving": 5.0,
            "created_at": "2025-01-01T00:00:00Z"
          },
          {
            "id": 50002,
            "meal_id": 12001,
            "name": "Avena",
            "quantity": 50.0,
            "unit": "gr",
            "alternatives": null,
            "is_optional": false,
            "calories_per_serving": 190,
            "protein_per_serving": 7.0,
            "carbs_per_serving": 34.0,
            "fat_per_serving": 3.5,
            "created_at": "2025-01-01T00:00:00Z"
          }
        ]
      },
      {
        "id": 12002,
        "daily_plan_id": 2401,
        "meal_type": "lunch",
        "name": "Pechuga con Arroz",
        "description": "Almuerzo balanceado",
        "preparation_instructions": "1. Cocinar pechuga a la plancha...",
        "calories": 620,
        "protein_g": 55.0,
        "carbs_g": 70.0,
        "fat_g": 8.0,
        "fiber_g": 5.0,
        "image_url": null,
        "video_url": null,
        "order_in_day": 2,
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": null,
        "ingredients": [
          {
            "id": 50003,
            "meal_id": 12002,
            "name": "Pechuga de pollo",
            "quantity": 200.0,
            "unit": "gr",
            "alternatives": "Pechuga de pavo",
            "is_optional": false,
            "calories_per_serving": 330,
            "protein_per_serving": 62.0,
            "carbs_per_serving": 0.0,
            "fat_per_serving": 7.0,
            "created_at": "2025-01-01T00:00:00Z"
          }
        ]
      }
    ],
    "progress": {
      "id": 9001,
      "user_id": 100,
      "daily_plan_id": 2401,
      "date": "2025-12-24T00:00:00Z",
      "meals_completed": 1,
      "total_meals": 5,
      "completion_percentage": 20.0,
      "overall_satisfaction": null,
      "difficulty_rating": null,
      "notes": null,
      "weight_kg": 75.5,
      "body_fat_percentage": 18.0,
      "created_at": "2025-12-24T08:00:00Z",
      "updated_at": "2025-12-24T08:30:00Z"
    },
    "completion_percentage": 20.0,
    "plan": {
      "id": 123,
      "title": "Mi Plan de Pérdida de Grasa",
      "plan_type": "template"
    },
    "current_day": 24,
    "status": "running",
    "days_until_start": null
  },

  "completion_streak": 7,

  "weekly_progress": [
    {
      "id": 9002,
      "user_id": 100,
      "daily_plan_id": 2395,
      "date": "2025-12-18T00:00:00Z",
      "meals_completed": 5,
      "total_meals": 5,
      "completion_percentage": 100.0,
      "overall_satisfaction": 5,
      "difficulty_rating": 3,
      "notes": "Excelente día",
      "weight_kg": 76.2,
      "body_fat_percentage": 18.5,
      "created_at": "2025-12-18T22:00:00Z",
      "updated_at": "2025-12-18T22:30:00Z"
    },
    {
      "id": 9003,
      "user_id": 100,
      "daily_plan_id": 2396,
      "date": "2025-12-19T00:00:00Z",
      "meals_completed": 4,
      "total_meals": 5,
      "completion_percentage": 80.0,
      "overall_satisfaction": 4,
      "difficulty_rating": 3,
      "notes": null,
      "weight_kg": 76.0,
      "body_fat_percentage": 18.4,
      "created_at": "2025-12-19T21:00:00Z",
      "updated_at": "2025-12-19T21:15:00Z"
    }
  ]
}
```

---

## 📊 Campos Clave a Destacar

### Estados del Plan (status)
- `"not_started"` - Plan no ha comenzado (futuro)
- `"running"` - Plan en progreso activo
- `"finished"` - Plan completado

### Tipos de Plan (plan_type)
- `"template"` - Plan individual/personalizado
- `"live"` - Challenge grupal con fechas sincronizadas

### Tipos de Comida (meal_type)
- `"breakfast"` - Desayuno
- `"mid_morning"` - Snack de media mañana
- `"lunch"` - Almuerzo
- `"afternoon"` - Merienda
- `"dinner"` - Cena
- `"post_workout"` - Comida post-entreno
- `"late_snack"` - Snack nocturno

---

## 🎯 Casos de Uso del Dashboard

### 1. Pantalla Principal de Nutrición
```typescript
// Mostrar planes en progreso
dashboard.template_plans.forEach(plan => {
  if (plan.status === "running") {
    renderActivePlan(plan);
  }
});

// Mostrar challenges activos
dashboard.live_plans.forEach(plan => {
  if (plan.is_live_active) {
    renderLiveChallenge(plan);
  }
});
```

### 2. Plan del Día
```typescript
if (dashboard.today_plan) {
  const { meals, completion_percentage, current_day } = dashboard.today_plan;

  renderTodayMeals(meals);
  renderProgress(completion_percentage);
  renderDayCounter(current_day);
}
```

### 3. Métricas de Progreso
```typescript
// Racha actual
showStreak(dashboard.completion_streak);

// Progreso semanal
const weeklyChart = dashboard.weekly_progress.map(day => ({
  date: day.date,
  completion: day.completion_percentage
}));
renderWeeklyChart(weeklyChart);
```

### 4. Descubrir Planes
```typescript
// Planes disponibles para unirse
dashboard.available_plans.forEach(plan => {
  renderAvailablePlan({
    id: plan.id,
    title: plan.title,
    followers: plan.total_followers,
    rating: plan.avg_satisfaction
  });
});
```

---

## ✅ Resumen

**Endpoint:** `GET /api/v1/nutrition/dashboard`

**Categorías:**
1. **template_plans** - Planes individuales del usuario
2. **live_plans** - Challenges grupales activos
3. **available_plans** - Planes públicos para unirse
4. **today_plan** - Comidas y progreso de hoy
5. **completion_streak** - Días consecutivos cumpliendo
6. **weekly_progress** - Progreso de últimos 7 días

**Campos Calculados Importantes:**
- `current_day` - Día actual del plan
- `status` - Estado del plan (not_started/running/finished)
- `days_until_start` - Días hasta que inicie (para planes futuros)
- `completion_percentage` - % de completación

**Respuesta Optimizada para:**
- Vista principal de nutrición
- Estado general del usuario
- Tareas pendientes del día
- Descubrimiento de nuevos planes
- Métricas de progreso
