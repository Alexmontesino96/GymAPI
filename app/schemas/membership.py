from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, validator
from decimal import Decimal


# === Esquemas Base ===

class MembershipPlanBase(BaseModel):
    """Esquema base para planes de membresía"""
    name: str = Field(..., min_length=1, max_length=100, description="Nombre del plan")
    description: Optional[str] = Field(None, description="Descripción del plan")
    price_cents: int = Field(..., ge=0, description="Precio en centavos")
    currency: str = Field("EUR", min_length=3, max_length=3, description="Código de moneda")
    billing_interval: str = Field(..., description="Intervalo de facturación: month, year, one_time")
    duration_days: int = Field(..., ge=1, description="Duración en días")
    is_active: bool = Field(True, description="Si el plan está activo")
    features: Optional[str] = Field(None, description="Características del plan (JSON)")
    max_bookings_per_month: Optional[int] = Field(None, ge=0, description="Límite de reservas mensuales")

    @validator('billing_interval')
    def validate_billing_interval(cls, v):
        allowed = ['month', 'year', 'one_time']
        if v not in allowed:
            raise ValueError(f'billing_interval must be one of: {allowed}')
        return v

    @validator('currency')
    def validate_currency(cls, v):
        return v.upper()


class MembershipPlanCreate(MembershipPlanBase):
    """Esquema para crear un plan de membresía"""
    # gym_id se obtiene automáticamente del header via middleware
    pass


class MembershipPlanUpdate(BaseModel):
    """Esquema para actualizar un plan de membresía"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    price_cents: Optional[int] = Field(None, ge=0)
    currency: Optional[str] = Field(None, min_length=3, max_length=3)
    billing_interval: Optional[str] = None
    duration_days: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None
    features: Optional[str] = None
    max_bookings_per_month: Optional[int] = Field(None, ge=0)

    @validator('billing_interval')
    def validate_billing_interval(cls, v):
        if v is not None:
            allowed = ['month', 'year', 'one_time']
            if v not in allowed:
                raise ValueError(f'billing_interval must be one of: {allowed}')
        return v


class MembershipPlan(MembershipPlanBase):
    """Esquema completo de un plan de membresía"""
    id: int
    gym_id: int
    stripe_price_id: Optional[str] = None
    stripe_product_id: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    # Campos calculados
    price_amount: Optional[float] = None
    is_recurring: Optional[bool] = None

    class Config:
        from_attributes = True

    @validator('price_amount', always=True)
    def calculate_price_amount(cls, v, values):
        """Convertir price_cents a la unidad principal de la moneda"""
        if 'price_cents' in values:
            return values['price_cents'] / 100.0
        return v

    @validator('is_recurring', always=True)
    def calculate_is_recurring(cls, v, values):
        if 'billing_interval' in values:
            return values['billing_interval'] in ['month', 'year']
        return v


# === Esquemas para UserGym con membresía ===

class UserMembershipBase(BaseModel):
    """Esquema base para membresía de usuario"""
    is_active: bool = Field(True, description="Si la membresía está activa")
    membership_expires_at: Optional[datetime] = Field(None, description="Fecha de expiración")
    membership_type: str = Field("free", description="Tipo de membresía: free, paid, trial")
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    last_payment_at: Optional[datetime] = None
    notes: Optional[str] = Field(None, max_length=500)


class UserMembershipUpdate(UserMembershipBase):
    """Esquema para actualizar membresía de usuario"""
    pass


class UserMembership(UserMembershipBase):
    """Esquema completo de membresía de usuario"""
    id: int
    user_id: int
    gym_id: int
    role: str  # GymRoleType
    created_at: datetime

    # Campos calculados
    is_expired: Optional[bool] = None
    days_until_expiry: Optional[int] = None

    class Config:
        from_attributes = True

    @validator('is_expired', always=True)
    def calculate_is_expired(cls, v, values):
        if values.get('membership_expires_at'):
            return datetime.now() > values['membership_expires_at']
        return False

    @validator('days_until_expiry', always=True)
    def calculate_days_until_expiry(cls, v, values):
        expires_at = values.get('membership_expires_at')
        if expires_at and expires_at > datetime.now():
            return (expires_at - datetime.now()).days
        return None


# === Esquemas para respuestas de API ===

class MembershipStatus(BaseModel):
    """Estado de membresía de un usuario en un gimnasio"""
    user_id: int
    gym_id: int
    gym_name: str
    is_active: bool
    membership_type: str
    expires_at: Optional[datetime] = None
    days_remaining: Optional[int] = None
    plan_name: Optional[str] = None
    can_access: bool

    class Config:
        from_attributes = True


class PurchaseMembershipRequest(BaseModel):
    """Solicitud para comprar una membresía"""
    plan_id: int = Field(..., gt=0, description="ID del plan a comprar (debe ser mayor a 0)")
    success_url: Optional[str] = Field(None, description="URL de éxito personalizada")
    cancel_url: Optional[str] = Field(None, description="URL de cancelación personalizada")


class PurchaseMembershipResponse(BaseModel):
    """Respuesta al iniciar compra de membresía"""
    checkout_url: str = Field(..., description="URL de checkout de Stripe")
    session_id: str = Field(..., description="ID de sesión de Stripe")
    plan_name: str
    price_amount: float
    currency: str


# === Esquemas para listados ===

class MembershipPlanList(BaseModel):
    """Lista de planes de membresía"""
    plans: List[MembershipPlan]
    total: int
    gym_id: int
    gym_name: str


class MembershipSummary(BaseModel):
    """Resumen de membresías para dashboard"""
    total_members: int
    active_members: int
    paid_members: int
    trial_members: int
    expired_members: int
    revenue_current_month: float
    new_members_this_month: int 