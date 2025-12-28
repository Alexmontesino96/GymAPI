# 🚨 GUÍA URGENTE PARA FRONTEND: Corrección de Errores 404

## 📊 RESUMEN EJECUTIVO
Se han detectado **3 errores críticos 404** en producción que están afectando la experiencia del usuario:
1. **PUT /api/v1/nutrition/meals/{id}** - ⚠️ **CRÍTICO:** NO existe PUT ni DELETE para comidas
2. **POST /api/v1/nutrition/daily-plans/{id}/meals** - URL incorrecta (usar `days` no `daily-plans`)
3. **GET /api/v1/activity-feed/realtime** - Módulo no habilitado para gym_id=4

## ❌ PROBLEMAS DETECTADOS EN PRODUCCIÓN

### Problema 1: Endpoint de Actualización de Comidas NO EXISTE

#### ❌ LO QUE ESTÁN HACIENDO MAL:
```javascript
// INCORRECTO - Este endpoint NO ESTÁ IMPLEMENTADO en el backend
PUT /api/v1/nutrition/meals/3
```

#### ⚠️ REALIDAD:
**NO EXISTE un endpoint para actualizar/editar comidas directamente.** El backend no tiene implementada esta funcionalidad.

#### ✅ ALTERNATIVAS DISPONIBLES:

**⚠️ IMPORTANTE: Tampoco existe DELETE para meals**

La única opción disponible actualmente es trabajar con los ingredientes o usar la IA para regenerar el contenido de las comidas.

**Opción 2: Actualizar solo los ingredientes**
```javascript
// Si solo necesitas cambiar ingredientes, puedes:
// 1. Eliminar ingredientes existentes
DELETE /api/v1/nutrition/ingredients/{ingredient_id}

// 2. Agregar nuevos ingredientes
POST /api/v1/nutrition/meals/{meal_id}/ingredients
```

**Opción 3: Usar IA para regenerar ingredientes**
```javascript
// Generar nuevos ingredientes con IA (reemplaza los existentes)
POST /api/v1/nutrition/meals/{meal_id}/ingredients/ai-generate

// Luego aplicarlos
POST /api/v1/nutrition/meals/{meal_id}/ingredients/ai-apply
```

#### 📝 SOLUCIÓN TEMPORAL EN FRONTEND:
```javascript
// ❌ ANTES (NO FUNCIONA)
async function updateMeal(mealId, updatedData) {
  const response = await fetch(
    `${API_URL}/api/v1/nutrition/meals/${mealId}`,
    {
      method: 'PUT',  // NO EXISTE
      // ...
    }
  );
}

// ⚠️ REALIDAD ACTUAL
// NO existe PUT para actualizar comidas
// NO existe DELETE para eliminar comidas
// Solo puedes:
// 1. Crear nuevas comidas
// 2. Modificar ingredientes
// 3. Usar IA para regenerar contenido

// ✅ WORKAROUND: Deshabilitar edición de comidas
function MealEditButton({ meal }) {
  return (
    <button
      disabled
      title="Edición de comidas no disponible temporalmente"
      className="btn-disabled"
    >
      Editar (No disponible)
    </button>
  );
}

// ✅ ALTERNATIVA: Solo permitir regenerar con IA
async function regenerateMealWithAI(mealId, preferences) {
  try {
    // Generar nuevos ingredientes con IA
    const generateResponse = await fetch(
      `${API_URL}/api/v1/nutrition/meals/${mealId}/ingredients/ai-generate`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          dietary_restrictions: preferences.restrictions,
          calories_target: preferences.calories,
          // ...
        })
      }
    );

    const generatedData = await generateResponse.json();

    // Aplicar los ingredientes generados
    const applyResponse = await fetch(
      `${API_URL}/api/v1/nutrition/meals/${mealId}/ingredients/ai-apply`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          ingredients: generatedData.ingredients,
          recipe: generatedData.recipe
        })
      }
    );

    return applyResponse.json();
  } catch (error) {
    console.error('Error regenerando comida con IA:', error);
    throw error;
  }
}
```

#### 🎯 RECOMENDACIÓN CRÍTICA:
**DESHABILITEN COMPLETAMENTE LA EDICIÓN DE COMIDAS** en el UI. El backend NO tiene endpoints para:
- ❌ GET /meals/{id} (obtener una comida específica)
- ❌ PUT /meals/{id} (actualizar) comidas
- ❌ DELETE /meals/{id} (eliminar) comidas

Solo pueden:
- ✅ Crear nuevas comidas
- ✅ Modificar ingredientes individuales
- ✅ Regenerar con IA

**ACCIÓN URGENTE:** Notifiquen al equipo de backend que necesitan implementar estos endpoints CRUD básicos.

📖 **VER GUÍA COMPLETA DE ENDPOINTS ALTERNATIVOS:** [NUTRITION_ENDPOINTS_ALTERNATIVES.md](./NUTRITION_ENDPOINTS_ALTERNATIVES.md)

---

### Problema 2: URL Incorrecta para Agregar Comidas a Daily Plans

#### ❌ LO QUE ESTÁN HACIENDO MAL:
```javascript
// INCORRECTO - Este endpoint NO existe
POST /api/v1/nutrition/daily-plans/10/meals
```

#### ✅ FORMA CORRECTA:
```javascript
// CORRECTO - Usar "days" en lugar de "daily-plans"
POST /api/v1/nutrition/days/10/meals
```

#### Ejemplo de Implementación Correcta:
```javascript
// ❌ ANTES (MAL)
async function addMealToDailyPlan(dailyPlanId, mealData) {
  const response = await fetch(
    `${API_URL}/api/v1/nutrition/daily-plans/${dailyPlanId}/meals`,  // WRONG!
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
        'X-Gym-Id': gymId
      },
      body: JSON.stringify(mealData)
    }
  );
}

// ✅ DESPUÉS (BIEN)
async function addMealToDailyPlan(dailyPlanId, mealData) {
  const response = await fetch(
    `${API_URL}/api/v1/nutrition/days/${dailyPlanId}/meals`,  // CORRECT!
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
        'X-Gym-Id': gymId
      },
      body: JSON.stringify(mealData)
    }
  );
}
```

#### Payload Esperado:
```json
{
  "name": "Desayuno Energético",
  "meal_type": "breakfast",  // breakfast, lunch, dinner, snack, other
  "recipe_instructions": "1. Preparar avena con leche...",
  "target_calories": 400,
  "target_proteins": 20,
  "target_carbs": 60,
  "target_fats": 10,
  "preparation_time": "15 min",
  "order": 1
}
```

---

### Problema 3: Activity Feed No Habilitado para el Gimnasio

#### ❌ LO QUE ESTÁN HACIENDO MAL:
```javascript
// La app móvil está llamando este endpoint cada 30 segundos
GET /api/v1/activity-feed/realtime
// Retorna 404 porque el módulo no está habilitado para el gym
```

#### 🔍 CAUSA RAÍZ:
El módulo `activity_feed` NO está habilitado para el gimnasio con ID 4. Este es un módulo premium que debe activarse por gimnasio.

#### ✅ SOLUCIÓN INMEDIATA:

**Opción 1: Deshabilitar temporalmente en la app**
```swift
// iOS - En tu ActivityFeedService
func fetchRealtimeStats() {
    // COMENTAR TEMPORALMENTE hasta que el módulo esté activo
    // guard let gymId = currentGymId else { return }
    //
    // networkClient.get("/api/v1/activity-feed/realtime") { result in
    //     // ...
    // }

    // Retornar datos mock mientras tanto
    return MockActivityData.realtimeStats()
}
```

**Opción 2: Verificar si el módulo está disponible primero**
```javascript
// JavaScript/React Native
async function checkActivityFeedAvailable() {
  try {
    const response = await fetch(
      `${API_URL}/api/v1/gyms/${gymId}/modules`,
      {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      }
    );

    const modules = await response.json();
    const hasActivityFeed = modules.includes('activity_feed');

    if (!hasActivityFeed) {
      console.log('Activity Feed no disponible para este gym');
      // No hacer polling del endpoint
      return false;
    }

    return true;
  } catch (error) {
    return false;
  }
}

// Usar así:
async function startRealtimePolling() {
  const isAvailable = await checkActivityFeedAvailable();

  if (!isAvailable) {
    // Mostrar UI alternativa o mensaje
    showMessage('Feed de actividad no disponible en tu plan actual');
    return;
  }

  // Solo hacer polling si está disponible
  setInterval(() => {
    fetchRealtimeStats();
  }, 30000);
}
```

---

## 📋 LISTA COMPLETA DE ENDPOINTS CORRECTOS DE NUTRITION

### Planes Nutricionales
```javascript
// Listar planes
GET /api/v1/nutrition/plans

// Obtener un plan específico
GET /api/v1/nutrition/plans/{plan_id}

// Crear nuevo plan
POST /api/v1/nutrition/plans

// Actualizar plan
PUT /api/v1/nutrition/plans/{plan_id}

// Archivar plan
POST /api/v1/nutrition/plans/{plan_id}/archive

// Seguir/Unirse a un plan
POST /api/v1/nutrition/plans/{plan_id}/follow

// Dejar de seguir
DELETE /api/v1/nutrition/plans/{plan_id}/unfollow
```

### Daily Plans (Días del Plan)
```javascript
// Listar días de un plan
GET /api/v1/nutrition/plans/{plan_id}/days

// Obtener un día específico
GET /api/v1/nutrition/days/{daily_plan_id}

// Crear nuevo día
POST /api/v1/nutrition/plans/{plan_id}/days

// ⚠️ IMPORTANTE: Para agregar comidas a un día
POST /api/v1/nutrition/days/{daily_plan_id}/meals  // NO "daily-plans"!
```

### Comidas (Meals)
```javascript
// ⚠️ IMPORTANTE: NO existen endpoints CRUD básicos para meals
// NO existe: GET /api/v1/nutrition/meals/{meal_id}
// NO existe: PUT /api/v1/nutrition/meals/{meal_id}
// NO existe: DELETE /api/v1/nutrition/meals/{meal_id}

// Solo existen estos endpoints:
// Marcar comida como completada
POST /api/v1/nutrition/meals/{meal_id}/complete

// Agregar ingredientes
POST /api/v1/nutrition/meals/{meal_id}/ingredients

// Generar ingredientes con IA
POST /api/v1/nutrition/meals/{meal_id}/ingredients/ai-generate

// Aplicar ingredientes generados
POST /api/v1/nutrition/meals/{meal_id}/ingredients/ai-apply
```

### Dashboard y Analytics
```javascript
// Mi dashboard de nutrición
GET /api/v1/nutrition/dashboard

// Plan de hoy
GET /api/v1/nutrition/today

// Analytics
GET /api/v1/nutrition/analytics
```

---

## 🔧 CAMBIOS NECESARIOS EN EL CÓDIGO

### Frontend Web (React)
```javascript
// src/services/nutritionService.js

const API_ENDPOINTS = {
  // ❌ ELIMINAR ESTA LÍNEA
  // ADD_MEAL: '/api/v1/nutrition/daily-plans/:id/meals',

  // ✅ USAR ESTA EN SU LUGAR
  ADD_MEAL: '/api/v1/nutrition/days/:id/meals',

  // Resto de endpoints...
};
```

### App Móvil (React Native / Swift)
```javascript
// services/ActivityFeedService.js

class ActivityFeedService {
  constructor() {
    this.pollingInterval = null;
    this.isModuleAvailable = false;
  }

  async initialize() {
    // Verificar disponibilidad antes de empezar polling
    this.isModuleAvailable = await this.checkModuleAvailability();

    if (this.isModuleAvailable) {
      this.startPolling();
    }
  }

  async checkModuleAvailability() {
    // Implementar verificación de módulo
    // Retornar false por ahora para gym_id=4
    return false;
  }

  startPolling() {
    if (!this.isModuleAvailable) return;

    this.pollingInterval = setInterval(() => {
      this.fetchRealtimeStats();
    }, 30000);
  }

  stopPolling() {
    if (this.pollingInterval) {
      clearInterval(this.pollingInterval);
      this.pollingInterval = null;
    }
  }
}
```

---

## ⚡ ACCIONES INMEDIATAS REQUERIDAS

### 1. Para el Equipo de Frontend Web:
- [ ] **CRÍTICO**: Deshabilitar edición de comidas o implementar workaround de eliminar/recrear
- [ ] Cambiar la URL de `daily-plans` a `days` en el servicio de nutrición
- [ ] Actualizar cualquier referencia a `/daily-plans/` en el código
- [ ] Remover llamadas a `PUT /api/v1/nutrition/meals/{id}`
- [ ] Probar la creación de comidas con el endpoint correcto

### 2. Para el Equipo de App Móvil:
- [ ] Detener el polling de `/activity-feed/realtime` para gym_id=4
- [ ] Implementar verificación de módulos disponibles
- [ ] Agregar manejo de errores 404 sin mostrar alertas al usuario
- [ ] Considerar implementar un backoff exponencial en lugar de polling fijo

### 3. Para Ambos Equipos:
- [ ] Revisar todos los endpoints en uso contra esta documentación
- [ ] Implementar manejo de errores más robusto para 404s
- [ ] No asumir que todos los módulos están disponibles

---

## 🎯 TIPS DE DEBUGGING

### Cómo verificar si un endpoint existe:
```bash
# Desde terminal
curl -X GET "https://gymapi-eh6m.onrender.com/api/v1/docs" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Buscar el endpoint en la documentación Swagger
```

### Cómo verificar módulos habilitados:
```javascript
// Este endpoint te dirá qué módulos están activos
GET /api/v1/gyms/{gym_id}

// Respuesta incluye:
{
  "id": 4,
  "name": "Gym Name",
  "enabled_modules": ["nutrition", "chat", "billing"],  // activity_feed NO está aquí
  // ...
}
```

---

## 📞 CONTACTO PARA DUDAS

Si tienen dudas sobre algún endpoint:
1. Revisar la documentación Swagger en `/api/v1/docs`
2. Verificar este documento actualizado
3. Probar directamente con Postman/Insomnia antes de implementar

---

**IMPORTANTE:** Estos cambios deben implementarse INMEDIATAMENTE para evitar errores 404 en producción que están afectando la experiencia del usuario.

*Documento creado: 26 de Diciembre 2024*
*Última actualización: 27 de Diciembre 2024 - CRÍTICO: NO existe PUT ni DELETE para meals*
*Por: Claude Code Assistant*