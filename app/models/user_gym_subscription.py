from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class UserGymSubscription(Base):
    """
    Tabla de vinculación entre UserGymStripeProfile y suscripciones de Stripe.
    
    Permite que un usuario tenga múltiples suscripciones activas en el mismo gym
    (ej: Plan Basic + Plan Premium simultáneamente).
    """
    __tablename__ = "user_gym_subscriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Relación con UserGymStripeProfile
    user_gym_stripe_profile_id = Column(
        Integer, 
        ForeignKey("user_gym_stripe_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Suscripción específica en Stripe
    stripe_subscription_id = Column(
        String(255), 
        nullable=False, 
        unique=True,
        index=True
    )
    
    # Plan de membresía asociado
    plan_id = Column(
        Integer,
        ForeignKey("membership_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Estado de la suscripción
    status = Column(
        String(50), 
        nullable=False, 
        default="active",
        server_default="active"
    )
    
    # Timestamps
    created_at = Column(
        DateTime, 
        nullable=False, 
        default=func.now(),
        server_default=func.now()
    )
    
    updated_at = Column(
        DateTime, 
        nullable=False, 
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now()
    )
    
    canceled_at = Column(DateTime, nullable=True)
    
    # Notas adicionales
    notes = Column(Text, nullable=True)
    
    # Relaciones
    stripe_profile = relationship(
        "UserGymStripeProfile", 
        back_populates="subscriptions"
    )
    
    plan = relationship(
        "MembershipPlan",
        back_populates="subscriptions"
    )
    
    # Índices compuestos para optimización
    __table_args__ = (
        Index('idx_user_gym_subscriptions_profile_status', 'user_gym_stripe_profile_id', 'status'),
        Index('idx_user_gym_subscriptions_plan', 'plan_id'),
        Index('idx_user_gym_subscriptions_created', 'created_at'),
        UniqueConstraint('stripe_subscription_id', name='uq_stripe_subscription_id'),
    )
    
    def __repr__(self):
        return f"<UserGymSubscription(id={self.id}, stripe_subscription_id='{self.stripe_subscription_id}', status='{self.status}')>"
    
    @property
    def is_active(self):
        """Verificar si la suscripción está activa"""
        return self.status == "active"
    
    @property
    def is_canceled(self):
        """Verificar si la suscripción está cancelada"""
        return self.status == "canceled"
    
    def cancel(self):
        """Marcar suscripción como cancelada"""
        self.status = "canceled"
        self.canceled_at = func.now()
        self.updated_at = func.now()
    
    def reactivate(self):
        """Reactivar suscripción cancelada"""
        self.status = "active"
        self.canceled_at = None
        self.updated_at = func.now() 