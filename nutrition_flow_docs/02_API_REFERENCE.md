# 📖 API Reference - Sistema de Nutrición

## 📋 Índice de Endpoints

### [Gestión de Planes](#gestión-de-planes)
- [GET /plans](#get-plans) - Listar planes
- [POST /plans](#post-plans) - Crear plan
- [GET /plans/{id}](#get-plansid) - Obtener plan
- [PUT /plans/{id}](#put-plansid) - Actualizar plan
- [DELETE /plans/{id}](#delete-plansid) - Eliminar plan
- [POST /plans/{id}/follow](#post-plansidfollow) - Seguir plan
- [DELETE /plans/{id}/follow](#delete-plansidfollow) - Dejar de seguir

### [Gestión de Comidas](#gestión-de-comidas)
- [GET /meals](#get-meals) - Listar comidas
- [POST /days/{id}/meals](#post-daysidmeals) - Crear comida
- [PUT /meals/{id}](#put-mealsid) - Actualizar comida
- [DELETE /meals/{id}](#delete-mealsid) - Eliminar comida
- [POST /meals/{id}/complete](#post-mealsidcomplete) - Completar comida
- [POST /meals/{id}/ingredients](#post-mealsidin

) - Agregar ingredientes

### [Generación con IA](#generación-con-ia)
- [POST /meals/{id}/ingredients/ai-generate](#post-mealsidingredients-ai-generate) - Generar con IA
- [POST /meals/{id}/ingredients/ai-apply](#post-mealsidingredients-ai-apply) - Aplicar IA

### [Seguridad Médica](#seguridad-médica)
- [POST /safety-check](#post-safety-check) - Evaluación de seguridad
- [GET /safety-check/validate/{id}](#get-safety-checkvalidateid) - Validar screening

### [Dashboard y Analytics](#dashboard-y-analytics)
- [GET /plans/categorized](#get-planscategorized) - Planes categorizados
- [GET /my-plans](#get-my-plans) - Mis planes activos
- [GET /my-plans/today](#get-my-planstoday) - Plan del día
- [GET /my-progress](#get-my-progress) - Mi progreso
- [GET /plans/{id}/analytics](#get-plansidanalytics) - Analytics del plan

---

## Gestión de Planes

### GET /plans
**Listar todos los planes del gimnasio**

#### Request
```http
GET /api/v1/nutrition/plans?page=1&per_page=20&is_public=true&plan_type=template
```

#### Query Parameters
| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| page | int | No | Página actual (default: 1) |
| per_page | int | No | Items por página (default: 20) |
| is_public | bool | No | Filtrar públicos/privados |
| plan_type | string | No | template/live/archived |
| nutrition_goal | string | No | weight_loss/muscle_gain/maintenance |
| difficulty_level | string | No | beginner/intermediate/advanced |
| min_calories | int | No | Calorías mínimas |
| max_calories | int | No | Calorías máximas |

#### Response 200 OK
```json
{
  "plans": [
    {
      "id": 1,
      "title": "Plan Definición Muscular",
      "description": "Plan de 30 días para definición",
      "duration_days": 30,
      "daily_calories": 1800,
      "nutrition_goal": "muscle_gain",
      "difficulty_level": "intermediate",
      "budget_level": "medium",
      "plan_type": "template",
      "is_public": true,
      "creator": {
        "id": 5,
        "full_name": "Carlos Trainer",
        "role": "trainer"
      },
      "total_followers": 45,
      "avg_satisfaction": 4.6,
      "created_at": "2024-01-15T10:00:00Z"
    }
  ],
  "total": 150,
  "page": 1,
  "per_page": 20,
  "has_next": true,
  "has_prev": false
}
```

---

### POST /plans
**Crear nuevo plan nutricional**

⚠️ **Requiere**: Rol trainer o admin

#### Request
```json
{
  "title": "Plan Pérdida de Peso Saludable",
  "description": "Plan equilibrado de 21 días",
  "duration_days": 21,
  "daily_calories": 1500,
  "daily_protein": 120,
  "daily_carbs": 150,
  "daily_fat": 50,
  "nutrition_goal": "weight_loss",
  "difficulty_level": "beginner",
  "budget_level": "low",
  "dietary_restrictions": ["vegetarian", "gluten_free"],
  "plan_type": "template",
  "is_public": false,
  "start_date": null,
  "tags": ["saludable", "vegetariano", "económico"]
}
```

#### Response 201 Created
```json
{
  "id": 123,
  "title": "Plan Pérdida de Peso Saludable",
  "status": "draft",
  "created_at": "2024-12-29T10:30:00Z",
  "daily_plans": []
}
```

#### Errores Comunes
- `403 Forbidden`: Usuario no es trainer/admin
- `400 Bad Request`: Datos inválidos
- `409 Conflict`: Ya existe plan con ese título

---

### GET /plans/{id}
**Obtener detalles completos de un plan**

#### Response 200 OK
```json
{
  "id": 123,
  "title": "Plan Pérdida de Peso Saludable",
  "description": "Plan equilibrado de 21 días",
  "duration_days": 21,
  "daily_calories": 1500,
  "macros": {
    "protein": 120,
    "carbs": 150,
    "fat": 50
  },
  "daily_plans": [
    {
      "id": 1,
      "day_number": 1,
      "date": null,
      "meals": [
        {
          "id": 101,
          "meal_type": "breakfast",
          "name": "Desayuno Proteico",
          "calories": 400,
          "preparation_time": 15,
          "ingredients": [...]
        }
      ]
    }
  ],
  "followers": {
    "total": 45,
    "active": 23,
    "completed": 12,
    "abandoned": 10
  },
  "analytics": {
    "completion_rate": 75.5,
    "avg_satisfaction": 4.6,
    "most_liked_meal": "Desayuno Proteico"
  }
}
```

---

### PUT /plans/{id}
**Actualizar plan existente**

⚠️ **Requiere**: Ser el creador del plan

#### Request
```json
{
  "title": "Plan Pérdida de Peso Saludable v2",
  "is_public": true,
  "daily_calories": 1600
}
```

#### Response 200 OK
```json
{
  "id": 123,
  "title": "Plan Pérdida de Peso Saludable v2",
  "updated_at": "2024-12-29T11:00:00Z"
}
```

---

### DELETE /plans/{id}
**Eliminar plan (soft delete)**

⚠️ **Requiere**: Ser el creador y no tener seguidores activos

#### Response 204 No Content

#### Errores Comunes
- `409 Conflict`: Plan tiene seguidores activos
- `403 Forbidden`: No es el creador

---

### POST /plans/{id}/follow
**Seguir un plan nutricional**

🔒 **Validación de Seguridad**: Si el plan es restrictivo (<1500 cal), requiere safety screening válido

#### Response 200 OK
```json
{
  "id": 456,
  "user_id": 789,
  "plan_id": 123,
  "is_active": true,
  "start_date": "2024-12-29T00:00:00Z",
  "current_day": 1,
  "notifications_enabled": true,
  "notification_time_breakfast": "08:00",
  "notification_time_lunch": "13:00",
  "notification_time_dinner": "20:00"
}
```

#### Errores Comunes
- `403 Forbidden`: Requiere evaluación de seguridad
- `400 Bad Request`: Ya sigues este plan
- `404 Not Found`: Plan no existe

#### Respuesta de Error por Seguridad
```json
{
  "detail": {
    "message": "Este plan requiere una evaluación de seguridad médica",
    "reason": "restrictive_plan",
    "action_required": "safety_screening",
    "endpoint": "/api/v1/nutrition/safety-check",
    "plan_calories": 1200
  }
}
```

---

### DELETE /plans/{id}/follow
**Dejar de seguir un plan**

#### Response 200 OK
```json
{
  "message": "Has dejado de seguir el plan exitosamente",
  "plan_id": 123,
  "days_followed": 15,
  "completion_percentage": 71.4
}
```

---

## Gestión de Comidas

### GET /meals
**Listar comidas de un plan o día**

#### Query Parameters
| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| plan_id | int | No | ID del plan |
| day_id | int | No | ID del día |
| meal_type | string | No | breakfast/lunch/dinner/snack |

#### Response 200 OK
```json
{
  "meals": [
    {
      "id": 101,
      "meal_type": "breakfast",
      "name": "Desayuno Proteico",
      "description": "Rico en proteínas y fibra",
      "calories": 400,
      "protein": 30,
      "carbs": 40,
      "fat": 15,
      "preparation_time": 15,
      "difficulty": "easy",
      "ingredients_count": 8,
      "photo_url": "https://...",
      "is_favorite": false
    }
  ]
}
```

---

### POST /days/{id}/meals
**Crear nueva comida en un día**

⚠️ **Requiere**: Ser el creador del plan

#### Request
```json
{
  "meal_type": "lunch",
  "name": "Ensalada César Proteica",
  "description": "Ensalada completa con pollo",
  "preparation_time": 20,
  "calories": 450,
  "protein": 35,
  "carbs": 30,
  "fat": 20,
  "recipe_instructions": "1. Preparar lechuga...\n2. Cocinar pollo...",
  "photo_url": "https://..."
}
```

#### Response 201 Created
```json
{
  "id": 102,
  "day_id": 1,
  "meal_type": "lunch",
  "name": "Ensalada César Proteica",
  "created_at": "2024-12-29T12:00:00Z"
}
```

---

### POST /meals/{id}/complete
**Marcar comida como completada**

#### Request
```json
{
  "satisfaction_rating": 5,
  "notes": "Muy rica y fácil de preparar",
  "photo_url": "https://user-photo...",
  "actual_calories": 420,
  "completion_percentage": 100
}
```

#### Response 200 OK
```json
{
  "id": 789,
  "meal_id": 101,
  "user_id": 456,
  "completed_at": "2024-12-29T13:30:00Z",
  "satisfaction_rating": 5,
  "daily_progress": {
    "meals_completed": 2,
    "meals_total": 4,
    "calories_consumed": 850,
    "calories_target": 1500,
    "completion_percentage": 50
  }
}
```

---

## Generación con IA

### POST /meals/{id}/ingredients/ai-generate
**Generar ingredientes con IA para una comida**

⚠️ **Requiere**: Rol trainer o admin

#### Request
```json
{
  "recipe_name": "Desayuno Mediterráneo",
  "target_calories": 400,
  "meal_type": "breakfast",
  "serving_size": 1,
  "dietary_restrictions": ["vegetarian", "dairy_free"],
  "cuisine_type": "mediterranean",
  "preparation_time_max": 20,
  "budget_level": "medium",
  "preferred_ingredients": ["tomate", "aguacate"],
  "excluded_ingredients": ["gluten"],
  "nutritional_focus": "high_protein"
}
```

#### Response 200 OK
```json
{
  "success": true,
  "ingredients": [
    {
      "name": "Huevos",
      "quantity": 2,
      "unit": "unidades",
      "calories": 140,
      "protein": 12,
      "carbs": 2,
      "fat": 10
    },
    {
      "name": "Tomate cherry",
      "quantity": 100,
      "unit": "g",
      "calories": 18,
      "protein": 0.9,
      "carbs": 3.9,
      "fat": 0.2
    },
    {
      "name": "Aguacate",
      "quantity": 50,
      "unit": "g",
      "calories": 80,
      "protein": 1,
      "carbs": 4,
      "fat": 7
    }
  ],
  "total_calories": 398,
  "total_protein": 32.5,
  "total_carbs": 28.3,
  "total_fat": 24.8,
  "preparation_instructions": [
    "Calentar sartén con aceite de oliva",
    "Batir los huevos y cocinar revueltos",
    "Cortar tomates y aguacate",
    "Servir todo junto con hierbas frescas"
  ],
  "ai_model": "gpt-4o-mini",
  "generation_time_ms": 1250,
  "cost_estimate": 0.0008
}
```

#### Errores Comunes
- `403 Forbidden`: No eres trainer/admin
- `404 Not Found`: Comida no existe
- `500 Internal Server Error`: Error de OpenAI

---

### POST /meals/{id}/ingredients/ai-apply
**Aplicar ingredientes generados por IA**

⚠️ **Requiere**: Rol trainer o admin

#### Request
```json
{
  "ingredients": [...],  // Array de ingredientes de ai-generate
  "replace_existing": false,
  "adjust_calories": true
}
```

#### Response 200 OK
```json
{
  "success": true,
  "ingredients_added": 8,
  "ingredients_replaced": 0,
  "meal_updated": true,
  "total_calories": 398,
  "total_protein": 32.5,
  "total_carbs": 28.3,
  "total_fat": 24.8
}
```

---

## Seguridad Médica

### POST /safety-check
**Crear evaluación de seguridad médica**

🏥 **Obligatorio para**: Planes restrictivos (<1500 cal)

#### Request
```json
{
  "age": 28,
  "is_pregnant": false,
  "is_breastfeeding": false,
  "has_diabetes": false,
  "has_heart_condition": false,
  "has_kidney_disease": false,
  "has_liver_disease": false,
  "has_eating_disorder": false,
  "has_other_condition": false,
  "other_condition_details": "",
  "takes_medications": false,
  "medication_list": "",
  "parental_consent_email": null,
  "accepts_disclaimer": true
}
```

#### Response 200 OK
```json
{
  "screening_id": 567,
  "risk_score": 2,
  "risk_level": "LOW",
  "can_proceed": true,
  "requires_professional": false,
  "warnings": [
    {
      "type": "reminder",
      "message": "Recuerda mantener una hidratación adecuada",
      "severity": "info",
      "requires_action": false
    }
  ],
  "next_step": "profile",
  "expires_at": "2024-12-30T14:00:00Z",
  "expires_in_hours": 24,
  "parental_consent_required": false,
  "professional_referral_reasons": [],
  "recommended_specialists": []
}
```

#### Response para Alto Riesgo
```json
{
  "screening_id": 568,
  "risk_score": 8,
  "risk_level": "CRITICAL",
  "can_proceed": false,
  "requires_professional": true,
  "warnings": [
    {
      "type": "medical_condition",
      "message": "Tu historial de trastornos alimentarios requiere supervisión profesional",
      "severity": "critical",
      "requires_action": true
    }
  ],
  "next_step": "professional_referral",
  "professional_referral_reasons": [
    "Historial de trastornos alimentarios",
    "Riesgo de recaída sin supervisión"
  ],
  "recommended_specialists": [
    "Psicólogo especializado en TCA",
    "Nutricionista clínico",
    "Médico especialista"
  ]
}
```

---

### GET /safety-check/validate/{id}
**Validar si un screening sigue vigente**

#### Response 200 OK
```json
{
  "valid": true,
  "screening_id": 567,
  "can_proceed": true,
  "risk_score": 2,
  "reason": "Screening válido y activo",
  "hours_remaining": 18.5
}
```

#### Response para Screening Expirado
```json
{
  "valid": false,
  "screening_id": 567,
  "can_proceed": false,
  "risk_score": 2,
  "reason": "Screening expirado, requiere nueva evaluación",
  "hours_remaining": 0
}
```

---

## Dashboard y Analytics

### GET /plans/categorized
**Obtener planes organizados por categorías**

#### Response 200 OK
```json
{
  "live_plans": [
    {
      "id": 101,
      "title": "Challenge Enero 2024",
      "plan_type": "live",
      "status": "running",
      "current_day": 15,
      "total_days": 30,
      "participants": 87,
      "start_date": "2024-01-01T00:00:00Z",
      "end_date": "2024-01-30T23:59:59Z"
    }
  ],
  "template_plans": [
    {
      "id": 102,
      "title": "Plan Mantenimiento",
      "plan_type": "template",
      "total_followers": 234,
      "avg_satisfaction": 4.7,
      "is_followed_by_user": false
    }
  ],
  "archived_plans": [
    {
      "id": 103,
      "title": "Challenge Verano 2023",
      "plan_type": "archived",
      "original_participants_count": 156,
      "archived_at": "2023-09-01T00:00:00Z",
      "total_followers": 45,
      "success_rate": 82.5
    }
  ],
  "my_active_plans": [
    {
      "id": 104,
      "title": "Mi Plan Actual",
      "current_day": 8,
      "total_days": 21,
      "completion_percentage": 38.1,
      "today_completed": false
    }
  ],
  "total": 12,
  "page": 1,
  "per_page": 20
}
```

---

### GET /my-plans
**Obtener planes que el usuario está siguiendo**

#### Response 200 OK
```json
{
  "active_plans": [
    {
      "plan_id": 123,
      "plan_title": "Plan Definición",
      "follower_id": 456,
      "start_date": "2024-12-15T00:00:00Z",
      "current_day": 14,
      "total_days": 30,
      "status": "running",
      "completion_percentage": 46.7,
      "meals_completed_today": 2,
      "meals_total_today": 4,
      "calories_consumed_today": 850,
      "calories_target_today": 1800,
      "last_activity": "2024-12-29T13:30:00Z"
    }
  ],
  "completed_plans": [...],
  "abandoned_plans": [...]
}
```

---

### GET /my-plans/today
**Obtener el plan del día actual**

#### Response 200 OK
```json
{
  "date": "2024-12-29",
  "day_number": 14,
  "plan": {
    "id": 123,
    "title": "Plan Definición"
  },
  "meals": [
    {
      "id": 201,
      "meal_type": "breakfast",
      "name": "Desayuno Proteico",
      "scheduled_time": "08:00",
      "calories": 400,
      "completed": true,
      "satisfaction_rating": 5
    },
    {
      "id": 202,
      "meal_type": "lunch",
      "name": "Ensalada César",
      "scheduled_time": "13:00",
      "calories": 450,
      "completed": true,
      "satisfaction_rating": 4
    },
    {
      "id": 203,
      "meal_type": "snack",
      "name": "Batido de Frutas",
      "scheduled_time": "16:00",
      "calories": 200,
      "completed": false
    },
    {
      "id": 204,
      "meal_type": "dinner",
      "name": "Salmón con Verduras",
      "scheduled_time": "20:00",
      "calories": 500,
      "completed": false
    }
  ],
  "summary": {
    "total_calories_target": 1550,
    "total_calories_consumed": 850,
    "meals_completed": 2,
    "meals_pending": 2,
    "completion_percentage": 50,
    "macros_consumed": {
      "protein": 65,
      "carbs": 70,
      "fat": 30
    },
    "macros_target": {
      "protein": 120,
      "carbs": 155,
      "fat": 52
    }
  },
  "notifications": {
    "next_meal": "snack",
    "next_meal_time": "16:00",
    "reminder_sent": false
  }
}
```

---

### GET /my-progress
**Obtener progreso detallado del usuario**

#### Query Parameters
| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| plan_id | int | No | Filtrar por plan específico |
| date_from | date | No | Fecha inicio |
| date_to | date | No | Fecha fin |

#### Response 200 OK
```json
{
  "overall_stats": {
    "total_days": 14,
    "meals_completed": 42,
    "meals_total": 56,
    "completion_rate": 75,
    "average_satisfaction": 4.3,
    "total_calories_consumed": 21000,
    "total_calories_target": 25200,
    "adherence_percentage": 83.3
  },
  "daily_progress": [
    {
      "date": "2024-12-29",
      "day_number": 14,
      "meals_completed": 2,
      "meals_total": 4,
      "calories_consumed": 850,
      "calories_target": 1800,
      "completion_percentage": 50,
      "satisfaction_average": 4.5
    }
  ],
  "weekly_summary": [
    {
      "week_number": 1,
      "start_date": "2024-12-15",
      "end_date": "2024-12-21",
      "completion_rate": 85.7,
      "avg_calories": 1750,
      "weight_change": -0.5
    },
    {
      "week_number": 2,
      "start_date": "2024-12-22",
      "end_date": "2024-12-28",
      "completion_rate": 71.4,
      "avg_calories": 1680,
      "weight_change": -0.3
    }
  ],
  "achievements": [
    {
      "type": "streak",
      "title": "7 días consecutivos",
      "unlocked_at": "2024-12-21T20:00:00Z"
    }
  ],
  "trends": {
    "completion_trend": "improving",
    "satisfaction_trend": "stable",
    "adherence_trend": "declining"
  }
}
```

---

### GET /plans/{id}/analytics
**Obtener analytics detallados de un plan**

⚠️ **Requiere**: Ser el creador del plan

#### Response 200 OK
```json
{
  "plan_id": 123,
  "plan_title": "Plan Definición",
  "period": "all_time",
  "followers": {
    "total": 87,
    "active": 23,
    "completed": 45,
    "abandoned": 19,
    "retention_rate": 78.2
  },
  "engagement": {
    "avg_completion_rate": 72.5,
    "avg_days_followed": 18.5,
    "avg_satisfaction": 4.2,
    "photos_shared": 234,
    "comments_count": 567
  },
  "meal_performance": [
    {
      "meal_id": 101,
      "meal_name": "Desayuno Proteico",
      "completion_rate": 92.3,
      "avg_satisfaction": 4.8,
      "skip_rate": 7.7,
      "favorite_count": 45
    }
  ],
  "daily_performance": [
    {
      "day_number": 1,
      "completion_rate": 95,
      "dropout_rate": 2
    }
  ],
  "user_feedback": {
    "positive_keywords": ["delicioso", "fácil", "saciante"],
    "negative_keywords": ["caro", "mucho tiempo", "ingredientes raros"],
    "improvement_suggestions": [
      "Más opciones vegetarianas",
      "Reducir tiempo de preparación"
    ]
  },
  "financial": {
    "avg_daily_cost": 12.50,
    "cost_perception": "medium",
    "ingredient_availability": 4.1
  }
}
```

---

## Códigos de Error Comunes

### Estructura de Error Estándar
```json
{
  "detail": {
    "message": "Descripción legible del error",
    "error_code": "SPECIFIC_ERROR_CODE",
    "field": "campo_con_error",
    "value": "valor_problemático",
    "suggestion": "Cómo resolver el problema"
  }
}
```

### Códigos HTTP y Significados

| Código | Significado | Ejemplo |
|--------|------------|---------|
| 200 | Éxito | Operación completada |
| 201 | Creado | Recurso creado exitosamente |
| 204 | Sin contenido | Eliminación exitosa |
| 400 | Solicitud incorrecta | Datos inválidos |
| 401 | No autenticado | Token expirado o inválido |
| 403 | Prohibido | Sin permisos para la acción |
| 404 | No encontrado | Recurso no existe |
| 409 | Conflicto | Estado incompatible |
| 422 | Entidad no procesable | Validación fallida |
| 429 | Demasiadas solicitudes | Rate limit excedido |
| 500 | Error del servidor | Error interno |
| 503 | Servicio no disponible | Mantenimiento o sobrecarga |

### Errores Específicos del Dominio

#### NUTRITION_001: Plan Restrictivo Sin Screening
```json
{
  "detail": {
    "message": "Este plan requiere una evaluación de seguridad médica",
    "error_code": "NUTRITION_001",
    "reason": "restrictive_plan",
    "action_required": "safety_screening",
    "endpoint": "/api/v1/nutrition/safety-check"
  }
}
```

#### NUTRITION_002: Screening Expirado
```json
{
  "detail": {
    "message": "Tu evaluación médica ha expirado",
    "error_code": "NUTRITION_002",
    "expired_at": "2024-12-28T14:00:00Z",
    "action_required": "renew_screening"
  }
}
```

#### NUTRITION_003: Alto Riesgo Médico
```json
{
  "detail": {
    "message": "Tu perfil médico requiere supervisión profesional",
    "error_code": "NUTRITION_003",
    "risk_level": "HIGH",
    "recommended_specialists": ["Nutricionista clínico"]
  }
}
```

#### NUTRITION_004: Permiso Denegado
```json
{
  "detail": {
    "message": "Solo trainers y administradores pueden realizar esta acción",
    "error_code": "NUTRITION_004",
    "required_role": "trainer",
    "current_role": "member"
  }
}
```

---

## Rate Limiting

### Límites por Endpoint

| Endpoint | Límite | Ventana | Headers de Respuesta |
|----------|---------|---------|---------------------|
| General | 60 req | 1 min | X-RateLimit-Limit: 60 |
| AI Generation | 10 req | 1 min | X-RateLimit-Remaining: 8 |
| Safety Check | 5 req | 1 min | X-RateLimit-Reset: 1703856000 |
| Create Plans | 20 req | 1 hora | Retry-After: 45 |

### Respuesta 429 Too Many Requests
```json
{
  "detail": {
    "message": "Rate limit excedido",
    "limit": 60,
    "window": "1 minute",
    "retry_after": 45,
    "reset_at": "2024-12-29T14:01:00Z"
  }
}
```

---

## Headers de Autenticación

Todos los endpoints requieren autenticación JWT:

```http
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6...
```

### Token Claims Requeridos
```json
{
  "sub": "auth0|user_id",
  "gym_id": 1,
  "role": "trainer",
  "permissions": ["create:plans", "use:ai"],
  "exp": 1703856000
}
```

---

## Paginación

### Request Parameters
```http
GET /api/v1/nutrition/plans?page=2&per_page=50
```

### Response Headers
```http
X-Total-Count: 150
X-Page: 2
X-Per-Page: 50
X-Total-Pages: 3
Link: </api/v1/nutrition/plans?page=3>; rel="next",
      </api/v1/nutrition/plans?page=1>; rel="prev",
      </api/v1/nutrition/plans?page=1>; rel="first",
      </api/v1/nutrition/plans?page=3>; rel="last"
```

---

*Siguiente: [Sistema de Seguridad Médica →](./03_SEGURIDAD_MEDICA.md)*