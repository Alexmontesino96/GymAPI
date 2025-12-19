"""
Servicio de Setup para Dueños de Gimnasio

Este servicio maneja toda la lógica de creación de gimnasios con sus dueños,
incluyendo creación en Auth0, base de datos local y configuración inicial.
"""

from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
import requests
import logging

from app.models.gym import Gym, GymType
from app.models.user import User, UserRole
from app.models.user_gym import UserGym, GymRoleType
from app.models.gym_module import GymModule
from app.services.auth0_mgmt import Auth0ManagementService
from app.core.config import get_settings
from fastapi import HTTPException

logger = logging.getLogger(__name__)


class GymOwnerSetupService:
    """Servicio para configuración automatizada de dueños de gimnasio"""

    def __init__(self, db: Session):
        self.db = db
        self.auth0_service = Auth0ManagementService()
        self.settings = get_settings()

    async def create_gym_owner_workspace(
        self,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        phone: Optional[str],
        gym_name: str,
        gym_address: Optional[str],
        gym_phone: Optional[str],
        gym_email: Optional[str],
        timezone: str
    ) -> Dict[str, Any]:
        """
        Flujo completo de creación de gimnasio y dueño

        Pasos:
        1. Verificar email único en BD local y Auth0
        2. Crear usuario en Auth0 con contraseña
        3. Crear usuario en BD local
        4. Crear gimnasio en BD local
        5. Crear relación UserGym con rol OWNER
        6. Activar módulos esenciales
        7. Commit o rollback completo

        Raises:
            ValueError: Si datos inválidos o email ya existe
            HTTPException: Si falla algún paso crítico
        """
        auth0_user_id = None  # Para rollback si falla

        try:
            logger.info(f"Iniciando registro de gym owner: {email} - Gym: {gym_name}")

            # 1. Verificar email único
            await self._verify_email_availability(email)

            # 2. Crear usuario en Auth0 con contraseña
            auth0_user = await self._create_auth0_user(
                email, password, first_name, last_name, phone
            )
            auth0_user_id = auth0_user['user_id']
            logger.info(f"Usuario creado en Auth0: {auth0_user_id}")

            # 3. Crear usuario en BD local
            user = await self._create_local_user(
                email, first_name, last_name, phone, auth0_user_id
            )
            logger.info(f"Usuario creado en BD local (ID: {user.id})")

            # 4. Crear gimnasio
            gym = await self._create_gym(
                gym_name, gym_address, gym_phone, gym_email or email, timezone
            )
            logger.info(f"Gimnasio creado (ID: {gym.id}, Subdomain: {gym.subdomain})")

            # 5. Asociar usuario con gimnasio como OWNER
            user_gym = await self._create_user_gym_relationship(user.id, gym.id)
            logger.info(f"Usuario asignado como OWNER del gimnasio")

            # 6. Activar módulos esenciales
            modules_activated = await self._activate_gym_modules(gym.id)
            logger.info(f"Módulos activados: {len(modules_activated)}")

            # 7. Commit
            self.db.commit()
            logger.info(f"Setup completado - User: {user.id}, Gym: {gym.id}")

            return self._build_response(gym, user, modules_activated)

        except ValueError as e:
            # Errores de validación - no hacer rollback de Auth0
            self.db.rollback()
            logger.warning(f"Validación falló: {str(e)}")
            raise

        except Exception as e:
            # Rollback completo
            self.db.rollback()
            logger.error(f"Error creando gym owner workspace: {str(e)}", exc_info=True)

            # Rollback Auth0 si se creó el usuario
            if auth0_user_id:
                await self._cleanup_auth0_user(auth0_user_id)

            raise Exception(f"Error al crear workspace: {str(e)}")

    async def _verify_email_availability(self, email: str):
        """Verifica que el email no exista ni en BD local ni en Auth0"""
        # Verificar BD local
        existing_user = self.db.query(User).filter(User.email == email).first()
        if existing_user:
            raise ValueError(f"El email {email} ya está registrado")

        # Verificar Auth0
        try:
            is_available = self.auth0_service.check_email_availability(email)
            if not is_available:
                raise ValueError(f"El email {email} ya está en uso")
        except Exception as e:
            logger.warning(f"No se pudo verificar email en Auth0: {e}")
            # Continuar - la validación principal es la BD local

    async def _create_auth0_user(
        self,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        phone: Optional[str]
    ) -> Dict[str, Any]:
        """
        Crear usuario en Auth0 con contraseña usando Management API v2

        POST https://{domain}/api/v2/users
        """
        token = self.auth0_service.get_auth_token()
        url = f"https://{self.settings.AUTH0_DOMAIN}/api/v2/users"

        payload = {
            "email": email,
            "password": password,
            "connection": "Username-Password-Authentication",  # Database connection
            "email_verified": False,  # Requiere verificación
            "verify_email": True,  # Enviar email de verificación
            "name": f"{first_name} {last_name}",
            "given_name": first_name,
            "family_name": last_name,
            "user_metadata": {
                "phone": phone,
                "registration_type": "gym_owner"
            },
            "app_metadata": {
                "role": "OWNER",
                "registration_date": datetime.utcnow().isoformat()
            }
        }

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Error creando usuario en Auth0: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response: {e.response.text}")
            raise HTTPException(
                status_code=503,
                detail=f"Error al crear usuario en Auth0: {str(e)}"
            )

    async def _create_local_user(
        self,
        email: str,
        first_name: str,
        last_name: str,
        phone: Optional[str],
        auth0_id: str
    ) -> User:
        """Crear usuario en BD local"""
        user = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone_number=phone,
            auth0_id=auth0_id,
            role=UserRole.ADMIN,  # Rol local como ADMIN
            is_active=True,
            created_at=datetime.utcnow()
        )
        self.db.add(user)
        self.db.flush()  # Obtener ID sin commit
        return user

    async def _create_gym(
        self,
        name: str,
        address: Optional[str],
        phone: Optional[str],
        email: str,
        timezone: str
    ) -> Gym:
        """Crear gimnasio tradicional en BD"""
        # Generar subdomain único
        subdomain = name.lower().replace(" ", "-")
        subdomain = ''.join(c for c in subdomain if c.isalnum() or c == '-')
        subdomain = subdomain[:50]  # Limitar longitud

        # Verificar unicidad
        counter = 1
        original_subdomain = subdomain
        while self.db.query(Gym).filter(Gym.subdomain == subdomain).first():
            subdomain = f"{original_subdomain}-{counter}"
            counter += 1

        gym = Gym(
            name=name,
            type=GymType.gym,  # Gimnasio tradicional
            subdomain=subdomain,
            address=address,
            phone=phone,
            email=email,
            timezone=timezone,
            is_active=True,
            created_at=datetime.utcnow()
        )
        self.db.add(gym)
        self.db.flush()
        return gym

    async def _create_user_gym_relationship(self, user_id: int, gym_id: int) -> UserGym:
        """Crear relación usuario-gimnasio como OWNER"""
        user_gym = UserGym(
            user_id=user_id,
            gym_id=gym_id,
            role=GymRoleType.OWNER,  # Rol específico del gym
            is_active=True,
            membership_type="owner",
            created_at=datetime.utcnow()
        )
        self.db.add(user_gym)
        self.db.flush()
        return user_gym

    async def _activate_gym_modules(self, gym_id: int) -> list:
        """Activar módulos esenciales para gimnasios tradicionales"""

        essential_modules = [
            ("users", "Gestión de Miembros", True),
            ("schedule", "Clases y Horarios", True),
            ("events", "Eventos del Gimnasio", True),
            ("chat", "Mensajería", True),
            ("billing", "Pagos y Facturación", True),
            ("health", "Tracking de Salud", True),
            ("nutrition", "Planes Nutricionales", True),
            ("surveys", "Encuestas y Feedback", True),
            ("equipment", "Gestión de Equipos", True),
        ]

        modules_activated = []
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
                modules_activated.append(module_code)

        self.db.flush()
        return modules_activated

    async def _cleanup_auth0_user(self, auth0_user_id: str):
        """Eliminar usuario de Auth0 en caso de rollback"""
        try:
            token = self.auth0_service.get_auth_token()
            url = f"https://{self.settings.AUTH0_DOMAIN}/api/v2/users/{auth0_user_id}"
            headers = {"Authorization": f"Bearer {token}"}

            response = requests.delete(url, headers=headers)
            if response.status_code in [204, 404]:
                logger.info(f"Usuario Auth0 {auth0_user_id} eliminado en rollback")
            else:
                logger.error(f"Fallo al eliminar usuario Auth0: {response.text}")
        except Exception as e:
            logger.error(f"Error en rollback de Auth0: {e}")

    def _build_response(
        self,
        gym: Gym,
        user: User,
        modules_activated: list
    ) -> Dict[str, Any]:
        """Construir respuesta estructurada"""
        return {
            "success": True,
            "message": "Gimnasio y usuario creados exitosamente",
            "gym": {
                "id": gym.id,
                "name": gym.name,
                "subdomain": gym.subdomain,
                "type": gym.type.value,
                "timezone": gym.timezone,
                "is_active": gym.is_active
            },
            "user": {
                "id": user.id,
                "email": user.email,
                "name": f"{user.first_name} {user.last_name}",
                "role": user.role.value
            },
            "modules_activated": modules_activated,
            "stripe_setup_required": True,
            "next_steps": [
                "Verificar email haciendo clic en el enlace enviado",
                "Configurar Stripe Connect para pagos",
                "Configurar horarios del gimnasio",
                "Crear clases y horarios",
                "Agregar primeros miembros"
            ]
        }
