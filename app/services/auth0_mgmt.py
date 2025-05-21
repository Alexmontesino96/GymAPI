import os
import json
import time
import requests
from typing import Dict, Any, Optional, List
from fastapi import HTTPException
from app.core.config import get_settings


class RateLimiter:
    """
    Clase para limitar la tasa de operaciones por usuario o IP.
    """
    # Mapa de operaciones con su configuración de límites
    RATE_LIMITS = {
        "change_email": {"max_attempts": 3, "window_seconds": 3600},  # 3 intentos por hora
        "verify_email": {"max_attempts": 5, "window_seconds": 3600},  # 5 intentos por hora
        "reset_password": {"max_attempts": 3, "window_seconds": 3600},  # 3 intentos por hora
        "check_email": {"max_attempts": 10, "window_seconds": 600},  # 10 intentos por 10 minutos
    }

    def __init__(self):
        # Diccionario para rastrear solicitudes por clave (usuario_id o IP) y operación
        # Formato: {clave: {operación: [(timestamp, ...)]}
        self.user_requests = {}
        # Diccionario para rastrear solicitudes por IP
        # Formato: {ip: {operación: [(timestamp, ...)]}
        self.ip_requests = {}
    
    def can_perform_operation(self, operation: str, user_id: str = None, ip_key: str = None) -> bool:
        """
        Verifica si una operación puede ser realizada por un usuario o IP.
        
        Args:
            operation: Tipo de operación
            user_id: Identificador del usuario
            ip_key: Clave de IP para limitar solicitudes
            
        Returns:
            bool: True si la operación está permitida, False si excede el límite
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


class Auth0ManagementService:
    """
    Servicio para interactuar con la API de Management de Auth0.
    Proporciona métodos para gestionar usuarios, actualizar emails, etc.
    """
    
    def __init__(self):
        """
        Inicializa el servicio con las credenciales de Auth0.
        Los tokens de acceso se obtienen y se refrescan automáticamente.
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
            bool: True si el servicio está inicializado, False en caso contrario
        """
        return self._initialized
    
    async def initialize(self) -> bool:
        """
        Inicializa el servicio y verifica la conexión con Auth0.

        Returns:
            bool: True si la inicialización fue exitosa, False en caso contrario
        """
        try:
            # Intentar obtener un token para verificar la conexión
            self.get_auth_token()
            self._initialized = True
            return True
        except Exception as e:
            import logging
            logger = logging.getLogger("auth0_service")
            logger.error(f"Error inicializando Auth0 Management Service: {str(e)}")
            self._initialized = False
            return False
    
    def get_auth_token(self) -> str:
        """
        Obtiene un token de acceso para la API de Management de Auth0.
        El token se almacena en caché y se renueva automáticamente cuando expira.
        
        Returns:
            str: Token de acceso para la API de Management
        """
        # Verificar si el token actual es válido
        current_time = time.time()
        if self.token and current_time < self.token_expires_at - 60:  # 60 segundos de margen
            return self.token
        
        # Obtener un nuevo token
        url = f"https://{self.domain}/oauth/token"
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "audience": self.audience,
            "grant_type": "client_credentials"
        }
        headers = {"content-type": "application/json"}
        
        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            self.token = data.get("access_token")
            # Guardar cuándo expira el token (convertir expires_in a timestamp absoluto)
            self.token_expires_at = current_time + data.get("expires_in", 86400)
            
            return self.token
        except requests.RequestException as e:
            import logging
            logger = logging.getLogger("auth0_service")
            logger.error(f"Error al obtener token de Auth0: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error al conectar con Auth0: {str(e)}"
            )
    
    def update_user_email(self, auth0_id: str, new_email: str, verify_email: bool = False) -> Dict[str, Any]:
        """
        Actualiza el email de un usuario en Auth0.
        
        Args:
            auth0_id: ID de Auth0 del usuario (sub)
            new_email: Nuevo email para el usuario
            verify_email: Si se debe enviar un email de verificación
            
        Returns:
            Dict[str, Any]: Información del usuario actualizada
            
        Raises:
            HTTPException: Si hay un error al actualizar el email
        """
        # Comprobar rate limiting
        if not self.email_change_limiter.can_perform_operation("change_email", user_id=auth0_id):
            remaining_time = self._get_reset_time("change_email", auth0_id)
            raise HTTPException(
                status_code=429,
                detail=f"Has excedido el límite de cambios de email. Por favor, inténtalo de nuevo más tarde. Tiempo restante: {remaining_time} minutos"
            )
        
        token = self.get_auth_token()
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
            import logging
            logger = logging.getLogger("auth0_service")
            logger.info(f"Actualizando email para {auth0_id}: {new_email}, verificación: {verify_email}")
            
            response = requests.patch(url, json=payload, headers=headers)
            response.raise_for_status()
            
            logger.info(f"Email actualizado exitosamente para {auth0_id}")
            return response.json()
        except requests.RequestException as e:
            error_detail = f"Error al actualizar email en Auth0: {str(e)}"
            
            # Intentar obtener el mensaje de error detallado de Auth0
            if hasattr(e, 'response') and e.response:
                try:
                    error_data = e.response.json()
                    error_message = error_data.get('message', error_detail)
                    error_detail = f"{error_detail} - {error_message}"
                except:
                    pass
            
            logger.error(error_detail)
            
            status_code = 500
            if hasattr(e, 'response') and e.response:
                status_code = e.response.status_code
                
            raise HTTPException(
                status_code=status_code,
                detail=error_detail
            )
    
    def get_user(self, auth0_id: str) -> Dict[str, Any]:
        """
        Obtiene la información de un usuario de Auth0.
        
        Args:
            auth0_id: ID de Auth0 del usuario (sub)
            
        Returns:
            Dict[str, Any]: Información del usuario
            
        Raises:
            HTTPException: Si hay un error al obtener la información del usuario
        """
        token = self.get_auth_token()
        url = f"https://{self.domain}/api/v2/users/{auth0_id}"
        
        headers = {
            "Authorization": f"Bearer {token}"
        }
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            import logging
            logger = logging.getLogger("auth0_service")
            logger.error(f"Error al obtener información del usuario: {str(e)}")
            
            status_code = 500
            if hasattr(e, 'response') and e.response:
                status_code = e.response.status_code
                
            raise HTTPException(
                status_code=status_code,
                detail=f"Error al obtener información del usuario: {str(e)}"
            )
    
    def check_email_availability(self, email: str) -> bool:
        """
        Verifica si un email está disponible para ser utilizado en Auth0.
        
        Args:
            email: Email a verificar
            
        Returns:
            bool: True si el email está disponible, False si ya está en uso
            
        Raises:
            HTTPException: Si hay un error al consultar Auth0
        """
        token = self.get_auth_token()
        
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
            import logging
            logger = logging.getLogger("auth0_service")
            
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            users = response.json()
            # Si hay usuarios con ese email, no está disponible
            is_available = len(users) == 0
            
            logger.info(f"Verificando disponibilidad de email {email}: {is_available}")
            return is_available
        except requests.RequestException as e:
            logger.error(f"Error al verificar disponibilidad de email: {str(e)}")
            
            # En caso de error, asumimos que está disponible para evitar bloquear el flujo
            # pero logeamos el error para investigación
            return True
    
    def send_verification_email(self, user_id: str) -> bool:
        """
        Solicita a Auth0 que envíe un correo de verificación al usuario.
        
        Args:
            user_id: ID de Auth0 del usuario
            
        Returns:
            bool: True si se envió correctamente
            
        Raises:
            HTTPException: Si hay un error al enviar el correo
        """
        # Comprobar rate limiting
        if not self.verification_limiter.can_perform_operation("verify_email", user_id=user_id):
            remaining_time = self._get_reset_time("verify_email", user_id)
            raise HTTPException(
                status_code=429,
                detail=f"Has excedido el límite de envíos de verificación. Por favor, inténtalo de nuevo más tarde. Tiempo restante: {remaining_time} minutos"
            )
        
        token = self.get_auth_token()
        url = f"https://{self.domain}/api/v2/jobs/verification-email"
        
        payload = {
            "user_id": user_id
        }
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        try:
            import logging
            logger = logging.getLogger("auth0_service")
            logger.info(f"Enviando correo de verificación a {user_id}")
            
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            logger.info(f"Correo de verificación enviado exitosamente a {user_id}")
            return True
        except requests.RequestException as e:
            error_detail = f"Error al enviar correo de verificación: {str(e)}"
            
            if hasattr(e, 'response') and e.response:
                try:
                    error_data = e.response.json()
                    error_message = error_data.get('message', error_detail)
                    error_detail = f"{error_detail} - {error_message}"
                except:
                    pass
            
            logger.error(error_detail)
            
            status_code = 500
            if hasattr(e, 'response') and e.response:
                status_code = e.response.status_code
                
            raise HTTPException(
                status_code=status_code,
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
        """
        # Determinar el limiter correcto según la operación
        if operation == "change_email":
            limiter = self.email_change_limiter
            window = 60  # minutos (de 3600 segundos)
        elif operation == "verify_email":
            limiter = self.verification_limiter
            window = 10  # minutos (de 600 segundos)
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
        import math
        return math.ceil(seconds_remaining / 60)

    async def update_user_metadata(self, auth0_id: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Actualiza el app_metadata de un usuario en Auth0.
        
        Args:
            auth0_id: ID de Auth0 del usuario (auth0|xxxx)
            metadata: Diccionario con los metadatos a actualizar
            
        Returns:
            Dict[str, Any]: Información del usuario actualizada
            
        Raises:
            HTTPException: Si hay un error al actualizar los metadatos
        """
        token = self.get_auth_token()
        url = f"https://{self.domain}/api/v2/users/{auth0_id}"
        
        payload = {
            "app_metadata": metadata
        }
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        try:
            import logging
            logger = logging.getLogger("auth0_service")
            logger.info(f"Actualizando app_metadata para {auth0_id}: {json.dumps(metadata)}")
            
            response = requests.patch(url, json=payload, headers=headers)
            response.raise_for_status()
            
            logger.info(f"app_metadata actualizado exitosamente para {auth0_id}")
            return response.json()
        except requests.RequestException as e:
            error_detail = f"Error al actualizar app_metadata en Auth0: {str(e)}"
            
            # Intentar obtener el mensaje de error detallado de Auth0
            if hasattr(e, 'response') and e.response:
                try:
                    error_data = e.response.json()
                    error_message = error_data.get('message', error_detail)
                    error_detail = f"{error_detail} - {error_message}"
                except:
                    pass
            
            logger.error(error_detail)
            
            status_code = 500
            if hasattr(e, 'response') and e.response:
                status_code = e.response.status_code
                
            raise HTTPException(
                status_code=status_code,
                detail=error_detail
            )

    async def get_roles(self) -> List[Dict[str, Any]]:
        """
        Obtiene todos los roles definidos en Auth0.
        
        Returns:
            List[Dict[str, Any]]: Lista de roles disponibles en Auth0
            
        Raises:
            HTTPException: Si hay un error en la comunicación con Auth0
        """
        token = self.get_auth_token()
        url = f"https://{self.domain}/api/v2/roles"
        
        headers = {
            "Authorization": f"Bearer {token}"
        }
        
        try:
            import logging
            logger = logging.getLogger("auth0_service")
            logger.info(f"Obteniendo lista de roles de Auth0")
            
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            logger.info(f"Roles obtenidos exitosamente")
            return response.json()
        except requests.RequestException as e:
            error_detail = f"Error al obtener roles de Auth0: {str(e)}"
            
            if hasattr(e, 'response') and e.response:
                try:
                    error_data = e.response.json()
                    error_message = error_data.get('message', error_detail)
                    error_detail = f"{error_detail} - {error_message}"
                except:
                    pass
            
            logger.error(error_detail)
            
            status_code = 500
            if hasattr(e, 'response') and e.response:
                status_code = e.response.status_code
                
            raise HTTPException(
                status_code=status_code,
                detail=error_detail
            )

    async def get_role_by_name(self, role_name: str) -> Optional[Dict[str, Any]]:
        """
        Busca un rol por su nombre en Auth0.
        
        Args:
            role_name: Nombre del rol a buscar
            
        Returns:
            Dict[str, Any]: Información del rol si se encuentra, None en caso contrario
            
        Raises:
            HTTPException: Si hay un error en la comunicación con Auth0
        """
        roles = await self.get_roles()
        
        for role in roles:
            if role.get('name') == role_name:
                return role
                
        return None

    async def assign_roles_to_user(self, auth0_id: str, role_names: List[str]) -> bool:
        """
        Asigna roles a un usuario en Auth0.
        
        Args:
            auth0_id: ID de Auth0 del usuario
            role_names: Lista de nombres de roles a asignar
            
        Returns:
            bool: True si se asignaron correctamente
            
        Raises:
            HTTPException: Si hay un error en la comunicación con Auth0
        """
        import logging
        logger = logging.getLogger("auth0_service")
        
        # Primero, obtener los roles actuales del usuario
        token = self.get_auth_token()
        roles_url = f"https://{self.domain}/api/v2/users/{auth0_id}/roles"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        try:
            # Obtener roles actuales
            current_roles_response = requests.get(roles_url, headers=headers)
            current_roles_response.raise_for_status()
            current_roles = current_roles_response.json()
            
            # Eliminar roles actuales
            if current_roles:
                current_role_ids = [role["id"] for role in current_roles]
                delete_url = f"https://{self.domain}/api/v2/users/{auth0_id}/roles"
                delete_payload = {"roles": current_role_ids}
                
                delete_response = requests.delete(delete_url, json=delete_payload, headers=headers)
                delete_response.raise_for_status()
                logger.info(f"Roles eliminados para usuario {auth0_id}")
            
            # Obtener IDs de los nuevos roles
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
            
            # Asignar nuevos roles
            assign_url = f"https://{self.domain}/api/v2/users/{auth0_id}/roles"
            assign_payload = {"roles": role_ids}
            
            assign_response = requests.post(assign_url, json=assign_payload, headers=headers)
            assign_response.raise_for_status()
            
            logger.info(f"Roles asignados exitosamente a usuario {auth0_id}: {', '.join(role_names)}")
            return True
            
        except requests.RequestException as e:
            error_detail = f"Error asignando roles a usuario {auth0_id}: {str(e)}"
            
            if hasattr(e, 'response') and e.response:
                try:
                    error_data = e.response.json()
                    error_message = error_data.get('message', error_detail)
                    error_detail = f"{error_detail} - {error_message}"
                except:
                    pass
            
            logger.error(error_detail)
            return False


# Instancia global del servicio
auth0_mgmt_service = Auth0ManagementService() 