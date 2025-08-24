# 🍽️ Consulta de Meals en el Sistema Híbrido - Guía Completa

## 📋 **Estructura Jerárquica de Datos**

El sistema de nutrition está organizado en 4 niveles jerárquicos:

```
NutritionPlan (Plan completo - 30 días)
    └── DailyNutritionPlan (Día específico - Día 1, 2, 3...)
            └── Meal (Comida específica - Desayuno, Almuerzo, Cena...)
                    └── MealIngredient (Ingrediente - 200g pollo, 1 taza arroz...)
```

---

## 🎯 **Endpoints para Consultar Meals**

### 📅 **1. Obtener Meals de HOY (Endpoint Principal)**

#### **Template/Archived Plans**
```http
GET /api/v1/nutrition/today
Authorization: Bearer {token}
```

**Respuesta para Template:**
```json
{
  "date": "2024-01-15",
  "plan": {
    "id": 123,
    "title": "Plan de Pérdida de Peso - 30 días",
    "plan_type": "template"
  },
  "current_day": 15,  // Día basado en cuándo empezó el usuario
  "status": "running",
  "meals": [
    {
      "id": 1001,
      "meal_type": "breakfast",
      "meal_name": "Desayuno Proteico",
      "description": "Desayuno alto en proteínas para empezar el día",
      "calories": 350,
      "protein_g": 25.5,
      "carbs_g": 30.2,
      "fat_g": 12.1,
      "preparation_time_minutes": 15,
      "ingredients": [
        {
          "id": 2001,
          "ingredient_name": "Huevos",
          "quantity": 2,
          "unit": "unidades",
          "calories": 140
        },
        {
          "id": 2002,
          "ingredient_name": "Avena",
          "quantity": 50,
          "unit": "gramos",
          "calories": 190
        }
      ]
    },
    {
      "id": 1002,
      "meal_type": "lunch",
      "meal_name": "Almuerzo Balanceado",
      "description": "Almuerzo con carbohidratos complejos",
      "calories": 450,
      "protein_g": 35.0,
      "carbs_g": 45.0,
      "fat_g": 15.0,
      "preparation_time_minutes": 25,
      "ingredients": [
        {
          "id": 2003,
          "ingredient_name": "Pollo",
          "quantity": 150,
          "unit": "gramos",
          "calories": 250
        }
      ]
    }
  ],
  "completion_percentage": 33.3  // 1 de 3 comidas completadas
}
```

#### **Live Plans (Próximo a empezar)**
```http
GET /api/v1/nutrition/today
```

**Respuesta:**
```json
{
  "date": "2024-01-25",
  "plan": {
    "id": 456,
    "title": "Challenge Detox - 21 días",
    "plan_type": "live"
  },
  "current_day": 0,
  "status": "not_started",
  "days_until_start": 7,
  "meals": []  // Vacío porque aún no empezó
}
```

#### **Live Plans (Activo)**
```http
GET /api/v1/nutrition/today
```

**Respuesta:**
```json
{
  "date": "2024-02-05",
  "plan": {
    "id": 456,
    "title": "Challenge Detox - 21 días",
    "plan_type": "live"
  },
  "current_day": 5,  // Día basado en fecha global del plan
  "status": "running",
  "meals": [
    {
      "id": 3001,
      "meal_type": "breakfast",
      "meal_name": "Batido Detox Verde",
      "description": "Batido purificante para el día 5",
      "calories": 220,
      "ingredients": [
        {
          "id": 4001,
          "ingredient_name": "Espinaca",
          "quantity": 100,
          "unit": "gramos"
        },
        {
          "id": 4002,
          "ingredient_name": "Manzana verde",
          "quantity": 1,
          "unit": "unidad"
        }
      ]
    }
  ],
  "completion_percentage": 0
}
```

---

### 📊 **2. Obtener Plan Completo con Todos los Días**

```http
GET /api/v1/nutrition/plans/{plan_id}
Authorization: Bearer {token}
```

**Respuesta:**
```json
{
  "id": 123,
  "title": "Plan de Pérdida de Peso - 30 días",
  "description": "Plan completo de 30 días",
  "plan_type": "template",
  "duration_days": 30,
  "daily_plans": [
    {
      "id": 501,
      "day_number": 1,
      "total_calories": 1500,
      "total_protein_g": 120,
      "meals": [
        {
          "id": 1001,
          "meal_type": "breakfast",
          "meal_name": "Desayuno Día 1",
          "calories": 350,
          "ingredients": [...]
        },
        {
          "id": 1002,
          "meal_type": "lunch",
          "meal_name": "Almuerzo Día 1",
          "calories": 450,
          "ingredients": [...]
        }
      ]
    },
    {
      "id": 502,
      "day_number": 2,
      "total_calories": 1520,
      "meals": [...]
    }
    // ... resto de días hasta el 30
  ]
}
```

---

### 📅 **3. Obtener Meals de un Día Específico**

```http
GET /api/v1/nutrition/daily-plans/{daily_plan_id}
Authorization: Bearer {token}
```

**Respuesta:**
```json
{
  "id": 501,
  "nutrition_plan_id": 123,
  "day_number": 1,
  "total_calories": 1500,
  "total_protein_g": 120,
  "total_carbs_g": 150,
  "total_fat_g": 50,
  "notes": "Primer día del plan - enfoque en hidratación",
  "meals": [
    {
      "id": 1001,
      "meal_type": "breakfast",
      "meal_name": "Desayuno Energético",
      "description": "Desayuno para arrancar con energía",
      "calories": 350,
      "protein_g": 25,
      "preparation_time_minutes": 15,
      "cooking_instructions": "1. Batir los huevos...",
      "image_url": "https://example.com/breakfast.jpg",
      "order_in_day": 1,
      "ingredients": [
        {
          "id": 2001,
          "ingredient_name": "Huevos",
          "quantity": 2,
          "unit": "unidades",
          "calories": 140,
          "protein_g": 12,
          "carbs_g": 0.6,
          "fat_g": 10
        }
      ]
    }
  ]
}
```

---

### 🎨 **4. Dashboard Híbrido con Meals de Hoy**

```http
GET /api/v1/nutrition/dashboard
Authorization: Bearer {token}
```

**Respuesta:**
```json
{
  "today_plan": {
    "date": "2024-01-25",
    "plan": {
      "id": 456,
      "title": "Challenge Detox",
      "plan_type": "live"
    },
    "current_day": 5,
    "status": "running",
    "meals": [...]  // Meals completas del día
  },
  "live_plans": [
    {
      "id": 456,
      "title": "Challenge Detox",
      "plan_type": "live",
      "status": "running",
      "current_day": 5,
      "live_participants_count": 87
    }
  ],
  "template_plans": [
    {
      "id": 123,
      "title": "Plan Personal",
      "plan_type": "template",
      "status": "running",
      "current_day": 15
    }
  ]
}
```

---

## 🔄 **Lógica de Cálculo del Día Actual**

### 🟢 **Template Plans (Individual)**

```python
# Backend calcula así:
def get_current_plan_day(plan, follower):
    if plan.plan_type == 'template':
        days_since_subscription = (today - follower.start_date).days
        return min(days_since_subscription + 1, plan.duration_days)
```

**Ejemplo:**
- Usuario empezó el plan el 1 de enero
- Hoy es 15 de enero
- `current_day = (15-1) + 1 = 15`
- GET /today devuelve meals del Día 15

### 🔴 **Live Plans (Grupal)**

```python
# Backend calcula así:
def get_current_plan_day(plan, follower):
    if plan.plan_type == 'live':
        if today < plan.live_start_date:
            return 0  # No ha empezado
        else:
            days_since_live_start = (today - plan.live_start_date).days
            return min(days_since_live_start + 1, plan.duration_days)
```

**Ejemplo:**
- Plan live empezó el 1 de febrero
- Hoy es 5 de febrero
- `current_day = (5-1) + 1 = 5`
- GET /today devuelve meals del Día 5 para TODOS los usuarios

---

## 🍽️ **Flujo Práctico de Consulta**

### 📱 **Caso 1: Usuario abre la app en la mañana**

#### **Paso 1: Obtener meals de hoy**
```http
GET /api/v1/nutrition/today
```

#### **Paso 2: App muestra las meals del día**
```javascript
// Frontend recibe:
{
  "current_day": 15,
  "meals": [
    { "meal_type": "breakfast", "meal_name": "Avena con frutas" },
    { "meal_type": "lunch", "meal_name": "Ensalada con pollo" },
    { "meal_type": "dinner", "meal_name": "Salmón con verduras" }
  ]
}

// App renderiza:
// "Día 15 - Plan de Pérdida de Peso"
// ✅ Desayuno: Avena con frutas (completado)
// ⏳ Almuerzo: Ensalada con pollo (pendiente)
// ⏳ Cena: Salmón con verduras (pendiente)
```

### 📱 **Caso 2: Usuario quiere ver el plan completo**

#### **Paso 1: Obtener plan con todos los días**
```http
GET /api/v1/nutrition/plans/123
```

#### **Paso 2: App muestra calendario/lista**
```javascript
// Frontend recibe 30 días con todas las meals
// App puede renderizar:
// - Vista de calendario con meals por día
// - Lista de días navegable
// - Búsqueda de meals específicas
```

### 📱 **Caso 3: Usuario quiere ver un día específico**

#### **Paso 1: Usuario selecciona "Día 10"**
```http
GET /api/v1/nutrition/daily-plans/510  // ID del daily_plan del día 10
```

#### **Paso 2: App muestra detalles del día**
```javascript
// Frontend muestra:
// - Todas las meals del día 10
// - Información nutricional total
// - Instrucciones de preparación
// - Lista de compras (ingredientes)
```

---

## 🔧 **Consultas Avanzadas**

### 📊 **Obtener Meals por Tipo**

```http
GET /api/v1/nutrition/plans/123/meals?meal_type=breakfast
```

**Respuesta:**
```json
{
  "meals": [
    {
      "day_number": 1,
      "meal": { "meal_name": "Avena Day 1", ... }
    },
    {
      "day_number": 2,
      "meal": { "meal_name": "Smoothie Day 2", ... }
    }
    // Todos los desayunos del plan
  ]
}
```

### 🛒 **Obtener Lista de Compras**

```http
GET /api/v1/nutrition/plans/123/shopping-list?days=7
```

**Respuesta:**
```json
{
  "ingredients": [
    {
      "ingredient_name": "Huevos",
      "total_quantity": 14,
      "unit": "unidades",
      "days_used": [1, 2, 3, 5, 7]
    },
    {
      "ingredient_name": "Avena",
      "total_quantity": 350,
      "unit": "gramos",
      "days_used": [1, 3, 5, 7]
    }
  ]
}
```

### 📈 **Obtener Progreso de Meals**

```http
GET /api/v1/nutrition/progress?days=7
```

**Respuesta:**
```json
{
  "weekly_progress": [
    {
      "date": "2024-01-15",
      "completed_meals": 3,
      "total_meals": 3,
      "completion_percentage": 100
    },
    {
      "date": "2024-01-16",
      "completed_meals": 2,
      "total_meals": 3,
      "completion_percentage": 66.7
    }
  ]
}
```

---

## ⚡ **Completar/Descompletar Meals**

### ✅ **Marcar Meal como Completada**

```http
POST /api/v1/nutrition/meals/1001/complete
Authorization: Bearer {token}
```

**Respuesta:**
```json
{
  "message": "Meal completada exitosamente",
  "completion": {
    "meal_id": 1001,
    "completed_at": "2024-01-15T09:30:00Z",
    "notes": "Delicioso desayuno"
  }
}
```

### ❌ **Desmarcar Meal**

```http
DELETE /api/v1/nutrition/meals/1001/complete
Authorization: Bearer {token}
```

**Respuesta:**
```json
{
  "message": "Meal desmarcada exitosamente"
}
```

---

## 🎯 **Diferencias por Tipo de Plan**

### 📊 **Comparación de Comportamiento**

| Aspecto | Template | Live | Archived |
|---------|----------|------|----------|
| **GET /today** | Día basado en usuario | Día basado en plan | Día basado en usuario |
| **Sincronización** | Individual | Grupal | Individual |
| **Meals Disponibles** | Desde día 1 al actual | Solo día actual | Desde día 1 al actual |
| **Navegación** | Puede ver días futuros | Solo día actual y pasados | Puede ver días futuros |

### 🟢 **Template Plan - Usuario puede navegar libremente**
```http
GET /api/v1/nutrition/daily-plans/510  # Día 10
GET /api/v1/nutrition/daily-plans/525  # Día 25
GET /api/v1/nutrition/daily-plans/530  # Día 30
# ✅ Todas permitidas
```

### 🔴 **Live Plan - Solo día actual y anteriores**
```http
GET /api/v1/nutrition/today  # Día 5 actual
GET /api/v1/nutrition/daily-plans/504  # Día 4 (anterior)
GET /api/v1/nutrition/daily-plans/506  # Día 6 (futuro)
# ❌ Última prohibida - "Contenido disponible mañana"
```

---

## 🎨 **Implementación Frontend**

### 📱 **Hook para Meals de Hoy**
```typescript
const useTodayMeals = () => {
  const [meals, setMeals] = useState<Meal[]>([]);
  const [currentDay, setCurrentDay] = useState(0);
  
  useEffect(() => {
    fetch('/api/v1/nutrition/today')
      .then(res => res.json())
      .then(data => {
        setMeals(data.meals);
        setCurrentDay(data.current_day);
      });
  }, []);
  
  return { meals, currentDay };
};
```

### 🎨 **Componente de Meal**
```typescript
const MealCard = ({ meal, onComplete }) => (
  <div className="meal-card">
    <h3>{meal.meal_name}</h3>
    <p>{meal.description}</p>
    <div className="nutrition">
      <span>{meal.calories} cal</span>
      <span>{meal.protein_g}g proteína</span>
    </div>
    <button onClick={() => onComplete(meal.id)}>
      Completar
    </button>
    <div className="ingredients">
      {meal.ingredients.map(ing => (
        <span key={ing.id}>
          {ing.quantity} {ing.unit} {ing.ingredient_name}
        </span>
      ))}
    </div>
  </div>
);
```

---

## 🎉 **Resumen de Consulta de Meals**

### 🎯 **Endpoints Principales**
1. **`GET /nutrition/today`** - Meals de HOY (más usado)
2. **`GET /nutrition/plans/{id}`** - Plan completo con todos los días
3. **`GET /nutrition/daily-plans/{id}`** - Día específico con meals
4. **`GET /nutrition/dashboard`** - Dashboard con today incluido

### 🔄 **Lógica Híbrida**
- **Template**: `current_day` basado en cuándo empezó el usuario
- **Live**: `current_day` basado en fecha global del plan
- **Archived**: Funciona como template

### 🍽️ **Estructura de Datos**
- **Plan** → **Día** → **Meal** → **Ingrediente**
- Cada nivel tiene su endpoint específico
- Información nutricional agregada en cada nivel

### 📱 **Experiencia del Usuario**
- Usuario abre app → GET /today → Ve meals de hoy
- Usuario navega plan → GET /plans/{id} → Ve calendario completo
- Usuario completa meal → POST /meals/{id}/complete → Progreso actualizado

**🚀 El sistema de meals está completamente integrado con la lógica híbrida, proporcionando la experiencia correcta según el tipo de plan.** 