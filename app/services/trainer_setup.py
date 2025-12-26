"""
Servicio de Setup para Entrenadores Personales

Este servicio maneja toda la lógica de creación de workspaces para entrenadores,
incluyendo configuración de Stripe, módulos y planes de pago.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
import stripe
import logging

from app.models.gym import Gym, GymType
from app.models.user import User, UserRole
from app.models.user_gym import UserGym, GymRoleType
from app.models.gym_module import GymModule
from app.models.membership import MembershipPlan
from app.core.config import Settings

logger = logging.getLogger(__name__)
settings = Settings()

# Configurar Stripe si está disponible
if hasattr(settings, 'STRIPE_API_KEY') and settings.STRIPE_API_KEY:
    stripe.api_key = settings.STRIPE_API_KEY


class TrainerSetupService:
    """Servicio para configuración automatizada de entrenadores personales"""

    def __init__(self, db: Session):
        self.db = db

    async def create_trainer_workspace(
        self,
        email: str,
        first_name: str,
        last_name: str,
        phone: Optional[str] = None,
        specialties: Optional[List[str]] = None,
        certifications: Optional[List[Dict]] = None,
        timezone: str = "America/Mexico_City",
        max_clients: int = 30,
        bio: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Crear workspace completo para un entrenador personal

        Args:
            email: Email del entrenador
            first_name: Nombre del entrenador
            last_name: Apellido del entrenador
            phone: Teléfono opcional
            specialties: Lista de especialidades
            certifications: Lista de certificaciones
            timezone: Zona horaria del workspace
            max_clients: Límite de clientes simultáneos
            bio: Biografía del entrenador

        Returns:
            Dict con información del resultado

        Raises:
            ValueError: Si el usuario ya existe o hay datos inválidos
            Exception: Si hay errores en la creación
        """
        try:
            logger.info(f"Iniciando setup para entrenador: {first_name} {last_name} ({email})")

            # 1. Verificar si el usuario ya existe
            existing_user = self.db.query(User).filter(
                User.email == email
            ).first()

            if existing_user:
                # Verificar si ya tiene un workspace de entrenador
                existing_workspace = self.db.query(UserGym).join(Gym).filter(
                    UserGym.user_id == existing_user.id,
                    UserGym.role == GymRoleType.OWNER,
                    Gym.type == GymType.personal_trainer
                ).first()

                if existing_workspace:
                    raise ValueError(
                        f"El usuario {email} ya tiene un workspace de entrenador (ID: {existing_workspace.gym_id})"
                    )

                user = existing_user
                logger.info(f"Usuario existente encontrado (ID: {user.id})")
            else:
                # 2. Crear usuario nuevo
                user = await self._create_user(
                    email, first_name, last_name, phone
                )
                logger.info(f"Usuario creado (ID: {user.id})")

            # 3. Crear "gimnasio" personal
            gym = await self._create_gym(
                first_name, last_name, email, phone,
                timezone, specialties, certifications,
                max_clients, bio
            )
            logger.info(f"Workspace creado (ID: {gym.id}, Subdomain: {gym.subdomain})")

            # 4. Crear relación UserGym como OWNER
            user_gym = await self._create_user_gym_relationship(user.id, gym.id)
            logger.info(f"Entrenador asignado como OWNER")

            # 5. Configurar Stripe Connect (opcional)
            stripe_data = await self._setup_stripe_connect(gym, user)
            stripe_onboarding_url = stripe_data.get('onboarding_url') if stripe_data else None

            # 6. Activar módulos esenciales
            modules_created = await self._activate_modules(gym.id)
            logger.info(f"Módulos activados: {len(modules_created)}")

            # 7. Crear planes de pago default (DESACTIVADO - se crean manualmente)
            # plans_created = await self._create_default_payment_plans(gym.id)
            # logger.info(f"Planes de pago creados: {len(plans_created)}")
            plans_created = []  # Sin planes automáticos
            logger.info(f"Setup sin planes de pago predeterminados")

            # Commit final
            self.db.commit()
            logger.info(f"Setup completado para entrenador {user.id} - gym {gym.id}")

            # 8. Preparar respuesta
            result = self._build_response(
                gym, user, modules_created, plans_created, stripe_onboarding_url
            )

            return result

        except ValueError as e:
            self.db.rollback()
            logger.warning(f"Validación falló: {str(e)}")
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creando workspace: {str(e)}", exc_info=True)
            raise Exception(f"Error al crear workspace: {str(e)}")

    async def _create_user(
        self,
        email: str,
        first_name: str,
        last_name: str,
        phone: Optional[str]
    ) -> User:
        """Crear nuevo usuario con rol TRAINER"""
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
        return user

    async def _create_gym(
        self,
        first_name: str,
        last_name: str,
        email: str,
        phone: Optional[str],
        timezone: str,
        specialties: Optional[List[str]],
        certifications: Optional[List[Dict]],
        max_clients: int,
        bio: Optional[str]
    ) -> Gym:
        """Crear gimnasio personal para el entrenador"""

        gym_name = f"Entrenamiento Personal {first_name} {last_name}"

        # Generar subdomain único
        subdomain = f"{first_name.lower()}-{last_name.lower()}".replace(" ", "-")
        subdomain = ''.join(c for c in subdomain if c.isalnum() or c == '-')
        subdomain = subdomain[:50]  # Limitar longitud

        # Verificar unicidad del subdomain
        counter = 1
        original_subdomain = subdomain
        while self.db.query(Gym).filter(Gym.subdomain == subdomain).first():
            subdomain = f"{original_subdomain}-{counter}"
            counter += 1

        # Descripción del workspace
        description = bio if bio else f"Espacio de entrenamiento personalizado de {first_name} {last_name}"

        gym = Gym(
            name=gym_name,
            type=GymType.personal_trainer,
            subdomain=subdomain,
            email=email,
            phone=phone,
            timezone=timezone,
            is_active=True,
            trainer_specialties=specialties or ["Fitness General"],
            trainer_certifications=certifications or [],
            max_clients=max_clients,
            description=description
        )
        self.db.add(gym)
        self.db.flush()
        return gym

    async def _create_user_gym_relationship(self, user_id: int, gym_id: int) -> UserGym:
        """Crear relación entre usuario y gimnasio como OWNER"""
        user_gym = UserGym(
            user_id=user_id,
            gym_id=gym_id,
            role=GymRoleType.OWNER,
            is_active=True,
            membership_type="owner",
            created_at=datetime.utcnow()
        )
        self.db.add(user_gym)
        self.db.flush()
        return user_gym

    async def _setup_stripe_connect(
        self,
        gym: Gym,
        user: User
    ) -> Optional[Dict[str, str]]:
        """Configurar cuenta Stripe Connect para el entrenador"""
        try:
            if not hasattr(settings, 'STRIPE_API_KEY') or not settings.STRIPE_API_KEY:
                logger.warning("Stripe API key no configurada, omitiendo setup de Stripe")
                return None

            # Crear cuenta Connect Standard
            account = stripe.Account.create(
                type="standard",
                country="MX",
                email=user.email,
                capabilities={
                    "transfers": {"requested": True},
                    "card_payments": {"requested": True}
                },
                business_profile={
                    "name": gym.name,
                    "product_description": "Servicios de entrenamiento personal",
                    "support_email": gym.email
                },
                metadata={
                    "gym_id": str(gym.id),
                    "user_id": str(user.id),
                    "type": "personal_trainer"
                }
            )

            # Generar link de onboarding
            frontend_url = getattr(settings, 'FRONTEND_URL', 'https://app.example.com')
            account_link = stripe.AccountLink.create(
                account=account.id,
                refresh_url=f"{frontend_url}/stripe/refresh",
                return_url=f"{frontend_url}/stripe/success",
                type="account_onboarding"
            )

            # Guardar en BD si existe la tabla
            try:
                from app.models.gym_stripe import GymStripeAccount
                gym_stripe = GymStripeAccount(
                    gym_id=gym.id,
                    stripe_account_id=account.id,
                    is_connected=False,
                    created_at=datetime.utcnow()
                )
                self.db.add(gym_stripe)
                logger.info(f"Stripe Connect configurado: {account.id}")
            except ImportError:
                logger.warning("Tabla GymStripeAccount no encontrada")

            return {
                "account_id": account.id,
                "onboarding_url": account_link.url
            }

        except Exception as e:
            logger.error(f"Error configurando Stripe: {e}")
            return None

    async def _activate_modules(self, gym_id: int) -> List[str]:
        """Activar módulos esenciales para el entrenador"""

        essential_modules = [
            ("users", "Gestión de Clientes", True),
            ("chat", "Mensajería", True),
            ("health", "Tracking de Salud", True),
            ("nutrition", "Planes Nutricionales", True),
            ("billing", "Pagos y Facturación", True),
            ("appointments", "Agenda de Citas", True),
            ("progress", "Progreso de Clientes", True),
            # Módulos premium - desactivados por defecto
            ("surveys", "Encuestas y Feedback", False),
            ("stories", "Historias", False),
            ("posts", "Publicaciones", False),
            # Módulos no aplicables para entrenadores
            ("equipment", "Gestión de Equipos", False),
            ("classes", "Clases Grupales", False),
            ("schedule", "Horarios del Gimnasio", False)
        ]

        modules_created = []
        for module_code, description, is_active in essential_modules:
            module = GymModule(
                gym_id=gym_id,
                module_code=module_code,
                is_active=is_active,
                description=description,
                config={},
                created_at=datetime.utcnow()
            )
            self.db.add(module)

            if is_active:
                modules_created.append(module_code)

        self.db.flush()
        return modules_created

    async def _create_default_payment_plans(self, gym_id: int) -> List[str]:
        """Crear planes de pago predeterminados"""

        default_plans = [
            {
                "name": "Sesión Individual",
                "type": "one_time",
                "price": 50000,  # $500 MXN
                "currency": "mxn",
                "sessions": 1
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

        plans_created = []

        for plan_data in default_plans:
            try:
                # Crear en Stripe si está configurado
                stripe_price_id = None
                if hasattr(settings, 'STRIPE_API_KEY') and settings.STRIPE_API_KEY:
                    try:
                        if plan_data["type"] == "subscription":
                            stripe_price = stripe.Price.create(
                                unit_amount=plan_data["price"],
                                currency=plan_data["currency"],
                                recurring={"interval": plan_data.get("interval", "month")},
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
                                    "sessions": str(plan_data.get("sessions", 1))
                                }
                            )
                        stripe_price_id = stripe_price.id
                    except Exception as e:
                        logger.warning(f"Error creando precio en Stripe para {plan_data['name']}: {e}")

                # Guardar en BD
                membership_plan = MembershipPlan(
                    gym_id=gym_id,
                    name=plan_data["name"],
                    stripe_price_id=stripe_price_id,
                    price=plan_data["price"],
                    currency=plan_data["currency"],
                    billing_interval=plan_data.get("interval", "one_time"),
                    is_active=True,
                    features=f"{plan_data.get('sessions', '')} sesiones" if plan_data.get('sessions') else "Sesiones ilimitadas",
                    created_at=datetime.utcnow()
                )
                self.db.add(membership_plan)
                plans_created.append(plan_data["name"])

            except Exception as e:
                logger.error(f"Error creando plan {plan_data['name']}: {e}")
                continue

        self.db.flush()
        return plans_created

    def _build_response(
        self,
        gym: Gym,
        user: User,
        modules_created: List[str],
        plans_created: List[str],
        stripe_onboarding_url: Optional[str]
    ) -> Dict[str, Any]:
        """Construir respuesta estructurada del setup"""

        response = {
            "success": True,
            "message": "Espacio de trabajo creado exitosamente",
            "workspace": {
                "id": gym.id,
                "name": gym.name,
                "subdomain": gym.subdomain,
                "type": gym.type.value,
                "email": gym.email,
                "timezone": gym.timezone,
                "specialties": gym.trainer_specialties,
                "max_clients": gym.max_clients
            },
            "user": {
                "id": user.id,
                "email": user.email,
                "name": f"{user.first_name} {user.last_name}",
                "role": user.role.value
            },
            "modules_activated": modules_created,
            "payment_plans": plans_created,
            "next_steps": [
                "Completar configuración de perfil",
                "Crear planes de pago personalizados",
                "Agregar primeros clientes",
                "Configurar horario de disponibilidad"
            ]
        }

        if stripe_onboarding_url:
            response["stripe_onboarding_url"] = stripe_onboarding_url
            response["next_steps"].insert(0, "Completar onboarding de Stripe para recibir pagos")

        return response


# Función helper para uso desde scripts
async def create_trainer_workspace_from_dict(db: Session, data: Dict[str, Any]) -> Dict[str, Any]:
    """Helper para crear workspace desde diccionario de datos"""
    service = TrainerSetupService(db)
    return await service.create_trainer_workspace(**data)