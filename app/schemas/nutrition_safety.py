"""
Schemas para el sistema de seguridad nutricional
"""

from pydantic import BaseModel, Field, validator, EmailStr
from typing import Optional, List, Dict, Literal
from datetime import datetime
from enum import Enum


class MedicalCondition(str, Enum):
    """Condiciones médicas relevantes para nutrición"""
    DIABETES = "diabetes"
    HEART_CONDITION = "heart_condition"
    KIDNEY_DISEASE = "kidney_disease"
    LIVER_DISEASE = "liver_disease"
    EATING_DISORDER = "eating_disorder"
    THYROID_DISORDER = "thyroid_disorder"
    HYPERTENSION = "hypertension"
    HIGH_CHOLESTEROL = "high_cholesterol"
    NONE = "none"


class RiskLevel(str, Enum):
    """Niveles de riesgo"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ==================== REQUEST SCHEMAS ====================

class SafetyScreeningRequest(BaseModel):
    """Request para screening de seguridad (Paso 0)"""

    # Edad (requerido para validaciones)
    age: int = Field(..., ge=13, le=120, description="Edad del usuario")

    # Condiciones médicas (checkboxes)
    has_diabetes: bool = Field(False, description="Tiene diabetes tipo 1 o 2")
    has_heart_condition: bool = Field(False, description="Problemas cardíacos o presión alta")
    has_kidney_disease: bool = Field(False, description="Enfermedad renal")
    has_liver_disease: bool = Field(False, description="Enfermedad hepática")
    has_eating_disorder: bool = Field(False, description="Historial de trastorno alimentario")
    has_other_condition: bool = Field(False, description="Otra condición médica relevante")
    other_condition_details: Optional[str] = Field(None, max_length=500)

    # Estado especial
    is_pregnant: bool = Field(False, description="Está embarazada")
    is_breastfeeding: bool = Field(False, description="Está en período de lactancia")

    # Consentimientos
    accepts_disclaimer: bool = Field(..., description="Acepta el disclaimer legal")
    parental_consent_email: Optional[EmailStr] = Field(
        None,
        description="Email del padre/tutor si es menor de 18"
    )

    # Metadata opcional
    timezone: Optional[str] = Field("UTC", description="Zona horaria del usuario")
    language: Optional[str] = Field("es", description="Idioma preferido")

    @validator('age')
    def validate_age(cls, v):
        if v < 13:
            raise ValueError("La edad mínima es 13 años")
        return v

    @validator('parental_consent_email')
    def validate_parental_consent(cls, v, values):
        age = values.get('age')
        if age and age < 18 and not v:
            raise ValueError("Menores de 18 años requieren email de consentimiento parental")
        return v

    @validator('other_condition_details')
    def validate_other_condition(cls, v, values):
        if values.get('has_other_condition') and not v:
            raise ValueError("Por favor especifica la condición médica")
        return v

    class Config:
        schema_extra = {
            "example": {
                "age": 25,
                "has_diabetes": False,
                "has_heart_condition": False,
                "has_kidney_disease": False,
                "has_liver_disease": False,
                "has_eating_disorder": False,
                "has_other_condition": False,
                "is_pregnant": False,
                "is_breastfeeding": False,
                "accepts_disclaimer": True,
                "parental_consent_email": None,
                "timezone": "America/Mexico_City",
                "language": "es"
            }
        }


class ParentalConsentVerification(BaseModel):
    """Request para verificar consentimiento parental"""
    token: str = Field(..., min_length=36, max_length=36, description="Token UUID enviado por email")

    class Config:
        schema_extra = {
            "example": {
                "token": "550e8400-e29b-41d4-a716-446655440000"
            }
        }


# ==================== RESPONSE SCHEMAS ====================

class SafetyWarning(BaseModel):
    """Advertencia de seguridad individual"""
    level: RiskLevel
    message: str
    recommendation: Optional[str] = None
    requires_action: bool = False


class SafetyScreeningResponse(BaseModel):
    """Response del screening de seguridad"""
    screening_id: int = Field(..., description="ID del screening para referencia futura")
    risk_score: int = Field(..., ge=0, le=10, description="Score de riesgo calculado (0-10)")
    risk_level: RiskLevel = Field(..., description="Nivel de riesgo categorizado")
    can_proceed: bool = Field(..., description="Si puede continuar con la creación del plan")
    requires_professional: bool = Field(..., description="Si requiere supervisión profesional")
    warnings: List[SafetyWarning] = Field(
        default_factory=list,
        description="Lista de advertencias de seguridad"
    )
    next_step: Literal["profile", "professional_referral", "parental_consent"] = Field(
        ...,
        description="Siguiente paso en el flujo"
    )
    expires_at: datetime = Field(..., description="Cuándo expira este screening")
    expires_in_hours: int = Field(24, description="Horas hasta expiración")

    # Si requiere consentimiento parental
    parental_consent_required: bool = False
    parental_consent_sent_to: Optional[str] = None

    # Si requiere derivación profesional
    professional_referral_reasons: List[str] = Field(default_factory=list)
    recommended_specialists: List[str] = Field(default_factory=list)

    class Config:
        schema_extra = {
            "example": {
                "screening_id": 123,
                "risk_score": 2,
                "risk_level": "low",
                "can_proceed": True,
                "requires_professional": False,
                "warnings": [
                    {
                        "level": "medium",
                        "message": "IMC indica sobrepeso",
                        "recommendation": "Considera supervisión profesional para mejores resultados",
                        "requires_action": False
                    }
                ],
                "next_step": "profile",
                "expires_at": "2024-12-29T10:00:00Z",
                "expires_in_hours": 24,
                "parental_consent_required": False,
                "professional_referral_reasons": [],
                "recommended_specialists": []
            }
        }


class ScreeningValidationResponse(BaseModel):
    """Response de validación de screening"""
    valid: bool
    screening_id: int
    can_proceed: bool
    risk_score: int
    reason: Optional[str] = None
    hours_remaining: Optional[float] = None

    class Config:
        schema_extra = {
            "example": {
                "valid": True,
                "screening_id": 123,
                "can_proceed": True,
                "risk_score": 2,
                "reason": None,
                "hours_remaining": 22.5
            }
        }


class ProfessionalReferralInfo(BaseModel):
    """Información de derivación a profesional"""
    required: bool
    reasons: List[str]
    specialist_types: List[str]
    urgency: Literal["immediate", "soon", "routine"]
    message: str
    resources: List[Dict[str, str]]

    class Config:
        schema_extra = {
            "example": {
                "required": True,
                "reasons": [
                    "Historial de trastorno alimentario",
                    "IMC extremadamente bajo"
                ],
                "specialist_types": [
                    "Nutricionista clínico",
                    "Psicólogo especializado en TCA"
                ],
                "urgency": "soon",
                "message": "Tu condición requiere atención profesional especializada",
                "resources": [
                    {
                        "name": "Asociación de Nutricionistas",
                        "url": "https://ejemplo.com/nutricionistas",
                        "type": "directory"
                    }
                ]
            }
        }


# ==================== CALCULATION SCHEMAS ====================

class RiskCalculation(BaseModel):
    """Cálculo detallado del riesgo"""
    base_score: int
    medical_conditions_score: int
    special_conditions_score: int
    age_factor_score: int
    total_score: int
    risk_level: RiskLevel
    factors: List[str]

    class Config:
        schema_extra = {
            "example": {
                "base_score": 0,
                "medical_conditions_score": 2,
                "special_conditions_score": 3,
                "age_factor_score": 0,
                "total_score": 5,
                "risk_level": "medium",
                "factors": [
                    "Diabetes presente (+2)",
                    "Embarazo detectado (+3)"
                ]
            }
        }


# ==================== DATABASE SCHEMAS ====================

class SafetyScreeningDB(BaseModel):
    """Schema para almacenamiento en DB"""
    id: int
    user_id: int
    gym_id: int
    age: int
    medical_conditions: Dict[str, bool]
    is_pregnant: bool
    is_breastfeeding: bool
    accepts_disclaimer: bool
    parental_consent_email: Optional[str]
    parental_consent_token: Optional[str]
    parental_consent_verified: bool
    risk_score: int
    risk_level: RiskLevel
    can_proceed: bool
    requires_professional: bool
    warnings: List[SafetyWarning]
    created_at: datetime
    expires_at: datetime
    ip_address: Optional[str]
    user_agent: Optional[str]

    class Config:
        orm_mode = True


# ==================== ERROR SCHEMAS ====================

class SafetyError(BaseModel):
    """Error relacionado con seguridad"""
    error_code: str
    message: str
    details: Optional[Dict] = None

    class Config:
        schema_extra = {
            "example": {
                "error_code": "SCREENING_EXPIRED",
                "message": "El screening de seguridad ha expirado",
                "details": {
                    "screening_id": 123,
                    "expired_at": "2024-12-28T10:00:00Z"
                }
            }
        }


# ==================== UTILITY FUNCTIONS ====================

def calculate_risk_score(screening: SafetyScreeningRequest) -> tuple[int, RiskLevel]:
    """
    Calcula el score de riesgo basado en las respuestas
    Returns: (score, risk_level)
    """
    score = 0

    # Condiciones médicas graves (+2 cada una)
    if screening.has_diabetes:
        score += 2
    if screening.has_heart_condition:
        score += 2
    if screening.has_kidney_disease:
        score += 2
    if screening.has_eating_disorder:
        score += 3  # Mayor peso para TCA

    # Condiciones médicas moderadas (+1 cada una)
    if screening.has_liver_disease:
        score += 1
    if screening.has_other_condition:
        score += 1

    # Estados especiales
    if screening.is_pregnant:
        score += 3
    if screening.is_breastfeeding:
        score += 2

    # Factor edad
    if screening.age < 16:
        score += 2
    elif screening.age < 18:
        score += 1
    elif screening.age > 65:
        score += 1
    elif screening.age > 70:
        score += 2

    # Limitar a máximo 10
    score = min(score, 10)

    # Determinar nivel
    if score <= 2:
        level = RiskLevel.LOW
    elif score <= 4:
        level = RiskLevel.MEDIUM
    elif score <= 7:
        level = RiskLevel.HIGH
    else:
        level = RiskLevel.CRITICAL

    return score, level


def generate_safety_warnings(
    screening: SafetyScreeningRequest,
    risk_score: int,
    risk_level: RiskLevel
) -> List[SafetyWarning]:
    """
    Genera las advertencias de seguridad basadas en el screening
    """
    warnings = []

    if screening.has_diabetes:
        warnings.append(SafetyWarning(
            level=RiskLevel.MEDIUM,
            message="Diabetes requiere manejo cuidadoso de carbohidratos",
            recommendation="Monitorea tu glucosa regularmente y ajusta el plan según necesites",
            requires_action=False
        ))

    if screening.has_heart_condition:
        warnings.append(SafetyWarning(
            level=RiskLevel.MEDIUM,
            message="Condición cardíaca puede requerir restricción de sodio",
            recommendation="Consulta con tu cardiólogo sobre límites de sodio",
            requires_action=False
        ))

    if screening.is_pregnant:
        warnings.append(SafetyWarning(
            level=RiskLevel.HIGH,
            message="El embarazo requiere nutrición especializada",
            recommendation="Este plan debe ser revisado por tu obstetra o nutricionista",
            requires_action=True
        ))

    if screening.has_eating_disorder:
        warnings.append(SafetyWarning(
            level=RiskLevel.CRITICAL,
            message="Historial de TCA requiere supervisión profesional",
            recommendation="Trabaja con un equipo especializado en trastornos alimentarios",
            requires_action=True
        ))

    if risk_score >= 5:
        warnings.append(SafetyWarning(
            level=risk_level,
            message="Múltiples factores de riesgo detectados",
            recommendation="Considera fuertemente supervisión profesional",
            requires_action=risk_score >= 7
        ))

    return warnings