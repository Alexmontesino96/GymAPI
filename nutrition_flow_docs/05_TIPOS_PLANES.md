# 📊 Tipos de Planes Nutricionales

## 📋 Tabla de Contenidos
- [Overview](#overview)
- [Categorías de Planes](#categorías-de-planes)
- [Planes por Objetivo](#planes-por-objetivo)
- [Planes Especializados](#planes-especializados)
- [Personalización y Ajustes](#personalización-y-ajustes)
- [Restricciones Médicas](#restricciones-médicas)
- [Ciclos y Duraciones](#ciclos-y-duraciones)

## Overview

El sistema soporta múltiples tipos de planes nutricionales diseñados para diferentes objetivos, restricciones dietéticas y necesidades médicas. Todos los planes pueden ser generados por IA o creados manualmente por trainers/admins.

### Jerarquía de Planes
```
Planes Nutricionales
├── Por Objetivo (weight_loss, muscle_gain, maintenance)
├── Por Restricción (vegetarian, vegan, keto, etc.)
├── Por Condición Médica (diabetes, hipertensión, etc.)
├── Por Nivel de Actividad (sedentary, moderate, active)
└── Personalizados (combinaciones específicas)
```

## Categorías de Planes

### 1. Planes Estándar
Planes básicos disponibles para todos los usuarios sin restricciones especiales.

```python
class StandardPlan:
    """Planes sin restricciones médicas especiales"""

    characteristics = {
        "calorie_range": (1500, 3500),
        "meal_count": (3, 6),
        "duration": (7, 30),  # días
        "requires_screening": False  # Para planes > 2500 cal
    }
```

### 2. Planes Restrictivos
Planes que requieren screening médico para usuarios.

```python
class RestrictivePlan:
    """Planes con restricciones calóricas significativas"""

    characteristics = {
        "calorie_range": (1200, 1800),
        "requires_screening": True,  # SIEMPRE
        "not_suitable_for": [
            "pregnant",
            "breastfeeding",
            "under_18",
            "eating_disorder_history"
        ]
    }
```

## Planes por Objetivo

### 1. Pérdida de Peso (weight_loss)
```json
{
    "goal": "weight_loss",
    "characteristics": {
        "calorie_deficit": "15-25%",
        "typical_range": "1200-2000 cal",
        "protein_emphasis": "high",
        "duration": "4-12 semanas"
    },
    "macros_distribution": {
        "protein": "30-35%",
        "carbs": "35-40%",
        "fat": "25-30%"
    },
    "screening_required": true,  // Si < 1500 cal
    "sample_day": {
        "breakfast": "Avena con frutas y proteína (350 cal)",
        "snack": "Yogurt griego con nueces (150 cal)",
        "lunch": "Ensalada de pollo y quinoa (450 cal)",
        "snack": "Verduras con hummus (100 cal)",
        "dinner": "Pescado con vegetales al vapor (400 cal)"
    }
}
```

### 2. Ganancia Muscular (muscle_gain)
```json
{
    "goal": "muscle_gain",
    "characteristics": {
        "calorie_surplus": "10-20%",
        "typical_range": "2500-4000 cal",
        "protein_emphasis": "very_high",
        "duration": "8-16 semanas"
    },
    "macros_distribution": {
        "protein": "35-40%",
        "carbs": "40-45%",
        "fat": "20-25%"
    },
    "screening_required": false,
    "sample_day": {
        "breakfast": "Huevos con avena y plátano (550 cal)",
        "post_workout": "Batido de proteína con carbohidratos (350 cal)",
        "lunch": "Arroz con pollo y vegetales (650 cal)",
        "snack": "Sándwich de atún (400 cal)",
        "dinner": "Pasta con carne magra (700 cal)",
        "before_bed": "Caseína con frutos secos (300 cal)"
    }
}
```

### 3. Mantenimiento (maintenance)
```json
{
    "goal": "maintenance",
    "characteristics": {
        "calorie_balance": "0%",
        "typical_range": "1800-2500 cal",
        "balance": "equilibrado",
        "duration": "indefinido"
    },
    "macros_distribution": {
        "protein": "25-30%",
        "carbs": "45-50%",
        "fat": "25-30%"
    },
    "screening_required": false,
    "flexibility": "high"
}
```

### 4. Definición (definition)
```json
{
    "goal": "definition",
    "characteristics": {
        "calorie_deficit": "10-15%",
        "typical_range": "1600-2200 cal",
        "protein_emphasis": "very_high",
        "duration": "6-10 semanas"
    },
    "macros_distribution": {
        "protein": "40-45%",
        "carbs": "30-35%",
        "fat": "20-25%"
    },
    "screening_required": false,
    "special_focus": "preservar masa muscular"
}
```

### 5. Rendimiento Deportivo (performance)
```json
{
    "goal": "performance",
    "characteristics": {
        "calorie_adjustment": "según actividad",
        "typical_range": "2200-3500 cal",
        "carb_emphasis": "high",
        "duration": "según temporada"
    },
    "macros_distribution": {
        "protein": "20-25%",
        "carbs": "50-60%",
        "fat": "20-25%"
    },
    "timing": "crítico",
    "pre_workout": "carbohidratos complejos",
    "post_workout": "proteína + carbohidratos simples"
}
```

## Planes Especializados

### 1. Restricciones Dietéticas

#### Vegetariano
```python
vegetarian_plan = {
    "excluded_foods": ["carne", "pescado", "aves"],
    "protein_sources": [
        "huevos",
        "lácteos",
        "legumbres",
        "quinoa",
        "frutos secos",
        "tofu"
    ],
    "supplementation": ["B12", "hierro", "omega-3"],
    "calorie_range": "normal"
}
```

#### Vegano
```python
vegan_plan = {
    "excluded_foods": [
        "todos productos animales",
        "huevos",
        "lácteos",
        "miel"
    ],
    "protein_sources": [
        "legumbres",
        "quinoa",
        "frutos secos",
        "semillas",
        "tofu",
        "tempeh"
    ],
    "supplementation": ["B12", "D3", "hierro", "omega-3", "calcio"],
    "requires_careful_planning": True
}
```

#### Keto
```python
keto_plan = {
    "macros": {
        "carbs": "< 5%",  # < 20-30g/día
        "protein": "20-25%",
        "fat": "70-75%"
    },
    "medical_supervision": "recomendada",
    "not_suitable_for": [
        "diabetes_tipo_1",
        "embarazadas",
        "problemas_renales"
    ],
    "adaptation_period": "2-4 semanas"
}
```

#### Paleo
```python
paleo_plan = {
    "excluded_foods": [
        "granos",
        "lácteos",
        "legumbres",
        "azúcar procesada",
        "alimentos procesados"
    ],
    "focus": "alimentos enteros",
    "protein_emphasis": "high",
    "suitable_for": "most users"
}
```

#### Sin Gluten
```python
gluten_free_plan = {
    "excluded_foods": [
        "trigo",
        "cebada",
        "centeno",
        "avena no certificada"
    ],
    "medical_requirement": "celíacos",
    "alternatives": [
        "arroz",
        "quinoa",
        "maíz",
        "papa"
    ]
}
```

### 2. Condiciones Médicas Específicas

#### Diabetes
```python
diabetes_plan = {
    "type": "diabetes_management",
    "characteristics": {
        "glycemic_index": "low",
        "meal_frequency": "5-6 comidas pequeñas",
        "carb_counting": True,
        "fiber": "high"
    },
    "restrictions": {
        "simple_sugars": "minimal",
        "refined_carbs": "avoid",
        "portion_control": "critical"
    },
    "requires_professional": True,
    "monitoring": "glucose levels"
}
```

#### Hipertensión
```python
hypertension_plan = {
    "type": "blood_pressure_management",
    "characteristics": {
        "sodium": "< 2000mg/día",
        "potassium": "high",
        "dash_diet_principles": True
    },
    "emphasis": [
        "frutas",
        "vegetales",
        "granos enteros",
        "proteínas magras"
    ],
    "avoid": [
        "sal añadida",
        "alimentos procesados",
        "alcohol excesivo"
    ]
}
```

#### Colesterol Alto
```python
cholesterol_plan = {
    "type": "lipid_management",
    "characteristics": {
        "saturated_fat": "< 7% calorías totales",
        "trans_fat": "0g",
        "cholesterol": "< 200mg/día",
        "fiber": "25-35g/día"
    },
    "emphasis": [
        "omega-3",
        "fibra soluble",
        "esteroles vegetales"
    ]
}
```

## Personalización y Ajustes

### Sistema de Personalización Dinámica
```python
class PlanCustomization:
    def adjust_plan(self, base_plan, user_preferences):
        """
        Ajusta plan base según preferencias del usuario
        """
        adjustments = {
            "meal_timing": self.adjust_meal_schedule(
                user_preferences.schedule
            ),
            "portion_sizes": self.calculate_portions(
                user_preferences.activity_level,
                user_preferences.metabolic_rate
            ),
            "food_swaps": self.generate_alternatives(
                user_preferences.dislikes,
                user_preferences.allergies
            ),
            "macro_distribution": self.fine_tune_macros(
                user_preferences.training_style
            )
        }
        return self.apply_adjustments(base_plan, adjustments)
```

### Factores de Ajuste

#### Por Edad
```python
age_adjustments = {
    "18-25": {
        "calorie_multiplier": 1.0,
        "protein_needs": "standard"
    },
    "26-35": {
        "calorie_multiplier": 0.98,
        "protein_needs": "standard"
    },
    "36-45": {
        "calorie_multiplier": 0.95,
        "protein_needs": "slightly_higher"
    },
    "46-55": {
        "calorie_multiplier": 0.92,
        "protein_needs": "higher",
        "calcium_emphasis": True
    },
    "56+": {
        "calorie_multiplier": 0.88,
        "protein_needs": "higher",
        "vitamin_d_emphasis": True
    }
}
```

#### Por Nivel de Actividad
```python
activity_multipliers = {
    "sedentary": {
        "tdee_multiplier": 1.2,
        "carb_needs": "lower"
    },
    "lightly_active": {
        "tdee_multiplier": 1.375,
        "carb_needs": "moderate"
    },
    "moderately_active": {
        "tdee_multiplier": 1.55,
        "carb_needs": "moderate_high"
    },
    "very_active": {
        "tdee_multiplier": 1.725,
        "carb_needs": "high"
    },
    "extremely_active": {
        "tdee_multiplier": 1.9,
        "carb_needs": "very_high"
    }
}
```

## Restricciones Médicas

### Matriz de Incompatibilidades
```python
medical_incompatibilities = {
    "pregnancy": {
        "restricted_plans": ["weight_loss", "keto", "very_low_calorie"],
        "required_nutrients": ["folic_acid", "iron", "calcium"],
        "min_calories": 1800
    },
    "breastfeeding": {
        "restricted_plans": ["weight_loss", "restrictive"],
        "extra_calories": 500,
        "hydration": "critical"
    },
    "kidney_disease": {
        "protein_limit": "moderate",
        "potassium": "monitor",
        "phosphorus": "limit"
    },
    "eating_disorder_history": {
        "restricted_plans": ["all_restrictive"],
        "requires_professional": True,
        "focus": "balanced_eating"
    }
}
```

### Validación Automática
```python
def validate_plan_compatibility(user_medical_profile, plan_type):
    """
    Verifica si un plan es seguro para el usuario
    """
    incompatibilities = []

    for condition in user_medical_profile.conditions:
        if plan_type in medical_incompatibilities[condition]["restricted_plans"]:
            incompatibilities.append({
                "condition": condition,
                "reason": f"Plan {plan_type} no recomendado para {condition}"
            })

    if incompatibilities:
        return {
            "compatible": False,
            "issues": incompatibilities,
            "recommendation": "Consulte con un profesional"
        }

    return {"compatible": True}
```

## Ciclos y Duraciones

### Duraciones Recomendadas por Objetivo
```python
duration_guidelines = {
    "weight_loss": {
        "min": 4,  # semanas
        "recommended": 8,
        "max": 12,
        "break_after": "12 semanas"
    },
    "muscle_gain": {
        "min": 8,
        "recommended": 12,
        "max": 16,
        "deload_week": "cada 4 semanas"
    },
    "definition": {
        "min": 6,
        "recommended": 8,
        "max": 10,
        "intensity": "progressive"
    },
    "maintenance": {
        "min": "indefinido",
        "adjustments": "mensuales"
    }
}
```

### Progresión y Ajustes
```python
class PlanProgression:
    def calculate_weekly_adjustments(self, week, goal):
        """
        Ajustes semanales según progreso
        """
        if goal == "weight_loss":
            # Reducción gradual de calorías
            return {
                "week_1-2": "baseline",
                "week_3-4": "-5%",
                "week_5-6": "-7%",
                "week_7-8": "-10%",
                "refeed_day": "weekly after week 4"
            }

        elif goal == "muscle_gain":
            # Incremento progresivo
            return {
                "week_1-4": "baseline",
                "week_5-8": "+5%",
                "week_9-12": "+10%",
                "deload": "week 4, 8, 12"
            }
```

### Transiciones Entre Planes
```python
transition_protocol = {
    "from_loss_to_maintenance": {
        "duration": "2 semanas",
        "calorie_increase": "gradual +100cal/semana",
        "monitoring": "peso y medidas"
    },
    "from_gain_to_definition": {
        "duration": "1 semana",
        "adjustment": "reducir carbohidratos primero",
        "maintain": "proteína alta"
    },
    "from_restrictive_to_normal": {
        "duration": "3 semanas",
        "supervision": "recomendada",
        "approach": "reverse dieting"
    }
}
```

## Métricas de Éxito

### KPIs por Tipo de Plan
```python
success_metrics = {
    "weight_loss": [
        "pérdida de peso semanal (0.5-1kg)",
        "reducción de medidas",
        "energía mantenida",
        "adherencia > 80%"
    ],
    "muscle_gain": [
        "ganancia de peso controlada (0.25-0.5kg/semana)",
        "incremento de fuerza",
        "medidas musculares",
        "composición corporal"
    ],
    "performance": [
        "mejora en tiempos/marcas",
        "recuperación optimizada",
        "energía durante entrenamientos",
        "consistencia"
    ]
}
```

---

**Siguiente:** [06_GUIA_INTEGRACION.md](06_GUIA_INTEGRACION.md) - Guía de integración para desarrolladores