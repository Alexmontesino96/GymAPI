# 💻 Ejemplos de Código - Endpoints CRUD de Nutrición

*Colección completa de ejemplos en múltiples lenguajes y frameworks*
*Última actualización: 28 de Diciembre 2024*

## 📋 Tabla de Contenidos

1. [JavaScript/TypeScript](#javascripttypescript)
2. [Python](#python)
3. [React](#react)
4. [Vue.js](#vuejs)
5. [Angular](#angular)
6. [Swift (iOS)](#swift-ios)
7. [Kotlin (Android)](#kotlin-android)
8. [cURL](#curl)
9. [Postman](#postman)
10. [Axios Interceptors](#axios-interceptors)

---

## JavaScript/TypeScript

### Clase Completa del Servicio

```typescript
// nutritionService.ts
interface MealData {
  id: number;
  name: string;
  meal_type: 'breakfast' | 'lunch' | 'dinner' | 'snack';
  time: string;
  target_calories: number;
  target_proteins?: number;
  target_carbs?: number;
  target_fats?: number;
  recipe_instructions?: string;
  ingredients?: IngredientData[];
}

interface IngredientData {
  id: number;
  name: string;
  quantity: number;
  unit: string;
  calories: number;
  proteins?: number;
  carbs?: number;
  fats?: number;
}

interface DailyPlanData {
  id: number;
  plan_id: number;
  day_number: number;
  day_name: string;
  description?: string;
  meals: MealData[];
  total_calories?: number;
}

class NutritionService {
  private baseURL: string;
  private headers: HeadersInit;

  constructor(token: string, gymId: number) {
    this.baseURL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
    this.headers = {
      'Authorization': `Bearer ${token}`,
      'X-Gym-Id': gymId.toString(),
      'Content-Type': 'application/json'
    };
  }

  // ============== MEALS ==============

  async getMeal(mealId: number): Promise<MealData> {
    const response = await fetch(
      `${this.baseURL}/api/v1/nutrition/meals/${mealId}`,
      {
        method: 'GET',
        headers: this.headers
      }
    );

    if (!response.ok) {
      throw await this.handleError(response);
    }

    return response.json();
  }

  async updateMeal(mealId: number, data: Partial<MealData>): Promise<MealData> {
    const response = await fetch(
      `${this.baseURL}/api/v1/nutrition/meals/${mealId}`,
      {
        method: 'PUT',
        headers: this.headers,
        body: JSON.stringify(data)
      }
    );

    if (!response.ok) {
      throw await this.handleError(response);
    }

    return response.json();
  }

  async deleteMeal(mealId: number): Promise<void> {
    const response = await fetch(
      `${this.baseURL}/api/v1/nutrition/meals/${mealId}`,
      {
        method: 'DELETE',
        headers: this.headers
      }
    );

    if (!response.ok) {
      throw await this.handleError(response);
    }
  }

  // ============== DAILY PLANS ==============

  async getDailyPlan(dailyPlanId: number): Promise<DailyPlanData> {
    const response = await fetch(
      `${this.baseURL}/api/v1/nutrition/days/${dailyPlanId}`,
      {
        method: 'GET',
        headers: this.headers
      }
    );

    if (!response.ok) {
      throw await this.handleError(response);
    }

    return response.json();
  }

  async getPlanDays(planId: number): Promise<DailyPlanData[]> {
    const response = await fetch(
      `${this.baseURL}/api/v1/nutrition/plans/${planId}/days`,
      {
        method: 'GET',
        headers: this.headers
      }
    );

    if (!response.ok) {
      throw await this.handleError(response);
    }

    return response.json();
  }

  async updateDailyPlan(
    dailyPlanId: number,
    data: { day_name?: string; description?: string }
  ): Promise<DailyPlanData> {
    const response = await fetch(
      `${this.baseURL}/api/v1/nutrition/days/${dailyPlanId}`,
      {
        method: 'PUT',
        headers: this.headers,
        body: JSON.stringify(data)
      }
    );

    if (!response.ok) {
      throw await this.handleError(response);
    }

    return response.json();
  }

  async deleteDailyPlan(dailyPlanId: number): Promise<void> {
    const response = await fetch(
      `${this.baseURL}/api/v1/nutrition/days/${dailyPlanId}`,
      {
        method: 'DELETE',
        headers: this.headers
      }
    );

    if (!response.ok) {
      throw await this.handleError(response);
    }
  }

  // ============== INGREDIENTS ==============

  async updateIngredient(
    ingredientId: number,
    data: Partial<IngredientData>
  ): Promise<IngredientData> {
    const response = await fetch(
      `${this.baseURL}/api/v1/nutrition/ingredients/${ingredientId}`,
      {
        method: 'PUT',
        headers: this.headers,
        body: JSON.stringify(data)
      }
    );

    if (!response.ok) {
      throw await this.handleError(response);
    }

    return response.json();
  }

  async deleteIngredient(ingredientId: number): Promise<void> {
    const response = await fetch(
      `${this.baseURL}/api/v1/nutrition/ingredients/${ingredientId}`,
      {
        method: 'DELETE',
        headers: this.headers
      }
    );

    if (!response.ok) {
      throw await this.handleError(response);
    }
  }

  // ============== ERROR HANDLING ==============

  private async handleError(response: Response): Promise<Error> {
    let message = 'Error desconocido';

    try {
      const error = await response.json();
      message = error.detail || error.message || message;
    } catch {
      // Si no es JSON, usar status text
      message = response.statusText;
    }

    switch (response.status) {
      case 401:
        return new Error('Token expirado o inválido');
      case 403:
        return new Error('Sin permisos para esta operación');
      case 404:
        return new Error('Recurso no encontrado');
      case 422:
        return new Error(`Datos inválidos: ${message}`);
      default:
        return new Error(message);
    }
  }
}

export default NutritionService;
```

### Ejemplos de Uso

```javascript
// Inicializar servicio
const nutritionService = new NutritionService(
  'eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...',
  4
);

// Ejemplo 1: Obtener una comida
try {
  const meal = await nutritionService.getMeal(3);
  console.log('Comida:', meal.name);
  console.log('Calorías:', meal.target_calories);
  console.log('Ingredientes:', meal.ingredients.length);
} catch (error) {
  console.error('Error:', error.message);
}

// Ejemplo 2: Actualizar una comida
try {
  const updated = await nutritionService.updateMeal(3, {
    name: 'Desayuno Energético Plus',
    target_calories: 500,
    recipe_instructions: 'Nueva receta mejorada...'
  });
  console.log('Comida actualizada:', updated);
} catch (error) {
  console.error('Error actualizando:', error.message);
}

// Ejemplo 3: Eliminar una comida
try {
  await nutritionService.deleteMeal(999);
  console.log('Comida eliminada exitosamente');
} catch (error) {
  console.error('Error eliminando:', error.message);
}

// Ejemplo 4: Obtener todos los días de un plan
try {
  const days = await nutritionService.getPlanDays(1);
  days.forEach(day => {
    console.log(`Día ${day.day_number}: ${day.day_name}`);
    console.log(`  Comidas: ${day.meals.length}`);
    console.log(`  Calorías totales: ${day.total_calories}`);
  });
} catch (error) {
  console.error('Error:', error.message);
}
```

---

## Python

### Cliente Completo con Requests

```python
# nutrition_client.py
import requests
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import json

@dataclass
class NutritionClient:
    base_url: str
    token: str
    gym_id: int

    def __post_init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.token}',
            'X-Gym-Id': str(self.gym_id),
            'Content-Type': 'application/json'
        })

    # ============== MEALS ==============

    def get_meal(self, meal_id: int) -> Dict[str, Any]:
        """Obtener una comida específica con sus ingredientes"""
        response = self.session.get(
            f"{self.base_url}/api/v1/nutrition/meals/{meal_id}"
        )
        response.raise_for_status()
        return response.json()

    def update_meal(self, meal_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Actualizar una comida"""
        response = self.session.put(
            f"{self.base_url}/api/v1/nutrition/meals/{meal_id}",
            json=data
        )
        response.raise_for_status()
        return response.json()

    def delete_meal(self, meal_id: int) -> bool:
        """Eliminar una comida"""
        response = self.session.delete(
            f"{self.base_url}/api/v1/nutrition/meals/{meal_id}"
        )
        response.raise_for_status()
        return response.status_code == 204

    # ============== DAILY PLANS ==============

    def get_daily_plan(self, daily_plan_id: int) -> Dict[str, Any]:
        """Obtener un día específico del plan"""
        response = self.session.get(
            f"{self.base_url}/api/v1/nutrition/days/{daily_plan_id}"
        )
        response.raise_for_status()
        return response.json()

    def get_plan_days(self, plan_id: int) -> List[Dict[str, Any]]:
        """Obtener todos los días de un plan"""
        response = self.session.get(
            f"{self.base_url}/api/v1/nutrition/plans/{plan_id}/days"
        )
        response.raise_for_status()
        return response.json()

    def update_daily_plan(
        self,
        daily_plan_id: int,
        day_name: Optional[str] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Actualizar un día del plan"""
        data = {}
        if day_name:
            data['day_name'] = day_name
        if description:
            data['description'] = description

        response = self.session.put(
            f"{self.base_url}/api/v1/nutrition/days/{daily_plan_id}",
            json=data
        )
        response.raise_for_status()
        return response.json()

    def delete_daily_plan(self, daily_plan_id: int) -> bool:
        """Eliminar un día del plan (renumera automáticamente)"""
        response = self.session.delete(
            f"{self.base_url}/api/v1/nutrition/days/{daily_plan_id}"
        )
        response.raise_for_status()
        return response.status_code == 204

    # ============== INGREDIENTS ==============

    def update_ingredient(
        self,
        ingredient_id: int,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Actualizar un ingrediente"""
        response = self.session.put(
            f"{self.base_url}/api/v1/nutrition/ingredients/{ingredient_id}",
            json=data
        )
        response.raise_for_status()
        return response.json()

    def delete_ingredient(self, ingredient_id: int) -> bool:
        """Eliminar un ingrediente"""
        response = self.session.delete(
            f"{self.base_url}/api/v1/nutrition/ingredients/{ingredient_id}"
        )
        response.raise_for_status()
        return response.status_code == 204


# Ejemplo de uso
if __name__ == "__main__":
    # Inicializar cliente
    client = NutritionClient(
        base_url="http://localhost:8000",
        token="eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
        gym_id=4
    )

    # Ejemplo 1: Obtener comida
    try:
        meal = client.get_meal(3)
        print(f"Comida: {meal['name']}")
        print(f"Calorías: {meal['target_calories']}")
        print(f"Ingredientes: {len(meal.get('ingredients', []))}")
    except requests.HTTPError as e:
        print(f"Error: {e}")

    # Ejemplo 2: Actualizar comida
    try:
        updated = client.update_meal(3, {
            'name': 'Desayuno Modificado',
            'target_calories': 450
        })
        print(f"Actualizado: {updated['name']}")
    except requests.HTTPError as e:
        print(f"Error: {e}")

    # Ejemplo 3: Obtener días del plan
    try:
        days = client.get_plan_days(1)
        for day in days:
            print(f"Día {day['day_number']}: {day['day_name']}")
            print(f"  Comidas: {len(day['meals'])}")
    except requests.HTTPError as e:
        print(f"Error: {e}")
```

### Async con aiohttp

```python
# async_nutrition_client.py
import aiohttp
import asyncio
from typing import Dict, Any, List, Optional

class AsyncNutritionClient:
    def __init__(self, base_url: str, token: str, gym_id: int):
        self.base_url = base_url
        self.headers = {
            'Authorization': f'Bearer {token}',
            'X-Gym-Id': str(gym_id),
            'Content-Type': 'application/json'
        }

    async def get_meal(self, session: aiohttp.ClientSession, meal_id: int) -> Dict:
        async with session.get(
            f"{self.base_url}/api/v1/nutrition/meals/{meal_id}",
            headers=self.headers
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def update_meal(
        self,
        session: aiohttp.ClientSession,
        meal_id: int,
        data: Dict
    ) -> Dict:
        async with session.put(
            f"{self.base_url}/api/v1/nutrition/meals/{meal_id}",
            headers=self.headers,
            json=data
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def delete_meal(
        self,
        session: aiohttp.ClientSession,
        meal_id: int
    ) -> bool:
        async with session.delete(
            f"{self.base_url}/api/v1/nutrition/meals/{meal_id}",
            headers=self.headers
        ) as response:
            response.raise_for_status()
            return response.status == 204

    async def get_multiple_meals(
        self,
        session: aiohttp.ClientSession,
        meal_ids: List[int]
    ) -> List[Dict]:
        """Obtener múltiples comidas en paralelo"""
        tasks = [self.get_meal(session, meal_id) for meal_id in meal_ids]
        return await asyncio.gather(*tasks, return_exceptions=True)


# Ejemplo de uso
async def main():
    client = AsyncNutritionClient(
        base_url="http://localhost:8000",
        token="eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
        gym_id=4
    )

    async with aiohttp.ClientSession() as session:
        # Obtener múltiples comidas en paralelo
        meal_ids = [1, 2, 3, 4, 5]
        meals = await client.get_multiple_meals(session, meal_ids)

        for i, meal in enumerate(meals):
            if isinstance(meal, dict):
                print(f"Comida {meal_ids[i]}: {meal.get('name')}")
            else:
                print(f"Error obteniendo comida {meal_ids[i]}: {meal}")

        # Actualizar una comida
        updated = await client.update_meal(session, 3, {
            'name': 'Desayuno Async',
            'target_calories': 500
        })
        print(f"Actualizado: {updated['name']}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## React

### Hook Personalizado con SWR

```jsx
// hooks/useNutritionMeal.js
import useSWR, { mutate } from 'swr';
import { useState } from 'react';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const fetcher = (url) => {
  const token = localStorage.getItem('token');
  const gymId = localStorage.getItem('gymId');

  return fetch(url, {
    headers: {
      'Authorization': `Bearer ${token}`,
      'X-Gym-Id': gymId
    }
  }).then(res => {
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  });
};

export function useNutritionMeal(mealId) {
  const { data, error, isLoading } = useSWR(
    mealId ? `${API_BASE}/api/v1/nutrition/meals/${mealId}` : null,
    fetcher,
    {
      revalidateOnFocus: false,
      revalidateOnReconnect: false,
      dedupingInterval: 60000, // 1 minuto
    }
  );

  const [isUpdating, setIsUpdating] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const updateMeal = async (updates) => {
    setIsUpdating(true);
    try {
      const response = await fetch(
        `${API_BASE}/api/v1/nutrition/meals/${mealId}`,
        {
          method: 'PUT',
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`,
            'X-Gym-Id': localStorage.getItem('gymId'),
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(updates)
        }
      );

      if (!response.ok) throw new Error('Error actualizando');

      const updated = await response.json();

      // Actualizar cache de SWR
      mutate(
        `${API_BASE}/api/v1/nutrition/meals/${mealId}`,
        updated,
        false
      );

      return updated;
    } finally {
      setIsUpdating(false);
    }
  };

  const deleteMeal = async () => {
    setIsDeleting(true);
    try {
      const response = await fetch(
        `${API_BASE}/api/v1/nutrition/meals/${mealId}`,
        {
          method: 'DELETE',
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`,
            'X-Gym-Id': localStorage.getItem('gymId')}`,
          }
        }
      );

      if (!response.ok) throw new Error('Error eliminando');

      // Invalidar cache
      mutate(`${API_BASE}/api/v1/nutrition/meals/${mealId}`, null, false);

      return true;
    } finally {
      setIsDeleting(false);
    }
  };

  return {
    meal: data,
    isLoading,
    isError: error,
    isUpdating,
    isDeleting,
    updateMeal,
    deleteMeal
  };
}
```

### Componente con el Hook

```jsx
// components/MealEditor.jsx
import React, { useState } from 'react';
import { useNutritionMeal } from '../hooks/useNutritionMeal';

function MealEditor({ mealId, onClose }) {
  const {
    meal,
    isLoading,
    isError,
    isUpdating,
    isDeleting,
    updateMeal,
    deleteMeal
  } = useNutritionMeal(mealId);

  const [formData, setFormData] = useState({});
  const [editMode, setEditMode] = useState(false);

  if (isLoading) return <div>Cargando...</div>;
  if (isError) return <div>Error cargando comida</div>;
  if (!meal) return null;

  const handleSave = async () => {
    try {
      await updateMeal(formData);
      setEditMode(false);
      alert('Comida actualizada');
    } catch (error) {
      alert('Error: ' + error.message);
    }
  };

  const handleDelete = async () => {
    if (!confirm('¿Eliminar esta comida?')) return;

    try {
      await deleteMeal();
      alert('Comida eliminada');
      onClose();
    } catch (error) {
      alert('Error: ' + error.message);
    }
  };

  return (
    <div className="meal-editor">
      {editMode ? (
        <div>
          <input
            value={formData.name || meal.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            placeholder="Nombre"
          />
          <input
            type="number"
            value={formData.target_calories || meal.target_calories}
            onChange={(e) => setFormData({
              ...formData,
              target_calories: parseInt(e.target.value)
            })}
            placeholder="Calorías"
          />
          <textarea
            value={formData.recipe_instructions || meal.recipe_instructions}
            onChange={(e) => setFormData({
              ...formData,
              recipe_instructions: e.target.value
            })}
            placeholder="Instrucciones"
          />
          <button onClick={handleSave} disabled={isUpdating}>
            {isUpdating ? 'Guardando...' : 'Guardar'}
          </button>
          <button onClick={() => setEditMode(false)}>Cancelar</button>
        </div>
      ) : (
        <div>
          <h2>{meal.name}</h2>
          <p>Calorías: {meal.target_calories}</p>
          <p>Proteínas: {meal.target_proteins}g</p>
          <p>Carbohidratos: {meal.target_carbs}g</p>
          <p>Grasas: {meal.target_fats}g</p>

          <div className="ingredients">
            <h3>Ingredientes</h3>
            {meal.ingredients?.map(ing => (
              <div key={ing.id}>
                {ing.name} - {ing.quantity} {ing.unit}
                ({ing.calories} cal)
              </div>
            ))}
          </div>

          <button onClick={() => setEditMode(true)}>Editar</button>
          <button onClick={handleDelete} disabled={isDeleting}>
            {isDeleting ? 'Eliminando...' : 'Eliminar'}
          </button>
        </div>
      )}
    </div>
  );
}

export default MealEditor;
```

---

## Vue.js

### Composable con Vue 3

```javascript
// composables/useNutrition.js
import { ref, computed } from 'vue';

export function useNutrition() {
  const baseURL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
  const loading = ref(false);
  const error = ref(null);

  const headers = computed(() => ({
    'Authorization': `Bearer ${localStorage.getItem('token')}`,
    'X-Gym-Id': localStorage.getItem('gymId') || '4',
    'Content-Type': 'application/json'
  }));

  // GET Meal
  const getMeal = async (mealId) => {
    loading.value = true;
    error.value = null;

    try {
      const response = await fetch(
        `${baseURL}/api/v1/nutrition/meals/${mealId}`,
        { headers: headers.value }
      );

      if (!response.ok) throw new Error(response.statusText);

      return await response.json();
    } catch (err) {
      error.value = err.message;
      throw err;
    } finally {
      loading.value = false;
    }
  };

  // UPDATE Meal
  const updateMeal = async (mealId, data) => {
    loading.value = true;
    error.value = null;

    try {
      const response = await fetch(
        `${baseURL}/api/v1/nutrition/meals/${mealId}`,
        {
          method: 'PUT',
          headers: headers.value,
          body: JSON.stringify(data)
        }
      );

      if (!response.ok) throw new Error(response.statusText);

      return await response.json();
    } catch (err) {
      error.value = err.message;
      throw err;
    } finally {
      loading.value = false;
    }
  };

  // DELETE Meal
  const deleteMeal = async (mealId) => {
    loading.value = true;
    error.value = null;

    try {
      const response = await fetch(
        `${baseURL}/api/v1/nutrition/meals/${mealId}`,
        {
          method: 'DELETE',
          headers: headers.value
        }
      );

      if (!response.ok) throw new Error(response.statusText);

      return true;
    } catch (err) {
      error.value = err.message;
      throw err;
    } finally {
      loading.value = false;
    }
  };

  // GET Plan Days
  const getPlanDays = async (planId) => {
    loading.value = true;
    error.value = null;

    try {
      const response = await fetch(
        `${baseURL}/api/v1/nutrition/plans/${planId}/days`,
        { headers: headers.value }
      );

      if (!response.ok) throw new Error(response.statusText);

      return await response.json();
    } catch (err) {
      error.value = err.message;
      throw err;
    } finally {
      loading.value = false;
    }
  };

  return {
    loading,
    error,
    getMeal,
    updateMeal,
    deleteMeal,
    getPlanDays
  };
}
```

### Componente Vue

```vue
<!-- MealCard.vue -->
<template>
  <div class="meal-card">
    <div v-if="loading" class="loading">Cargando...</div>

    <div v-else-if="error" class="error">
      Error: {{ error }}
    </div>

    <div v-else-if="meal">
      <div v-if="!editing">
        <h2>{{ meal.name }}</h2>
        <p>Tipo: {{ meal.meal_type }}</p>
        <p>Hora: {{ meal.time }}</p>
        <p>Calorías: {{ meal.target_calories }}</p>

        <div class="ingredients">
          <h3>Ingredientes ({{ meal.ingredients?.length || 0 }})</h3>
          <div v-for="ing in meal.ingredients" :key="ing.id">
            {{ ing.name }} - {{ ing.quantity }}{{ ing.unit }}
            ({{ ing.calories }} cal)
          </div>
        </div>

        <button @click="startEditing">Editar</button>
        <button @click="handleDelete">Eliminar</button>
      </div>

      <div v-else>
        <input v-model="editForm.name" placeholder="Nombre" />
        <input
          v-model.number="editForm.target_calories"
          type="number"
          placeholder="Calorías"
        />
        <textarea
          v-model="editForm.recipe_instructions"
          placeholder="Instrucciones"
        ></textarea>

        <button @click="handleSave" :disabled="saving">
          {{ saving ? 'Guardando...' : 'Guardar' }}
        </button>
        <button @click="cancelEditing">Cancelar</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useNutrition } from '@/composables/useNutrition';

const props = defineProps({
  mealId: {
    type: Number,
    required: true
  }
});

const emit = defineEmits(['updated', 'deleted']);

const { getMeal, updateMeal, deleteMeal, loading, error } = useNutrition();

const meal = ref(null);
const editing = ref(false);
const editForm = ref({});
const saving = ref(false);

onMounted(async () => {
  meal.value = await getMeal(props.mealId);
});

const startEditing = () => {
  editForm.value = {
    name: meal.value.name,
    target_calories: meal.value.target_calories,
    recipe_instructions: meal.value.recipe_instructions
  };
  editing.value = true;
};

const cancelEditing = () => {
  editing.value = false;
  editForm.value = {};
};

const handleSave = async () => {
  saving.value = true;
  try {
    const updated = await updateMeal(props.mealId, editForm.value);
    meal.value = updated;
    editing.value = false;
    emit('updated', updated);
    alert('Comida actualizada');
  } catch (err) {
    alert('Error: ' + err.message);
  } finally {
    saving.value = false;
  }
};

const handleDelete = async () => {
  if (!confirm('¿Eliminar esta comida?')) return;

  try {
    await deleteMeal(props.mealId);
    emit('deleted', props.mealId);
    alert('Comida eliminada');
  } catch (err) {
    alert('Error: ' + err.message);
  }
};
</script>
```

---

## Angular

### Servicio Angular

```typescript
// nutrition.service.ts
import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../environments/environment';

interface Meal {
  id: number;
  name: string;
  meal_type: string;
  time: string;
  target_calories: number;
  target_proteins?: number;
  target_carbs?: number;
  target_fats?: number;
  recipe_instructions?: string;
  ingredients?: Ingredient[];
}

interface Ingredient {
  id: number;
  name: string;
  quantity: number;
  unit: string;
  calories: number;
}

interface DailyPlan {
  id: number;
  day_number: number;
  day_name: string;
  description?: string;
  meals: Meal[];
}

@Injectable({
  providedIn: 'root'
})
export class NutritionService {
  private apiUrl = `${environment.apiUrl}/api/v1/nutrition`;

  constructor(private http: HttpClient) {}

  private getHeaders(): HttpHeaders {
    return new HttpHeaders({
      'Authorization': `Bearer ${localStorage.getItem('token')}`,
      'X-Gym-Id': localStorage.getItem('gymId') || '4',
      'Content-Type': 'application/json'
    });
  }

  // MEALS
  getMeal(mealId: number): Observable<Meal> {
    return this.http.get<Meal>(
      `${this.apiUrl}/meals/${mealId}`,
      { headers: this.getHeaders() }
    );
  }

  updateMeal(mealId: number, data: Partial<Meal>): Observable<Meal> {
    return this.http.put<Meal>(
      `${this.apiUrl}/meals/${mealId}`,
      data,
      { headers: this.getHeaders() }
    );
  }

  deleteMeal(mealId: number): Observable<void> {
    return this.http.delete<void>(
      `${this.apiUrl}/meals/${mealId}`,
      { headers: this.getHeaders() }
    );
  }

  // DAILY PLANS
  getDailyPlan(dailyPlanId: number): Observable<DailyPlan> {
    return this.http.get<DailyPlan>(
      `${this.apiUrl}/days/${dailyPlanId}`,
      { headers: this.getHeaders() }
    );
  }

  getPlanDays(planId: number): Observable<DailyPlan[]> {
    return this.http.get<DailyPlan[]>(
      `${this.apiUrl}/plans/${planId}/days`,
      { headers: this.getHeaders() }
    );
  }

  updateDailyPlan(
    dailyPlanId: number,
    data: { day_name?: string; description?: string }
  ): Observable<DailyPlan> {
    return this.http.put<DailyPlan>(
      `${this.apiUrl}/days/${dailyPlanId}`,
      data,
      { headers: this.getHeaders() }
    );
  }

  deleteDailyPlan(dailyPlanId: number): Observable<void> {
    return this.http.delete<void>(
      `${this.apiUrl}/days/${dailyPlanId}`,
      { headers: this.getHeaders() }
    );
  }

  // INGREDIENTS
  updateIngredient(
    ingredientId: number,
    data: Partial<Ingredient>
  ): Observable<Ingredient> {
    return this.http.put<Ingredient>(
      `${this.apiUrl}/ingredients/${ingredientId}`,
      data,
      { headers: this.getHeaders() }
    );
  }

  deleteIngredient(ingredientId: number): Observable<void> {
    return this.http.delete<void>(
      `${this.apiUrl}/ingredients/${ingredientId}`,
      { headers: this.getHeaders() }
    );
  }
}
```

### Componente Angular

```typescript
// meal-editor.component.ts
import { Component, OnInit, Input } from '@angular/core';
import { NutritionService } from '../services/nutrition.service';

@Component({
  selector: 'app-meal-editor',
  template: `
    <div class="meal-editor" *ngIf="meal">
      <div *ngIf="!editing">
        <h2>{{ meal.name }}</h2>
        <p>Calorías: {{ meal.target_calories }}</p>
        <p>Tiempo: {{ meal.time }}</p>

        <button (click)="startEditing()">Editar</button>
        <button (click)="deleteMeal()">Eliminar</button>
      </div>

      <div *ngIf="editing">
        <input [(ngModel)]="editForm.name" placeholder="Nombre">
        <input
          type="number"
          [(ngModel)]="editForm.target_calories"
          placeholder="Calorías">
        <textarea
          [(ngModel)]="editForm.recipe_instructions"
          placeholder="Instrucciones"></textarea>

        <button (click)="saveMeal()" [disabled]="saving">
          {{ saving ? 'Guardando...' : 'Guardar' }}
        </button>
        <button (click)="cancelEditing()">Cancelar</button>
      </div>
    </div>
  `
})
export class MealEditorComponent implements OnInit {
  @Input() mealId!: number;

  meal: any = null;
  editing = false;
  saving = false;
  editForm: any = {};

  constructor(private nutritionService: NutritionService) {}

  ngOnInit() {
    this.loadMeal();
  }

  loadMeal() {
    this.nutritionService.getMeal(this.mealId).subscribe(
      meal => this.meal = meal,
      error => console.error('Error:', error)
    );
  }

  startEditing() {
    this.editForm = { ...this.meal };
    this.editing = true;
  }

  cancelEditing() {
    this.editing = false;
    this.editForm = {};
  }

  saveMeal() {
    this.saving = true;
    this.nutritionService.updateMeal(this.mealId, this.editForm).subscribe(
      updated => {
        this.meal = updated;
        this.editing = false;
        this.saving = false;
        alert('Comida actualizada');
      },
      error => {
        this.saving = false;
        alert('Error: ' + error.message);
      }
    );
  }

  deleteMeal() {
    if (!confirm('¿Eliminar esta comida?')) return;

    this.nutritionService.deleteMeal(this.mealId).subscribe(
      () => alert('Comida eliminada'),
      error => alert('Error: ' + error.message)
    );
  }
}
```

---

## Swift (iOS)

### Cliente Swift

```swift
// NutritionService.swift
import Foundation

struct Meal: Codable {
    let id: Int
    var name: String
    var mealType: String
    var time: String
    var targetCalories: Int
    var targetProteins: Double?
    var targetCarbs: Double?
    var targetFats: Double?
    var recipeInstructions: String?
    var ingredients: [Ingredient]?

    enum CodingKeys: String, CodingKey {
        case id, name, time, ingredients
        case mealType = "meal_type"
        case targetCalories = "target_calories"
        case targetProteins = "target_proteins"
        case targetCarbs = "target_carbs"
        case targetFats = "target_fats"
        case recipeInstructions = "recipe_instructions"
    }
}

struct Ingredient: Codable {
    let id: Int
    var name: String
    var quantity: Double
    var unit: String
    var calories: Int
    var proteins: Double?
    var carbs: Double?
    var fats: Double?
}

class NutritionService {
    private let baseURL = "http://localhost:8000/api/v1/nutrition"
    private let token: String
    private let gymId: Int

    init(token: String, gymId: Int) {
        self.token = token
        self.gymId = gymId
    }

    private func createRequest(
        url: URL,
        method: String,
        body: Data? = nil
    ) -> URLRequest {
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("\(gymId)", forHTTPHeaderField: "X-Gym-Id")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = body
        return request
    }

    // GET Meal
    func getMeal(mealId: Int) async throws -> Meal {
        let url = URL(string: "\(baseURL)/meals/\(mealId)")!
        let request = createRequest(url: url, method: "GET")

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw URLError(.badServerResponse)
        }

        return try JSONDecoder().decode(Meal.self, from: data)
    }

    // UPDATE Meal
    func updateMeal(mealId: Int, updates: [String: Any]) async throws -> Meal {
        let url = URL(string: "\(baseURL)/meals/\(mealId)")!
        let body = try JSONSerialization.data(withJSONObject: updates)
        let request = createRequest(url: url, method: "PUT", body: body)

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw URLError(.badServerResponse)
        }

        return try JSONDecoder().decode(Meal.self, from: data)
    }

    // DELETE Meal
    func deleteMeal(mealId: Int) async throws {
        let url = URL(string: "\(baseURL)/meals/\(mealId)")!
        let request = createRequest(url: url, method: "DELETE")

        let (_, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 204 else {
            throw URLError(.badServerResponse)
        }
    }
}

// Uso en SwiftUI View
struct MealDetailView: View {
    @State private var meal: Meal?
    @State private var isLoading = true
    @State private var errorMessage: String?

    let mealId: Int
    let nutritionService: NutritionService

    var body: some View {
        Group {
            if isLoading {
                ProgressView()
            } else if let meal = meal {
                VStack(alignment: .leading) {
                    Text(meal.name)
                        .font(.title)
                    Text("Calorías: \(meal.targetCalories)")
                    Text("Hora: \(meal.time)")

                    if let ingredients = meal.ingredients {
                        Text("Ingredientes:")
                            .font(.headline)
                        ForEach(ingredients, id: \.id) { ingredient in
                            Text("\(ingredient.name): \(ingredient.quantity)\(ingredient.unit)")
                        }
                    }

                    HStack {
                        Button("Editar") {
                            // Navegar a vista de edición
                        }
                        Button("Eliminar") {
                            Task {
                                await deleteMeal()
                            }
                        }
                        .foregroundColor(.red)
                    }
                }
            } else if let error = errorMessage {
                Text("Error: \(error)")
                    .foregroundColor(.red)
            }
        }
        .task {
            await loadMeal()
        }
    }

    func loadMeal() async {
        do {
            meal = try await nutritionService.getMeal(mealId: mealId)
            isLoading = false
        } catch {
            errorMessage = error.localizedDescription
            isLoading = false
        }
    }

    func deleteMeal() async {
        do {
            try await nutritionService.deleteMeal(mealId: mealId)
            // Navegar hacia atrás
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}
```

---

## Kotlin (Android)

### Cliente Kotlin con Retrofit

```kotlin
// NutritionService.kt
import retrofit2.http.*

data class Meal(
    val id: Int,
    val name: String,
    val meal_type: String,
    val time: String,
    val target_calories: Int,
    val target_proteins: Double?,
    val target_carbs: Double?,
    val target_fats: Double?,
    val recipe_instructions: String?,
    val ingredients: List<Ingredient>?
)

data class Ingredient(
    val id: Int,
    val name: String,
    val quantity: Double,
    val unit: String,
    val calories: Int
)

data class DailyPlan(
    val id: Int,
    val day_number: Int,
    val day_name: String,
    val description: String?,
    val meals: List<Meal>
)

interface NutritionApi {
    @GET("nutrition/meals/{meal_id}")
    suspend fun getMeal(
        @Path("meal_id") mealId: Int,
        @Header("Authorization") token: String,
        @Header("X-Gym-Id") gymId: String
    ): Meal

    @PUT("nutrition/meals/{meal_id}")
    suspend fun updateMeal(
        @Path("meal_id") mealId: Int,
        @Body updates: Map<String, Any>,
        @Header("Authorization") token: String,
        @Header("X-Gym-Id") gymId: String
    ): Meal

    @DELETE("nutrition/meals/{meal_id}")
    suspend fun deleteMeal(
        @Path("meal_id") mealId: Int,
        @Header("Authorization") token: String,
        @Header("X-Gym-Id") gymId: String
    )

    @GET("nutrition/days/{daily_plan_id}")
    suspend fun getDailyPlan(
        @Path("daily_plan_id") dailyPlanId: Int,
        @Header("Authorization") token: String,
        @Header("X-Gym-Id") gymId: String
    ): DailyPlan

    @GET("nutrition/plans/{plan_id}/days")
    suspend fun getPlanDays(
        @Path("plan_id") planId: Int,
        @Header("Authorization") token: String,
        @Header("X-Gym-Id") gymId: String
    ): List<DailyPlan>
}

// Repository
class NutritionRepository(
    private val api: NutritionApi,
    private val token: String,
    private val gymId: String
) {
    private fun authToken() = "Bearer $token"

    suspend fun getMeal(mealId: Int): Result<Meal> {
        return try {
            val meal = api.getMeal(mealId, authToken(), gymId)
            Result.success(meal)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun updateMeal(mealId: Int, updates: Map<String, Any>): Result<Meal> {
        return try {
            val updated = api.updateMeal(mealId, updates, authToken(), gymId)
            Result.success(updated)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun deleteMeal(mealId: Int): Result<Unit> {
        return try {
            api.deleteMeal(mealId, authToken(), gymId)
            Result.success(Unit)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}
```

### ViewModel con LiveData

```kotlin
// MealViewModel.kt
import androidx.lifecycle.ViewModel
import androidx.lifecycle.MutableLiveData
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.launch

class MealViewModel(
    private val repository: NutritionRepository
) : ViewModel() {

    private val _meal = MutableLiveData<Meal?>()
    val meal: LiveData<Meal?> = _meal

    private val _loading = MutableLiveData<Boolean>()
    val loading: LiveData<Boolean> = _loading

    private val _error = MutableLiveData<String?>()
    val error: LiveData<String?> = _error

    fun loadMeal(mealId: Int) {
        viewModelScope.launch {
            _loading.value = true
            repository.getMeal(mealId).fold(
                onSuccess = { meal ->
                    _meal.value = meal
                    _loading.value = false
                },
                onFailure = { exception ->
                    _error.value = exception.message
                    _loading.value = false
                }
            )
        }
    }

    fun updateMeal(mealId: Int, updates: Map<String, Any>) {
        viewModelScope.launch {
            _loading.value = true
            repository.updateMeal(mealId, updates).fold(
                onSuccess = { updated ->
                    _meal.value = updated
                    _loading.value = false
                },
                onFailure = { exception ->
                    _error.value = exception.message
                    _loading.value = false
                }
            )
        }
    }

    fun deleteMeal(mealId: Int, onSuccess: () -> Unit) {
        viewModelScope.launch {
            repository.deleteMeal(mealId).fold(
                onSuccess = {
                    onSuccess()
                },
                onFailure = { exception ->
                    _error.value = exception.message
                }
            )
        }
    }
}
```

---

## cURL

### Ejemplos Completos con cURL

```bash
# Variables de entorno
export TOKEN="eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."
export GYM_ID="4"
export BASE_URL="http://localhost:8000/api/v1"

# ============== MEALS ==============

# GET Meal
curl -X GET "$BASE_URL/nutrition/meals/3" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Gym-Id: $GYM_ID" \
  | jq .

# UPDATE Meal
curl -X PUT "$BASE_URL/nutrition/meals/3" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Gym-Id: $GYM_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Desayuno Actualizado",
    "target_calories": 450,
    "target_proteins": 30.0,
    "recipe_instructions": "Nueva receta mejorada..."
  }' \
  | jq .

# DELETE Meal
curl -X DELETE "$BASE_URL/nutrition/meals/999" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Gym-Id: $GYM_ID" \
  -w "\nHTTP Status: %{http_code}\n"

# ============== DAILY PLANS ==============

# GET Daily Plan
curl -X GET "$BASE_URL/nutrition/days/10" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Gym-Id: $GYM_ID" \
  | jq .

# GET All Days of a Plan
curl -X GET "$BASE_URL/nutrition/plans/1/days" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Gym-Id: $GYM_ID" \
  | jq '.[] | {day: .day_number, name: .day_name, meals: .meals | length}'

# UPDATE Daily Plan
curl -X PUT "$BASE_URL/nutrition/days/10" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Gym-Id: $GYM_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "day_name": "Lunes Power",
    "description": "Día de máxima energía"
  }' \
  | jq .

# DELETE Daily Plan
curl -X DELETE "$BASE_URL/nutrition/days/10" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Gym-Id: $GYM_ID" \
  -w "\nHTTP Status: %{http_code}\n"

# ============== INGREDIENTS ==============

# UPDATE Ingredient
curl -X PUT "$BASE_URL/nutrition/ingredients/101" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Gym-Id: $GYM_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Avena integral",
    "quantity": 150,
    "unit": "gramos",
    "calories": 550
  }' \
  | jq .

# DELETE Ingredient
curl -X DELETE "$BASE_URL/nutrition/ingredients/101" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Gym-Id: $GYM_ID" \
  -w "\nHTTP Status: %{http_code}\n"
```

### Script Bash para Testing

```bash
#!/bin/bash
# test_nutrition_endpoints.sh

set -e

# Configuración
TOKEN=${1:-"tu_token_aqui"}
GYM_ID=${2:-4}
BASE_URL="http://localhost:8000/api/v1"

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "Testing Nutrition CRUD Endpoints"
echo "================================"

# Función para test
test_endpoint() {
    local method=$1
    local endpoint=$2
    local data=$3
    local expected_status=$4

    echo -n "Testing $method $endpoint... "

    if [ -z "$data" ]; then
        response=$(curl -s -o /dev/null -w "%{http_code}" \
            -X $method "$BASE_URL$endpoint" \
            -H "Authorization: Bearer $TOKEN" \
            -H "X-Gym-Id: $GYM_ID")
    else
        response=$(curl -s -o /dev/null -w "%{http_code}" \
            -X $method "$BASE_URL$endpoint" \
            -H "Authorization: Bearer $TOKEN" \
            -H "X-Gym-Id: $GYM_ID" \
            -H "Content-Type: application/json" \
            -d "$data")
    fi

    if [ "$response" == "$expected_status" ]; then
        echo -e "${GREEN}✓${NC} (Status: $response)"
    else
        echo -e "${RED}✗${NC} (Expected: $expected_status, Got: $response)"
    fi
}

# Tests
test_endpoint "GET" "/nutrition/meals/3" "" "200"
test_endpoint "PUT" "/nutrition/meals/3" '{"name":"Test Meal"}' "200"
test_endpoint "DELETE" "/nutrition/meals/999" "" "204"
test_endpoint "GET" "/nutrition/days/10" "" "200"
test_endpoint "GET" "/nutrition/plans/1/days" "" "200"
test_endpoint "PUT" "/nutrition/days/10" '{"day_name":"Test Day"}' "200"
test_endpoint "PUT" "/nutrition/ingredients/101" '{"quantity":100}' "200"
test_endpoint "DELETE" "/nutrition/ingredients/999" "" "204"

echo "================================"
echo "Tests completed!"
```

---

## Postman

### Colección Postman JSON

```json
{
  "info": {
    "name": "Nutrition CRUD API",
    "description": "Complete CRUD operations for nutrition module",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "auth": {
    "type": "bearer",
    "bearer": [
      {
        "key": "token",
        "value": "{{auth_token}}",
        "type": "string"
      }
    ]
  },
  "variable": [
    {
      "key": "base_url",
      "value": "http://localhost:8000/api/v1",
      "type": "string"
    },
    {
      "key": "gym_id",
      "value": "4",
      "type": "string"
    },
    {
      "key": "auth_token",
      "value": "",
      "type": "string"
    }
  ],
  "item": [
    {
      "name": "Meals",
      "item": [
        {
          "name": "Get Meal",
          "event": [
            {
              "listen": "test",
              "script": {
                "exec": [
                  "pm.test(\"Status code is 200\", function () {",
                  "    pm.response.to.have.status(200);",
                  "});",
                  "",
                  "pm.test(\"Response has meal data\", function () {",
                  "    var jsonData = pm.response.json();",
                  "    pm.expect(jsonData).to.have.property('id');",
                  "    pm.expect(jsonData).to.have.property('name');",
                  "    pm.expect(jsonData).to.have.property('ingredients');",
                  "});"
                ]
              }
            }
          ],
          "request": {
            "method": "GET",
            "header": [
              {
                "key": "X-Gym-Id",
                "value": "{{gym_id}}"
              }
            ],
            "url": {
              "raw": "{{base_url}}/nutrition/meals/3",
              "host": ["{{base_url}}"],
              "path": ["nutrition", "meals", "3"]
            }
          }
        },
        {
          "name": "Update Meal",
          "request": {
            "method": "PUT",
            "header": [
              {
                "key": "X-Gym-Id",
                "value": "{{gym_id}}"
              }
            ],
            "body": {
              "mode": "raw",
              "raw": "{\n  \"name\": \"Desayuno Actualizado {{$timestamp}}\",\n  \"target_calories\": 450,\n  \"target_proteins\": 30.0,\n  \"target_carbs\": 55.0,\n  \"target_fats\": 15.0,\n  \"recipe_instructions\": \"1. Preparar avena\\n2. Añadir frutas\\n3. Servir caliente\"\n}",
              "options": {
                "raw": {
                  "language": "json"
                }
              }
            },
            "url": {
              "raw": "{{base_url}}/nutrition/meals/3",
              "host": ["{{base_url}}"],
              "path": ["nutrition", "meals", "3"]
            }
          }
        },
        {
          "name": "Delete Meal",
          "request": {
            "method": "DELETE",
            "header": [
              {
                "key": "X-Gym-Id",
                "value": "{{gym_id}}"
              }
            ],
            "url": {
              "raw": "{{base_url}}/nutrition/meals/999",
              "host": ["{{base_url}}"],
              "path": ["nutrition", "meals", "999"]
            }
          }
        }
      ]
    },
    {
      "name": "Daily Plans",
      "item": [
        {
          "name": "Get Daily Plan",
          "request": {
            "method": "GET",
            "header": [
              {
                "key": "X-Gym-Id",
                "value": "{{gym_id}}"
              }
            ],
            "url": {
              "raw": "{{base_url}}/nutrition/days/10",
              "host": ["{{base_url}}"],
              "path": ["nutrition", "days", "10"]
            }
          }
        },
        {
          "name": "Get Plan Days",
          "request": {
            "method": "GET",
            "header": [
              {
                "key": "X-Gym-Id",
                "value": "{{gym_id}}"
              }
            ],
            "url": {
              "raw": "{{base_url}}/nutrition/plans/1/days",
              "host": ["{{base_url}}"],
              "path": ["nutrition", "plans", "1", "days"]
            }
          }
        },
        {
          "name": "Update Daily Plan",
          "request": {
            "method": "PUT",
            "header": [
              {
                "key": "X-Gym-Id",
                "value": "{{gym_id}}"
              }
            ],
            "body": {
              "mode": "raw",
              "raw": "{\n  \"day_name\": \"Lunes Power {{$timestamp}}\",\n  \"description\": \"Día de máxima energía con carbohidratos complejos\"\n}",
              "options": {
                "raw": {
                  "language": "json"
                }
              }
            },
            "url": {
              "raw": "{{base_url}}/nutrition/days/10",
              "host": ["{{base_url}}"],
              "path": ["nutrition", "days", "10"]
            }
          }
        }
      ]
    },
    {
      "name": "Ingredients",
      "item": [
        {
          "name": "Update Ingredient",
          "request": {
            "method": "PUT",
            "header": [
              {
                "key": "X-Gym-Id",
                "value": "{{gym_id}}"
              }
            ],
            "body": {
              "mode": "raw",
              "raw": "{\n  \"name\": \"Avena integral\",\n  \"quantity\": 120,\n  \"unit\": \"gramos\",\n  \"calories\": 450,\n  \"proteins\": 20.0,\n  \"carbs\": 75.0,\n  \"fats\": 8.0\n}",
              "options": {
                "raw": {
                  "language": "json"
                }
              }
            },
            "url": {
              "raw": "{{base_url}}/nutrition/ingredients/101",
              "host": ["{{base_url}}"],
              "path": ["nutrition", "ingredients", "101"]
            }
          }
        },
        {
          "name": "Delete Ingredient",
          "request": {
            "method": "DELETE",
            "header": [
              {
                "key": "X-Gym-Id",
                "value": "{{gym_id}}"
              }
            ],
            "url": {
              "raw": "{{base_url}}/nutrition/ingredients/999",
              "host": ["{{base_url}}"],
              "path": ["nutrition", "ingredients", "999"]
            }
          }
        }
      ]
    }
  ]
}
```

---

## Axios Interceptors

### Configuración Global con Interceptors

```javascript
// axiosConfig.js
import axios from 'axios';

// Crear instancia de axios
const nutritionAPI = axios.create({
  baseURL: process.env.REACT_APP_API_URL || 'http://localhost:8000',
  timeout: 10000
});

// Request interceptor para agregar headers
nutritionAPI.interceptors.request.use(
  config => {
    const token = localStorage.getItem('token');
    const gymId = localStorage.getItem('gymId');

    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    if (gymId) {
      config.headers['X-Gym-Id'] = gymId;
    }

    // Log de requests en desarrollo
    if (process.env.NODE_ENV === 'development') {
      console.log('Request:', config.method?.toUpperCase(), config.url);
    }

    return config;
  },
  error => {
    return Promise.reject(error);
  }
);

// Response interceptor para manejar errores
nutritionAPI.interceptors.response.use(
  response => {
    // Log de respuestas exitosas
    if (process.env.NODE_ENV === 'development') {
      console.log('Response:', response.status, response.config.url);
    }
    return response;
  },
  error => {
    const { response } = error;

    if (response) {
      switch (response.status) {
        case 401:
          // Token expirado - redirigir a login
          localStorage.removeItem('token');
          window.location.href = '/login';
          break;

        case 403:
          // Sin permisos
          console.error('Sin permisos para esta operación');
          break;

        case 404:
          // No encontrado
          console.error('Recurso no encontrado');
          break;

        case 422:
          // Validación fallida
          console.error('Datos inválidos:', response.data);
          break;

        case 500:
          // Error del servidor
          console.error('Error del servidor');
          break;
      }
    }

    return Promise.reject(error);
  }
);

// API Methods
export const nutritionService = {
  // Meals
  getMeal: (mealId) =>
    nutritionAPI.get(`/api/v1/nutrition/meals/${mealId}`),

  updateMeal: (mealId, data) =>
    nutritionAPI.put(`/api/v1/nutrition/meals/${mealId}`, data),

  deleteMeal: (mealId) =>
    nutritionAPI.delete(`/api/v1/nutrition/meals/${mealId}`),

  // Daily Plans
  getDailyPlan: (dailyPlanId) =>
    nutritionAPI.get(`/api/v1/nutrition/days/${dailyPlanId}`),

  getPlanDays: (planId) =>
    nutritionAPI.get(`/api/v1/nutrition/plans/${planId}/days`),

  updateDailyPlan: (dailyPlanId, data) =>
    nutritionAPI.put(`/api/v1/nutrition/days/${dailyPlanId}`, data),

  deleteDailyPlan: (dailyPlanId) =>
    nutritionAPI.delete(`/api/v1/nutrition/days/${dailyPlanId}`),

  // Ingredients
  updateIngredient: (ingredientId, data) =>
    nutritionAPI.put(`/api/v1/nutrition/ingredients/${ingredientId}`, data),

  deleteIngredient: (ingredientId) =>
    nutritionAPI.delete(`/api/v1/nutrition/ingredients/${ingredientId}`)
};

export default nutritionAPI;
```

---

*Documentación creada por: Claude Code Assistant*
*Última actualización: 28 de Diciembre 2024*
*Versión: 1.0.0*