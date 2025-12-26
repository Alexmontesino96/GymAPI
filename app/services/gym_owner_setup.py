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
from app.models.module import Module
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
        gym_type: str,
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
                gym_name, gym_type, gym_address, gym_phone, gym_email or email, timezone
            )
            logger.info(f"Gimnasio creado (ID: {gym.id}, Subdomain: {gym.subdomain}, Type: {gym_type})")

            # 5. Asociar usuario con gimnasio como OWNER
            user_gym = await self._create_user_gym_relationship(user.id, gym.id)
            logger.info(f"Usuario asignado como OWNER del gimnasio")

            # 6. Activar módulos esenciales
            modules_activated = await self._activate_gym_modules(gym.id, gym_type)
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
        # Verificar si el usuario ya existe (puede haber sido creado por el webhook)
        existing_user = self.db.query(User).filter(User.auth0_id == auth0_id).first()
        if existing_user:
            logger.info(f"Usuario ya existe en BD (creado por webhook): {existing_user.id}")
            return existing_user

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
        gym_type: str,
        address: Optional[str],
        phone: Optional[str],
        email: str,
        timezone: str
    ) -> Gym:
        """Crear gimnasio en BD con tipo especificado"""
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

        # Convertir string a GymType enum
        gym_type_enum = GymType.gym if gym_type == "gym" else GymType.personal_trainer

        gym = Gym(
            name=name,
            type=gym_type_enum,
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

    async def _activate_gym_modules(self, gym_id: int, gym_type: str) -> list:
        """Activar módulos esenciales según el tipo de gimnasio"""

        if gym_type == "gym":
            # Módulos para gimnasios tradicionales
            essential_modules = [
                ("users", "Gestión de Miembros", True),
                ("schedule", "Clases y Horarios", True),
                ("events", "Eventos del Gimnasio", True),
                ("chat", "Mensajería", True),
                ("billing", "Pagos y Facturación", True),
                ("health", "Tracking de Salud", True),
                ("equipment", "Gestión de Equipos", True),
                ("classes", "Clases Grupales", True),
                ("attendance", "Asistencia", True),
                # Módulos premium - desactivados por defecto
                ("nutrition", "Planes Nutricionales", False),
                ("surveys", "Encuestas y Feedback", False),
                ("stories", "Historias", False),
                ("posts", "Publicaciones", False),
            ]
        else:  # personal_trainer
            # Módulos para entrenadores personales
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
                ("schedule", "Horarios del Gimnasio", False),
            ]

        modules_activated = []
        for module_code, description, is_active in essential_modules:
            # Buscar el módulo en la tabla modules por su código
            module = self.db.query(Module).filter(Module.code == module_code).first()

            if not module:
                logger.warning(f"Módulo {module_code} no encontrado en la tabla modules, saltando...")
                continue

            # Crear la relación gym-module
            gym_module = GymModule(
                gym_id=gym_id,
                module_id=module.id,
                active=is_active,
                activated_at=datetime.utcnow() if is_active else None
            )
            self.db.add(gym_module)

            if is_active:
                modules_activated.append(module_code)

        self.db.flush()
        return modules_activated

    async def _cleanup_auth0_user(self, auth0_user_id: str):
        """Eliminar usuario de Auth0 en caso de rollback"""
        try:
            # 1. Eliminar de Auth0
            token = self.auth0_service.get_auth_token()
            url = f"https://{self.settings.AUTH0_DOMAIN}/api/v2/users/{auth0_user_id}"
            headers = {"Authorization": f"Bearer {token}"}

            response = requests.delete(url, headers=headers)
            if response.status_code in [204, 404]:
                logger.info(f"Usuario Auth0 {auth0_user_id} eliminado en rollback")
            else:
                logger.error(f"Fallo al eliminar usuario Auth0: {response.text}")

            # 2. Eliminar de BD local si existe (puede haber sido creado por webhook)
            local_user = self.db.query(User).filter(User.auth0_id == auth0_user_id).first()
            if local_user:
                logger.info(f"Eliminando usuario local {local_user.id} creado por webhook durante rollback")
                self.db.delete(local_user)
                self.db.commit()  # Commit explícito para eliminar usuario del webhook
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
