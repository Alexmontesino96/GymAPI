# Guía de Endpoints de Nutrición - Frontend

Documentación completa para integrar los endpoints de nutrición en el frontend, enfocada en visualizar planes nutricionales que los usuarios están siguiendo.

## Tabla de Contenidos

1. [Flujo General](#flujo-general)
2. [Autenticación](#autenticación)
3. [Endpoints Principales](#endpoints-principales)
4. [Casos de Uso Comunes](#casos-de-uso-comunes)
5. [Tipos de Planes](#tipos-de-planes)
6. [Estados de Planes](#estados-de-planes)
7. [Ejemplos de Código](#ejemplos-de-código)

---

## Flujo General

### Para ver un plan que el usuario está siguiendo:

```
1. Obtener Dashboard → GET /api/v1/nutrition/dashboard
   ├─ Ver planes activos del usuario
   ├─ Ver planes live en los que participa
   └─ Ver comidas de hoy

2. Ver detalles de un plan → GET /api/v1/nutrition/plans/{plan_id}
   ├─ Ver todos los días del plan
   ├─ Ver todas las comidas por día
   └─ Ver ingredientes de cada comida

3. Ver comidas de hoy → GET /api/v1/nutrition/today
   ├─ Comidas específicas para el día actual
   ├─ Progreso del día
   └─ Información del plan activo

4. Completar una comida → POST /api/v1/nutrition/meals/{meal_id}/complete
   ├─ Marcar comida como consumida
   ├─ Agregar rating y fotos opcionales
   └─ Actualiza progreso automáticamente
```

---

## Autenticación

Todos los endpoints requieren autenticación mediante token JWT de Auth0 en el header:

```javascript
headers: {
  'Authorization': `Bearer ${auth0Token}`,
  'Content-Type': 'application/json'
}
```

El token debe incluir el `gym_id` en los custom claims para multi-tenancy.

---

## Endpoints Principales

### 1. Dashboard Nutricional

**Endpoint:** `GET /api/v1/nutrition/dashboard`

**Descripción:** Vista principal con todos los planes del usuario organizados por categorías.

**Respuesta:**
```json
{
  "user_id": 123,
  "active_plans": [
    {
      "plan_id": 456,
      "plan_name": "Plan Pérdida de Peso",
      "plan_type": "template",
      "current_day": 15,
      "status": "running",
      "completion_percentage": 85.5,
      "total_days": 30
    }
  ],
  "weekly_summary": {
    "total_meals_planned": 35,
    "total_meals_completed": 28,
    "completion_rate": 80.0,
    "avg_calories": 1650,
    "avg_satisfaction": 4.5
  },
  "monthly_summary": {
    "total_days_active": 25,
    "total_meals_completed": 120,
    "completion_rate": 82.5
  },
  "current_streak": 7,
  "longest_streak": 21,
  "total_meals_completed": 450,
  "favorite_meals": [
    {
      "meal_id": 789,
      "meal_name": "Batido Proteico Verde",
      "times_completed": 15,
      "avg_satisfaction": 5.0
    }
  ],
  "nutritional_goals_progress": {
    "calories": {
      "target": 1500,
      "current_avg": 1520,
      "variance_percentage": 1.3
    },
    "protein_g": {
      "target": 120.0,
      "current_avg": 118.5,
      "variance_percentage": -1.25
    }
  }
}
```

**Cuándo usar:**
- Pantalla principal de la sección de nutrición
- Mostrar resumen general del progreso
- Ver planes activos y disponibles

---

### 2. Comidas de Hoy

**Endpoint:** `GET /api/v1/nutrition/today`

**Descripción:** Obtiene las comidas específicas que el usuario debe consumir HOY.

**Lógica de cálculo del día:**
- **Template:** Basado en cuándo el usuario empezó individualmente
- **Live:** Basado en fecha global del plan (todos ven el mismo día)

**Respuesta Exitosa (Plan Activo):**
```json
{
  "date": "2024-01-15T00:00:00Z",
  "current_day": 15,
  "status": "running",
  "plan": {
    "id": 123,
    "title": "Plan Pérdida de Peso",
    "plan_type": "template",
    "goal": "weight_loss",
    "target_calories": 1500,
    "duration_days": 30
  },
  "daily_plan": {
    "id": 456,
    "day_number": 15,
    "total_calories": 1520,
    "total_protein_g": 120.0,
    "total_carbs_g": 150.0,
    "total_fat_g": 45.0,
    "notes": "Día de entrenamiento intenso - aumentar carbohidratos"
  },
  "meals": [
    {
      "id": 789,
      "meal_type": "breakfast",
      "name": "Avena con Frutas y Proteína",
      "description": "Desayuno energético y balanceado",
      "calories": 350,
      "protein_g": 25.0,
      "carbs_g": 45.0,
      "fat_g": 8.0,
      "fiber_g": 8.0,
      "preparation_time_minutes": 10,
      "cooking_instructions": "1. Calentar avena con leche...",
      "image_url": "https://example.com/avena.jpg",
      "order_in_day": 1,
      "ingredients": [
        {
          "id": 101,
          "name": "Avena",
          "quantity": 50.0,
          "unit": "gramos",
          "calories_per_serving": 185,
          "protein_per_serving": 7.0,
          "is_optional": false,
          "alternatives": ["Quinoa", "Amaranto"]
        },
        {
          "id": 102,
          "name": "Plátano",
          "quantity": 1.0,
          "unit": "unidad",
          "calories_per_serving": 105,
          "is_optional": false
        },
        {
          "id": 103,
          "name": "Proteína en polvo",
          "quantity": 30.0,
          "unit": "gramos",
          "calories_per_serving": 120,
          "protein_per_serving": 24.0
        }
      ],
      "user_completion": null
    },
    {
      "id": 790,
      "meal_type": "mid_morning",
      "name": "Snack de Almendras",
      "calories": 160,
      "ingredients": [...],
      "user_completion": {
        "id": 201,
        "completed_at": "2024-01-15T10:30:00Z",
        "satisfaction_rating": 4,
        "photo_url": "https://example.com/my-snack.jpg"
      }
    },
    {
      "id": 791,
      "meal_type": "lunch",
      "name": "Pechuga de Pollo con Arroz Integral",
      "calories": 520,
      "ingredients": [...]
    }
  ],
  "progress": {
    "id": 301,
    "meals_completed": 1,
    "total_meals": 5,
    "completion_percentage": 20.0,
    "overall_satisfaction": null,
    "difficulty_rating": null,
    "weight_kg": null
  },
  "completion_percentage": 20.0
}
```

**Respuesta Plan Live No Iniciado:**
```json
{
  "date": "2024-01-15T00:00:00Z",
  "current_day": 0,
  "status": "not_started",
  "days_until_start": 7,
  "plan": {
    "id": 456,
    "title": "Challenge Detox 21 Días",
    "plan_type": "live",
    "live_start_date": "2024-01-22T00:00:00Z",
    "live_participants_count": 87
  },
  "meals": []
}
```

**Respuesta Sin Planes Activos:**
```json
{
  "date": "2024-01-15T00:00:00Z",
  "current_day": 0,
  "status": "not_started",
  "meals": []
}
```

**Cuándo usar:**
- Pantalla principal de comidas del día
- Widget "Mis comidas de hoy"
- Notificaciones push de recordatorio

---

### 3. Detalles Completos de un Plan

**Endpoint:** `GET /api/v1/nutrition/plans/{plan_id}`

**Descripción:** Obtiene toda la información de un plan incluyendo TODOS los días, comidas e ingredientes.

**Parámetros:**
- `plan_id` (path): ID del plan nutricional

**Respuesta:**
```json
{
  "id": 123,
  "title": "Plan Detox 21 Días",
  "description": "Plan completo de desintoxicación...",
  "goal": "weight_loss",
  "difficulty_level": "beginner",
  "budget_level": "medium",
  "dietary_restrictions": "none",
  "duration_days": 21,
  "is_recurring": false,
  "target_calories": 1500,
  "target_protein_g": 90.0,
  "target_carbs_g": 150.0,
  "target_fat_g": 50.0,
  "is_public": true,
  "tags": ["detox", "pérdida peso", "principiante"],
  "plan_type": "live",
  "live_start_date": "2024-02-01T00:00:00Z",
  "live_end_date": "2024-02-21T00:00:00Z",
  "is_live_active": true,
  "live_participants_count": 87,
  "current_day": 5,
  "status": "running",
  "days_until_start": 0,
  "creator_id": 1,
  "creator_name": "Dr. Martínez",
  "gym_id": 1,
  "is_active": true,
  "created_at": "2024-01-15T00:00:00Z",
  "is_followed_by_user": true,
  "total_followers": 150,
  "avg_satisfaction": 4.8,
  "daily_plans": [
    {
      "id": 201,
      "day_number": 1,
      "planned_date": "2024-02-01T00:00:00Z",
      "total_calories": 1520,
      "total_protein_g": 92.0,
      "total_carbs_g": 148.0,
      "total_fat_g": 51.0,
      "notes": "Primer día - hidratación importante",
      "is_published": true,
      "published_at": "2024-01-20T00:00:00Z",
      "meals": [
        {
          "id": 301,
          "meal_type": "breakfast",
          "name": "Batido Verde Detox",
          "description": "Batido antioxidante...",
          "preparation_time_minutes": 5,
          "cooking_instructions": "1. Licuar espinaca...",
          "calories": 250,
          "protein_g": 15.0,
          "carbs_g": 30.0,
          "fat_g": 8.0,
          "fiber_g": 5.0,
          "image_url": "https://example.com/batido.jpg",
          "order_in_day": 1,
          "ingredients": [
            {
              "id": 401,
              "name": "Espinaca",
              "quantity": 100.0,
              "unit": "gramos",
              "alternatives": ["Kale", "Acelga"],
              "is_optional": false,
              "calories_per_serving": 23,
              "protein_per_serving": 2.9
            }
          ]
        },
        {
          "id": 302,
          "meal_type": "lunch",
          "name": "Ensalada Completa",
          "calories": 450,
          "ingredients": [...]
        }
      ]
    },
    {
      "id": 202,
      "day_number": 2,
      "total_calories": 1500,
      "meals": [...]
    }
  ]
}
```

**Control de Acceso:**
- Planes públicos: Cualquier miembro puede verlos
- Planes privados: Solo creador y seguidores activos
- Creadores: Acceso total a sus planes
- Seguidores: Acceso si están siguiendo activamente

**Cuándo usar:**
- Pantalla de detalles del plan
- Vista previa antes de seguir un plan
- Navegación completa del contenido
- Planificación de compras (ver todos los ingredientes)

---

### 4. Seguir un Plan Nutricional

**Endpoint:** `POST /api/v1/nutrition/plans/{plan_id}/follow`

**Descripción:** Permite al usuario comenzar a seguir un plan nutricional.

**Parámetros:**
- `plan_id` (path): ID del plan a seguir

**Body:** No requiere body (usa valores por defecto)

**Body Opcional (para personalizar notificaciones):**
```json
{
  "notifications_enabled": true,
  "notification_time_breakfast": "08:00",
  "notification_time_lunch": "13:00",
  "notification_time_dinner": "20:00"
}
```

**Respuesta:**
```json
{
  "id": 123,
  "user_id": 456,
  "plan_id": 789,
  "is_active": true,
  "start_date": "2024-01-15T00:00:00Z",
  "end_date": null,
  "notifications_enabled": true,
  "notification_time_breakfast": "08:00",
  "notification_time_lunch": "13:00",
  "notification_time_dinner": "20:00",
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Comportamiento por tipo de plan:**
- **Template:** Usuario inicia inmediatamente (hoy)
- **Live (futuro):** Usuario queda registrado, inicia en fecha del plan
- **Live (activo):** Usuario se une y sincroniza con el día actual
- **Archived:** Usuario inicia como template individual

**Validaciones:**
- Plan existe y pertenece al gimnasio
- Usuario no está siguiendo ya este plan
- Plan es público o usuario tiene acceso
- Plan live no está terminado

**Errores comunes:**
```json
// 400 - Ya siguiendo el plan
{
  "detail": "Ya estás siguiendo este plan nutricional"
}

// 403 - Plan privado sin acceso
{
  "detail": "No tienes acceso a este plan privado"
}

// 404 - Plan no encontrado
{
  "detail": "Plan nutricional no encontrado"
}
```

**Cuándo usar:**
- Botón "Empezar Plan"
- Botón "Unirse al Challenge"
- Reactivar plan pausado

---

### 5. Completar una Comida

**Endpoint:** `POST /api/v1/nutrition/meals/{meal_id}/complete`

**Descripción:** Marca una comida como consumida y actualiza el progreso.

**Parámetros:**
- `meal_id` (path): ID de la comida a completar

**Body (todos los campos opcionales):**
```json
{
  "satisfaction_rating": 5,
  "photo_url": "https://example.com/my-meal.jpg",
  "notes": "Estuvo deliciosa, muy fácil de preparar",
  "ingredients_modified": {
    "cambios": "Usé miel en lugar de azúcar"
  },
  "portion_size_modifier": 1.0
}
```

**Respuesta:**
```json
{
  "id": 789,
  "user_id": 123,
  "meal_id": 456,
  "satisfaction_rating": 5,
  "photo_url": "https://example.com/my-meal.jpg",
  "notes": "Estuvo deliciosa, muy fácil de preparar",
  "ingredients_modified": {
    "cambios": "Usé miel en lugar de azúcar"
  },
  "portion_size_modifier": 1.0,
  "completed_at": "2024-01-15T12:30:00Z",
  "created_at": "2024-01-15T12:30:00Z"
}
```

**Impacto en el sistema:**
- Actualiza progreso diario automáticamente
- Recalcula porcentaje de completación del día
- Actualiza racha de días consecutivos
- Contribuye a analytics del plan
- Puede disparar notificaciones de logros

**Validaciones:**
- La comida existe y pertenece al gimnasio
- El usuario está siguiendo el plan activamente
- La comida no ha sido completada previamente

**Errores comunes:**
```json
// 400 - Comida ya completada
{
  "detail": "Ya completaste esta comida anteriormente"
}

// 400 - No siguiendo el plan
{
  "detail": "No estás siguiendo el plan que contiene esta comida"
}
```

**Cuándo usar:**
- Checkbox de comida completada
- Subir foto de la comida
- Dar feedback después de comer

---

### 6. Dejar de Seguir un Plan

**Endpoint:** `DELETE /api/v1/nutrition/plans/{plan_id}/follow`

**Descripción:** Detiene el seguimiento de un plan nutricional.

**Parámetros:**
- `plan_id` (path): ID del plan

**Respuesta:** `204 No Content`

**Cuándo usar:**
- Botón "Abandonar Plan"
- Pausar plan temporalmente
- Cambiar a otro plan

---

## Tipos de Planes

### TEMPLATE (Plantilla)
- Usuario inicia cuando quiere
- Progreso individual
- `current_day` basado en fecha de inicio del usuario
- Puede seguirse múltiples veces

**Ejemplo:** "Plan 30 Días Pérdida de Peso"

### LIVE (En Vivo)
- Fecha de inicio fija para todos
- Progreso sincronizado
- `current_day` basado en fecha global
- Challenges grupales

**Ejemplo:** "Challenge Detox - Inicia 1 Febrero"

### ARCHIVED (Archivado)
- Plan live terminado convertido en template
- Preserva información histórica
- Reutilizable como template individual

**Ejemplo:** "Challenge Verano 2023 (Archivado)"

---

## Estados de Planes

### NOT_STARTED
- Plan live que aún no ha empezado
- `days_until_start` indica días restantes
- `meals` array vacío

**UI Sugerida:**
```
🕒 Inicia en 7 días
👥 87 personas ya se unieron
[Botón: Unirse al Challenge]
```

### RUNNING
- Plan actualmente activo
- Comidas disponibles para hoy
- Progreso trackeado

**UI Sugerida:**
```
✅ Día 5 de 21
📊 80% completado hoy
[Lista de comidas del día]
```

### FINISHED
- Plan completado
- Solo lectura de progreso histórico
- No se pueden completar más comidas

**UI Sugerida:**
```
🏁 Plan Completado
⭐ Calificación: 4.8/5
📊 Ver tu progreso
```

---

## Casos de Uso Comunes

### 1. Pantalla Principal de Nutrición

```javascript
// Cargar dashboard al abrir la sección
async function loadNutritionHome() {
  const dashboard = await fetch('/api/v1/nutrition/dashboard', {
    headers: { 'Authorization': `Bearer ${token}` }
  }).then(r => r.json());

  // Mostrar planes activos
  renderActivePlans(dashboard.active_plans);

  // Mostrar comidas de hoy
  renderTodayMeals(dashboard.today_plan || { meals: [] });

  // Mostrar estadísticas
  renderStats({
    streak: dashboard.current_streak,
    weeklyCompletion: dashboard.weekly_summary.completion_rate
  });

  // Mostrar planes disponibles
  renderAvailablePlans(dashboard.available_plans);
}
```

### 2. Ver Comidas del Día

```javascript
// Cargar comidas específicas de hoy
async function loadTodayMeals() {
  const today = await fetch('/api/v1/nutrition/today', {
    headers: { 'Authorization': `Bearer ${token}` }
  }).then(r => r.json());

  if (today.status === 'not_started' && today.days_until_start) {
    // Mostrar countdown
    showCountdown(today.days_until_start, today.plan);
  } else if (today.meals.length > 0) {
    // Mostrar comidas del día
    today.meals.forEach(meal => {
      renderMealCard(meal, today.current_day);
    });

    // Mostrar progreso
    showProgress(today.completion_percentage);
  } else {
    // Sugerir unirse a un plan
    showEmptyState();
  }
}
```

### 3. Detalles de un Plan

```javascript
// Ver todos los detalles de un plan antes de seguirlo
async function showPlanDetails(planId) {
  const plan = await fetch(`/api/v1/nutrition/plans/${planId}`, {
    headers: { 'Authorization': `Bearer ${token}` }
  }).then(r => r.json());

  // Header del plan
  renderPlanHeader({
    title: plan.title,
    duration: plan.duration_days,
    participants: plan.live_participants_count,
    type: plan.plan_type,
    status: plan.status
  });

  // Tabs: Resumen / Días / Comidas / Ingredientes
  renderTabs({
    overview: renderOverview(plan),
    days: renderDaysList(plan.daily_plans),
    meals: renderAllMeals(plan),
    ingredients: renderShoppingList(plan)
  });

  // Botón de acción
  if (plan.is_followed_by_user) {
    showButton('Ver Mi Progreso', () => goToProgress());
  } else {
    showButton('Empezar Plan', () => followPlan(planId));
  }
}
```

### 4. Completar Comida

```javascript
// Marcar comida como completada con foto y rating
async function completeMeal(mealId, photoUrl = null, rating = null) {
  const completion = await fetch(`/api/v1/nutrition/meals/${mealId}/complete`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      satisfaction_rating: rating,
      photo_url: photoUrl,
      notes: ''
    })
  }).then(r => r.json());

  // Actualizar UI
  markMealAsComplete(mealId);

  // Mostrar celebración si completó el día
  checkIfDayCompleted();

  // Refresh progreso
  refreshTodayProgress();
}
```

### 5. Seguir un Plan

```javascript
// Usuario se une a un plan
async function followPlan(planId) {
  try {
    const follower = await fetch(`/api/v1/nutrition/plans/${planId}/follow`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` }
    }).then(r => r.json());

    // Redirigir a vista de progreso
    showSuccessMessage('¡Plan activado con éxito!');
    navigateTo(`/nutrition/today`);

  } catch (error) {
    if (error.status === 400) {
      showError('Ya estás siguiendo este plan');
    }
  }
}
```

### 6. Lista de Ingredientes (Shopping List)

```javascript
// Generar lista de compras de un plan
function generateShoppingList(plan) {
  const ingredients = {};

  plan.daily_plans.forEach(day => {
    day.meals.forEach(meal => {
      meal.ingredients.forEach(ing => {
        const key = ing.name.toLowerCase();
        if (!ingredients[key]) {
          ingredients[key] = {
            name: ing.name,
            totalQuantity: 0,
            unit: ing.unit,
            alternatives: ing.alternatives
          };
        }
        ingredients[key].totalQuantity += ing.quantity;
      });
    });
  });

  return Object.values(ingredients);
}
```

---

## Ejemplos de Código

### React Component: Today's Meals

```jsx
import React, { useEffect, useState } from 'react';
import { useAuth0 } from '@auth0/auth0-react';

function TodayMealsScreen() {
  const [todayPlan, setTodayPlan] = useState(null);
  const [loading, setLoading] = useState(true);
  const { getAccessTokenSilently } = useAuth0();

  useEffect(() => {
    loadTodayMeals();
  }, []);

  async function loadTodayMeals() {
    try {
      const token = await getAccessTokenSilently();
      const response = await fetch('/api/v1/nutrition/today', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await response.json();
      setTodayPlan(data);
    } catch (error) {
      console.error('Error loading meals:', error);
    } finally {
      setLoading(false);
    }
  }

  async function handleCompleteMeal(mealId, rating) {
    const token = await getAccessTokenSilently();
    await fetch(`/api/v1/nutrition/meals/${mealId}/complete`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ satisfaction_rating: rating })
    });

    // Refresh
    loadTodayMeals();
  }

  if (loading) return <div>Cargando...</div>;

  if (!todayPlan || todayPlan.meals.length === 0) {
    return (
      <div className="empty-state">
        <h2>No tienes comidas programadas para hoy</h2>
        <button onClick={() => navigateTo('/nutrition/plans')}>
          Explorar Planes
        </button>
      </div>
    );
  }

  return (
    <div className="today-meals">
      <header>
        <h1>Comidas de Hoy</h1>
        <div className="plan-info">
          <span>{todayPlan.plan.title}</span>
          <span>Día {todayPlan.current_day}</span>
        </div>
        <div className="progress-bar">
          <div
            className="progress-fill"
            style={{ width: `${todayPlan.completion_percentage}%` }}
          />
        </div>
        <span>{todayPlan.completion_percentage.toFixed(0)}% completado</span>
      </header>

      <div className="meals-list">
        {todayPlan.meals.map(meal => (
          <MealCard
            key={meal.id}
            meal={meal}
            onComplete={(rating) => handleCompleteMeal(meal.id, rating)}
            isCompleted={!!meal.user_completion}
          />
        ))}
      </div>
    </div>
  );
}

function MealCard({ meal, onComplete, isCompleted }) {
  return (
    <div className={`meal-card ${isCompleted ? 'completed' : ''}`}>
      {meal.image_url && <img src={meal.image_url} alt={meal.name} />}

      <div className="meal-header">
        <span className="meal-type">{meal.meal_type}</span>
        <h3>{meal.name}</h3>
      </div>

      <div className="nutrition-info">
        <span>{meal.calories} kcal</span>
        <span>{meal.protein_g}g proteína</span>
        <span>{meal.carbs_g}g carbos</span>
        <span>{meal.fat_g}g grasas</span>
      </div>

      <details>
        <summary>Ver Ingredientes ({meal.ingredients.length})</summary>
        <ul className="ingredients-list">
          {meal.ingredients.map(ing => (
            <li key={ing.id}>
              {ing.quantity} {ing.unit} de {ing.name}
              {ing.alternatives?.length > 0 && (
                <small> (o {ing.alternatives.join(', ')})</small>
              )}
            </li>
          ))}
        </ul>
      </details>

      {!isCompleted ? (
        <button
          className="complete-btn"
          onClick={() => onComplete(5)}
        >
          ✓ Marcar como Completada
        </button>
      ) : (
        <div className="completed-badge">
          ✓ Completada a las {new Date(meal.user_completion.completed_at).toLocaleTimeString()}
        </div>
      )}
    </div>
  );
}

export default TodayMealsScreen;
```

### React Component: Plan Details

```jsx
import React, { useEffect, useState } from 'react';
import { useAuth0 } from '@auth0/auth0-react';
import { useParams } from 'react-router-dom';

function PlanDetailsScreen() {
  const { planId } = useParams();
  const [plan, setPlan] = useState(null);
  const [loading, setLoading] = useState(true);
  const { getAccessTokenSilently } = useAuth0();

  useEffect(() => {
    loadPlanDetails();
  }, [planId]);

  async function loadPlanDetails() {
    try {
      const token = await getAccessTokenSilently();
      const response = await fetch(`/api/v1/nutrition/plans/${planId}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await response.json();
      setPlan(data);
    } catch (error) {
      console.error('Error loading plan:', error);
    } finally {
      setLoading(false);
    }
  }

  async function handleFollowPlan() {
    try {
      const token = await getAccessTokenSilently();
      await fetch(`/api/v1/nutrition/plans/${planId}/follow`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });

      alert('¡Te has unido al plan exitosamente!');
      loadPlanDetails(); // Refresh para actualizar is_followed_by_user

    } catch (error) {
      alert('Error al unirse al plan');
    }
  }

  if (loading) return <div>Cargando plan...</div>;
  if (!plan) return <div>Plan no encontrado</div>;

  return (
    <div className="plan-details">
      <header className="plan-header">
        <h1>{plan.title}</h1>
        <div className="plan-badges">
          <span className="badge">{plan.plan_type}</span>
          <span className="badge">{plan.goal}</span>
          <span className="badge">{plan.difficulty_level}</span>
        </div>

        {plan.plan_type === 'live' && (
          <div className="live-info">
            <span>👥 {plan.live_participants_count} participantes</span>
            {plan.status === 'not_started' && (
              <span>🕒 Inicia en {plan.days_until_start} días</span>
            )}
            {plan.status === 'running' && (
              <span>📍 Día {plan.current_day} de {plan.duration_days}</span>
            )}
          </div>
        )}

        <p className="description">{plan.description}</p>

        <div className="nutrition-targets">
          <div>Calorías: {plan.target_calories}</div>
          <div>Proteína: {plan.target_protein_g}g</div>
          <div>Carbos: {plan.target_carbs_g}g</div>
          <div>Grasas: {plan.target_fat_g}g</div>
        </div>
      </header>

      <div className="plan-days">
        <h2>Plan de {plan.duration_days} días</h2>
        {plan.daily_plans.map(day => (
          <DayCard key={day.id} day={day} />
        ))}
      </div>

      <footer className="plan-actions">
        {!plan.is_followed_by_user ? (
          <button
            className="primary-btn"
            onClick={handleFollowPlan}
          >
            {plan.plan_type === 'live' ? 'Unirse al Challenge' : 'Empezar Plan'}
          </button>
        ) : (
          <div className="following-badge">
            ✓ Siguiendo este plan
          </div>
        )}
      </footer>
    </div>
  );
}

function DayCard({ day }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="day-card">
      <div
        className="day-header"
        onClick={() => setExpanded(!expanded)}
      >
        <h3>Día {day.day_number}</h3>
        <div className="day-nutrition">
          <span>{day.total_calories} kcal</span>
          <span>{day.total_protein_g}g proteína</span>
        </div>
        {day.notes && <p className="day-notes">{day.notes}</p>}
      </div>

      {expanded && (
        <div className="day-meals">
          {day.meals.map(meal => (
            <div key={meal.id} className="meal-preview">
              <span className="meal-type">{meal.meal_type}</span>
              <span className="meal-name">{meal.name}</span>
              <span className="meal-calories">{meal.calories} kcal</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default PlanDetailsScreen;
```

### React Native (Mobile) Example

```jsx
import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, Image } from 'react-native';
import { useAuth0 } from 'react-native-auth0';

function TodayMealsScreen({ navigation }) {
  const [todayPlan, setTodayPlan] = useState(null);
  const { getCredentials } = useAuth0();

  useEffect(() => {
    loadTodayMeals();
  }, []);

  async function loadTodayMeals() {
    const credentials = await getCredentials();
    const response = await fetch('https://api.mygym.com/api/v1/nutrition/today', {
      headers: { 'Authorization': `Bearer ${credentials.accessToken}` }
    });
    const data = await response.json();
    setTodayPlan(data);
  }

  async function completeMeal(mealId) {
    const credentials = await getCredentials();
    await fetch(`https://api.mygym.com/api/v1/nutrition/meals/${mealId}/complete`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${credentials.accessToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ satisfaction_rating: 5 })
    });

    loadTodayMeals(); // Refresh
  }

  if (!todayPlan) return <Text>Cargando...</Text>;

  return (
    <ScrollView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Comidas de Hoy</Text>
        <Text style={styles.planName}>{todayPlan.plan?.title}</Text>
        <View style={styles.progressBar}>
          <View
            style={[
              styles.progressFill,
              { width: `${todayPlan.completion_percentage}%` }
            ]}
          />
        </View>
        <Text>{todayPlan.completion_percentage.toFixed(0)}% completado</Text>
      </View>

      {todayPlan.meals.map(meal => (
        <View key={meal.id} style={styles.mealCard}>
          {meal.image_url && (
            <Image
              source={{ uri: meal.image_url }}
              style={styles.mealImage}
            />
          )}

          <Text style={styles.mealType}>{meal.meal_type}</Text>
          <Text style={styles.mealName}>{meal.name}</Text>

          <View style={styles.nutritionRow}>
            <Text>{meal.calories} kcal</Text>
            <Text>{meal.protein_g}g proteína</Text>
          </View>

          {!meal.user_completion ? (
            <TouchableOpacity
              style={styles.completeButton}
              onPress={() => completeMeal(meal.id)}
            >
              <Text style={styles.completeButtonText}>
                ✓ Marcar como Completada
              </Text>
            </TouchableOpacity>
          ) : (
            <View style={styles.completedBadge}>
              <Text>✓ Completada</Text>
            </View>
          )}
        </View>
      ))}
    </ScrollView>
  );
}

const styles = {
  container: { flex: 1, backgroundColor: '#f5f5f5' },
  header: { padding: 20, backgroundColor: 'white' },
  title: { fontSize: 24, fontWeight: 'bold' },
  planName: { fontSize: 16, color: '#666', marginTop: 5 },
  progressBar: {
    height: 8,
    backgroundColor: '#e0e0e0',
    borderRadius: 4,
    marginTop: 10
  },
  progressFill: {
    height: '100%',
    backgroundColor: '#4CAF50',
    borderRadius: 4
  },
  mealCard: {
    margin: 10,
    padding: 15,
    backgroundColor: 'white',
    borderRadius: 10,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3
  },
  mealImage: {
    width: '100%',
    height: 200,
    borderRadius: 8,
    marginBottom: 10
  },
  mealType: {
    fontSize: 12,
    color: '#666',
    textTransform: 'uppercase'
  },
  mealName: {
    fontSize: 18,
    fontWeight: 'bold',
    marginTop: 5
  },
  nutritionRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    marginTop: 10,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: '#e0e0e0'
  },
  completeButton: {
    marginTop: 15,
    backgroundColor: '#4CAF50',
    padding: 12,
    borderRadius: 8,
    alignItems: 'center'
  },
  completeButtonText: {
    color: 'white',
    fontWeight: 'bold'
  },
  completedBadge: {
    marginTop: 15,
    padding: 12,
    backgroundColor: '#e8f5e9',
    borderRadius: 8,
    alignItems: 'center'
  }
};

export default TodayMealsScreen;
```

---

## Resumen de URLs

### Base URL
```
https://api.tugimnasio.com/api/v1/nutrition
```

### Endpoints Clave para Usuarios

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/dashboard` | Dashboard completo del usuario |
| GET | `/today` | Comidas del día actual |
| GET | `/plans/{id}` | Detalles completos de un plan |
| POST | `/plans/{id}/follow` | Seguir un plan |
| DELETE | `/plans/{id}/follow` | Dejar de seguir un plan |
| POST | `/meals/{id}/complete` | Completar una comida |

---

## Mejores Prácticas

1. **Cachear respuestas:** `dashboard` y `plans/{id}` son costosos, cachear por 5-10 minutos
2. **Polling de /today:** Actualizar cada vez que el usuario abre la pantalla
3. **Optimistic UI:** Marcar comida como completada inmediatamente en UI, revertir si falla
4. **Manejo de imágenes:** Cargar imágenes lazy y con placeholders
5. **Offline support:** Cachear comidas del día para mostrar sin conexión
6. **Progress tracking:** Actualizar barra de progreso en tiempo real al completar comidas

---

## Soporte

Para más información, consultar:
- [Documentación completa de la API](/api/v1/docs)
- [Esquemas Pydantic](../app/schemas/nutrition.py)
- [Modelos de Base de Datos](../app/models/nutrition.py)
