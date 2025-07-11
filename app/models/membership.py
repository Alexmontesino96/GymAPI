from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.db.base_class import Base


class BillingInterval(str, enum.Enum):
    """
    Intervalos de facturación para los planes de membresía.
    """
    MONTH = "month"         # Mensual
    YEAR = "year"           # Anual
    ONE_TIME = "one_time"   # Pago único


class MembershipPlan(Base):
    """
    Planes de membresía para gimnasios.
    Cada gimnasio puede tener múltiples planes con diferentes precios y duraciones.
    """
    __tablename__ = "membership_plans"
    
    id = Column(Integer, primary_key=True, index=True)
    gym_id = Column(Integer, ForeignKey("gyms.id"), nullable=False, index=True)
    
    # Información básica del plan
    name = Column(String(100), nullable=False)  # "Mensual", "Anual", "Pase Día"
    description = Column(Text, nullable=True)
    
    # Pricing
    price_cents = Column(Integer, nullable=False)  # Precio en centavos (ej: 2999 = €29.99)
    currency = Column(String(3), default="EUR", nullable=False)
    billing_interval = Column(String(20), nullable=False)  # "month", "year", "one_time"
    
    # Duración y características
    duration_days = Column(Integer, nullable=False)  # Duración en días
    max_billing_cycles = Column(Integer, nullable=True)  # Máximo número de ciclos de facturación (None = ilimitado)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    
    # Integración con Stripe (se poblará en Fase 2)
    stripe_price_id = Column(String(255), nullable=True, unique=True, index=True)
    stripe_product_id = Column(String(255), nullable=True, index=True)
    
    # Metadatos
    features = Column(Text, nullable=True)  # JSON string con características del plan
    max_bookings_per_month = Column(Integer, nullable=True)  # Límite de reservas mensuales
    
    # Fechas
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    gym = relationship("Gym", back_populates="membership_planes")
    subscriptions = relationship("UserGymSubscription", back_populates="plan", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<MembershipPlan(id={self.id}, name='{self.name}', gym_id={self.gym_id})>"
    
    @property
    def price_amount(self) -> float:
        """Convertir precio de centavos a la unidad principal de la moneda"""
        return self.price_cents / 100.0
    
    @property
    def is_recurring(self) -> bool:
        """Verificar si es un plan recurrente"""
        return self.billing_interval in ["month", "year"]
    
    @property
    def is_limited_duration(self) -> bool:
        """Verificar si tiene duración limitada (número máximo de ciclos)"""
        return self.max_billing_cycles is not None and self.max_billing_cycles > 0
    
    @property
    def total_duration_days(self) -> int:
        """Calcular duración total en días si tiene ciclos limitados"""
        if not self.is_limited_duration:
            return self.duration_days
        
        # Calcular duración total basada en ciclos
        if self.billing_interval == "month":
            return self.max_billing_cycles * 30  # Aproximación
        elif self.billing_interval == "year":
            return self.max_billing_cycles * 365
        else:
            return self.duration_days  # Para one_time
    
    @property
    def subscription_description(self) -> str:
        """Descripción legible del tipo de suscripción"""
        if self.billing_interval == "one_time":
            return f"Pago único - {self.duration_days} días"
        elif self.is_limited_duration:
            interval_text = "mes" if self.billing_interval == "month" else "año"
            return f"Pago {interval_text}al por {self.max_billing_cycles} {interval_text}{'es' if self.max_billing_cycles > 1 else ''}"
        else:
            interval_text = "mensual" if self.billing_interval == "month" else "anual"
            return f"Suscripción {interval_text} ilimitada"