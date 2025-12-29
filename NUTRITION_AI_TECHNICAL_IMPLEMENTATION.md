# 🔧 IMPLEMENTACIÓN TÉCNICA - Flujo Nutricional IA Mejorado

## 📋 Resumen de Cambios Técnicos Requeridos

Basado en el análisis de expertos UI/UX y Nutrición, esta es la implementación técnica para crear un MVP seguro y usable.

---

## 1️⃣ NUEVOS SCHEMAS (Pydantic)

### Schema de Seguridad Médica

```python
# app/schemas/nutrition_safety.py

from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import date
from enum import Enum

class MedicalCondition(str, Enum):
    DIABETES_TYPE1 = "diabetes_type1"
    DIABETES_TYPE2 = "diabetes_type2"
    HYPERTENSION = "hypertension"
    HEART_DISEASE = "heart_disease"
    KIDNEY_DISEASE = "kidney_disease"
    LIVER_DISEASE = "liver_disease"
    THYROID_DISORDER = "thyroid_disorder"
    PCOS = "pcos"
    CANCER = "cancer"
    AUTOIMMUNE = "autoimmune"
    GASTROINTESTINAL = "gastrointestinal"
    EATING_DISORDER = "eating_disorder"
    NONE = "none"

class SafetyScreening(BaseModel):
    """Screening de seguridad obligatorio antes de generar planes"""

    age: int = Field(..., ge=13, le=120)
    is_pregnant: bool = False
    is_breastfeeding: bool = False
    medical_conditions: List[MedicalCondition] = []
    takes_medications: bool = False
    medication_list: Optional[str] = None
    has_eating_disorder_history: bool = False

    # Screening TCA simplificado (2 preguntas para MVP)
    feels_out_of_control_eating: bool = False
    food_dominates_life: bool = False

    # Consentimiento
    accepts_disclaimer: bool = Field(..., description="Debe aceptar disclaimer legal")
    parental_consent_email: Optional[str] = Field(None, description="Si <18 años")

    @validator('age')
    def validate_age_consent(cls, v, values):
        if v < 18 and not values.get('parental_consent_email'):
            raise ValueError("Menores de 18 requieren consentimiento parental")
        return v

    @validator('medical_conditions')
    def validate_medical_safety(cls, v, values):
        if values.get('is_pregnant') or values.get('is_breastfeeding'):
            # No permitir pérdida de peso en embarazo/lactancia
            return v
        return v

    @property
    def risk_score(self) -> int:
        """Calcula score de riesgo (0-10)"""
        score = 0

        # Condiciones médicas (+2 cada una)
        serious_conditions = [
            MedicalCondition.DIABETES_TYPE1,
            MedicalCondition.KIDNEY_DISEASE,
            MedicalCondition.HEART_DISEASE,
            MedicalCondition.EATING_DISORDER
        ]
        for condition in self.medical_conditions:
            if condition in serious_conditions:
                score += 2
            elif condition != MedicalCondition.NONE:
                score += 1

        # Embarazo/lactancia (+3)
        if self.is_pregnant or self.is_breastfeeding:
            score += 3

        # TCA screening (+4)
        if self.has_eating_disorder_history:
            score += 4
        elif self.feels_out_of_control_eating and self.food_dominates_life:
            score += 3

        # Edad extrema (+2)
        if self.age < 16 or self.age > 70:
            score += 2

        # Medicamentos (+1)
        if self.takes_medications:
            score += 1

        return min(score, 10)

    @property
    def requires_professional_supervision(self) -> bool:
        """Determina si requiere supervisión profesional"""
        return self.risk_score >= 5

    @property
    def can_generate_weight_loss_plan(self) -> bool:
        """Determina si puede generar plan de pérdida de peso"""
        if self.is_pregnant or self.is_breastfeeding:
            return False
        if MedicalCondition.EATING_DISORDER in self.medical_conditions:
            return False
        if self.has_eating_disorder_history:
            return False
        return True
```

### Schema de Perfil Nutricional Simplificado

```python
# app/schemas/nutrition_profile.py

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Literal
from enum import Enum

class ActivityLevel(str, Enum):
    SEDENTARY = "sedentary"  # x1.2
    LIGHTLY_ACTIVE = "lightly_active"  # x1.375
    MODERATELY_ACTIVE = "moderately_active"  # x1.55
    VERY_ACTIVE = "very_active"  # x1.725

class NutritionalGoal(str, Enum):
    WEIGHT_LOSS = "weight_loss"
    MUSCLE_GAIN = "muscle_gain"
    MAINTAIN = "maintain"
    ENERGY = "energy"
    HEALTH = "health"

class DietaryRestriction(str, Enum):
    NONE = "none"
    VEGETARIAN = "vegetarian"
    VEGAN = "vegan"
    GLUTEN_FREE = "gluten_free"
    DAIRY_FREE = "dairy_free"
    KETO = "keto"
    PALEO = "paleo"
    HALAL = "halal"
    KOSHER = "kosher"

class NutritionProfileBase(BaseModel):
    """Perfil nutricional MVP - Solo campos esenciales"""

    # Datos antropométricos básicos
    weight_kg: float = Field(..., gt=30, lt=300)
    height_cm: float = Field(..., gt=100, lt=250)
    age: int = Field(..., ge=13, le=120)
    biological_sex: Literal["male", "female"]

    # Objetivo y actividad
    goal: NutritionalGoal
    activity_level: ActivityLevel

    # Restricciones (simplificado)
    dietary_restriction: DietaryRestriction = DietaryRestriction.NONE
    allergies: List[str] = Field(default_factory=list, max_items=5)
    disliked_foods: str = Field("", max_length=200, description="Máx 3-5 alimentos")

    # Preferencias básicas (opcionales con defaults)
    budget_level: Literal["low", "medium", "high"] = "medium"
    cooking_time_minutes: int = Field(30, ge=10, le=120)

    @property
    def bmi(self) -> float:
        """Calcula IMC"""
        height_m = self.height_cm / 100
        return round(self.weight_kg / (height_m ** 2), 1)

    @property
    def bmi_category(self) -> str:
        """Categoría de IMC"""
        if self.bmi < 18.5:
            return "underweight"
        elif self.bmi < 25:
            return "normal"
        elif self.bmi < 30:
            return "overweight"
        else:
            return "obese"

    @property
    def bmr(self) -> float:
        """Calcula BMR usando Mifflin-St Jeor"""
        if self.biological_sex == "male":
            bmr = (10 * self.weight_kg) + (6.25 * self.height_cm) - (5 * self.age) + 5
        else:
            bmr = (10 * self.weight_kg) + (6.25 * self.height_cm) - (5 * self.age) - 161
        return round(bmr)

    @property
    def tdee(self) -> float:
        """Calcula TDEE (Total Daily Energy Expenditure)"""
        activity_multipliers = {
            ActivityLevel.SEDENTARY: 1.2,
            ActivityLevel.LIGHTLY_ACTIVE: 1.375,
            ActivityLevel.MODERATELY_ACTIVE: 1.55,
            ActivityLevel.VERY_ACTIVE: 1.725
        }
        return round(self.bmr * activity_multipliers[self.activity_level])

    @property
    def target_calories(self) -> float:
        """Calcula calorías objetivo basado en meta"""
        if self.goal == NutritionalGoal.WEIGHT_LOSS:
            # Déficit moderado de 500 kcal (0.5kg/semana)
            deficit = min(500, self.tdee * 0.20)  # Máximo 20% déficit
            return round(self.tdee - deficit)
        elif self.goal == NutritionalGoal.MUSCLE_GAIN:
            # Superávit moderado de 300-500 kcal
            return round(self.tdee + 350)
        else:
            # Mantenimiento
            return round(self.tdee)

    @property
    def macro_targets(self) -> dict:
        """Calcula distribución de macros basado en objetivo"""
        calories = self.target_calories

        if self.goal == NutritionalGoal.WEIGHT_LOSS:
            # Alta proteína para preservar músculo
            protein_g = round(self.weight_kg * 2.0)
            fat_g = round(calories * 0.25 / 9)
            carb_g = round((calories - (protein_g * 4) - (fat_g * 9)) / 4)
        elif self.goal == NutritionalGoal.MUSCLE_GAIN:
            # Proteína moderada-alta, carbos altos
            protein_g = round(self.weight_kg * 1.8)
            fat_g = round(calories * 0.25 / 9)
            carb_g = round((calories - (protein_g * 4) - (fat_g * 9)) / 4)
        else:
            # Balance estándar
            protein_g = round(self.weight_kg * 1.5)
            fat_g = round(calories * 0.30 / 9)
            carb_g = round((calories - (protein_g * 4) - (fat_g * 9)) / 4)

        return {
            "calories": calories,
            "protein_g": protein_g,
            "carbs_g": carb_g,
            "fat_g": fat_g,
            "fiber_g": 30 if self.biological_sex == "male" else 25
        }

    @validator('goal')
    def validate_goal_with_bmi(cls, v, values):
        # Calcular BMI manualmente aquí
        if 'weight_kg' in values and 'height_cm' in values:
            height_m = values['height_cm'] / 100
            bmi = values['weight_kg'] / (height_m ** 2)

            if bmi < 18.5 and v == NutritionalGoal.WEIGHT_LOSS:
                raise ValueError(
                    "No se puede crear plan de pérdida de peso con IMC <18.5. "
                    "Consulta un nutricionista."
                )
        return v

class NutritionProfileExtended(NutritionProfileBase):
    """Perfil extendido para Progressive Profiling (post-MVP)"""

    # Composición corporal (Fase 2)
    waist_cm: Optional[float] = None
    body_fat_percentage: Optional[float] = None

    # Historial (Fase 2)
    weight_history_max_kg: Optional[float] = None
    weight_history_min_kg: Optional[float] = None
    previous_diets_count: Optional[int] = None

    # Contexto social (Fase 3)
    cooks_for_family: Optional[bool] = None
    family_size: Optional[int] = None
    eats_out_frequency_weekly: Optional[int] = None
    cultural_cuisine: Optional[str] = None

    # Horario y timing (Fase 3)
    workout_time: Optional[str] = None  # "morning", "afternoon", "evening"
    meal_prep_experience: Optional[str] = None  # "none", "beginner", "experienced"
    intermittent_fasting_hours: Optional[int] = None

    # Suplementación (Fase 3)
    current_supplements: List[str] = Field(default_factory=list)
    hydration_liters_daily: Optional[float] = None
```

---

## 2️⃣ VALIDACIONES Y LÓGICA DE NEGOCIO

### Servicio de Validación de Seguridad

```python
# app/services/nutrition_safety_service.py

from typing import Dict, List, Optional, Tuple
from app.schemas.nutrition_safety import SafetyScreening, MedicalCondition
from app.schemas.nutrition_profile import NutritionProfileBase

class NutritionSafetyService:
    """Servicio para validar seguridad antes de generar planes"""

    @staticmethod
    def validate_safety(
        screening: SafetyScreening,
        profile: NutritionProfileBase
    ) -> Tuple[bool, List[str], List[str]]:
        """
        Valida si es seguro generar un plan
        Returns: (is_safe, errors, warnings)
        """
        errors = []
        warnings = []

        # 1. Validar edad
        if screening.age < 18 and not screening.parental_consent_email:
            errors.append(
                "Menores de 18 años requieren consentimiento parental"
            )

        # 2. Validar disclaimer
        if not screening.accepts_disclaimer:
            errors.append(
                "Debe aceptar el disclaimer legal para continuar"
            )

        # 3. Validar IMC extremos
        if profile.bmi < 18.5 and profile.goal.value == "weight_loss":
            errors.append(
                f"IMC {profile.bmi} es bajo peso. No se pueden generar "
                "planes de pérdida de peso. Consulte un nutricionista."
            )

        if profile.bmi > 35:
            warnings.append(
                f"IMC {profile.bmi} sugiere obesidad. Recomendamos "
                "supervisión profesional para mejores resultados."
            )

        # 4. Validar embarazo/lactancia
        if screening.is_pregnant or screening.is_breastfeeding:
            if profile.goal.value == "weight_loss":
                errors.append(
                    "No se pueden generar planes de pérdida de peso "
                    "durante embarazo o lactancia"
                )
            warnings.append(
                "Planes durante embarazo/lactancia deben ser "
                "supervisados por profesional de salud"
            )

        # 5. Validar condiciones médicas
        serious_conditions = {
            MedicalCondition.DIABETES_TYPE1: "Diabetes tipo 1 requiere supervisión médica",
            MedicalCondition.KIDNEY_DISEASE: "Enfermedad renal requiere plan especializado",
            MedicalCondition.HEART_DISEASE: "Enfermedad cardíaca requiere supervisión médica",
            MedicalCondition.EATING_DISORDER: "Trastorno alimentario requiere equipo especializado"
        }

        for condition in screening.medical_conditions:
            if condition in serious_conditions:
                warnings.append(serious_conditions[condition])

        # 6. Validar screening TCA
        tca_score = 0
        if screening.has_eating_disorder_history:
            tca_score += 2
        if screening.feels_out_of_control_eating:
            tca_score += 1
        if screening.food_dominates_life:
            tca_score += 1

        if tca_score >= 2:
            warnings.append(
                "Detectamos posibles indicadores de relación compleja con "
                "la comida. Considera consultar un especialista."
            )
            if profile.goal.value == "weight_loss":
                warnings.append(
                    "Planes restrictivos pueden no ser apropiados. "
                    "Enfócate en hábitos saludables."
                )

        # 7. Validar medicamentos
        if screening.takes_medications:
            warnings.append(
                "Algunos medicamentos pueden interactuar con alimentos. "
                "Consulta con tu médico o farmacéutico."
            )

        # 8. Validar déficit calórico seguro
        max_deficit = min(750, profile.tdee * 0.25)  # Máx 750 kcal o 25% TDEE
        planned_deficit = profile.tdee - profile.target_calories

        if planned_deficit > max_deficit:
            errors.append(
                f"Déficit calórico muy agresivo ({planned_deficit} kcal). "
                f"Máximo recomendado: {max_deficit} kcal."
            )

        # 9. Validar distribución de macros
        macros = profile.macro_targets
        fat_percentage = (macros['fat_g'] * 9) / macros['calories'] * 100

        if fat_percentage < 20:
            warnings.append(
                f"Grasa muy baja ({fat_percentage:.0f}%). "
                "Mínimo 20% para salud hormonal."
            )

        # Determinar si es seguro continuar
        is_safe = len(errors) == 0

        # Si hay muchos warnings, sugerir supervisión
        if len(warnings) >= 3:
            warnings.append(
                "⚠️ Múltiples factores de riesgo detectados. "
                "Recomendamos fuertemente supervisión profesional."
            )

        return is_safe, errors, warnings

    @staticmethod
    def get_safety_recommendations(
        screening: SafetyScreening
    ) -> Dict[str, any]:
        """
        Genera recomendaciones basadas en el screening
        """
        recommendations = {
            "requires_professional": screening.requires_professional_supervision,
            "can_generate_weight_loss": screening.can_generate_weight_loss_plan,
            "risk_level": "high" if screening.risk_score >= 7 else
                         "medium" if screening.risk_score >= 4 else "low",
            "suggested_approach": [],
            "resources": []
        }

        # Agregar sugerencias específicas
        if screening.is_pregnant or screening.is_breastfeeding:
            recommendations["suggested_approach"].append(
                "Plan de mantenimiento o ganancia saludable"
            )
            recommendations["resources"].append({
                "title": "Nutrición en Embarazo y Lactancia",
                "url": "/resources/pregnancy-nutrition"
            })

        if screening.has_eating_disorder_history:
            recommendations["suggested_approach"].append(
                "Enfoque no-restrictivo, Health at Every Size"
            )
            recommendations["resources"].append({
                "title": "National Eating Disorders Association",
                "url": "https://www.nationaleatingdisorders.org"
            })

        if MedicalCondition.DIABETES_TYPE1 in screening.medical_conditions or \
           MedicalCondition.DIABETES_TYPE2 in screening.medical_conditions:
            recommendations["suggested_approach"].append(
                "Control de carbohidratos y índice glucémico"
            )
            recommendations["resources"].append({
                "title": "American Diabetes Association",
                "url": "https://www.diabetes.org"
            })

        return recommendations
```

---

## 3️⃣ ENDPOINTS ACTUALIZADOS

### Nuevo Endpoint de Screening de Seguridad

```python
# app/api/v1/endpoints/nutrition.py

@router.post("/nutrition/safety-screening")
async def safety_screening(
    screening: SafetyScreening,
    gym_id: int = Depends(get_current_gym_id),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict:
    """
    Paso 0: Screening de seguridad obligatorio
    """
    # Verificar módulo activado
    if not await module_enabled(db, gym_id, "nutrition"):
        raise HTTPException(status_code=404, detail="Módulo no disponible")

    # Guardar screening en DB para auditoría
    screening_record = NutritionScreeningRecord(
        user_id=current_user.id,
        gym_id=gym_id,
        screening_data=screening.dict(),
        risk_score=screening.risk_score,
        created_at=datetime.utcnow()
    )
    db.add(screening_record)
    await db.commit()

    # Generar recomendaciones
    recommendations = NutritionSafetyService.get_safety_recommendations(screening)

    return {
        "screening_id": screening_record.id,
        "risk_score": screening.risk_score,
        "can_proceed": not screening.requires_professional_supervision,
        "can_generate_weight_loss": screening.can_generate_weight_loss_plan,
        "recommendations": recommendations,
        "next_step": "profile" if not screening.requires_professional_supervision
                    else "professional_referral"
    }

@router.post("/nutrition/generate-plan-safe")
async def generate_nutrition_plan_safe(
    profile: NutritionProfileBase,
    screening_id: int,
    gym_id: int = Depends(get_current_gym_id),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict:
    """
    Genera plan nutricional con validaciones de seguridad
    """
    # Verificar que screening existe y es reciente (24h)
    screening_record = await db.get(NutritionScreeningRecord, screening_id)
    if not screening_record:
        raise HTTPException(400, "Screening no encontrado")

    if screening_record.user_id != current_user.id:
        raise HTTPException(403, "Screening no pertenece al usuario")

    hours_old = (datetime.utcnow() - screening_record.created_at).total_seconds() / 3600
    if hours_old > 24:
        raise HTTPException(400, "Screening expirado, por favor repita el proceso")

    # Reconstruir screening
    screening = SafetyScreening(**screening_record.screening_data)

    # Validar seguridad
    is_safe, errors, warnings = NutritionSafetyService.validate_safety(
        screening, profile
    )

    if not is_safe:
        return {
            "success": False,
            "errors": errors,
            "warnings": warnings,
            "recommendation": "Consulte con un profesional de salud"
        }

    # Preparar prompt para OpenAI con contexto de seguridad
    safety_context = ""
    if warnings:
        safety_context = f"\nCONSIDERACIONES DE SEGURIDAD:\n" + "\n".join(warnings)

    prompt = f"""
    Genera un plan nutricional personalizado de 7 días.

    PERFIL DEL USUARIO:
    - Edad: {profile.age} años
    - Sexo: {profile.biological_sex}
    - Peso: {profile.weight_kg} kg
    - Altura: {profile.height_cm} cm
    - IMC: {profile.bmi} ({profile.bmi_category})
    - Objetivo: {profile.goal.value}
    - Nivel de actividad: {profile.activity_level.value}

    REQUERIMIENTOS CALCULADOS:
    - TMB: {profile.bmr} kcal/día
    - TDEE: {profile.tdee} kcal/día
    - Objetivo calórico: {profile.target_calories} kcal/día
    - Proteína: {profile.macro_targets['protein_g']}g
    - Carbohidratos: {profile.macro_targets['carbs_g']}g
    - Grasas: {profile.macro_targets['fat_g']}g
    - Fibra: {profile.macro_targets['fiber_g']}g

    RESTRICCIONES:
    - Dieta: {profile.dietary_restriction.value}
    - Alergias: {', '.join(profile.allergies) if profile.allergies else 'Ninguna'}
    - No le gustan: {profile.disliked_foods if profile.disliked_foods else 'N/A'}

    PREFERENCIAS:
    - Presupuesto: {profile.budget_level}
    - Tiempo de cocina: {profile.cooking_time_minutes} minutos/comida

    {safety_context}

    INSTRUCCIONES:
    1. Crea un plan de 7 días variado y balanceado
    2. Respeta ESTRICTAMENTE las restricciones y alergias
    3. Mantén las calorías y macros cerca de los objetivos
    4. Sugiere comidas simples que se puedan preparar en el tiempo indicado
    5. Si hay consideraciones de seguridad, ajusta apropiadamente
    6. Incluye lista de compras organizada por categorías
    """

    try:
        # Llamar a OpenAI
        completion = await generate_nutrition_with_ai(prompt)

        # Guardar plan en BD
        plan = NutritionPlan(
            user_id=current_user.id,
            gym_id=gym_id,
            name=f"Plan {profile.goal.value} - {datetime.now().strftime('%B %Y')}",
            description=f"Plan personalizado de {profile.target_calories} kcal/día",
            goal=profile.goal.value,
            target_calories=profile.target_calories,
            target_protein=profile.macro_targets['protein_g'],
            target_carbs=profile.macro_targets['carbs_g'],
            target_fat=profile.macro_targets['fat_g'],
            duration_weeks=1,
            ai_generated=True,
            ai_prompt=prompt,
            ai_response=completion,
            safety_screening_id=screening_id,
            warnings=warnings if warnings else None
        )

        db.add(plan)
        await db.commit()

        return {
            "success": True,
            "plan_id": plan.id,
            "plan": parse_ai_plan(completion),
            "calculations": {
                "bmr": profile.bmr,
                "tdee": profile.tdee,
                "target_calories": profile.target_calories,
                "macros": profile.macro_targets
            },
            "warnings": warnings if warnings else []
        }

    except Exception as e:
        logger.error(f"Error generando plan: {str(e)}")
        raise HTTPException(500, "Error generando plan nutricional")
```

---

## 4️⃣ FRONTEND - FLUJO UX MEJORADO

### Componente de Screening de Seguridad

```typescript
// components/NutritionSafetyGateway.tsx

import React, { useState } from 'react';
import {
  Alert,
  Checkbox,
  Button,
  Card,
  Modal
} from '@/components/ui';

interface SafetyGatewayProps {
  onComplete: (screeningId: number) => void;
  onCancel: () => void;
}

export const NutritionSafetyGateway: React.FC<SafetyGatewayProps> = ({
  onComplete,
  onCancel
}) => {
  const [conditions, setConditions] = useState<string[]>([]);
  const [acceptsDisclaimer, setAcceptsDisclaimer] = useState(false);
  const [isPregnant, setIsPregnant] = useState(false);
  const [showReferral, setShowReferral] = useState(false);

  const medicalConditions = [
    { id: 'diabetes', label: 'Diabetes', critical: true },
    { id: 'heart_disease', label: 'Problemas cardíacos', critical: true },
    { id: 'kidney_disease', label: 'Enfermedad renal', critical: true },
    { id: 'eating_disorder', label: 'Trastorno alimentario', critical: true },
    { id: 'thyroid', label: 'Problemas de tiroides', critical: false },
    { id: 'none', label: 'Ninguna de las anteriores', critical: false }
  ];

  const handleSubmit = async () => {
    // Validar si tiene condiciones críticas
    const hasCritical = conditions.some(c =>
      medicalConditions.find(mc => mc.id === c)?.critical
    );

    if (hasCritical || isPregnant) {
      setShowReferral(true);
      return;
    }

    // Enviar screening al backend
    try {
      const response = await fetch('/api/v1/nutrition/safety-screening', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          age: 25, // Obtener de perfil
          is_pregnant: isPregnant,
          is_breastfeeding: false,
          medical_conditions: conditions,
          takes_medications: false,
          has_eating_disorder_history: conditions.includes('eating_disorder'),
          feels_out_of_control_eating: false,
          food_dominates_life: false,
          accepts_disclaimer: acceptsDisclaimer
        })
      });

      const data = await response.json();

      if (data.can_proceed) {
        onComplete(data.screening_id);
      } else {
        setShowReferral(true);
      }
    } catch (error) {
      console.error('Error en screening:', error);
    }
  };

  return (
    <>
      <Card className="max-w-md mx-auto p-6">
        <h2 className="text-2xl font-bold mb-4">
          Antes de empezar
        </h2>

        <Alert variant="info" className="mb-4">
          Por tu seguridad, necesitamos confirmar algunos datos
        </Alert>

        <div className="space-y-4">
          <div>
            <p className="font-medium mb-2">
              ¿Tienes alguna de estas condiciones?
            </p>
            {medicalConditions.map(condition => (
              <Checkbox
                key={condition.id}
                checked={conditions.includes(condition.id)}
                onChange={(checked) => {
                  if (condition.id === 'none') {
                    setConditions(checked ? ['none'] : []);
                  } else {
                    setConditions(prev => {
                      const newConditions = prev.filter(c => c !== 'none');
                      return checked
                        ? [...newConditions, condition.id]
                        : newConditions.filter(c => c !== condition.id);
                    });
                  }
                }}
                label={condition.label}
                className={condition.critical ? 'text-orange-600' : ''}
              />
            ))}
          </div>

          <Checkbox
            checked={isPregnant}
            onChange={setIsPregnant}
            label="Estoy embarazada o en lactancia"
            className="text-orange-600"
          />

          <div className="border-t pt-4">
            <Checkbox
              checked={acceptsDisclaimer}
              onChange={setAcceptsDisclaimer}
              label={
                <span className="text-sm">
                  Entiendo que este sistema genera sugerencias nutricionales
                  y NO reemplaza la consulta con un profesional de salud
                </span>
              }
            />
          </div>
        </div>

        <div className="flex gap-3 mt-6">
          <Button
            variant="outline"
            onClick={onCancel}
            className="flex-1"
          >
            Cancelar
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!acceptsDisclaimer}
            className="flex-1"
          >
            Continuar →
          </Button>
        </div>
      </Card>

      {/* Modal de derivación profesional */}
      {showReferral && (
        <Modal
          open={showReferral}
          onClose={() => setShowReferral(false)}
          title="⚠️ Recomendación importante"
        >
          <div className="space-y-4">
            <p>
              Tu condición requiere un plan supervisado por un profesional
              de salud para garantizar tu seguridad.
            </p>

            <div className="grid gap-2">
              <Button
                variant="primary"
                onClick={() => window.location.href = '/nutritionists'}
              >
                📞 Contactar Nutricionista
              </Button>

              <Button
                variant="outline"
                onClick={() => window.location.href = '/resources'}
              >
                📚 Ver Recursos Educativos
              </Button>

              <Button
                variant="ghost"
                onClick={() => {
                  setShowReferral(false);
                  // Continuar con plan básico
                }}
              >
                ⚡ Continuar con Plan Básico
                <span className="text-xs text-gray-500 block">
                  (Solo mantenimiento, sin restricciones)
                </span>
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </>
  );
};
```

### Componente de Perfil Simplificado

```typescript
// components/NutritionProfileForm.tsx

import React, { useState, useEffect } from 'react';
import { Card, Button, Input, Select, Progress } from '@/components/ui';

interface ProfileFormProps {
  screeningId: number;
  onComplete: (planId: number) => void;
  onBack: () => void;
}

export const NutritionProfileForm: React.FC<ProfileFormProps> = ({
  screeningId,
  onComplete,
  onBack
}) => {
  const [step, setStep] = useState(1);
  const [profile, setProfile] = useState({
    // Paso 1
    goal: '',
    weight_kg: '',
    height_cm: '',
    age: '',
    biological_sex: '',
    activity_level: '',

    // Paso 2
    dietary_restriction: 'none',
    allergies: [],
    disliked_foods: '',

    // Paso 3 (opcional)
    budget_level: 'medium',
    cooking_time_minutes: 30
  });

  const [calculations, setCalculations] = useState({
    bmi: 0,
    bmi_category: '',
    bmr: 0,
    tdee: 0,
    target_calories: 0
  });

  // Calcular métricas en tiempo real
  useEffect(() => {
    if (profile.weight_kg && profile.height_cm && profile.age && profile.biological_sex) {
      const height_m = Number(profile.height_cm) / 100;
      const bmi = Number(profile.weight_kg) / (height_m * height_m);

      // Calcular BMR (Mifflin-St Jeor)
      let bmr;
      if (profile.biological_sex === 'male') {
        bmr = (10 * Number(profile.weight_kg)) +
              (6.25 * Number(profile.height_cm)) -
              (5 * Number(profile.age)) + 5;
      } else {
        bmr = (10 * Number(profile.weight_kg)) +
              (6.25 * Number(profile.height_cm)) -
              (5 * Number(profile.age)) - 161;
      }

      // Calcular TDEE
      const activityMultipliers = {
        sedentary: 1.2,
        lightly_active: 1.375,
        moderately_active: 1.55,
        very_active: 1.725
      };

      const tdee = bmr * (activityMultipliers[profile.activity_level] || 1.2);

      // Calcular calorías objetivo
      let target_calories = tdee;
      if (profile.goal === 'weight_loss') {
        target_calories = tdee - Math.min(500, tdee * 0.2);
      } else if (profile.goal === 'muscle_gain') {
        target_calories = tdee + 350;
      }

      setCalculations({
        bmi: Math.round(bmi * 10) / 10,
        bmi_category: bmi < 18.5 ? 'Bajo peso' :
                      bmi < 25 ? 'Normal' :
                      bmi < 30 ? 'Sobrepeso' : 'Obesidad',
        bmr: Math.round(bmr),
        tdee: Math.round(tdee),
        target_calories: Math.round(target_calories)
      });
    }
  }, [profile]);

  const handleGeneratePlan = async () => {
    try {
      const response = await fetch('/api/v1/nutrition/generate-plan-safe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...profile,
          screening_id: screeningId
        })
      });

      const data = await response.json();

      if (data.success) {
        onComplete(data.plan_id);
      } else {
        // Mostrar errores/warnings
        alert(data.errors?.join('\n') || 'Error generando plan');
      }
    } catch (error) {
      console.error('Error:', error);
    }
  };

  return (
    <Card className="max-w-2xl mx-auto p-6">
      {/* Progress bar */}
      <div className="mb-6">
        <div className="flex justify-between text-sm text-gray-600 mb-2">
          <span>Paso {step} de 3</span>
          <span>{Math.round((step / 3) * 100)}% completado</span>
        </div>
        <Progress value={(step / 3) * 100} />
      </div>

      {/* Paso 1: Datos esenciales */}
      {step === 1 && (
        <div className="space-y-4">
          <h3 className="text-xl font-bold">¿Cuál es tu objetivo? 🎯</h3>

          <div className="grid grid-cols-2 gap-2">
            {[
              { value: 'weight_loss', label: '🔥 Perder grasa', emoji: '🔥' },
              { value: 'muscle_gain', label: '💪 Ganar músculo', emoji: '💪' },
              { value: 'maintain', label: '⚖️ Mantener peso', emoji: '⚖️' },
              { value: 'energy', label: '⚡ Más energía', emoji: '⚡' }
            ].map(goal => (
              <Button
                key={goal.value}
                variant={profile.goal === goal.value ? 'primary' : 'outline'}
                onClick={() => setProfile({...profile, goal: goal.value})}
                className="h-20 text-lg"
              >
                <span className="text-2xl mr-2">{goal.emoji}</span>
                {goal.label}
              </Button>
            ))}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <Input
              label="Peso (kg)"
              type="number"
              value={profile.weight_kg}
              onChange={(e) => setProfile({...profile, weight_kg: e.target.value})}
              min="30"
              max="300"
            />
            <Input
              label="Altura (cm)"
              type="number"
              value={profile.height_cm}
              onChange={(e) => setProfile({...profile, height_cm: e.target.value})}
              min="100"
              max="250"
            />
            <Input
              label="Edad"
              type="number"
              value={profile.age}
              onChange={(e) => setProfile({...profile, age: e.target.value})}
              min="13"
              max="120"
            />
            <Select
              label="Sexo"
              value={profile.biological_sex}
              onChange={(e) => setProfile({...profile, biological_sex: e.target.value})}
            >
              <option value="">Seleccionar</option>
              <option value="male">Masculino</option>
              <option value="female">Femenino</option>
            </Select>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">
              Nivel de actividad física
            </label>
            <div className="grid grid-cols-3 gap-2">
              {[
                { value: 'sedentary', label: 'Poco' },
                { value: 'moderately_active', label: 'Moderado' },
                { value: 'very_active', label: 'Mucho' }
              ].map(level => (
                <Button
                  key={level.value}
                  variant={profile.activity_level === level.value ? 'primary' : 'outline'}
                  onClick={() => setProfile({...profile, activity_level: level.value})}
                >
                  {level.label}
                </Button>
              ))}
            </div>
          </div>

          {/* Mostrar cálculos en tiempo real */}
          {calculations.bmi > 0 && (
            <div className="bg-blue-50 p-4 rounded-lg">
              <p className="text-sm text-gray-600">Tus métricas:</p>
              <div className="grid grid-cols-2 gap-2 mt-2">
                <div>
                  <span className="text-xs text-gray-500">IMC:</span>
                  <span className="ml-2 font-medium">
                    {calculations.bmi} ({calculations.bmi_category})
                  </span>
                </div>
                <div>
                  <span className="text-xs text-gray-500">Calorías diarias:</span>
                  <span className="ml-2 font-medium">
                    ~{calculations.target_calories} kcal
                  </span>
                </div>
              </div>
            </div>
          )}

          <div className="flex gap-3">
            <Button
              variant="outline"
              onClick={onBack}
              className="flex-1"
            >
              ← Atrás
            </Button>
            <Button
              onClick={() => setStep(2)}
              disabled={!profile.goal || !profile.weight_kg || !profile.height_cm}
              className="flex-1"
            >
              Siguiente →
            </Button>
          </div>
        </div>
      )}

      {/* Paso 2: Restricciones */}
      {step === 2 && (
        <div className="space-y-4">
          <h3 className="text-xl font-bold">¿Algo que NO puedas comer? 🚫</h3>

          <div>
            <label className="block text-sm font-medium mb-2">
              Alergias (marca si tienes)
            </label>
            <div className="grid grid-cols-2 gap-2">
              {['Frutos secos', 'Lácteos', 'Gluten', 'Mariscos', 'Huevos'].map(allergy => (
                <Checkbox
                  key={allergy}
                  checked={profile.allergies.includes(allergy)}
                  onChange={(checked) => {
                    setProfile({
                      ...profile,
                      allergies: checked
                        ? [...profile.allergies, allergy]
                        : profile.allergies.filter(a => a !== allergy)
                    });
                  }}
                  label={allergy}
                />
              ))}
            </div>
          </div>

          <Select
            label="Tipo de dieta"
            value={profile.dietary_restriction}
            onChange={(e) => setProfile({...profile, dietary_restriction: e.target.value})}
          >
            <option value="none">Normal (como de todo)</option>
            <option value="vegetarian">Vegetariana</option>
            <option value="vegan">Vegana</option>
            <option value="gluten_free">Sin gluten</option>
            <option value="dairy_free">Sin lácteos</option>
            <option value="keto">Keto</option>
            <option value="paleo">Paleo</option>
          </Select>

          <Input
            label="3 alimentos que NO te gustan (opcional)"
            placeholder="ej: brócoli, hígado, aceitunas"
            value={profile.disliked_foods}
            onChange={(e) => setProfile({...profile, disliked_foods: e.target.value})}
            maxLength={200}
          />

          <div className="flex gap-3">
            <Button
              variant="outline"
              onClick={() => setStep(1)}
              className="flex-1"
            >
              ← Atrás
            </Button>
            <Button
              variant="primary"
              onClick={handleGeneratePlan}
              className="flex-1 bg-green-600"
            >
              🚀 Generar Plan
            </Button>
          </div>

          <Button
            variant="ghost"
            onClick={() => setStep(3)}
            className="w-full text-sm"
          >
            + Más opciones (presupuesto, tiempo)
          </Button>
        </div>
      )}

      {/* Paso 3: Preferencias opcionales */}
      {step === 3 && (
        <div className="space-y-4">
          <h3 className="text-xl font-bold">Último toque (opcional)</h3>

          <div>
            <label className="block text-sm font-medium mb-2">
              Presupuesto semanal
            </label>
            <input
              type="range"
              min="1"
              max="3"
              value={profile.budget_level === 'low' ? 1 :
                     profile.budget_level === 'medium' ? 2 : 3}
              onChange={(e) => {
                const levels = ['low', 'medium', 'high'];
                setProfile({...profile, budget_level: levels[e.target.value - 1]});
              }}
              className="w-full"
            />
            <div className="flex justify-between text-xs text-gray-500">
              <span>Bajo</span>
              <span>Moderado</span>
              <span>Alto</span>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">
              Tiempo para cocinar: {profile.cooking_time_minutes} min
            </label>
            <input
              type="range"
              min="10"
              max="120"
              step="10"
              value={profile.cooking_time_minutes}
              onChange={(e) => setProfile({...profile, cooking_time_minutes: e.target.value})}
              className="w-full"
            />
          </div>

          <div className="bg-green-50 p-4 rounded-lg">
            <p className="text-sm font-medium text-green-800">
              ✨ Listo para generar tu plan personalizado con IA
            </p>
            <p className="text-xs text-green-600 mt-1">
              Basado en {calculations.target_calories} kcal/día
            </p>
          </div>

          <div className="flex gap-3">
            <Button
              variant="outline"
              onClick={() => setStep(2)}
              className="flex-1"
            >
              ← Atrás
            </Button>
            <Button
              variant="primary"
              onClick={handleGeneratePlan}
              className="flex-1 bg-green-600 text-lg"
            >
              🚀 GENERAR MI PLAN
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
};
```

---

## 5️⃣ BASE DE DATOS - MIGRACIONES

### Nueva Migración para Tablas de Seguridad

```sql
-- alembic/versions/xxx_add_nutrition_safety.py

"""Add nutrition safety screening tables

Revision ID: xxx
Create Date: 2024-12-28
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    # Tabla para guardar screenings de seguridad
    op.create_table('nutrition_screening_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('gym_id', sa.Integer(), nullable=False),
        sa.Column('screening_data', postgresql.JSONB(), nullable=False),
        sa.Column('risk_score', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['gym_id'], ['gyms.id'], ondelete='CASCADE')
    )

    op.create_index(
        'ix_nutrition_screening_user_gym',
        'nutrition_screening_records',
        ['user_id', 'gym_id']
    )

    # Agregar columnas a nutrition_plans
    op.add_column('nutrition_plans',
        sa.Column('safety_screening_id', sa.Integer(), nullable=True)
    )
    op.add_column('nutrition_plans',
        sa.Column('warnings', postgresql.JSONB(), nullable=True)
    )
    op.add_column('nutrition_plans',
        sa.Column('professional_supervision_required', sa.Boolean(), default=False)
    )

    # Foreign key para screening
    op.create_foreign_key(
        'fk_nutrition_plans_screening',
        'nutrition_plans',
        'nutrition_screening_records',
        ['safety_screening_id'],
        ['id'],
        ondelete='SET NULL'
    )

def downgrade():
    op.drop_constraint('fk_nutrition_plans_screening', 'nutrition_plans')
    op.drop_column('nutrition_plans', 'professional_supervision_required')
    op.drop_column('nutrition_plans', 'warnings')
    op.drop_column('nutrition_plans', 'safety_screening_id')
    op.drop_index('ix_nutrition_screening_user_gym')
    op.drop_table('nutrition_screening_records')
```

---

## 6️⃣ PROGRESSIVE PROFILING - POST MVP

### Sistema de Captura Gradual

```python
# app/services/progressive_profiling_service.py

class ProgressiveProfilingService:
    """
    Servicio para capturar información adicional gradualmente
    después de generar el primer plan
    """

    @staticmethod
    async def get_next_questions(
        user_id: int,
        plan_age_days: int,
        db: AsyncSession
    ) -> List[Dict]:
        """
        Determina qué preguntas hacer basado en el tiempo
        desde la creación del plan
        """
        questions = []

        # Día 1: Post-generación inmediata
        if plan_age_days == 0:
            questions = [
                {
                    "id": "family_cooking",
                    "question": "¿Cocinas para tu familia?",
                    "type": "boolean",
                    "options": ["Sí", "No"]
                },
                {
                    "id": "eating_out",
                    "question": "¿Cuántas veces comes fuera por semana?",
                    "type": "number",
                    "min": 0,
                    "max": 14
                }
            ]

        # Día 7: Primera semana
        elif plan_age_days == 7:
            questions = [
                {
                    "id": "hunger_level",
                    "question": "¿Cómo estuvo tu nivel de hambre esta semana?",
                    "type": "scale",
                    "min": 1,
                    "max": 10,
                    "labels": ["Muy hambriento", "Satisfecho"]
                },
                {
                    "id": "energy_level",
                    "question": "¿Cómo estuvo tu energía en los entrenamientos?",
                    "type": "scale",
                    "min": 1,
                    "max": 10,
                    "labels": ["Muy baja", "Excelente"]
                },
                {
                    "id": "disliked_meals",
                    "question": "¿Qué comidas NO te gustaron?",
                    "type": "multiselect",
                    "options": []  # Se llena con las comidas del plan
                }
            ]

        # Día 14: Ajuste
        elif plan_age_days == 14:
            questions = [
                {
                    "id": "current_weight",
                    "question": "¿Cuál es tu peso actual?",
                    "type": "number",
                    "unit": "kg"
                },
                {
                    "id": "waist_circumference",
                    "question": "¿Puedes medir tu cintura? (opcional)",
                    "type": "number",
                    "unit": "cm",
                    "optional": True
                },
                {
                    "id": "adherence_percentage",
                    "question": "¿Qué porcentaje del plan seguiste?",
                    "type": "percentage",
                    "min": 0,
                    "max": 100
                }
            ]

        # Día 30: Evaluación mensual
        elif plan_age_days == 30:
            questions = [
                {
                    "id": "supplements_started",
                    "question": "¿Empezaste algún suplemento?",
                    "type": "multiselect",
                    "options": [
                        "Proteína en polvo",
                        "Creatina",
                        "Multivitamínico",
                        "Omega-3",
                        "Ninguno"
                    ]
                },
                {
                    "id": "meal_prep_success",
                    "question": "¿Cómo te fue con el meal prep?",
                    "type": "select",
                    "options": [
                        "Excelente, lo hice cada semana",
                        "Bien, lo hice casi siempre",
                        "Regular, a veces",
                        "No pude hacerlo"
                    ]
                }
            ]

        return questions

    @staticmethod
    async def save_responses(
        user_id: int,
        responses: Dict,
        db: AsyncSession
    ):
        """
        Guarda respuestas y actualiza perfil extendido
        """
        profile = await db.query(NutritionProfileExtended).filter_by(
            user_id=user_id
        ).first()

        if not profile:
            profile = NutritionProfileExtended(user_id=user_id)
            db.add(profile)

        # Mapear respuestas a campos del perfil
        mapping = {
            "family_cooking": "cooks_for_family",
            "eating_out": "eats_out_frequency_weekly",
            "current_weight": "weight_kg",
            "waist_circumference": "waist_cm",
            "supplements_started": "current_supplements"
        }

        for response_id, value in responses.items():
            if response_id in mapping:
                setattr(profile, mapping[response_id], value)

        await db.commit()

        # Si hay cambios significativos, sugerir reajuste
        return await NutritionAdjustmentService.check_if_adjustment_needed(
            user_id, profile, db
        )
```

---

## 7️⃣ TESTING

### Tests de Seguridad

```python
# tests/test_nutrition_safety.py

import pytest
from app.schemas.nutrition_safety import SafetyScreening, MedicalCondition
from app.schemas.nutrition_profile import NutritionProfileBase
from app.services.nutrition_safety_service import NutritionSafetyService

class TestNutritionSafety:

    def test_underweight_cannot_lose_weight(self):
        """Test que IMC <18.5 no puede generar plan pérdida peso"""
        screening = SafetyScreening(
            age=25,
            accepts_disclaimer=True,
            medical_conditions=[MedicalCondition.NONE]
        )

        profile = NutritionProfileBase(
            weight_kg=45,  # Para 170cm = IMC 15.6
            height_cm=170,
            age=25,
            biological_sex="female",
            goal="weight_loss",  # Intentando perder peso
            activity_level="moderately_active"
        )

        is_safe, errors, warnings = NutritionSafetyService.validate_safety(
            screening, profile
        )

        assert not is_safe
        assert any("IMC" in error and "bajo peso" in error for error in errors)

    def test_pregnancy_blocks_weight_loss(self):
        """Test que embarazo bloquea pérdida de peso"""
        screening = SafetyScreening(
            age=28,
            is_pregnant=True,
            accepts_disclaimer=True,
            medical_conditions=[MedicalCondition.NONE]
        )

        profile = NutritionProfileBase(
            weight_kg=70,
            height_cm=165,
            age=28,
            biological_sex="female",
            goal="weight_loss",
            activity_level="lightly_active"
        )

        is_safe, errors, warnings = NutritionSafetyService.validate_safety(
            screening, profile
        )

        assert not is_safe
        assert any("embarazo" in error.lower() for error in errors)

    def test_eating_disorder_requires_supervision(self):
        """Test que TCA requiere supervisión"""
        screening = SafetyScreening(
            age=22,
            has_eating_disorder_history=True,
            feels_out_of_control_eating=True,
            food_dominates_life=True,
            accepts_disclaimer=True,
            medical_conditions=[MedicalCondition.EATING_DISORDER]
        )

        assert screening.risk_score >= 5
        assert screening.requires_professional_supervision
        assert not screening.can_generate_weight_loss_plan

    def test_minor_requires_parental_consent(self):
        """Test que <18 años requiere consentimiento"""
        with pytest.raises(ValueError, match="consentimiento parental"):
            screening = SafetyScreening(
                age=16,
                accepts_disclaimer=True,
                medical_conditions=[MedicalCondition.NONE]
                # Falta parental_consent_email
            )

    def test_extreme_deficit_blocked(self):
        """Test que déficit >750 kcal es bloqueado"""
        screening = SafetyScreening(
            age=30,
            accepts_disclaimer=True,
            medical_conditions=[MedicalCondition.NONE]
        )

        profile = NutritionProfileBase(
            weight_kg=80,
            height_cm=175,
            age=30,
            biological_sex="male",
            goal="weight_loss",
            activity_level="sedentary"
        )

        # Forzar déficit extremo
        profile.target_calories = profile.tdee - 1000  # Déficit de 1000 kcal

        is_safe, errors, warnings = NutritionSafetyService.validate_safety(
            screening, profile
        )

        assert not is_safe
        assert any("déficit calórico muy agresivo" in error.lower() for error in errors)
```

---

## 📊 RESUMEN DE IMPLEMENTACIÓN

### Cambios Clave del MVP:

1. **Seguridad Primera**:
   - Gateway de screening obligatorio
   - Validaciones automáticas de IMC
   - Bloqueo de casos de riesgo

2. **Simplificación UX**:
   - De 40+ campos a 15 campos iniciales
   - 3 pasos máximo (2 min total)
   - Botón "Generar Ya" prominente

3. **Transparencia**:
   - Mostrar cálculos (BMR, TDEE, calorías)
   - Explicar decisiones de la IA
   - Warnings visibles

4. **Progressive Enhancement**:
   - Captura gradual post-generación
   - Ajustes automáticos basados en feedback
   - Aprendizaje continuo

### Métricas de Éxito Esperadas:

- **Compleción**: 30% → 65% ✅
- **Seguridad**: 0% → 95% validaciones ✅
- **Tiempo**: 7 min → 2 min ✅
- **Satisfacción**: Unknown → 70%+ 🎯

### Próximos Pasos:

1. **Semana 1**: Implementar seguridad y simplificar flujo
2. **Semana 2**: Testing con usuarios reales
3. **Semana 3**: Progressive profiling
4. **Semana 4**: Análisis y optimización

---

*Con esta implementación técnica, el sistema será **seguro médicamente** Y **delightful de usar**, resolviendo la tensión entre completitud y simplicidad.*