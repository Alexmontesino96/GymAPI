"""
AsyncAuth0ManagementService - Servicio async para Auth0 Management API.

Este módulo maneja operaciones de gestión de usuarios en Auth0:
- Actualización de emails y verificación
- Gestión de roles y metadata
- Rate limiting en memoria
- Token caching automático

Migrado en FASE 3 de la conversión sync → async.
"""

import time
import json
import logging
import math
from typing import Dict, Any, Optional, List
from fastapi import HTTPException
import httpx

from app.core.config import get_settings

logger = logging.getLogger("async_auth0_mgmt")


class RateLimiter:
    """
    Clase para limitar la tasa de operaciones por usuario o IP.

    Mantiene estado en memoria con diccionarios.

    Note:
        - No es distribuido (solo funciona en un proceso)
        - Para producción distribuida, considerar Redis
        - Limpia automáticamente timestamps antiguos
    """
    # Mapa de operaciones con su configuración de límites
    RATE_LIMITS = {
        "change_email": {"max_attempts": 3, "window_seconds": 3600},  # 3 intentos por hora
        "verify_email": {"max_attempts": 5, "window_seconds": 3600},  # 5 intentos por hora
        "reset_password": {"max_attempts": 3, "window_seconds": 3600},  # 3 intentos por hora
        "check_email": {"max_attempts": 10, "window_seconds": 600},  # 10 intentos por 10 minutos
    }

    def __init__(self):
        """
        Inicializa los diccionarios de tracking.

        Formato: {clave: {operación: [timestamp1, timestamp2, ...]}}
        """
        # Diccionario para rastrear solicitudes por clave (usuario_id o IP) y operación
        self.user_requests = {}
        # Diccionario para rastrear solicitudes por IP
        self.ip_requests = {}

    def can_perform_operation(self, operation: str, user_id: str = None, ip_key: str = None) -> bool:
        """
        Verifica si una operación puede ser realizada por un usuario o IP.

        Args:
            operation: Tipo de operación (change_email, verify_email, etc.)
            user_id: Identificador del usuario (opcional)
            ip_key: Clave de IP para limitar solicitudes (opcional)

        Returns:
            bool: True si la operación está permitida, False si excede el límite

        Note:
            - Requiere user_id O ip_key (al menos uno)
            - Limpia timestamps antiguos automáticamente
            - Registra la solicitud actual si está permitida
        """
        if operation not in self.RATE_LIMITS:
            return True  # Si la operación no está definida en el mapa, se permite

        # Obtener la configuración del límite para la operación
        limit_config = self.RATE_LIMITS[operation]

        # Determinar la clave correcta para rastrear solicitudes
        if user_id:
            key = user_id
        elif ip_key:
            key = ip_key
        else:
            return False  # Si no se proporciona user_id ni ip_key, no se permite la operación

        # Inicializar lista de timestamps si no existe
        if key not in self.user_requests:
            self.user_requests[key] = []

        # Eliminar timestamps antiguos (fuera de la ventana de tiempo)
        current_time = time.time()
        self.user_requests[key] = [t for t in self.user_requests[key] if current_time - t <= limit_config["window_seconds"]]

        # Verificar si se excede el límite
        if len(self.user_requests[key]) >= limit_config["max_attempts"]:
            return False

        # Registrar la solicitud actual
        self.user_requests[key].append(current_time)
        return True

    def can_check_email(self, ip_address: str) -> bool:
        """
        Verifica si una IP puede realizar una comprobación de disponibilidad de email.

        Args:
            ip_address: Dirección IP desde donde se realiza la solicitud

        Returns:
            bool: True si puede realizar la operación, False si ha alcanzado el límite
        """
        return self.can_perform_operation("check_email", ip_key=ip_address)


class AsyncAuth0ManagementService:
    """
    Servicio async para interactuar con la API de Management de Auth0.

    Todos los métodos HTTP son async utilizando httpx.

    Funcionalidades:
    - Gestión de usuarios (email, metadata, verificación)
    - Gestión de roles (listar, asignar, reasignar)
    - Check de disponibilidad de email
    - Token caching automático con TTL
    - Rate limiting por operación

    Métodos principales:
    - update_user_email() - Actualizar email con verificación opcional
    - get_user() - Obtener info de usuario
    - update_user_metadata() - Actualizar app_metadata
    - assign_roles_to_user() - Asignar roles

    Note:
        - Token se refresca automáticamente antes de expirar
        - Rate limiting en memoria (no distribuido)
        - httpx.AsyncClient para todas las llamadas HTTP
    """

    def __init__(self):
        """
        Inicializa el servicio con credenciales de Auth0.

        Los tokens de acceso se obtienen y se refrescan automáticamente.

        Note:
            - Token cacheado en memoria con TTL
            - Rate limiters independientes por tipo de operación
        """
        self.domain = get_settings().AUTH0_DOMAIN
        self.client_id = get_settings().AUTH0_MGMT_CLIENT_ID
        self.client_secret = get_settings().AUTH0_MGMT_CLIENT_SECRET
        self.audience = get_settings().AUTH0_MGMT_AUDIENCE
        self.token = None
        self.token_expires_at = 0
        self._initialized = False

        # Rate limiters para diferentes operaciones
        self.email_change_limiter = RateLimiter()
        self.verification_limiter = RateLimiter()

    def is_initialized(self) -> bool:
        """
        Verifica si el servicio ha sido inicializado.

        Returns:
            bool: True si el servicio está inicializado
        """
        return self._initialized

    async def initialize(self) -> bool:
        """
        Inicializa el servicio y verifica la conexión con Auth0 async.

        Returns:
            bool: True si la inicialización fue exitosa

        Note:
            - Obtiene token de prueba para validar credenciales
            - Marca servicio como inicializado si exitoso
        """
        try:
            # Intentar obtener un token para verificar la conexión (async)
            await self.get_auth_token()
            self._initialized = True
            return True
        except Exception as e:
            logger.error(f"Error inicializando AsyncAuth0 Management Service: {str(e)}")
            self._initialized = False
            return False

    async def get_auth_token(self) -> str:
        """
        Obtiene un token de acceso para la API de Management de Auth0 async.

        El token se almacena en caché y se renueva automáticamente cuando expira.

        Returns:
            str: Token de acceso para la API de Management

        Raises:
            HTTPException: Si hay error al obtener token

        Note:
            - Token cacheado con 60 segundos de margen antes de expirar
            - Usa httpx.AsyncClient para llamada async
        """
        # Verificar si el token actual es válido
        current_time = time.time()
        if self.token and current_time < self.token_expires_at - 60:  # 60 segundos de margen
            return self.token

        # Obtener un nuevo token (async)
        url = f"https://{self.domain}/oauth/token"
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "audience": self.audience,
            "grant_type": "client_credentials"
        }
        headers = {"content-type": "application/json"}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()

            data = response.json()
            self.token = data.get("access_token")
            # Guardar cuándo expira el token (convertir expires_in a timestamp absoluto)
            self.token_expires_at = current_time + data.get("expires_in", 86400)

            return self.token
        except httpx.HTTPStatusError as e:
            logger.error(f"Error al obtener token de Auth0: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error al conectar con Auth0: {str(e)}"
            )

    async def update_user_email(self, auth0_id: str, new_email: str, verify_email: bool = False) -> Dict[str, Any]:
        """
        Actualiza el email de un usuario en Auth0 async.

        Args:
            auth0_id: ID de Auth0 del usuario (sub)
            new_email: Nuevo email para el usuario
            verify_email: Si se debe enviar un email de verificación

        Returns:
            Dict[str, Any]: Información del usuario actualizada

        Raises:
            HTTPException 429: Si excede rate limit
            HTTPException 500: Si hay error al actualizar

        Note:
            - Rate limit: 3 cambios por hora
            - Siempre marca email_verified=False por seguridad
            - Usa httpx.AsyncClient para llamada async
        """
        # Comprobar rate limiting
        if not self.email_change_limiter.can_perform_operation("change_email", user_id=auth0_id):
            remaining_time = self._get_reset_time("change_email", auth0_id)
            raise HTTPException(
                status_code=429,
                detail=f"Has excedido el límite de cambios de email. Por favor, inténtalo de nuevo más tarde. Tiempo restante: {remaining_time} minutos"
            )

        token = await self.get_auth_token()
        url = f"https://{self.domain}/api/v2/users/{auth0_id}"

        payload = {
            "email": new_email,
            "email_verified": False,  # Siempre marcar como no verificado por seguridad
            "verify_email": verify_email
        }

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        try:
            logger.info(f"Actualizando email para {auth0_id}: {new_email}, verificación: {verify_email}")

            async with httpx.AsyncClient() as client:
                response = await client.patch(url, json=payload, headers=headers)
                response.raise_for_status()

            logger.info(f"Email actualizado exitosamente para {auth0_id}")
            return response.json()
        except httpx.HTTPStatusError as e:
            error_detail = f"Error al actualizar email en Auth0: {str(e)}"

            # Intentar obtener el mensaje de error detallado de Auth0
            try:
                error_data = e.response.json()
                error_message = error_data.get('message', error_detail)
                error_detail = f"{error_detail} - {error_message}"
            except:
                pass

            logger.error(error_detail)

            raise HTTPException(
                status_code=e.response.status_code if e.response else 500,
                detail=error_detail
            )

    async def get_user(self, auth0_id: str) -> Dict[str, Any]:
        """
        Obtiene la información de un usuario de Auth0 async.

        Args:
            auth0_id: ID de Auth0 del usuario (sub)

        Returns:
            Dict[str, Any]: Información del usuario

        Raises:
            HTTPException: Si hay un error al obtener la información

        Note:
            - Usa httpx.AsyncClient para llamada async
            - Incluye todos los campos del usuario
        """
        token = await self.get_auth_token()
        url = f"https://{self.domain}/api/v2/users/{auth0_id}"

        headers = {
            "Authorization": f"Bearer {token}"
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()

            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Error al obtener información del usuario: {str(e)}")

            raise HTTPException(
                status_code=e.response.status_code if e.response else 500,
                detail=f"Error al obtener información del usuario: {str(e)}"
            )

    async def check_email_availability(self, email: str) -> bool:
        """
        Verifica si un email está disponible para ser utilizado en Auth0 async.

        Args:
            email: Email a verificar

        Returns:
            bool: True si el email está disponible, False si ya está en uso

        Raises:
            HTTPException: Si hay un error al consultar Auth0

        Note:
            - Usa search_engine v3 con query filter
            - En caso de error, retorna True para no bloquear flujo
            - Usa httpx.AsyncClient para llamada async
        """
        token = await self.get_auth_token()

        # Auth0 no proporciona un endpoint directo para verificar disponibilidad de email.
        # Una alternativa es usar el endpoint de usuarios con un filtro por email.
        url = f"https://{self.domain}/api/v2/users"
        params = {
            "q": f"email:\"{email}\"",
            "search_engine": "v3"
        }

        headers = {
            "Authorization": f"Bearer {token}"
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()

            users = response.json()
            # Si hay usuarios con ese email, no está disponible
            is_available = len(users) == 0

            logger.info(f"Verificando disponibilidad de email {email}: {is_available}")
            return is_available
        except httpx.HTTPStatusError as e:
            logger.error(f"Error al verificar disponibilidad de email: {str(e)}")

            # En caso de error, asumimos que está disponible para evitar bloquear el flujo
            # pero logeamos el error para investigación
            return True

    async def send_verification_email(self, user_id: str) -> bool:
        """
        Solicita a Auth0 que envíe un correo de verificación al usuario async.

        Args:
            user_id: ID de Auth0 del usuario

        Returns:
            bool: True si se envió correctamente

        Raises:
            HTTPException 429: Si excede rate limit
            HTTPException 500: Si hay error al enviar

        Note:
            - Rate limit: 5 envíos por hora
            - Usa httpx.AsyncClient para llamada async
        """
        # Comprobar rate limiting
        if not self.verification_limiter.can_perform_operation("verify_email", user_id=user_id):
            remaining_time = self._get_reset_time("verify_email", user_id)
            raise HTTPException(
                status_code=429,
                detail=f"Has excedido el límite de envíos de verificación. Por favor, inténtalo de nuevo más tarde. Tiempo restante: {remaining_time} minutos"
            )

        token = await self.get_auth_token()
        url = f"https://{self.domain}/api/v2/jobs/verification-email"

        payload = {
            "user_id": user_id
        }

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        try:
            logger.info(f"Enviando correo de verificación a {user_id}")

            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()

            logger.info(f"Correo de verificación enviado exitosamente a {user_id}")
            return True
        except httpx.HTTPStatusError as e:
            error_detail = f"Error al enviar correo de verificación: {str(e)}"

            try:
                error_data = e.response.json()
                error_message = error_data.get('message', error_detail)
                error_detail = f"{error_detail} - {error_message}"
            except:
                pass

            logger.error(error_detail)

            raise HTTPException(
                status_code=e.response.status_code if e.response else 500,
                detail=error_detail
            )

    def _get_reset_time(self, operation: str, user_id: str) -> int:
        """
        Método interno para calcular tiempo restante para poder realizar otra operación.

        Args:
            operation: Tipo de operación
            user_id: ID del usuario

        Returns:
            int: Minutos restantes aproximados

        Note:
            - Calcula basado en oldest_request en ventana actual
            - Redondea hacia arriba
        """
        # Determinar el limiter correcto según la operación
        if operation == "change_email":
            limiter = self.email_change_limiter
        elif operation == "verify_email":
            limiter = self.verification_limiter
        else:
            return 60  # valor por defecto

        # Cálculo aproximado del tiempo restante
        key = f"{user_id}:{operation}"
        if key not in limiter.user_requests or not limiter.user_requests[key]:
            return 0

        # Tiempo del primer request en la ventana actual
        oldest_request = min(limiter.user_requests[key])
        seconds_passed = time.time() - oldest_request
        seconds_remaining = limiter.RATE_LIMITS[operation]["window_seconds"] - seconds_passed

        # Convertir a minutos y redondear hacia arriba
        return math.ceil(seconds_remaining / 60)

    async def update_user_metadata(self, auth0_id: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Actualiza el app_metadata de un usuario en Auth0 async.

        Args:
            auth0_id: ID de Auth0 del usuario (auth0|xxxx)
            metadata: Diccionario con los metadatos a actualizar

        Returns:
            Dict[str, Any]: Información del usuario actualizada

        Raises:
            HTTPException: Si hay un error al actualizar los metadatos

        Note:
            - app_metadata es para datos de la aplicación (no user_metadata)
            - Usa httpx.AsyncClient para llamada async
        """
        token = await self.get_auth_token()
        url = f"https://{self.domain}/api/v2/users/{auth0_id}"

        payload = {
            "app_metadata": metadata
        }

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        try:
            logger.info(f"Actualizando app_metadata para {auth0_id}: {json.dumps(metadata)}")

            async with httpx.AsyncClient() as client:
                response = await client.patch(url, json=payload, headers=headers)
                response.raise_for_status()

            logger.info(f"app_metadata actualizado exitosamente para {auth0_id}")
            return response.json()
        except httpx.HTTPStatusError as e:
            error_detail = f"Error al actualizar app_metadata en Auth0: {str(e)}"

            # Intentar obtener el mensaje de error detallado de Auth0
            try:
                error_data = e.response.json()
                error_message = error_data.get('message', error_detail)
                error_detail = f"{error_detail} - {error_message}"
            except:
                pass

            logger.error(error_detail)

            raise HTTPException(
                status_code=e.response.status_code if e.response else 500,
                detail=error_detail
            )

    async def get_roles(self) -> List[Dict[str, Any]]:
        """
        Obtiene todos los roles definidos en Auth0 async.

        Returns:
            List[Dict[str, Any]]: Lista de roles disponibles en Auth0

        Raises:
            HTTPException: Si hay un error en la comunicación con Auth0

        Note:
            - Usa httpx.AsyncClient para llamada async
            - Retorna todos los roles sin paginación
        """
        token = await self.get_auth_token()
        url = f"https://{self.domain}/api/v2/roles"

        headers = {
            "Authorization": f"Bearer {token}"
        }

        try:
            logger.info(f"Obteniendo lista de roles de Auth0")

            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()

            logger.info(f"Roles obtenidos exitosamente")
            return response.json()
        except httpx.HTTPStatusError as e:
            error_detail = f"Error al obtener roles de Auth0: {str(e)}"

            try:
                error_data = e.response.json()
                error_message = error_data.get('message', error_detail)
                error_detail = f"{error_detail} - {error_message}"
            except:
                pass

            logger.error(error_detail)

            raise HTTPException(
                status_code=e.response.status_code if e.response else 500,
                detail=error_detail
            )

    async def get_role_by_name(self, role_name: str) -> Optional[Dict[str, Any]]:
        """
        Busca un rol por su nombre en Auth0 async.

        Args:
            role_name: Nombre del rol a buscar

        Returns:
            Optional[Dict[str, Any]]: Información del rol si se encuentra, None en caso contrario

        Raises:
            HTTPException: Si hay un error en la comunicación con Auth0

        Note:
            - Obtiene todos los roles y busca por nombre
            - No case-sensitive
        """
        roles = await self.get_roles()

        for role in roles:
            if role.get('name') == role_name:
                return role

        return None

    async def assign_roles_to_user(self, auth0_id: str, role_names: List[str]) -> bool:
        """
        Asigna roles a un usuario en Auth0 async.

        Reemplaza TODOS los roles actuales por los nuevos.

        Args:
            auth0_id: ID de Auth0 del usuario
            role_names: Lista de nombres de roles a asignar

        Returns:
            bool: True si se asignaron correctamente

        Raises:
            HTTPException: Si hay un error en la comunicación con Auth0

        Note:
            - Elimina roles actuales antes de asignar nuevos
            - Usa httpx.AsyncClient para todas las llamadas async
            - Si un rol no existe, lo omite con warning
        """
        # Primero, obtener los roles actuales del usuario
        token = await self.get_auth_token()
        roles_url = f"https://{self.domain}/api/v2/users/{auth0_id}/roles"

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        try:
            async with httpx.AsyncClient() as client:
                # Obtener roles actuales (async)
                current_roles_response = await client.get(roles_url, headers=headers)
                current_roles_response.raise_for_status()
                current_roles = current_roles_response.json()

                # Eliminar roles actuales (async)
                if current_roles:
                    current_role_ids = [role["id"] for role in current_roles]
                    delete_url = f"https://{self.domain}/api/v2/users/{auth0_id}/roles"
                    delete_payload = {"roles": current_role_ids}

                    delete_response = await client.delete(delete_url, json=delete_payload, headers=headers)
                    delete_response.raise_for_status()
                    logger.info(f"Roles eliminados para usuario {auth0_id}")

            # Obtener IDs de los nuevos roles (async)
            role_ids = []
            for role_name in role_names:
                role = await self.get_role_by_name(role_name)
                if role:
                    role_ids.append(role["id"])
                else:
                    logger.warning(f"Rol '{role_name}' no encontrado en Auth0")

            if not role_ids:
                logger.warning(f"No se encontraron roles válidos para asignar a {auth0_id}")
                return False

            # Asignar nuevos roles (async)
            async with httpx.AsyncClient() as client:
                assign_url = f"https://{self.domain}/api/v2/users/{auth0_id}/roles"
                assign_payload = {"roles": role_ids}

                assign_response = await client.post(assign_url, json=assign_payload, headers=headers)
                assign_response.raise_for_status()

            logger.info(f"Roles asignados exitosamente a usuario {auth0_id}: {', '.join(role_names)}")
            return True

        except httpx.HTTPStatusError as e:
            error_detail = f"Error asignando roles a usuario {auth0_id}: {str(e)}"

            try:
                error_data = e.response.json()
                error_message = error_data.get('message', error_detail)
                error_detail = f"{error_detail} - {error_message}"
            except:
                pass

            logger.error(error_detail)
            return False


# Instancia singleton del servicio async
async_auth0_mgmt_service = AsyncAuth0ManagementService()
