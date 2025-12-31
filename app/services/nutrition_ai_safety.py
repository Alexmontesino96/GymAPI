"""
Servicio de seguridad médica para el módulo de IA nutricional.
CRÍTICO: Este servicio debe ejecutarse ANTES de cualquier generación de planes con IA.
"""

from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime, date
from enum import Enum
from sqlalchemy.orm import Session
import logging

from app.models.user import User
from app.models.nutrition import NutritionGoal

logger = logging.getLogger(__name__)


class MedicalCondition(str, Enum):
    """Condiciones médicas relevantes para nutrición"""
    NONE = "none"
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
    PREGNANCY = "pregnancy"
    BREASTFEEDING = "breastfeeding"


class RiskLevel(str, Enum):
    """Niveles de riesgo médico"""
    LOW = "low"           # 0-2 puntos: Puede proceder normalmente
    MODERATE = "moderate" # 3-4 puntos: Proceder con precauciones
    HIGH = "high"        # 5-7 puntos: Requiere supervisión recomendada
    CRITICAL = "critical" # 8+ puntos: Requiere supervisión obligatoria


class SafetyScreening:
    """Modelo de screening de seguridad médica"""

    def __init__(
        self,
        age: int,
        weight: float,
        height: float,
        sex: str,
        is_pregnant: bool = False,
        is_breastfeeding: bool = False,
        medical_conditions: List[MedicalCondition] = None,
        takes_medications: bool = False,
        medication_list: Optional[str] = None,
        has_eating_disorder_history: bool = False,
        goal: NutritionGoal = NutritionGoal.MAINTAIN
    ):
        self.age = age
        self.weight = weight
        self.height = height
        self.sex = sex
        self.is_pregnant = is_pregnant
        self.is_breastfeeding = is_breastfeeding
        self.medical_conditions = medical_conditions or []
        self.takes_medications = takes_medications
        self.medication_list = medication_list
        self.has_eating_disorder_history = has_eating_disorder_history
        self.goal = goal

        # Calcular IMC
        self.bmi = self.calculate_bmi()

    def calculate_bmi(self) -> float:
        """Calcula el IMC (Índice de Masa Corporal)"""
        if self.height > 0:
            height_m = self.height / 100  # convertir cm a metros
            return self.weight / (height_m ** 2)
        return 0

    @property
    def risk_score(self) -> int:
        """
        Calcula el puntaje de riesgo médico (0-10).
        Mayor puntaje = mayor riesgo = más supervisión requerida.
        """
        score = 0

        # Condiciones médicas serias (+2 cada una)
        serious_conditions = [
            MedicalCondition.DIABETES_TYPE1,
            MedicalCondition.KIDNEY_DISEASE,
            MedicalCondition.HEART_DISEASE,
            MedicalCondition.EATING_DISORDER,
            MedicalCondition.CANCER
        ]

        for condition in self.medical_conditions:
            if condition in serious_conditions:
                score += 2
            elif condition != MedicalCondition.NONE:
                score += 1

        # Embarazo/lactancia (+3)
        if self.is_pregnant or self.is_breastfeeding:
            score += 3

        # Historial de trastornos alimentarios (+4)
        if self.has_eating_disorder_history:
            score += 4

        # Edad de riesgo
        if self.age < 16 or self.age > 70:
            score += 2
        elif self.age < 18 or self.age > 65:
            score += 1

        # IMC extremo
        if self.bmi < 18.5 or self.bmi > 35:
            score += 2
        elif self.bmi < 20 or self.bmi > 30:
            score += 1

        # Medicamentos (+1)
        if self.takes_medications:
            score += 1

        return min(score, 10)

    @property
    def risk_level(self) -> RiskLevel:
        """Determina el nivel de riesgo basado en el puntaje"""
        score = self.risk_score

        if score >= 8:
            return RiskLevel.CRITICAL
        elif score >= 5:
            return RiskLevel.HIGH
        elif score >= 3:
            return RiskLevel.MODERATE
        else:
            return RiskLevel.LOW

    @property
    def can_generate_weight_loss(self) -> bool:
        """Determina si es seguro generar un plan de pérdida de peso"""
        # Restricciones absolutas
        if self.is_pregnant or self.is_breastfeeding:
            return False

        if MedicalCondition.EATING_DISORDER in self.medical_conditions:
            return False

        if self.has_eating_disorder_history:
            return False

        if self.bmi < 18.5:  # Bajo peso
            return False

        if self.age < 18:  # Menores de edad
            return False

        return True


class NutritionAISafetyService:
    """
    Servicio de evaluación de seguridad médica para planes nutricionales con IA.
    """

    def __init__(self, db: Session):
        self.db = db

    async def evaluate_user_safety(
        self,
        user_id: int,
        screening_data: Dict[str, Any],
        gym_id: int
    ) -> Tuple[RiskLevel, List[str], Optional[str]]:
        """
        Evalúa el nivel de riesgo médico de un usuario.

        Args:
            user_id: ID del usuario
            screening_data: Datos del screening médico
            gym_id: ID del gimnasio

        Returns:
            Tuple de (nivel_riesgo, warnings, mensaje_derivación)
        """
        # Crear objeto de screening
        screening = SafetyScreening(**screening_data)

        warnings = []
        referral_message = None

        # Evaluaciones específicas
        if screening.is_pregnant:
            warnings.append("⚠️ Embarazo detectado - Se requieren ajustes nutricionales especiales")
            if screening.goal == NutritionGoal.WEIGHT_LOSS:
                warnings.append("🚫 Pérdida de peso no recomendada durante el embarazo")
                referral_message = "Por favor consulte con su obstetra antes de hacer cambios dietéticos"

        if screening.is_breastfeeding:
            warnings.append("⚠️ Lactancia detectada - Requerimientos calóricos aumentados")
            if screening.goal == NutritionGoal.WEIGHT_LOSS:
                warnings.append("⚠️ La restricción calórica puede afectar la producción de leche")

        # Evaluar trastornos alimentarios
        if screening.has_eating_disorder_history:
            warnings.append("🚨 Historial de trastornos alimentarios detectado")
            referral_message = "Este servicio requiere supervisión de un profesional especializado en TCA"

        # Evaluar condiciones médicas
        medical_warnings = self._evaluate_medical_conditions(screening.medical_conditions)
        warnings.extend(medical_warnings)

        # Evaluar IMC
        bmi_warnings = self._evaluate_bmi(screening.bmi, screening.goal)
        warnings.extend(bmi_warnings)

        # Evaluar edad
        if screening.age < 18:
            warnings.append("⚠️ Menor de edad - Se requiere supervisión parental")
            if not referral_message:
                referral_message = "Recomendamos supervisión de un nutricionista pediátrico"
        elif screening.age > 70:
            warnings.append("⚠️ Adulto mayor - Consideraciones nutricionales especiales")

        # Determinar mensaje de derivación final
        risk_level = screening.risk_level

        if risk_level == RiskLevel.CRITICAL and not referral_message:
            referral_message = "⛔ Supervisión médica profesional OBLIGATORIA antes de proceder"
        elif risk_level == RiskLevel.HIGH and not referral_message:
            referral_message = "⚠️ Se recomienda encarecidamente consultar con un nutricionista"
        elif risk_level == RiskLevel.MODERATE and not referral_message:
            referral_message = "💡 Considere consultar con un profesional para mejores resultados"

        # Log para auditoría
        logger.info(
            f"Safety evaluation for user {user_id} in gym {gym_id}: "
            f"{risk_level.value} (score: {screening.risk_score})"
        )

        # Guardar evaluación en base de datos
        await self._save_safety_evaluation(
            user_id, gym_id, screening, risk_level, warnings
        )

        return (risk_level, warnings, referral_message)

    def _evaluate_medical_conditions(
        self,
        conditions: List[MedicalCondition]
    ) -> List[str]:
        """Evalúa condiciones médicas y genera warnings específicos"""
        warnings = []

        condition_warnings = {
            MedicalCondition.DIABETES_TYPE1: "🩺 Diabetes Tipo 1 - Requiere ajuste de insulina con cambios dietéticos",
            MedicalCondition.DIABETES_TYPE2: "🩺 Diabetes Tipo 2 - Control de carbohidratos esencial",
            MedicalCondition.HYPERTENSION: "🩺 Hipertensión - Restricción de sodio requerida",
            MedicalCondition.HEART_DISEASE: "🩺 Enfermedad cardíaca - Dieta baja en grasas saturadas",
            MedicalCondition.KIDNEY_DISEASE: "🩺 Enfermedad renal - Control de proteínas y minerales",
            MedicalCondition.LIVER_DISEASE: "🩺 Enfermedad hepática - Restricciones específicas requeridas",
            MedicalCondition.THYROID_DISORDER: "🩺 Trastorno tiroideo - Puede afectar el metabolismo",
            MedicalCondition.PCOS: "🩺 SOP - Dieta baja en carbohidratos puede ser beneficiosa",
            MedicalCondition.CANCER: "🩺 Cáncer - Requerimientos nutricionales especiales",
            MedicalCondition.AUTOIMMUNE: "🩺 Enfermedad autoinmune - Considerar dieta antiinflamatoria",
            MedicalCondition.GASTROINTESTINAL: "🩺 Problemas GI - Ajustes en fibra y alimentos irritantes"
        }

        for condition in conditions:
            if condition in condition_warnings:
                warnings.append(condition_warnings[condition])

        return warnings

    def _evaluate_bmi(self, bmi: float, goal: NutritionGoal) -> List[str]:
        """Evalúa el IMC y genera warnings según el objetivo"""
        warnings = []

        if bmi < 18.5:
            warnings.append("⚠️ IMC bajo (<18.5) - Pérdida de peso no recomendada")
            if goal == NutritionGoal.WEIGHT_LOSS:
                warnings.append("🚫 Objetivo de pérdida de peso contraindicado con IMC bajo")
        elif bmi > 35:
            warnings.append("⚠️ IMC elevado (>35) - Se recomienda supervisión médica")
            warnings.append("💡 Pérdida de peso gradual recomendada (0.5-1kg/semana)")
        elif bmi > 30:
            warnings.append("⚠️ IMC en rango de obesidad - Enfoque gradual recomendado")

        return warnings

    async def can_generate_restrictive_plan(
        self,
        user_id: int,
        target_calories: int,
        screening: SafetyScreening
    ) -> Tuple[bool, Optional[str]]:
        """
        Determina si es seguro generar un plan con restricción calórica.

        Returns:
            Tuple de (es_seguro, mensaje_error)
        """
        # Calcular TDEE aproximado
        tdee = self._calculate_tdee(screening)
        deficit = tdee - target_calories

        # Límites de seguridad
        MAX_DEFICIT = 1000  # kcal/día máximo
        MIN_CALORIES_WOMEN = 1200
        MIN_CALORIES_MEN = 1500

        # Validar déficit
        if deficit > MAX_DEFICIT:
            return (False,
                   f"Déficit calórico demasiado agresivo ({deficit} kcal/día). "
                   f"Máximo recomendado: {MAX_DEFICIT} kcal/día")

        # Validar mínimos absolutos
        min_calories = MIN_CALORIES_MEN if screening.sex == "male" else MIN_CALORIES_WOMEN

        if target_calories < min_calories:
            return (False,
                   f"Objetivo calórico muy bajo ({target_calories} kcal). "
                   f"Mínimo recomendado: {min_calories} kcal")

        # Validar según condiciones específicas
        if screening.is_pregnant or screening.is_breastfeeding:
            min_safe = tdee - 300  # Máximo 300 kcal de déficit
            if target_calories < min_safe:
                return (False,
                       "Durante embarazo/lactancia, el déficit máximo es 300 kcal/día")

        # Validar según edad
        if screening.age < 18:
            return (False, "Planes restrictivos no recomendados para menores de 18 años")

        return (True, None)

    def _calculate_tdee(self, screening: SafetyScreening) -> int:
        """
        Calcula el TDEE (Total Daily Energy Expenditure) aproximado.
        Usa la fórmula de Mifflin-St Jeor.
        """
        # Calcular BMR (Basal Metabolic Rate)
        if screening.sex == "male":
            bmr = 10 * screening.weight + 6.25 * screening.height - 5 * screening.age + 5
        else:
            bmr = 10 * screening.weight + 6.25 * screening.height - 5 * screening.age - 161

        # Factor de actividad (asumimos sedentario para seguridad)
        activity_factor = 1.2

        # Ajustes especiales
        if screening.is_pregnant:
            bmr += 300  # Segundo trimestre promedio
        elif screening.is_breastfeeding:
            bmr += 500  # Lactancia exclusiva

        return int(bmr * activity_factor)

    async def _save_safety_evaluation(
        self,
        user_id: int,
        gym_id: int,
        screening: SafetyScreening,
        risk_level: RiskLevel,
        warnings: List[str]
    ) -> None:
        """
        Guarda la evaluación de seguridad en la base de datos para auditoría.
        """
        # TODO: Implementar modelo de DB para guardar evaluaciones
        # Por ahora, solo logging detallado
        evaluation_data = {
            'user_id': user_id,
            'gym_id': gym_id,
            'timestamp': datetime.utcnow().isoformat(),
            'risk_level': risk_level.value,
            'risk_score': screening.risk_score,
            'bmi': screening.bmi,
            'age': screening.age,
            'medical_conditions': [c.value for c in screening.medical_conditions],
            'warnings': warnings,
            'can_generate_weight_loss': screening.can_generate_weight_loss
        }

        logger.info(f"Safety evaluation saved: {evaluation_data}")

        # En producción, guardar en tabla safety_evaluations
        # safety_eval = SafetyEvaluation(**evaluation_data)
        # self.db.add(safety_eval)
        # self.db.commit()

    def get_medical_disclaimer(self, risk_level: RiskLevel) -> str:
        """
        Genera el disclaimer médico apropiado según el nivel de riesgo.
        """
        disclaimers = {
            RiskLevel.LOW: (
                "Este plan nutricional es una guía general. "
                "Consulte con su médico si experimenta cualquier síntoma adverso."
            ),
            RiskLevel.MODERATE: (
                "⚠️ AVISO IMPORTANTE: Este plan nutricional es una guía general. "
                "Dadas sus condiciones, se recomienda consultar con un profesional de salud "
                "antes de realizar cambios significativos en su dieta."
            ),
            RiskLevel.HIGH: (
                "⚠️ ADVERTENCIA: Debido a sus condiciones médicas, este plan nutricional "
                "DEBE ser supervisado por un profesional de salud. No realice cambios "
                "dietéticos sin consultar primero con su médico o nutricionista."
            ),
            RiskLevel.CRITICAL: (
                "🚨 ATENCIÓN CRÍTICA: Sus condiciones médicas requieren SUPERVISIÓN MÉDICA OBLIGATORIA. "
                "Este plan es solo una referencia y NO debe implementarse sin la aprobación y "
                "seguimiento de su equipo médico. Consulte inmediatamente con su médico."
            )
        }

        return disclaimers.get(risk_level, disclaimers[RiskLevel.LOW])