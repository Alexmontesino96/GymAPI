# Optimizacion GET /nutrition/plans - Eliminacion de include_details

## Problema

El endpoint `GET /api/v1/nutrition/plans?include_details=true` tardaba **15.6 segundos** en produccion con solo 20 planes.

### Causa raiz

Cuando `include_details=true`, el endpoint cargaba `daily_plans` y `meals` con eager loading pero **NO cargaba `ingredients`**. Esto causaba un problema N+1:

- Eager loading: 2-3 queries (~300ms)
- Pydantic serializa la respuesta y accede a `meal.ingredients` para cada comida
- Como `ingredients` no fue eager-loaded, SQLAlchemy dispara un **lazy load** (query individual) por cada comida
- 20 planes x 3 dias x ~5 comidas = ~300 queries individuales a la DB remota
- ~300 queries x ~50ms cada una = **~15 segundos**

### Impacto adicional

La operacion era sincrona y bloqueaba el event loop de FastAPI, impidiendo que otros requests se procesaran durante esos 15 segundos. Los cron jobs de APScheduler tambien se perdian.

---

## Solucion aplicada

### Cambio de arquitectura

El endpoint `GET /plans` ahora **solo retorna datos de resumen** (metadata del plan). Para ver el detalle completo (dias, comidas, ingredientes), el frontend debe usar `GET /plans/{plan_id}`.

| Endpoint | Proposito | Tiempo esperado |
|---|---|---|
| `GET /plans` | Listado/cards de planes (resumen) | ~200-300ms |
| `GET /plans/{plan_id}` | Detalle completo de un plan | ~300-500ms |

### Archivos modificados

1. **`app/api/v1/endpoints/nutrition.py`**
   - Eliminados parametros `include_details` y `max_days` del endpoint `GET /plans`
   - Simplificado docstring

2. **`app/services/nutrition_plan_service.py`**
   - Eliminados parametros `include_details` y `max_days` de `list_nutrition_plans_cached()`
   - Corregido N+1 en `get_nutrition_plan_with_details()`: agregado `selectinload(Meal.ingredients)` al eager loading

3. **`app/repositories/nutrition.py`**
   - Eliminado metodo `get_public_plans_with_details()` (ya no se necesita)
   - Simplificado `get_public_plans_with_total_cached()`: eliminados parametros `include_details` y `max_days`

4. **`app/schemas/nutrition.py`**
   - Actualizado comentario en campo `daily_plans`

### Fix adicional: GET /plans/{plan_id}

El endpoint de detalle individual tenia el mismo bug N+1 (no cargaba ingredients). Se agrego `selectinload(Meal.ingredients)` al eager loading, reduciendo el tiempo de ~1.2s a ~300-500ms.

---

## Respuesta del API para el frontend

### GET /api/v1/nutrition/plans (LISTADO)

**Parametros disponibles:**
- `page` (default: 1)
- `per_page` (default: 20, max: 100)
- `goal` - Filtro por objetivo (weight_loss, muscle_gain, bulk, cut, etc.)
- `difficulty_level` - Filtro por dificultad (beginner, intermediate, advanced)
- `budget_level` - Filtro por presupuesto (economic, medium, premium)
- `dietary_restrictions` - Filtro por restricciones (vegetarian, vegan, etc.)
- `search_query` - Busqueda por titulo/descripcion
- `creator_id` - Filtro por creador
- `plan_type` - Filtro por tipo (template, live, archived)
- `status` - Filtro por estado (not_started, running, finished)
- `is_live_active` - Solo planes live activos

**Respuesta:**

```json
{
  "plans": [
    {
      "id": 40,
      "title": "Plan de Volumen",
      "description": "Plan para ganar masa muscular...",
      "goal": "bulk",
      "difficulty_level": "beginner",
      "budget_level": "medium",
      "dietary_restrictions": "none",
      "duration_days": 7,
      "is_recurring": false,
      "target_calories": 2100,
      "target_protein_g": 150.0,
      "target_carbs_g": 230.0,
      "target_fat_g": 60.0,
      "is_public": true,
      "tags": ["volumen", "principiante"],
      "plan_type": "template",
      "live_start_date": null,
      "live_end_date": null,
      "is_live_active": false,
      "live_participants_count": 0,
      "creator_id": 10,
      "gym_id": 4,
      "is_active": true,
      "created_at": "2026-03-08T19:00:44",
      "updated_at": "2026-03-08T19:00:44",
      "current_day": null,
      "status": null,
      "days_until_start": null,
      "total_followers": 5
    }
  ],
  "total": 24,
  "page": 1,
  "per_page": 20,
  "has_next": true,
  "has_prev": false
}
```

**Campos clave para cards/listados:**
- `id` - Para navegar al detalle
- `title`, `description` - Informacion principal
- `goal`, `difficulty_level`, `budget_level` - Badges/tags
- `plan_type` - Tipo de plan (template/live/archived)
- `duration_days` - Duracion
- `target_calories` - Calorias objetivo
- `total_followers` - Popularidad
- `status`, `current_day` - Estado actual (solo planes LIVE)
- `created_at` - Fecha de creacion

**NO incluye:** `daily_plans`, `meals`, `ingredients` (usar GET /plans/{id} para eso)

---

### GET /api/v1/nutrition/plans/{plan_id} (DETALLE)

**Respuesta:** Todo lo anterior + detalle completo

```json
{
  "id": 40,
  "title": "Plan de Volumen",
  "goal": "bulk",
  "plan_type": "template",
  "duration_days": 7,
  "target_calories": 2100,
  "daily_plans": [
    {
      "id": 101,
      "day_number": 1,
      "total_calories": 2000,
      "total_protein_g": 155.0,
      "total_carbs_g": 220.0,
      "total_fat_g": 58.0,
      "meals": [
        {
          "id": 501,
          "meal_type": "breakfast",
          "name": "Avena con Frutas y Proteina",
          "calories": 400,
          "protein_g": 30.0,
          "carbs_g": 50.0,
          "fat_g": 10.0,
          "preparation_time_minutes": 10,
          "cooking_instructions": "Cocinar la avena...",
          "ingredients": [
            {
              "id": 1001,
              "name": "avena",
              "quantity": 80,
              "unit": "g",
              "is_optional": false,
              "alternatives": ["quinoa en hojuelas"]
            },
            {
              "id": 1002,
              "name": "proteina en polvo",
              "quantity": 30,
              "unit": "g",
              "is_optional": false
            }
          ]
        }
      ]
    }
  ],
  "creator_name": "Alex Montesino",
  "is_followed_by_user": true
}
```

---

## Flujo recomendado en el frontend

1. **Pantalla de listado:** `GET /plans` → Mostrar cards con info basica
2. **Usuario toca un plan:** `GET /plans/{id}` → Mostrar detalle completo con dias, comidas e ingredientes
3. **Filtros:** Usar query params de `GET /plans` (goal, plan_type, search_query, etc.)

---

## Metricas de performance

| Escenario | Antes | Despues | Mejora |
|---|---|---|---|
| GET /plans (listado) | 15,571ms | ~300ms | **98%** |
| GET /plans/{id} (detalle) | 1,226ms | ~400ms | **67%** |
| Event loop bloqueado | 14s+ | 0s | Eliminado |
| Queries a DB (listado) | ~302 | ~2 | **99%** |
