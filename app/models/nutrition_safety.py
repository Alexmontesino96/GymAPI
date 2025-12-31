"""
Modelos de base de datos para el sistema de seguridad nutricional
"""

from sqlalchemy import (
    Column, Integer, String, Boolean, Float, DateTime,
    ForeignKey, JSON, Text, Enum as SQLEnum
)
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
import enum

from app.db.base import Base


class RiskLevel(enum.Enum):
    """Niveles de riesgo médico"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SafetyScreening(Base):
    """
    Almacena evaluaciones de seguridad médica para planes nutricionales.
    CRÍTICO: Registro de auditoría para cumplimiento legal.
    """
    __tablename__ = "nutrition_safety_screenings"

    # Identificadores
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    gym_id = Column(Integer, ForeignKey("gyms.id"), nullable=False, index=True)

    # Datos demográficos
    age = Column(Integer, nullable=False)
    weight = Column(Float, nullable=False)  # en kg
    height = Column(Float, nullable=False)  # en cm
    sex = Column(String(10), nullable=False)  # male/female/other

    # Condiciones médicas (almacenado como JSON array)
    medical_conditions = Column(JSON, default=list)  # ["diabetes", "hypertension", etc]

    # Estados especiales
    is_pregnant = Column(Boolean, default=False, nullable=False)
    is_breastfeeding = Column(Boolean, default=False, nullable=False)

    # Medicamentos
    takes_medications = Column(Boolean, default=False, nullable=False)
    medication_list = Column(Text, nullable=True)

    # Historial
    has_eating_disorder_history = Column(Boolean, default=False, nullable=False)
    other_conditions_text = Column(Text, nullable=True)

    # Evaluación de riesgo
    risk_score = Column(Integer, nullable=False)  # 0-10
    risk_level = Column(String(20), nullable=False, index=True)  # Usando String en lugar de Enum para evitar conflictos
    can_proceed = Column(Boolean, default=True, nullable=False)
    requires_professional = Column(Boolean, default=False, nullable=False)

    # Warnings y recomendaciones (JSON array)
    warnings = Column(JSON, default=list)
    professional_referral_reasons = Column(JSON, default=list)
    recommended_specialists = Column(JSON, default=list)

    # Control parental (para menores)
    parental_consent_email = Column(String(255), nullable=True)
    parental_consent_token = Column(String(36), nullable=True, unique=True)
    parental_consent_verified = Column(Boolean, default=False, nullable=False)
    parental_consent_verified_at = Column(DateTime(timezone=True), nullable=True)

    # Consentimientos
    accepts_disclaimer = Column(Boolean, default=False, nullable=False)
    disclaimer_version = Column(String(20), default="1.0")

    # Timestamps y expiración
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    last_updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    # Metadata de auditoría
    ip_address = Column(String(45), nullable=True)  # IPv6 max length
    user_agent = Column(Text, nullable=True)
    client_platform = Column(String(50), nullable=True)  # web/ios/android

    # Relaciones
    user = relationship("User", backref="safety_screenings")
    gym = relationship("Gym", backref="safety_screenings")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Auto-calcular expiración si no se proporciona (24 horas default)
        if not self.expires_at:
            self.expires_at = datetime.utcnow() + timedelta(hours=24)

    def is_expired(self) -> bool:
        """Verifica si el screening ha expirado"""
        return datetime.utcnow() > self.expires_at

    def is_high_risk(self) -> bool:
        """Verifica si es de alto riesgo"""
        return self.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]

    def can_generate_weight_loss(self) -> bool:
        """Determina si puede generar planes de pérdida de peso"""
        if self.is_pregnant or self.is_breastfeeding:
            return False
        if self.has_eating_disorder_history:
            return False
        if self.risk_level == RiskLevel.CRITICAL:
            return False
        # Verificar IMC
        if self.height > 0:
            height_m = self.height / 100
            bmi = self.weight / (height_m ** 2)
            if bmi < 18.5:  # Bajo peso
                return False
        if self.age < 18:  # Menores
            return False
        return True

    def to_dict(self) -> dict:
        """Convierte a diccionario para serialización"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'gym_id': self.gym_id,
            'age': self.age,
            'risk_score': self.risk_score,
            'risk_level': self.risk_level.value if self.risk_level else None,
            'can_proceed': self.can_proceed,
            'requires_professional': self.requires_professional,
            'warnings': self.warnings or [],
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'is_expired': self.is_expired(),
            'can_generate_weight_loss': self.can_generate_weight_loss()
        }


class SafetyAuditLog(Base):
    """
    Log de auditoría para todas las generaciones con IA.
    CRÍTICO: Para cumplimiento legal y trazabilidad.
    """
    __tablename__ = "nutrition_safety_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    gym_id = Column(Integer, ForeignKey("gyms.id"), nullable=False, index=True)
    screening_id = Column(Integer, ForeignKey("nutrition_safety_screenings.id"), nullable=True)

    # Tipo de acción
    action_type = Column(String(50), nullable=False)  # "ai_generation", "plan_creation", "safety_override"
    action_details = Column(JSON, nullable=True)

    # Resultado
    was_allowed = Column(Boolean, nullable=False)
    denial_reason = Column(Text, nullable=True)

    # Plan generado (si aplica)
    generated_plan_id = Column(Integer, ForeignKey("nutrition_plans.id"), nullable=True)

    # IA metadata
    ai_model_used = Column(String(50), nullable=True)  # "gpt-4o-mini"
    ai_prompt_hash = Column(String(64), nullable=True)  # Hash del prompt para auditoría
    ai_response_summary = Column(Text, nullable=True)
    ai_cost_estimate = Column(Float, nullable=True)  # En USD

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    # Metadata
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)

    # Relaciones
    user = relationship("User", backref="safety_audit_logs")
    gym = relationship("Gym", backref="audit_logs")
    screening = relationship("SafetyScreening", backref="audit_logs")

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'user_id': self.user_id,
            'gym_id': self.gym_id,
            'action_type': self.action_type,
            'was_allowed': self.was_allowed,
            'denial_reason': self.denial_reason,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }