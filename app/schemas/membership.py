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
    max_billing_cycles: Optional[int] = Field(None, ge=1, description="Máximo número de ciclos de facturación (None = ilimitado)")
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
    
    @validator('max_billing_cycles')
    def validate_max_billing_cycles(cls, v, values):
        """Validar que max_billing_cycles sea coherente con billing_interval"""
        if v is not None:
            billing_interval = values.get('billing_interval')
            if billing_interval == 'one_time' and v != 1:
                raise ValueError('max_billing_cycles must be 1 for one_time billing_interval')
            elif billing_interval in ['month', 'year'] and v < 1:
                raise ValueError('max_billing_cycles must be >= 1 for recurring billing_interval')
        return v


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
    max_billing_cycles: Optional[int] = Field(None, ge=1)
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
    is_limited_duration: Optional[bool] = None
    total_duration_days: Optional[int] = None
    subscription_description: Optional[str] = None

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
    
    @validator('is_limited_duration', always=True)
    def calculate_is_limited_duration(cls, v, values):
        max_cycles = values.get('max_billing_cycles')
        return max_cycles is not None and max_cycles > 0
    
    @validator('total_duration_days', always=True)
    def calculate_total_duration_days(cls, v, values):
        max_cycles = values.get('max_billing_cycles')
        duration_days = values.get('duration_days')
        billing_interval = values.get('billing_interval')
        
        if max_cycles is not None and max_cycles > 0:
            if billing_interval == "month":
                return max_cycles * 30
            elif billing_interval == "year":
                return max_cycles * 365
        
        return duration_days
    
    @validator('subscription_description', always=True)
    def calculate_subscription_description(cls, v, values):
        billing_interval = values.get('billing_interval')
        max_cycles = values.get('max_billing_cycles')
        duration_days = values.get('duration_days')
        
        if billing_interval == "one_time":
            return f"Pago único - {duration_days} días"
        elif max_cycles is not None and max_cycles > 0:
            interval_text = "mes" if billing_interval == "month" else "año"
            return f"Pago {interval_text}al por {max_cycles} {interval_text}{'es' if max_cycles > 1 else ''}"
        else:
            interval_text = "mensual" if billing_interval == "month" else "anual"
            return f"Suscripción {interval_text} ilimitada"


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


class AdminCreatePaymentLinkRequest(BaseModel):
    """Solicitud administrativa para crear link de pago para un usuario específico"""
    user_id: int = Field(..., gt=0, description="ID del usuario que debe pagar")
    plan_id: int = Field(..., gt=0, description="ID del plan a comprar")
    success_url: Optional[str] = Field(None, description="URL de éxito personalizada")
    cancel_url: Optional[str] = Field(None, description="URL de cancelación personalizada")
    notes: Optional[str] = Field(None, max_length=500, description="Notas adicionales sobre el pago")
    expires_in_hours: Optional[int] = Field(24, ge=1, le=168, description="Link expira en X horas (1-168, default: 24)")


class PurchaseMembershipResponse(BaseModel):
    """Respuesta al iniciar compra de membresía"""
    checkout_url: str = Field(..., description="URL de checkout de Stripe")
    session_id: str = Field(..., description="ID de sesión de Stripe")
    plan_name: str
    price_amount: float
    currency: str


class AdminPaymentLinkResponse(BaseModel):
    """Respuesta administrativa al crear link de pago"""
    checkout_url: str = Field(..., description="URL de checkout de Stripe")
    session_id: str = Field(..., description="ID de sesión de Stripe")
    plan_name: str
    price_amount: float
    currency: str
    user_email: str = Field(..., description="Email del usuario destinatario")
    user_name: str = Field(..., description="Nombre del usuario destinatario")
    expires_at: datetime = Field(..., description="Fecha de expiración del link")
    notes: Optional[str] = Field(None, description="Notas adicionales")
    created_by_admin: str = Field(..., description="Email del administrador que creó el link")


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