# 📌 GUÍA: Endpoints Alternativos para Operaciones de Comidas (Meals)

## ⚠️ PROBLEMA: No existen endpoints CRUD para Meals

El backend NO tiene implementados:
- ❌ `GET /api/v1/nutrition/meals/{id}`
- ❌ `PUT /api/v1/nutrition/meals/{id}`
- ❌ `DELETE /api/v1/nutrition/meals/{id}`

## ✅ SOLUCIÓN: Endpoints Alternativos que SÍ Funcionan

### 1️⃣ Para OBTENER información de una comida (Reemplaza GET /meals/{id})

#### Opción A: Obtener el Plan Completo con todas sus comidas
```javascript
// ✅ USAR ESTE ENDPOINT
GET /api/v1/nutrition/plans/{plan_id}

// Retorna el plan completo con:
// - Todos los días del plan
// - Todas las comidas de cada día
// - Todos los ingredientes de cada comida
```

**Ejemplo de implementación:**
```javascript
async function getMealInfo(planId, mealId) {
  // Paso 1: Obtener el plan completo
  const response = await fetch(
    `${API_URL}/api/v1/nutrition/plans/${planId}`,
    {
      headers: {
        'Authorization': `Bearer ${token}`,
        'X-Gym-Id': gymId
      }
    }
  );

  const plan = await response.json();

  // Paso 2: Buscar la comida específica dentro del plan
  let targetMeal = null;

  plan.daily_plans.forEach(dailyPlan => {
    dailyPlan.meals.forEach(meal => {
      if (meal.id === mealId) {
        targetMeal = meal;
      }
    });
  });

  return targetMeal;
}
```

**Response del plan incluye:**
```json
{
  "id": 1,
  "title": "Plan de 21 días",
  "daily_plans": [
    {
      "id": 10,
      "day_number": 1,
      "day_name": "Día 1 - Inicio",
      "meals": [
        {
          "id": 3,  // ← Este es el ID de la comida
          "name": "Desayuno Energético",
          "meal_type": "breakfast",
          "target_calories": 400,
          "ingredients": [
            {
              "id": 45,
              "name": "Avena",
              "quantity": 50,
              "unit": "g",
              "calories": 195
            }
          ],
          "recipe_instructions": "1. Preparar la avena..."
        }
      ]
    }
  ]
}
```

#### Opción B: Obtener las comidas de HOY
```javascript
// ✅ Si necesitas las comidas del día actual
GET /api/v1/nutrition/today

// Retorna solo las comidas que el usuario debe consumir HOY
// Ideal para la vista principal del usuario
```

**Response:**
```json
{
  "date": "2024-12-27",
  "plan": {
    "id": 1,
    "title": "Plan Detox"
  },
  "current_day": 7,
  "meals": [
    {
      "id": 3,
      "name": "Desayuno del Día 7",
      "meal_type": "breakfast",
      "ingredients": [...],
      "is_completed": false
    }
  ],
  "progress_percentage": 33.3
}
```

#### Opción C: Obtener el Dashboard completo
```javascript
// ✅ Para una vista general de todos los planes y comidas
GET /api/v1/nutrition/dashboard

// Retorna:
// - Planes template activos
// - Planes live activos
// - Plan de hoy con sus comidas
// - Estadísticas generales
```

---

### 2️⃣ Para ACTUALIZAR una comida (Reemplaza PUT /meals/{id})

**NO EXISTE** forma directa de actualizar una comida. Alternativas:

#### Opción A: Regenerar con IA (RECOMENDADO)
```javascript
// ✅ PASO 1: Generar nuevos ingredientes con IA
POST /api/v1/nutrition/meals/{meal_id}/ingredients/ai-generate

// Body:
{
  "dietary_restrictions": ["vegetarian"],
  "calories_target": 400,
  "preferences": "Sin gluten, alto en proteína"
}

// ✅ PASO 2: Aplicar los ingredientes generados
POST /api/v1/nutrition/meals/{meal_id}/ingredients/ai-apply

// Body:
{
  "ingredients": [...],  // Los que retornó el paso 1
  "recipe": "Nuevas instrucciones..."
}
```

#### Opción B: Modificar ingredientes individualmente
```javascript
// Agregar nuevo ingrediente
POST /api/v1/nutrition/meals/{meal_id}/ingredients

// Body:
{
  "name": "Quinoa",
  "quantity": 100,
  "unit": "g",
  "calories": 368,
  "proteins": 14.1,
  "carbs": 64.2,
  "fats": 6.1
}

// Eliminar ingrediente (si existe el endpoint)
DELETE /api/v1/nutrition/ingredients/{ingredient_id}
```

---

### 3️⃣ Para ELIMINAR una comida (Reemplaza DELETE /meals/{id})

**NO EXISTE** endpoint para eliminar comidas. Alternativas:

#### Opción A: No mostrar la comida en el UI
```javascript
// En el frontend, simplemente ocultar la comida
function MealCard({ meal }) {
  const [isHidden, setIsHidden] = useState(false);

  if (isHidden) return null;

  return (
    <div className="meal-card">
      <button onClick={() => setIsHidden(true)}>
        Ocultar comida
      </button>
      {/* Resto del contenido */}
    </div>
  );
}
```

#### Opción B: Marcar como completada y no mostrar
```javascript
// Marcar como completada (aunque no lo esté)
POST /api/v1/nutrition/meals/{meal_id}/complete

// Body:
{
  "completed_at": "2024-12-27T10:00:00Z",
  "notes": "Saltada por preferencia del usuario"
}

// Luego en el UI, filtrar comidas completadas
const activeMeals = meals.filter(m => !m.is_completed);
```

---

## 🎯 RECOMENDACIONES PARA EL FRONTEND

### 1. Cachear la información del plan
```javascript
// Como no hay GET individual, cachea el plan completo
const planCache = new Map();

async function getPlanWithCache(planId) {
  if (planCache.has(planId)) {
    return planCache.get(planId);
  }

  const plan = await fetchPlan(planId);
  planCache.set(planId, plan);

  // Limpiar cache después de 5 minutos
  setTimeout(() => planCache.delete(planId), 5 * 60 * 1000);

  return plan;
}
```

### 2. Extraer comida del plan cacheado
```javascript
function getMealFromPlan(plan, mealId) {
  for (const dailyPlan of plan.daily_plans) {
    const meal = dailyPlan.meals.find(m => m.id === mealId);
    if (meal) {
      return {
        ...meal,
        day_number: dailyPlan.day_number,
        day_name: dailyPlan.day_name
      };
    }
  }
  return null;
}
```

### 3. UI adaptado a las limitaciones
```javascript
function MealActions({ meal, plan }) {
  return (
    <div className="meal-actions">
      {/* ✅ Funciones que SÍ existen */}
      <button onClick={() => completeMeal(meal.id)}>
        ✅ Marcar completada
      </button>

      <button onClick={() => regenerateWithAI(meal.id)}>
        🤖 Regenerar con IA
      </button>

      <button onClick={() => addIngredient(meal.id)}>
        ➕ Agregar ingrediente
      </button>

      {/* ❌ Funciones que NO existen */}
      <button disabled title="No disponible">
        ✏️ Editar (No disponible)
      </button>

      <button disabled title="No disponible">
        🗑️ Eliminar (No disponible)
      </button>
    </div>
  );
}
```

### 4. Mensaje explicativo para usuarios
```javascript
function MealEditInfo() {
  return (
    <div className="info-message">
      <p>💡 <strong>Nota:</strong> La edición directa de comidas no está disponible.</p>
      <p>Puedes:</p>
      <ul>
        <li>✅ Regenerar el contenido con IA</li>
        <li>✅ Modificar ingredientes individuales</li>
        <li>✅ Marcar comidas como completadas</li>
      </ul>
    </div>
  );
}
```

---

## 📊 Resumen de Endpoints Disponibles

### ✅ LO QUE SÍ PUEDEN USAR:

```javascript
// Obtener información
GET  /api/v1/nutrition/plans/{plan_id}         // Plan completo con comidas
GET  /api/v1/nutrition/today                   // Comidas de hoy
GET  /api/v1/nutrition/dashboard               // Dashboard general

// Crear
POST /api/v1/nutrition/days/{daily_plan_id}/meals  // Crear nueva comida

// Modificar parcialmente
POST /api/v1/nutrition/meals/{meal_id}/complete              // Marcar completada
POST /api/v1/nutrition/meals/{meal_id}/ingredients           // Agregar ingrediente
POST /api/v1/nutrition/meals/{meal_id}/ingredients/ai-generate  // Generar con IA
POST /api/v1/nutrition/meals/{meal_id}/ingredients/ai-apply     // Aplicar IA
```

### ❌ LO QUE NO EXISTE:

```javascript
GET    /api/v1/nutrition/meals/{id}     // Ver comida individual
PUT    /api/v1/nutrition/meals/{id}     // Actualizar comida
DELETE /api/v1/nutrition/meals/{id}     // Eliminar comida
PATCH  /api/v1/nutrition/meals/{id}     // Actualización parcial
```

---

## 🚀 Implementación Sugerida

### Service completo para manejar comidas
```javascript
class MealService {
  constructor(apiUrl, token) {
    this.apiUrl = apiUrl;
    this.token = token;
    this.planCache = new Map();
  }

  // Obtener información de una comida
  async getMeal(planId, mealId) {
    const plan = await this.getPlanCached(planId);

    for (const dailyPlan of plan.daily_plans) {
      const meal = dailyPlan.meals.find(m => m.id === mealId);
      if (meal) {
        return {
          ...meal,
          daily_plan_id: dailyPlan.id,
          day_number: dailyPlan.day_number
        };
      }
    }

    throw new Error('Comida no encontrada');
  }

  // Obtener plan con cache
  async getPlanCached(planId) {
    if (this.planCache.has(planId)) {
      return this.planCache.get(planId);
    }

    const response = await fetch(
      `${this.apiUrl}/nutrition/plans/${planId}`,
      {
        headers: {
          'Authorization': `Bearer ${this.token}`
        }
      }
    );

    const plan = await response.json();
    this.planCache.set(planId, plan);

    // Limpiar cache después de 5 minutos
    setTimeout(() => this.planCache.delete(planId), 300000);

    return plan;
  }

  // "Actualizar" comida (regenerar con IA)
  async updateMeal(mealId, preferences) {
    // Generar con IA
    const generateResponse = await fetch(
      `${this.apiUrl}/nutrition/meals/${mealId}/ingredients/ai-generate`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(preferences)
      }
    );

    const generated = await generateResponse.json();

    // Aplicar cambios
    const applyResponse = await fetch(
      `${this.apiUrl}/nutrition/meals/${mealId}/ingredients/ai-apply`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(generated)
      }
    );

    // Limpiar cache para forzar recarga
    this.planCache.clear();

    return applyResponse.json();
  }

  // Crear nueva comida
  async createMeal(dailyPlanId, mealData) {
    const response = await fetch(
      `${this.apiUrl}/nutrition/days/${dailyPlanId}/meals`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(mealData)
      }
    );

    // Limpiar cache
    this.planCache.clear();

    return response.json();
  }

  // Marcar como completada
  async completeMeal(mealId) {
    const response = await fetch(
      `${this.apiUrl}/nutrition/meals/${mealId}/complete`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          completed_at: new Date().toISOString()
        })
      }
    );

    return response.json();
  }
}

// Uso
const mealService = new MealService(API_URL, authToken);

// Obtener info de una comida
const meal = await mealService.getMeal(planId, mealId);

// "Actualizar" con IA
const updated = await mealService.updateMeal(mealId, {
  dietary_restrictions: ['vegetarian'],
  calories_target: 400
});
```

---

## 🔴 IMPORTANTE PARA EL EQUIPO

1. **NO intenten usar** endpoints que no existen (GET, PUT, DELETE de meals)
2. **Usen el plan completo** como fuente de verdad para información de comidas
3. **Cacheen agresivamente** para evitar múltiples llamadas al mismo plan
4. **Adapten el UI** a las limitaciones actuales
5. **Comuniquen al backend** la necesidad de estos endpoints si son críticos

---

*Documento creado: 27 de Diciembre 2024*
*Por: Claude Code Assistant*