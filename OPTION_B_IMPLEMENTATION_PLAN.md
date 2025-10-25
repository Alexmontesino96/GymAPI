# 📋 OPCIÓN B: Plan de Implementación Detallado
## Ajustes Menores al Sistema Existente (1 Semana)

### 🎯 Estrategia Central
**Mantener un único codebase** añadiendo un campo `type` a la tabla `gyms` para diferenciar entre gimnasios tradicionales y entrenadores personales, con lógica condicional mínima en puntos clave del sistema.

---

## 📁 FASE 1: CAMBIOS EN LA BASE DE DATOS (Día 1)

### 1.1 Migración de Base de Datos
```python
# alembic/versions/xxx_add_gym_type_field.py
"""Add type field to gyms table for trainer support

Revision ID: xxx
Create Date: 2024-01-24
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import Enum

def upgrade():
    # Crear el enum type
    gym_type_enum = Enum('gym', 'personal_trainer', name='gym_type_enum')
    gym_type_enum.create(op.get_bind())

    # Agregar columna type con default 'gym'
    op.add_column('gyms',
        sa.Column('type', gym_type_enum, nullable=False, server_default='gym')
    )

    # Agregar índice para optimizar queries filtradas por type
    op.create_index('idx_gyms_type', 'gyms', ['type'])

    # Campos opcionales para entrenadores
    op.add_column('gyms',
        sa.Column('trainer_specialties', sa.JSON, nullable=True,
                  comment='Especialidades del entrenador (solo para type=personal_trainer)')
    )

    op.add_column('gyms',
        sa.Column('trainer_certifications', sa.JSON, nullable=True,
                  comment='Certificaciones del entrenador')
    )

    op.add_column('gyms',
        sa.Column('max_clients', sa.Integer, nullable=True,
                  comment='Máximo de clientes simultáneos (para entrenadores)')
    )

def downgrade():
    op.drop_index('idx_gyms_type')
    op.drop_column('gyms', 'max_clients')
    op.drop_column('gyms', 'trainer_certifications')
    op.drop_column('gyms', 'trainer_specialties')
    op.drop_column('gyms', 'type')

    # Eliminar el enum
    gym_type_enum = Enum('gym', 'personal_trainer', name='gym_type_enum')
    gym_type_enum.drop(op.get_bind())
```

### 1.2 Actualizar Modelo SQLAlchemy
```python
# app/models/gym.py

from enum import Enum as PyEnum

class GymType(str, PyEnum):
    GYM = "gym"
    PERSONAL_TRAINER = "personal_trainer"

class Gym(Base):
    __tablename__ = "gyms"

    # Campos existentes...
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)

    # NUEVO: Tipo de gimnasio
    type = Column(SQLEnum(GymType), nullable=False, default=GymType.GYM, index=True)

    # NUEVOS: Campos específicos para entrenadores (opcionales)
    trainer_specialties = Column(JSON, nullable=True)  # ["Fuerza", "CrossFit", "Yoga"]
    trainer_certifications = Column(JSON, nullable=True)  # [{"name": "NASM-CPT", "year": 2020}]
    max_clients = Column(Integer, nullable=True)  # Límite de clientes activos

    # Propiedades helper
    @property
    def is_personal_trainer(self) -> bool:
        return self.type == GymType.PERSONAL_TRAINER

    @property
    def is_traditional_gym(self) -> bool:
        return self.type == GymType.GYM
```

### 1.3 Schema Pydantic Actualizado
```python
# app/schemas/gym.py

from typing import Optional, List, Dict, Any
from enum import Enum

class GymType(str, Enum):
    gym = "gym"
    personal_trainer = "personal_trainer"

class GymSchema(BaseModel):
    id: int
    name: str
    type: GymType = GymType.gym

    # Campos específicos de entrenador
    trainer_specialties: Optional[List[str]] = None
    trainer_certifications: Optional[List[Dict[str, Any]]] = None
    max_clients: Optional[int] = None

    # Computed properties
    @property
    def display_name(self) -> str:
        """Nombre contextual según el tipo"""
        if self.type == GymType.personal_trainer:
            return self.name.replace("Entrenamiento Personal ", "")
        return self.name

    @property
    def entity_type_label(self) -> str:
        """Label para UI"""
        return "Espacio de Trabajo" if self.type == GymType.personal_trainer else "Gimnasio"
```

---

## 🔧 FASE 2: LÓGICA CONDICIONAL EN SERVICIOS (Día 2-3)

### 2.1 Servicio de Configuración
```python
# app/core/config.py

class Settings(BaseSettings):
    # Agregar helper methods para identificar contexto

    @staticmethod
    def get_terminology(gym_type: GymType) -> Dict[str, str]:
        """Retorna terminología apropiada según el tipo de gym"""
        if gym_type == GymType.PERSONAL_TRAINER:
            return {
                "gym": "espacio de trabajo",
                "members": "clientes",
                "trainers": "asistentes",
                "classes": "sesiones",
                "schedule": "agenda",
                "membership": "plan de entrenamiento"
            }
        return {
            "gym": "gimnasio",
            "members": "miembros",
            "trainers": "entrenadores",
            "classes": "clases",
            "schedule": "horario",
            "membership": "membresía"
        }

    @staticmethod
    def get_enabled_modules(gym_type: GymType) -> List[str]:
        """Módulos habilitados por defecto según tipo"""
        base_modules = ["users", "chat", "health", "nutrition", "billing"]

        if gym_type == GymType.GYM:
            return base_modules + ["schedule", "classes", "events", "equipment"]
        else:  # PERSONAL_TRAINER
            return base_modules + ["appointments", "progress_tracking"]
```

### 2.2 Middleware Adaptado
```python
# app/middleware/tenant_auth.py

class TenantAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Código existente...

        # NUEVO: Para entrenadores, simplificar acceso
        if hasattr(request.state, 'gym') and request.state.gym:
            gym = request.state.gym

            # Si es entrenador personal y es el owner, dar acceso completo
            if gym.type == GymType.PERSONAL_TRAINER:
                user = request.state.user
                if user:
                    # Verificar si es el owner
                    user_gym = db.query(UserGym).filter(
                        UserGym.user_id == user.id,
                        UserGym.gym_id == gym.id,
                        UserGym.role == GymRoleType.OWNER
                    ).first()

                    if user_gym:
                        # Establecer permisos máximos para el entrenador
                        request.state.is_trainer_owner = True
                        request.state.simplified_ui = True

        response = await call_next(request)
        return response
```

### 2.3 Dashboard Condicional
```python
# app/api/v1/endpoints/dashboard.py

@router.get("/dashboard/summary")
async def get_dashboard_summary(
    request: Request,
    db: Session = Depends(get_db),
    current_gym: GymSchema = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user),
    redis_client: Redis = Depends(get_redis_client)
):
    """Dashboard adaptado según tipo de gym"""

    # Detectar tipo de gimnasio
    if current_gym.type == GymType.PERSONAL_TRAINER:
        return await get_trainer_dashboard(
            db, current_gym, current_user, redis_client
        )
    else:
        return await get_gym_dashboard(
            db, current_gym, current_user, redis_client
        )

async def get_trainer_dashboard(
    db: Session,
    gym: GymSchema,
    user: Auth0User,
    redis: Redis
) -> Dict:
    """Dashboard simplificado para entrenadores"""

    # Cache key específico para trainers
    cache_key = f"trainer_dashboard:{gym.id}"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    # Métricas relevantes para entrenadores
    total_clients = db.query(UserGym).filter(
        UserGym.gym_id == gym.id,
        UserGym.role == GymRoleType.MEMBER,
        UserGym.is_active == True
    ).count()

    # Sesiones de hoy (eventos o citas)
    today = datetime.utcnow().date()
    sessions_today = db.query(Event).filter(
        Event.gym_id == gym.id,
        func.date(Event.start_time) == today
    ).count()

    # Próximas 5 sesiones
    upcoming_sessions = db.query(Event).filter(
        Event.gym_id == gym.id,
        Event.start_time > datetime.utcnow()
    ).order_by(Event.start_time).limit(5).all()

    # Ingresos del mes (Stripe)
    month_start = datetime.utcnow().replace(day=1)
    revenue_query = db.query(
        func.sum(Payment.amount)
    ).filter(
        Payment.gym_id == gym.id,
        Payment.created_at >= month_start,
        Payment.status == "succeeded"
    ).scalar() or 0

    dashboard = {
        "type": "trainer",
        "metrics": {
            "total_clients": total_clients,
            "active_clients": total_clients,  # Simplificado
            "sessions_today": sessions_today,
            "sessions_week": sessions_today * 5,  # Estimado
            "revenue_month": float(revenue_query) / 100,  # Cents a currency
            "next_session": upcoming_sessions[0] if upcoming_sessions else None
        },
        "quick_stats": {
            "new_clients_month": 0,  # TODO: Implementar
            "completion_rate": 95.0,  # TODO: Calcular real
            "avg_session_duration": 60  # minutos
        },
        "upcoming_sessions": [
            {
                "id": s.id,
                "title": s.title,
                "client": s.participants[0].name if s.participants else "Sin cliente",
                "time": s.start_time.isoformat(),
                "type": s.event_type or "training"
            }
            for s in upcoming_sessions
        ],
        "quick_actions": [
            {"id": "add_client", "label": "Nuevo Cliente", "icon": "user-plus"},
            {"id": "schedule_session", "label": "Agendar Sesión", "icon": "calendar"},
            {"id": "create_plan", "label": "Plan Nutricional", "icon": "clipboard"}
        ]
    }

    # Cachear por 5 minutos
    await redis.setex(cache_key, 300, json.dumps(dashboard, default=str))
    return dashboard

async def get_gym_dashboard(db, gym, user, redis) -> Dict:
    """Dashboard tradicional para gimnasios (código existente)"""
    # ... implementación existente ...
```

---

## 🚀 FASE 3: SCRIPT DE ONBOARDING (Día 3-4)

### 3.1 Script Principal de Setup
```python
# scripts/setup_trainer.py

import asyncio
import sys
from typing import Optional
import stripe
from datetime import datetime

from app.db.session import SessionLocal
from app.models import Gym, User, UserGym, GymModule, GymStripeAccount
from app.models.gym import GymType, GymRoleType
from app.core.config import settings

class TrainerSetup:
    """Configuración automatizada para entrenadores personales"""

    def __init__(self):
        self.db = SessionLocal()
        stripe.api_key = settings.STRIPE_API_KEY

    async def create_trainer_workspace(
        self,
        email: str,
        first_name: str,
        last_name: str,
        phone: Optional[str] = None,
        specialties: Optional[List[str]] = None,
        certifications: Optional[List[Dict]] = None
    ) -> Dict:
        """
        Crear workspace completo para un entrenador personal
        """
        try:
            # 1. Verificar si el usuario ya existe
            existing_user = self.db.query(User).filter(
                User.email == email
            ).first()

            if existing_user:
                # Verificar si ya tiene un gym
                existing_gym = self.db.query(UserGym).filter(
                    UserGym.user_id == existing_user.id,
                    UserGym.role == GymRoleType.OWNER
                ).first()

                if existing_gym:
                    return {
                        "success": False,
                        "message": "El usuario ya tiene un espacio de trabajo",
                        "gym_id": existing_gym.gym_id
                    }

                user = existing_user
            else:
                # 2. Crear usuario nuevo
                user = User(
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    phone=phone,
                    role=UserRole.TRAINER,  # Rol global
                    is_active=True,
                    created_at=datetime.utcnow()
                )
                self.db.add(user)
                self.db.flush()  # Obtener ID sin commit

            # 3. Crear "gimnasio" personal
            gym_name = f"Entrenamiento Personal {first_name} {last_name}"

            gym = Gym(
                name=gym_name,
                type=GymType.PERSONAL_TRAINER,
                email=email,
                phone=phone,
                timezone="America/Mexico_City",  # Configurable
                is_active=True,
                trainer_specialties=specialties or ["Fitness General"],
                trainer_certifications=certifications,
                max_clients=30,  # Límite default
                description=f"Espacio de entrenamiento personalizado de {first_name} {last_name}"
            )
            self.db.add(gym)
            self.db.flush()

            # 4. Crear relación UserGym como OWNER
            user_gym = UserGym(
                user_id=user.id,
                gym_id=gym.id,
                role=GymRoleType.OWNER,
                is_active=True,
                membership_type="owner",
                created_at=datetime.utcnow()
            )
            self.db.add(user_gym)

            # 5. Configurar Stripe Connect
            stripe_account = await self._setup_stripe_connect(gym, user)
            if stripe_account:
                gym_stripe = GymStripeAccount(
                    gym_id=gym.id,
                    stripe_account_id=stripe_account.id,
                    is_connected=False,  # Requiere onboarding
                    created_at=datetime.utcnow()
                )
                self.db.add(gym_stripe)

            # 6. Activar módulos esenciales
            essential_modules = [
                ("users", "Gestión de Clientes"),
                ("chat", "Mensajería"),
                ("health", "Tracking de Salud"),
                ("nutrition", "Planes Nutricionales"),
                ("billing", "Pagos y Facturación"),
                ("appointments", "Agenda de Citas"),
                ("progress", "Progreso de Clientes")
            ]

            for module_code, description in essential_modules:
                module = GymModule(
                    gym_id=gym.id,
                    module_code=module_code,
                    is_active=True,
                    description=description,
                    config={},  # Configuración default
                    created_at=datetime.utcnow()
                )
                self.db.add(module)

            # 7. Crear planes de pago default
            await self._create_default_payment_plans(gym.id)

            # 8. Configurar notificaciones
            await self._setup_notifications(gym.id, user.id)

            # Commit final
            self.db.commit()

            # 9. Enviar email de bienvenida
            await self._send_welcome_email(user, gym)

            return {
                "success": True,
                "message": "Espacio de trabajo creado exitosamente",
                "gym_id": gym.id,
                "user_id": user.id,
                "stripe_onboarding_url": stripe_account.onboarding_url if stripe_account else None,
                "next_steps": [
                    "Completar onboarding de Stripe",
                    "Agregar primeros clientes",
                    "Configurar horario de disponibilidad",
                    "Personalizar planes de pago"
                ]
            }

        except Exception as e:
            self.db.rollback()
            return {
                "success": False,
                "message": f"Error al crear workspace: {str(e)}"
            }
        finally:
            self.db.close()

    async def _setup_stripe_connect(self, gym: Gym, user: User) -> Optional[Any]:
        """Configurar cuenta Stripe Connect para el entrenador"""
        try:
            account = stripe.Account.create(
                type="express",  # o "standard" para más control
                country="MX",
                email=user.email,
                capabilities={
                    "transfers": {"requested": True},
                    "card_payments": {"requested": True}
                },
                business_profile={
                    "name": gym.name,
                    "product_description": "Servicios de entrenamiento personal"
                },
                metadata={
                    "gym_id": str(gym.id),
                    "user_id": str(user.id),
                    "type": "personal_trainer"
                }
            )

            # Generar link de onboarding
            account_link = stripe.AccountLink.create(
                account=account.id,
                refresh_url=f"{settings.FRONTEND_URL}/stripe/refresh",
                return_url=f"{settings.FRONTEND_URL}/stripe/success",
                type="account_onboarding"
            )

            account.onboarding_url = account_link.url
            return account

        except Exception as e:
            print(f"Error setting up Stripe: {e}")
            return None

    async def _create_default_payment_plans(self, gym_id: int):
        """Crear planes de pago predeterminados para el entrenador"""

        default_plans = [
            {
                "name": "Sesión Individual",
                "type": "one_time",
                "price": 50000,  # $500 MXN en centavos
                "currency": "mxn",
                "interval": None
            },
            {
                "name": "Paquete 5 Sesiones",
                "type": "package",
                "price": 225000,  # $2,250 MXN (10% descuento)
                "currency": "mxn",
                "sessions": 5
            },
            {
                "name": "Paquete 10 Sesiones",
                "type": "package",
                "price": 400000,  # $4,000 MXN (20% descuento)
                "currency": "mxn",
                "sessions": 10
            },
            {
                "name": "Mensualidad Ilimitada",
                "type": "subscription",
                "price": 300000,  # $3,000 MXN/mes
                "currency": "mxn",
                "interval": "month"
            }
        ]

        for plan_data in default_plans:
            # Crear en Stripe
            if plan_data["type"] == "subscription":
                stripe_price = stripe.Price.create(
                    unit_amount=plan_data["price"],
                    currency=plan_data["currency"],
                    recurring={"interval": plan_data["interval"]},
                    product_data={"name": plan_data["name"]},
                    metadata={"gym_id": str(gym_id)}
                )
            else:
                stripe_price = stripe.Price.create(
                    unit_amount=plan_data["price"],
                    currency=plan_data["currency"],
                    product_data={"name": plan_data["name"]},
                    metadata={
                        "gym_id": str(gym_id),
                        "sessions": plan_data.get("sessions", 1)
                    }
                )

            # Guardar en DB
            membership_plan = MembershipPlan(
                gym_id=gym_id,
                name=plan_data["name"],
                stripe_price_id=stripe_price.id,
                price=plan_data["price"],
                currency=plan_data["currency"],
                interval=plan_data.get("interval"),
                is_active=True,
                metadata={"sessions": plan_data.get("sessions")}
            )
            self.db.add(membership_plan)

    async def _setup_notifications(self, gym_id: int, user_id: int):
        """Configurar notificaciones para el entrenador"""
        # TODO: Implementar con OneSignal
        pass

    async def _send_welcome_email(self, user: User, gym: Gym):
        """Enviar email de bienvenida al entrenador"""
        # TODO: Implementar con servicio de email
        print(f"Welcome email would be sent to {user.email}")


# CLI para ejecutar el script
async def main():
    if len(sys.argv) < 4:
        print("Usage: python setup_trainer.py <email> <first_name> <last_name> [phone]")
        sys.exit(1)

    email = sys.argv[1]
    first_name = sys.argv[2]
    last_name = sys.argv[3]
    phone = sys.argv[4] if len(sys.argv) > 4 else None

    setup = TrainerSetup()
    result = await setup.create_trainer_workspace(
        email=email,
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        specialties=["Fitness", "Nutrición"],  # Ejemplo
        certifications=[
            {"name": "NASM-CPT", "year": 2020},
            {"name": "Precision Nutrition L1", "year": 2021}
        ]
    )

    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 🎨 FASE 4: ADAPTACIÓN DE UI/UX (Día 4-5)

### 4.1 Endpoints Contextuales
```python
# app/api/v1/endpoints/context.py

@router.get("/context/workspace")
async def get_workspace_context(
    current_gym: GymSchema = Depends(get_current_gym),
    current_user: User = Depends(get_current_user)
) -> Dict:
    """
    Retorna contexto y configuración según tipo de gym
    para que el frontend adapte la UI
    """

    terminology = Settings.get_terminology(current_gym.type)

    return {
        "workspace": {
            "id": current_gym.id,
            "name": current_gym.name,
            "type": current_gym.type,
            "is_personal_trainer": current_gym.type == GymType.PERSONAL_TRAINER
        },
        "terminology": terminology,
        "features": {
            "show_multiple_trainers": current_gym.type == GymType.GYM,
            "show_equipment": current_gym.type == GymType.GYM,
            "show_class_schedule": current_gym.type == GymType.GYM,
            "show_appointments": current_gym.type == GymType.PERSONAL_TRAINER,
            "show_client_progress": current_gym.type == GymType.PERSONAL_TRAINER,
            "simplified_billing": current_gym.type == GymType.PERSONAL_TRAINER
        },
        "navigation": get_navigation_menu(current_gym.type, current_user.role),
        "branding": {
            "logo_url": current_gym.logo_url,
            "primary_color": "#007bff" if current_gym.type == GymType.GYM else "#28a745",
            "app_title": current_gym.display_name
        }
    }

def get_navigation_menu(gym_type: GymType, user_role: str) -> List[Dict]:
    """Menú de navegación adaptado"""

    if gym_type == GymType.PERSONAL_TRAINER:
        return [
            {"id": "dashboard", "label": "Dashboard", "icon": "home", "path": "/"},
            {"id": "clients", "label": "Mis Clientes", "icon": "users", "path": "/clients"},
            {"id": "appointments", "label": "Agenda", "icon": "calendar", "path": "/appointments"},
            {"id": "nutrition", "label": "Planes Nutricionales", "icon": "apple", "path": "/nutrition"},
            {"id": "progress", "label": "Progreso", "icon": "chart-line", "path": "/progress"},
            {"id": "payments", "label": "Pagos", "icon": "credit-card", "path": "/payments"},
            {"id": "chat", "label": "Mensajes", "icon": "message-circle", "path": "/chat"},
            {"id": "settings", "label": "Configuración", "icon": "settings", "path": "/settings"}
        ]

    # Menú tradicional para gimnasios
    return [
        {"id": "dashboard", "label": "Dashboard", "icon": "home", "path": "/"},
        {"id": "members", "label": "Miembros", "icon": "users", "path": "/members"},
        {"id": "schedule", "label": "Horarios", "icon": "clock", "path": "/schedule"},
        {"id": "classes", "label": "Clases", "icon": "activity", "path": "/classes"},
        {"id": "trainers", "label": "Entrenadores", "icon": "user-check", "path": "/trainers"},
        # ... resto del menú tradicional
    ]
```

### 4.2 Adaptación de Módulos Existentes
```python
# app/api/v1/endpoints/users.py

@router.get("/clients")  # Alias para entrenadores
@router.get("/members")   # Path original
async def get_gym_members(
    request: Request,
    db: Session = Depends(get_db),
    current_gym: GymSchema = Depends(verify_gym_access),
    skip: int = 0,
    limit: int = 20,
    search: Optional[str] = None
) -> Dict:
    """
    Obtener miembros/clientes según el contexto
    """

    # Adaptar título según tipo
    entity_name = "clientes" if current_gym.is_personal_trainer else "miembros"

    # Query base
    query = db.query(User).join(UserGym).filter(
        UserGym.gym_id == current_gym.id,
        UserGym.role == GymRoleType.MEMBER,
        UserGym.is_active == True
    )

    # Para entrenadores, agregar información adicional
    if current_gym.is_personal_trainer:
        # Incluir última sesión, progreso, etc.
        members = query.offset(skip).limit(limit).all()

        enriched_members = []
        for member in members:
            # Obtener última sesión
            last_session = db.query(Event).filter(
                Event.gym_id == current_gym.id,
                Event.participants.any(User.id == member.id)
            ).order_by(Event.start_time.desc()).first()

            # Obtener progreso
            latest_health = db.query(HealthMetric).filter(
                HealthMetric.user_id == member.id,
                HealthMetric.gym_id == current_gym.id
            ).order_by(HealthMetric.created_at.desc()).first()

            enriched_members.append({
                "id": member.id,
                "name": f"{member.first_name} {member.last_name}",
                "email": member.email,
                "phone": member.phone,
                "photo_url": member.photo_url,
                "last_session": last_session.start_time if last_session else None,
                "next_session": None,  # TODO: Obtener próxima
                "current_weight": latest_health.weight if latest_health else None,
                "goal": member.fitness_goal,  # Asumiendo que existe este campo
                "status": "active" if last_session and
                         (datetime.utcnow() - last_session.start_time).days < 7
                         else "inactive"
            })

        return {
            "total": query.count(),
            "items": enriched_members,
            "entity_name": entity_name,
            "actions": [
                {"id": "add_client", "label": "Agregar Cliente"},
                {"id": "import_clients", "label": "Importar Lista"}
            ]
        }

    # Para gimnasios, mantener estructura existente
    members = query.offset(skip).limit(limit).all()
    return {
        "total": query.count(),
        "items": [MemberSchema.model_validate(m) for m in members],
        "entity_name": entity_name
    }
```

---

## 📊 FASE 5: TESTING Y VALIDACIÓN (Día 5-6)

### 5.1 Tests Unitarios
```python
# tests/test_trainer_setup.py

import pytest
from app.scripts.setup_trainer import TrainerSetup
from app.models.gym import GymType

@pytest.mark.asyncio
async def test_create_trainer_workspace():
    """Test crear workspace para entrenador"""

    setup = TrainerSetup()
    result = await setup.create_trainer_workspace(
        email="test.trainer@example.com",
        first_name="Juan",
        last_name="Pérez",
        phone="+525512345678",
        specialties=["CrossFit", "Nutrición"],
        certifications=[
            {"name": "CF-L1", "year": 2020}
        ]
    )

    assert result["success"] == True
    assert result["gym_id"] is not None

    # Verificar que se creó con tipo correcto
    gym = db.query(Gym).filter(Gym.id == result["gym_id"]).first()
    assert gym.type == GymType.PERSONAL_TRAINER
    assert gym.trainer_specialties == ["CrossFit", "Nutrición"]

@pytest.mark.asyncio
async def test_trainer_dashboard():
    """Test dashboard adaptado para entrenadores"""

    # Setup trainer gym
    trainer_gym = create_test_trainer_gym()

    response = await client.get(
        "/api/v1/dashboard/summary",
        headers={"X-Gym-ID": str(trainer_gym.id)}
    )

    assert response.status_code == 200
    data = response.json()

    assert data["type"] == "trainer"
    assert "total_clients" in data["metrics"]
    assert "quick_actions" in data

    # Verificar que no incluye métricas de gimnasio
    assert "equipment_usage" not in data["metrics"]
    assert "trainer_count" not in data["metrics"]
```

### 5.2 Tests de Integración
```python
# tests/integration/test_trainer_flow.py

@pytest.mark.integration
async def test_complete_trainer_flow():
    """Test flujo completo de entrenador"""

    # 1. Crear workspace de entrenador
    trainer = await create_trainer_workspace("trainer@test.com")

    # 2. Agregar cliente
    client = await add_client_to_trainer(trainer.gym_id, "client@test.com")

    # 3. Crear sesión/cita
    session = await create_training_session(
        gym_id=trainer.gym_id,
        trainer_id=trainer.user_id,
        client_id=client.id,
        date="2024-01-25T10:00:00"
    )

    # 4. Verificar dashboard
    dashboard = await get_trainer_dashboard(trainer.gym_id)
    assert dashboard["metrics"]["total_clients"] == 1
    assert dashboard["metrics"]["sessions_today"] == 1

    # 5. Procesar pago
    payment = await process_session_payment(
        session_id=session.id,
        amount=50000,  # $500 MXN
        payment_method="card"
    )

    assert payment.status == "succeeded"
```

---

## 🚢 FASE 6: DEPLOYMENT (Día 6-7)

### 6.1 Variables de Entorno
```bash
# .env.production

# Flags de feature
ENABLE_TRAINER_MODE=true
TRAINER_ONBOARDING_ENABLED=true
TRAINER_MAX_CLIENTS_DEFAULT=30

# URLs específicas
TRAINER_DASHBOARD_URL=https://app.trainerplatform.com
TRAINER_STRIPE_RETURN_URL=https://app.trainerplatform.com/stripe/return
```

### 6.2 Script de Migración para Producción
```bash
#!/bin/bash
# deploy_trainer_features.sh

echo "🚀 Deploying trainer features..."

# 1. Backup de base de datos
echo "📦 Creating database backup..."
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d_%H%M%S).sql

# 2. Aplicar migraciones
echo "🔄 Applying database migrations..."
alembic upgrade head

# 3. Verificar migraciones
echo "✅ Verifying migrations..."
python scripts/verify_trainer_migration.py

# 4. Crear índices adicionales
echo "📊 Creating performance indexes..."
psql $DATABASE_URL -c "CREATE INDEX CONCURRENTLY idx_gyms_type_active ON gyms(type, is_active);"

# 5. Cachear invalidation
echo "🗑️ Clearing cache..."
redis-cli FLUSHDB

# 6. Restart de servicios
echo "♻️ Restarting services..."
systemctl restart gymapi

echo "✅ Deployment complete!"
```

---

## 📈 MONITOREO Y MÉTRICAS

### Queries para Monitorear Adopción
```sql
-- Contar entrenadores registrados
SELECT COUNT(*) as trainer_count
FROM gyms
WHERE type = 'personal_trainer';

-- Métricas de uso por tipo
SELECT
    type,
    COUNT(*) as total,
    COUNT(CASE WHEN is_active THEN 1 END) as active,
    AVG(
        SELECT COUNT(*) FROM user_gyms ug
        WHERE ug.gym_id = g.id AND ug.role = 'MEMBER'
    ) as avg_members
FROM gyms g
GROUP BY type;

-- Ingresos por tipo
SELECT
    g.type,
    SUM(p.amount) / 100.0 as total_revenue,
    COUNT(DISTINCT p.user_id) as paying_users
FROM payments p
JOIN gyms g ON p.gym_id = g.id
WHERE p.created_at >= NOW() - INTERVAL '30 days'
GROUP BY g.type;
```

---

## ⏰ TIMELINE DETALLADO

| Día | Tareas | Entregables |
|-----|--------|-------------|
| **Día 1** | • Crear migración de BD<br>• Actualizar modelos<br>• Actualizar schemas | Branch con cambios de BD |
| **Día 2** | • Implementar lógica condicional<br>• Adaptar middleware<br>• Crear servicio de config | Servicios adaptados |
| **Día 3** | • Script de onboarding<br>• Dashboard adaptado<br>• Endpoints contextuales | Sistema funcional para trainers |
| **Día 4** | • Adaptación de UI/UX<br>• Alias de endpoints<br>• Menús dinámicos | UI completamente adaptada |
| **Día 5** | • Tests unitarios<br>• Tests de integración<br>• Documentación | Suite de tests completa |
| **Día 6** | • Deploy a staging<br>• Testing con datos reales<br>• Ajustes finales | Sistema en staging |
| **Día 7** | • Deploy a producción<br>• Monitoreo<br>• Soporte inicial | 🚀 Sistema live |

---

## 🎯 RESULTADO FINAL

Con esta implementación tendrás:

1. **Un único codebase** mantenible
2. **Diferenciación clara** entre gimnasios y entrenadores
3. **UI/UX adaptada** automáticamente según contexto
4. **Onboarding simplificado** para entrenadores
5. **Compatibilidad total** con el sistema existente
6. **Escalabilidad** para agregar más tipos en el futuro

**Tiempo total: 7 días laborables**
**Complejidad: Media**
**Riesgo: Bajo** (no afecta funcionalidad existente)