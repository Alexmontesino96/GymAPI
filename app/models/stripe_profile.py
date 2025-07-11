"""
Modelo para vincular usuarios con sus customers de Stripe por gym.
Soporte para arquitectura multitenant con Stripe Connect.
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base_class import Base


class UserGymStripeProfile(Base):
    """
    Vinculación entre usuarios y sus customers de Stripe por gym.
    
    Esta tabla resuelve el problema de duplicación de customers en Stripe
    manteniendo la separación multitenant necesaria.
    
    Casos de uso:
    - Un usuario puede tener múltiples customers (uno por gym)
    - Cada customer pertenece a la cuenta de Stripe Connect del gym
    - Evita duplicados dentro del mismo gym
    - Permite búsquedas eficientes
    """
    __tablename__ = "user_gym_stripe_profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    gym_id = Column(Integer, ForeignKey("gyms.id"), nullable=False, index=True)
    stripe_customer_id = Column(String(255), nullable=False, index=True)
    stripe_account_id = Column(String(255), nullable=False, index=True)  # Cuenta de Stripe Connect del gym
    email = Column(String(255), nullable=False)
    
    # 🆕 CAMPO PARA SUSCRIPCIONES
    stripe_subscription_id = Column(String(255), nullable=True, index=True)  # ID de suscripción activa
    
    # Metadatos
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Información adicional para debugging
    customer_created_at = Column(DateTime, nullable=True)  # Cuándo se creó en Stripe
    last_sync_at = Column(DateTime, nullable=True)  # Última sincronización
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('user_id', 'gym_id', name='uq_user_gym_stripe'),
        UniqueConstraint('stripe_customer_id', 'stripe_account_id', name='uq_customer_account'),
    )
    
    # Relaciones
    user = relationship("User", back_populates="stripe_profiles")
    gym = relationship("Gym", back_populates="stripe_profiles")
    subscriptions = relationship("UserGymSubscription", back_populates="stripe_profile", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<UserGymStripeProfile(user_id={self.user_id}, gym_id={self.gym_id}, customer_id={self.stripe_customer_id})>"


class GymStripeAccount(Base):
    """
    Cuenta de Stripe Connect para cada gym.
    
    Cada gym tiene su propia cuenta de Stripe Connect para:
    - Separación total de pagos
    - Cumplimiento regulatorio
    - Facturación independiente
    """
    __tablename__ = "gym_stripe_accounts"
    
    id = Column(Integer, primary_key=True, index=True)
    gym_id = Column(Integer, ForeignKey("gyms.id"), unique=True, nullable=False)
    stripe_account_id = Column(String(255), unique=True, nullable=False)
    
    # Tipo de cuenta
    account_type = Column(String(50), default="express", nullable=False)  # express, standard, custom
    
    # Estado de la cuenta
    onboarding_completed = Column(Boolean, default=False, nullable=False)
    charges_enabled = Column(Boolean, default=False, nullable=False)
    payouts_enabled = Column(Boolean, default=False, nullable=False)
    details_submitted = Column(Boolean, default=False, nullable=False)
    
    # Información adicional
    country = Column(String(2), default="US", nullable=False)  # Código ISO del país
    default_currency = Column(String(3), default="USD", nullable=False)  # Moneda por defecto
    
    # Metadatos
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Información de onboarding
    onboarding_url = Column(String(500), nullable=True)  # URL de onboarding
    onboarding_expires_at = Column(DateTime, nullable=True)  # Cuándo expira el onboarding
    
    # Relaciones
    gym = relationship("Gym", back_populates="stripe_account")
    
    def __repr__(self):
        return f"<GymStripeAccount(gym_id={self.gym_id}, account_id={self.stripe_account_id})>" 