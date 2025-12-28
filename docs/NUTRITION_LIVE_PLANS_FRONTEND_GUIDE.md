# 📱 Guía Frontend: Planes Nutricionales LIVE
*Última actualización: 26 de Diciembre 2024*

## 🎯 ¿Qué son los Planes LIVE?

Los planes LIVE son **planes nutricionales grupales sincronizados** donde todos los participantes están en el mismo día al mismo tiempo, como una clase grupal de nutrición.

### Diferencias entre tipos de planes:

| Característica | TEMPLATE | LIVE | ARCHIVED |
|---------------|----------|------|----------|
| **Propósito** | Plan individual personalizable | Plan grupal sincronizado | Historial/Referencia |
| **Sincronización** | Cada usuario a su ritmo | Todos en el mismo día | N/A |
| **Fecha inicio** | Cuando el usuario quiera | Fecha fija para todos | N/A |
| **Participantes** | Individual | Múltiples simultáneos | Solo lectura |
| **Notificaciones** | Personalizadas | Grupales sincronizadas | Sin notificaciones |
| **Progreso** | Individual | Compartido | N/A |

## 🔄 Cómo funciona la sincronización LIVE

### Concepto clave: `live_start_date`
```typescript
// El día actual se calcula automáticamente basado en live_start_date
const currentDay = calculateDaysSince(plan.live_start_date) + 1;

// Ejemplo:
// Si live_start_date = "2024-12-20"
// Y hoy es = "2024-12-26"
// Entonces currentDay = 7 (todos están en el día 7)
```

### Flujo de sincronización:
```
Día 1 (20 Dic)    Día 2 (21 Dic)    ...    Día 7 (26 Dic) ← HOY
     ↓                 ↓                          ↓
[Desayuno]        [Desayuno]              [Desayuno] ← Activo
[Almuerzo]        [Almuerzo]              [Almuerzo] ← Activo
[Cena]            [Cena]                  [Cena]     ← Activo

TODOS los participantes ven el MISMO día 7
```

## 📍 Endpoints principales para planes LIVE

### 1. Obtener planes LIVE disponibles
```typescript
GET /api/v1/nutrition/plans/live
```

**Response:**
```json
{
  "plans": [
    {
      "id": 456,
      "name": "Reto Detox 21 Días",
      "plan_type": "LIVE",
      "duration_days": 21,
      "is_live_active": true,
      "live_start_date": "2024-12-20T00:00:00",
      "live_participants_count": 45,
      "current_day": 7,  // Calculado en backend
      "days_remaining": 14,
      "created_by": {
        "name": "Coach María",
        "role": "trainer"
      }
    }
  ]
}
```

### 2. Unirse a un plan LIVE
```typescript
POST /api/v1/nutrition/plans/{plan_id}/follow

// Solo se puede unir a planes LIVE activos
// Verificación automática en backend
```

### 3. Obtener el día actual del plan LIVE
```typescript
GET /api/v1/nutrition/plans/{plan_id}/current-day
```

**Response:**
```json
{
  "plan_id": 456,
  "current_day": 7,
  "total_days": 21,
  "date_for_current_day": "2024-12-26",
  "daily_plan": {
    "day_number": 7,
    "day_name": "Día 7 - Energía",
    "meals": [
      {
        "id": 789,
        "name": "Desayuno Energético",
        "meal_type": "breakfast",
        "target_calories": 400,
        "ingredients": [...],
        "recipe_instructions": "...",
        "is_completed": false
      }
    ],
    "total_calories_goal": 1800
  }
}
```

### 4. Dashboard LIVE para el usuario
```typescript
GET /api/v1/nutrition/my-live-plan
```

**Response:**
```json
{
  "has_active_live_plan": true,
  "plan": {
    "id": 456,
    "name": "Reto Detox 21 Días",
    "current_day": 7,
    "progress_percentage": 33.3,
    "todays_meals": [...],
    "completed_meals_today": 1,
    "total_meals_today": 5,
    "participants": {
      "total": 45,
      "active_today": 38,
      "top_performers": [...]
    }
  }
}
```

## 💻 Implementación en React

### Hook para Planes LIVE
```tsx
// hooks/useLiveNutritionPlan.ts
import { useState, useEffect } from 'react';
import { NutritionAPIService } from '../services/nutritionAPI';

export function useLiveNutritionPlan(planId?: number) {
  const [livePlan, setLivePlan] = useState(null);
  const [currentDay, setCurrentDay] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [participants, setParticipants] = useState([]);

  useEffect(() => {
    if (!planId) return;

    const fetchLiveData = async () => {
      try {
        // Obtener día actual del plan
        const dayData = await NutritionAPIService.getCurrentDay(planId);
        setCurrentDay(dayData);

        // Obtener participantes activos
        const participantData = await NutritionAPIService.getLiveParticipants(planId);
        setParticipants(participantData);

        setIsLoading(false);
      } catch (error) {
        console.error('Error fetching live plan:', error);
        setIsLoading(false);
      }
    };

    // Fetch inicial
    fetchLiveData();

    // Actualizar cada 5 minutos para ver nuevos participantes
    const interval = setInterval(fetchLiveData, 5 * 60 * 1000);

    return () => clearInterval(interval);
  }, [planId]);

  const joinLivePlan = async (planId: number) => {
    try {
      await NutritionAPIService.followPlan(planId);
      // Refrescar datos
      window.location.reload();
    } catch (error) {
      if (error.response?.status === 400) {
        alert('Este plan LIVE ya comenzó. No puedes unirte después del día 3.');
      }
    }
  };

  const completeMeal = async (mealId: number) => {
    try {
      await NutritionAPIService.completeMeal(mealId);
      // Actualizar UI
      setCurrentDay(prev => ({
        ...prev,
        daily_plan: {
          ...prev.daily_plan,
          meals: prev.daily_plan.meals.map(meal =>
            meal.id === mealId
              ? { ...meal, is_completed: true }
              : meal
          )
        }
      }));
    } catch (error) {
      console.error('Error completing meal:', error);
    }
  };

  return {
    livePlan,
    currentDay,
    participants,
    isLoading,
    joinLivePlan,
    completeMeal
  };
}
```

### Componente de Plan LIVE
```tsx
// components/LiveNutritionPlan.tsx
import React from 'react';
import { useLiveNutritionPlan } from '../hooks/useLiveNutritionPlan';
import { MealCard } from './MealCard';
import { ParticipantsList } from './ParticipantsList';

export function LiveNutritionPlan({ planId }) {
  const {
    currentDay,
    participants,
    isLoading,
    completeMeal
  } = useLiveNutritionPlan(planId);

  if (isLoading) return <div>Cargando plan LIVE...</div>;
  if (!currentDay) return <div>No hay plan LIVE activo</div>;

  return (
    <div className="live-plan-container">
      {/* Header con sincronización */}
      <div className="sync-header">
        <h2>🔴 PLAN EN VIVO - Día {currentDay.current_day} de {currentDay.total_days}</h2>
        <div className="sync-indicator">
          <span className="pulse"></span>
          <span>{participants.length} participantes activos</span>
        </div>
      </div>

      {/* Progreso del día */}
      <div className="day-progress">
        <h3>{currentDay.daily_plan.day_name}</h3>
        <div className="progress-bar">
          <div
            className="progress-fill"
            style={{
              width: `${(currentDay.current_day / currentDay.total_days) * 100}%`
            }}
          />
        </div>
      </div>

      {/* Comidas del día actual */}
      <div className="meals-grid">
        {currentDay.daily_plan.meals.map(meal => (
          <MealCard
            key={meal.id}
            meal={meal}
            onComplete={() => completeMeal(meal.id)}
            isLive={true}
            showTimer={!meal.is_completed}
          />
        ))}
      </div>

      {/* Participantes activos */}
      <div className="participants-section">
        <h4>🏃‍♀️ Compañeros en este reto</h4>
        <ParticipantsList
          participants={participants}
          currentDay={currentDay.current_day}
        />
      </div>

      {/* Motivación grupal */}
      <div className="motivation-box">
        <p>💪 ¡{participants.filter(p => p.completed_today).length} personas
           ya completaron sus comidas de hoy!</p>
      </div>
    </div>
  );
}
```

### Componente de Lista de Planes LIVE
```tsx
// components/LivePlansList.tsx
import React, { useState, useEffect } from 'react';
import { NutritionAPIService } from '../services/nutritionAPI';

export function LivePlansList() {
  const [livePlans, setLivePlans] = useState([]);
  const [userPlan, setUserPlan] = useState(null);

  useEffect(() => {
    fetchLivePlans();
    checkUserPlan();
  }, []);

  const fetchLivePlans = async () => {
    const plans = await NutritionAPIService.getLivePlans();
    setLivePlans(plans.filter(p => p.is_live_active));
  };

  const checkUserPlan = async () => {
    const myPlan = await NutritionAPIService.getMyLivePlan();
    setUserPlan(myPlan);
  };

  const joinPlan = async (planId) => {
    try {
      await NutritionAPIService.followPlan(planId);
      alert('¡Te has unido al plan LIVE exitosamente!');
      window.location.href = `/nutrition/live/${planId}`;
    } catch (error) {
      if (error.response?.data?.detail) {
        alert(error.response.data.detail);
      }
    }
  };

  // Si el usuario ya tiene un plan LIVE
  if (userPlan) {
    return (
      <div className="active-live-plan">
        <h2>Tu Plan LIVE Activo</h2>
        <div className="plan-card active">
          <h3>{userPlan.name}</h3>
          <p>Día {userPlan.current_day} de {userPlan.duration_days}</p>
          <button
            onClick={() => window.location.href = `/nutrition/live/${userPlan.id}`}
          >
            Continuar Plan
          </button>
        </div>
      </div>
    );
  }

  // Mostrar planes disponibles
  return (
    <div className="live-plans-list">
      <h2>🔴 Planes LIVE Disponibles</h2>
      <p>Únete a un reto grupal y avanza junto a otros miembros</p>

      <div className="plans-grid">
        {livePlans.map(plan => (
          <div key={plan.id} className="plan-card">
            <div className="live-badge">EN VIVO</div>
            <h3>{plan.name}</h3>
            <div className="plan-details">
              <p>📅 Duración: {plan.duration_days} días</p>
              <p>👥 {plan.live_participants_count} participantes</p>
              <p>📍 Día actual: {plan.current_day}</p>
              <p>🏁 Comienza: {new Date(plan.live_start_date).toLocaleDateString()}</p>
            </div>

            {plan.current_day <= 3 ? (
              <button
                className="join-button"
                onClick={() => joinPlan(plan.id)}
              >
                Unirse al Reto
              </button>
            ) : (
              <button disabled className="join-button disabled">
                Ya comenzó (día {plan.current_day})
              </button>
            )}
          </div>
        ))}
      </div>

      {livePlans.length === 0 && (
        <p className="no-plans">No hay planes LIVE activos en este momento</p>
      )}
    </div>
  );
}
```

## 📊 Diferencias en el UI: TEMPLATE vs LIVE

### Plan TEMPLATE (Individual)
```tsx
<div className="template-plan">
  <h2>Mi Plan Personal</h2>
  <button onClick={nextDay}>Siguiente Día →</button>
  <button onClick={previousDay}>← Día Anterior</button>
  <p>Progreso personal: Día {userDay} de {totalDays}</p>
</div>
```

### Plan LIVE (Grupal)
```tsx
<div className="live-plan">
  <h2>🔴 PLAN GRUPAL EN VIVO</h2>
  <div className="sync-status">
    <span className="live-indicator">●</span>
    TODOS en el Día {currentDay}
  </div>
  <p>No puedes cambiar de día - sincronizado con el grupo</p>
  <ParticipantsList />
</div>
```

## 🔔 Notificaciones en Planes LIVE

Los planes LIVE tienen notificaciones especiales sincronizadas:

### Tipos de notificaciones LIVE:
1. **Recordatorio de comidas** (3 veces al día)
   - Desayuno: 8:00 AM
   - Almuerzo: 1:00 PM
   - Cena: 7:00 PM

2. **Motivación grupal** (1 vez al día)
   - "¡El 65% del grupo ya completó el desayuno!"

3. **Nuevo día disponible** (medianoche)
   - "¡Día 8 del reto ya disponible!"

### Implementar receptor de notificaciones:
```tsx
// Configurar OneSignal para recibir notificaciones LIVE
OneSignal.addEventListener('received', (notification) => {
  if (notification.data.type === 'live_meal_reminder') {
    // Actualizar UI con recordatorio
    showMealReminder(notification.data.meal_type);
  }

  if (notification.data.type === 'live_group_progress') {
    // Mostrar progreso del grupo
    updateGroupProgress(notification.data.stats);
  }
});
```

## 🎯 Reglas de negocio importantes

### 1. **Unirse a un plan LIVE**
- Solo se puede unir hasta el día 3
- No se puede unir a múltiples planes LIVE simultáneamente
- Una vez unido, no se puede "pausar" - el plan continúa

### 2. **Progreso en LIVE**
- Todos avanzan automáticamente cada día
- No se puede volver a días anteriores
- Los días futuros están bloqueados

### 3. **Completar comidas**
- Se puede completar comidas del día actual únicamente
- Las comidas de días pasados quedan como "no completadas"
- El progreso se comparte con otros participantes

### 4. **Finalización**
- Al terminar los días del plan, pasa automáticamente a ARCHIVED
- Los participantes reciben certificado de completación
- Se mantiene el historial pero no se puede modificar

## 📱 Estados del UI según el tipo de plan

```tsx
// Helper para determinar qué mostrar
function getNutritionPlanUI(plan) {
  switch(plan.plan_type) {
    case 'TEMPLATE':
      return {
        showDayNavigation: true,      // ← → para cambiar días
        showParticipants: false,
        showSyncStatus: false,
        allowDaySelection: true,
        title: 'Mi Plan Personal'
      };

    case 'LIVE':
      return {
        showDayNavigation: false,     // Sin navegación
        showParticipants: true,       // Lista de participantes
        showSyncStatus: true,         // Indicador "EN VIVO"
        allowDaySelection: false,     // Día fijo para todos
        title: '🔴 Plan Grupal LIVE'
      };

    case 'ARCHIVED':
      return {
        showDayNavigation: true,      // Ver historial
        showParticipants: false,
        showSyncStatus: false,
        allowDaySelection: true,
        readOnly: true,               // Solo lectura
        title: '📚 Plan Archivado'
      };
  }
}
```

## 🚀 Quick Start para Frontend

### 1. Instalar servicio de nutrición
```bash
# Copiar los archivos TypeScript del docs/
cp docs/nutrition-ai-types.ts src/types/
cp docs/nutrition-ai-service-example.ts src/services/
```

### 2. Configurar el servicio
```tsx
// src/services/nutritionAPI.ts
import NutritionAIService from './nutrition-ai-service-example';

const nutritionService = new NutritionAIService({
  baseURL: process.env.REACT_APP_API_URL,
  token: getUserToken(),
  gymId: getCurrentGymId()
});

export default nutritionService;
```

### 3. Implementar vista de planes LIVE
```tsx
// src/pages/NutritionLive.tsx
import { LivePlansList } from '../components/LivePlansList';
import { LiveNutritionPlan } from '../components/LiveNutritionPlan';

export function NutritionLivePage() {
  const { planId } = useParams();

  if (planId) {
    return <LiveNutritionPlan planId={parseInt(planId)} />;
  }

  return <LivePlansList />;
}
```

### 4. Agregar rutas
```tsx
// App.tsx
<Route path="/nutrition/live" element={<NutritionLivePage />} />
<Route path="/nutrition/live/:planId" element={<NutritionLivePage />} />
```

## ❓ FAQ Frontend

### ¿Cómo sé si un usuario está en un plan LIVE?
```typescript
GET /api/v1/nutrition/my-live-plan
// Si has_active_live_plan = true, está en un plan LIVE
```

### ¿Puedo mostrar días futuros en un plan LIVE?
No, solo el día actual. Los días futuros retornan 403.

### ¿Cómo manejo el cambio de día en LIVE?
Es automático a medianoche. Implementa polling o WebSocket para actualización en tiempo real.

### ¿Qué pasa si un usuario se une tarde a un plan LIVE?
Ve el día actual como todos. Los días anteriores aparecen como "no completados".

### ¿Puedo personalizar las horas de notificación en LIVE?
No, las notificaciones LIVE son grupales y tienen horarios fijos para todos.

## 📞 Soporte

Para dudas adicionales sobre la implementación de planes LIVE:
- Revisar los tests en `tests/nutrition/`
- Documentación de API en `/api/v1/docs`
- Logs de notificaciones en `nutrition_notifications.log`

---

*Documentación creada por Claude Code Assistant*
*26 de Diciembre 2024*