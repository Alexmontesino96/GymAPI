from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging

from fastapi import HTTPException, UploadFile, status, Depends
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from redis.asyncio import Redis

from app.repositories.user import user_repository
from app.schemas.user import UserCreate, UserUpdate, User, UserRoleUpdate, UserProfileUpdate, UserSearchParams, UserSyncFromAuth0
from app.models.user import User as UserModel, UserRole
from app.services.storage import storage_service
from app.core.config import settings
from app.db.redis_client import get_redis_client
from app.core.auth0_mgmt import auth0_mgmt_service


# --- Constantes para Tokens de Confirmación ---
# Mover a config si se usan en otros lugares
# SECRET_KEY = settings.SECRET_KEY
# ALGORITHM = "HS256"
# ACCESS_TOKEN_EXPIRE_MINUTES = 30

logger = logging.getLogger(__name__) # Logger a nivel de módulo


class UserService:
    
    # --- Métodos Helper para Tokens JWT de Confirmación (privados) ---
    # @staticmethod
    # def _create_email_confirmation_token(data: dict) -> str:
    #     to_encode = data.copy()
    #     expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    #     to_encode.update({"exp": expire, "type": "email_confirmation"})
    #     encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    #     return encoded_jwt

    # @staticmethod
    # def _verify_email_confirmation_token(token: str) -> Optional[dict]:
    #     try:
    #         payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    #         if payload.get("type") != "email_confirmation":
    #             logger.warning("Intento de usar token JWT de tipo incorrecto para confirmación de email")
    #             return None # No es el tipo de token correcto
    #         return payload
    #     except JWTError as e:
    #         logger.warning(f"Error al decodificar/validar token JWT de confirmación: {e}")
    #         return None
            
    # --- Métodos CRUD y Búsqueda existentes (sin cambios significativos) ---

    def get_user(self, db: Session, user_id: int) -> Optional[UserModel]:
        """
        Obtener un usuario por ID.
        """
        user = user_repository.get(db, id=user_id)
        if not user:
            # No lanzar excepción aquí, dejar que el endpoint decida
            return None
        return user

    def get_user_by_email(self, db: Session, email: str) -> Optional[UserModel]:
        """
        Obtener un usuario por email.
        """
        return user_repository.get_by_email(db, email=email)

    def get_user_by_auth0_id(self, db: Session, auth0_id: str) -> Optional[UserModel]:
        """
        Obtener un usuario por ID de Auth0.
        """
        return user_repository.get_by_auth0_id(db, auth0_id=auth0_id)

    def get_users(self, db: Session, skip: int = 0, limit: int = 100) -> List[UserModel]:
        """
        Obtener múltiples usuarios.
        """
        return user_repository.get_multi(db, skip=skip, limit=limit)

    def get_users_by_role(
        self, 
        db: Session, 
        role: UserRole, 
        skip: int = 0, 
        limit: int = 100,
        gym_id: Optional[int] = None # Nuevo parámetro
    ) -> List[UserModel]:
        """
        Obtener usuarios filtrados por rol (global o de un gimnasio específico).
        
        Args:
            db: Sesión de base de datos.
            role: Rol a buscar.
            skip: Omitir registros.
            limit: Límite de registros.
            gym_id: ID opcional del gimnasio para filtrar.
            
        Returns:
            Lista de usuarios.
            
        Raises:
            ValueError: Si se proporciona un gym_id que no existe.
        """
        if gym_id is not None:
            # Verificar que el gimnasio existe para dar un error claro si no
            from app.models.gym import Gym # Import local para evitar circularidad
            gym = db.query(Gym).filter(Gym.id == gym_id).first()
            if not gym:
                raise ValueError(f"Gimnasio con ID {gym_id} no encontrado.")
                
            # Llamar al método del repositorio que filtra por rol y gimnasio
            logger.info(f"Buscando usuarios con rol {role.name} en gym {gym_id}...")
            return user_repository.get_by_role_and_gym(
                db, role=role, gym_id=gym_id, skip=skip, limit=limit
            )
        else:
            # Llamar al método del repositorio que filtra solo por rol global
            logger.info(f"Buscando usuarios globales con rol {role.name}...")
            return user_repository.get_by_role(
                db, role=role, skip=skip, limit=limit
            )

    def search_users(self, db: Session, search_params: UserSearchParams, gym_id: Optional[int] = None) -> List[UserModel]:
        """
        Búsqueda avanzada de usuarios con múltiples criterios.
        Si se proporciona gym_id, la búsqueda se restringe a ese gimnasio.
        """
        return user_repository.search(
            db,
            name=search_params.name_contains,
            email=search_params.email_contains,
            role=search_params.role,
            is_active=search_params.is_active,
            created_before=search_params.created_before,
            created_after=search_params.created_after,
            gym_id=gym_id, # Pasar el gym_id
            skip=search_params.skip,
            limit=search_params.limit
        )

    def create_user(self, db: Session, user_in: UserCreate) -> UserModel:
        """
        Crear un nuevo usuario.
        """
        user = self.get_user_by_email(db, email=user_in.email)
        if user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe un usuario con este email en el sistema",
            )
        # TODO: Considerar si la creación aquí debería interactuar con Auth0 también
        #       o si este método es solo para creación administrativa interna.
        #       Si es para uso general, necesitaría contraseña y creación en Auth0.
        return user_repository.create(db, obj_in=user_in)

    def create_or_update_auth0_user(self, db: Session, auth0_user: Dict) -> UserModel:
        """
        Crear o actualizar un usuario a partir de datos de Auth0.
        """
        auth0_id = auth0_user.get("sub")
        if not auth0_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Los datos de Auth0 no contienen un ID (sub)",
            )
        
        auth0_email = auth0_user.get("email")
        
        user = self.get_user_by_auth0_id(db, auth0_id=auth0_id)
        if user:
            if auth0_email and auth0_email != user.email:
                logger.info(f"Actualizando email del usuario {user.id} de '{user.email}' a '{auth0_email}' vía sync Auth0")
                # Aquí solo actualizamos si el email de Auth0 es DIFERENTE.
                # No actualizamos email_verified aquí, eso lo maneja el flujo de cambio de email.
                return user_repository.update(db, db_obj=user, obj_in={"email": auth0_email})
            return user
        
        if auth0_email:
            user = self.get_user_by_email(db, email=auth0_email)
            if user:
                # Encontrado por email, actualizar Auth0 ID si falta
                if not user.auth0_id:
                    logger.info(f"Asociando Auth0 ID {auth0_id} al usuario existente {user.id} encontrado por email {auth0_email}")
                    return user_repository.update(db, db_obj=user, obj_in={"auth0_id": auth0_id})
                else:
                    # Conflicto: usuario encontrado por email pero ya tiene otro Auth0 ID
                    logger.error(f"Conflicto de sincronización Auth0: Email {auth0_email} ya está asociado al usuario {user.id} (Auth0 ID local: {user.auth0_id}), pero se intentó asociar con {auth0_id}")
                    # Podríamos lanzar excepción o simplemente devolver el usuario existente
                    return user # Por ahora, devolvemos el existente
            
        # Si no se encuentra, crear nuevo usuario
        logger.info(f"Creando nuevo usuario local para Auth0 ID {auth0_id} con email {auth0_email}")
        return user_repository.create_from_auth0(db, auth0_user=auth0_user)

    async def update_user(
        self, 
        db: Session, 
        user_id: int, 
        user_in: UserUpdate, 
        *,
        redis_client: Redis
    ) -> UserModel:
        """ Actualizar usuario... Args: ... redis_client... """
        user = self.get_user(db, user_id=user_id)
        if not user:
             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
        
        # Email update requiere await y pasar redis_client
        email_updated_in_auth0 = False
        if user_in.email and user_in.email != user.email and user.auth0_id:
             logger.warning(f"Actualización administrativa directa de email para usuario {user_id}: {user.email} -> {user_in.email}")
             try:
                # Pasar redis_client como keyword
                await auth0_mgmt_service.update_user_email(
                    auth0_id=user.auth0_id, 
                    new_email=user_in.email, 
                    verify_email=True, 
                    redis_client=redis_client
                )
                email_updated_in_auth0 = True
             except HTTPException as http_exc:
                 # Capturar HTTPExceptions (ej. 429 del rate limit) y relanzar
                 logger.error(f"HTTP Error al actualizar email en Auth0 durante update_user para {user_id}: {http_exc.detail}")
                 raise http_exc 
             except Exception as e:
                 # Otros errores de conexión/etc. con Auth0
                 logger.error(f"Error al actualizar email en Auth0 durante update_user para {user_id}: {e}")
                 # Decidir si fallar o continuar. Por ahora, continuamos actualizando localmente.
                 # Podríamos añadir un flag o log específico para indicar que Auth0 falló.
                 pass 

        # Actualizar localmente (síncrono)
        updated_user = user_repository.update(db, db_obj=user, obj_in=user_in)
        return updated_user

    def update_user_profile(self, db: Session, user_id: int, profile_in: UserProfileUpdate) -> UserModel:
        """
        Actualizar solo el perfil de un usuario.
        """
        user = self.get_user(db, user_id=user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
        return user_repository.update(db, db_obj=user, obj_in=profile_in)

    def update_user_role(self, db: Session, user_id: int, role_update: UserRoleUpdate, calling_user: UserModel) -> UserModel:
        """
        Actualizar el rol de un usuario.
        """
        user = self.get_user(db, user_id=user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
            
        valid_roles = [UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.TRAINER, UserRole.MEMBER]
        if role_update.role not in valid_roles:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rol no válido")
            
        # Usar comparación de rol explícita
        is_caller_super_admin = calling_user.role == UserRole.SUPER_ADMIN
        if user.role == UserRole.SUPER_ADMIN and not is_caller_super_admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No puedes modificar el rol de un SUPER_ADMIN.")
            
        update_data = {"role": role_update.role}
        if role_update.role == UserRole.SUPER_ADMIN:
            if not is_caller_super_admin:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo SUPER_ADMIN puede asignar este rol.")
            update_data["is_superuser"] = True
        # Mantener la lógica de quitar is_superuser si deja de ser SUPER_ADMIN
        elif getattr(user, 'is_superuser', False) and role_update.role != UserRole.SUPER_ADMIN:
             update_data["is_superuser"] = False
             
        # TODO: Actualizar roles en Auth0 si se mapean allí
        
        return user_repository.update(db, db_obj=user, obj_in=update_data)

    def delete_user(self, db: Session, user_id: int) -> UserModel:
        """
        Eliminar un usuario tanto localmente como en Auth0.
        Devuelve el objeto usuario tal como estaba antes de la eliminación local.
        """
        user = self.get_user(db, user_id=user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
            
        auth0_id_to_delete = user.auth0_id
        user_email_for_log = user.email 
        # No necesitamos copia, simplemente guardamos la referencia al objeto ORM
        # user_copy = UserModel(**UserSchema.from_orm(user).dict()) 

        # 1. Intentar eliminar de Auth0 primero
        if auth0_id_to_delete:
            try:
                logger.info(f"Intentando eliminar usuario {auth0_id_to_delete} ... de Auth0...")
                auth0_mgmt_service.delete_user(auth0_id_to_delete)
                logger.info(f"Usuario {auth0_id_to_delete} eliminado exitosamente de Auth0.")
            except HTTPException as e:
                if e.status_code == 404:
                    logger.warning(f"Usuario {auth0_id_to_delete} no encontrado en Auth0..., continuando...")
                else:
                    logger.error(f"Error HTTP ({e.status_code}) al eliminar usuario {auth0_id_to_delete} de Auth0: {e.detail}")
                    raise HTTPException(
                        status_code=e.status_code, 
                        detail=f"Error al eliminar usuario de Auth0: {e.detail}. No se eliminó localmente."
                    )
            except Exception as e:
                logger.error(f"Error inesperado al eliminar usuario {auth0_id_to_delete} de Auth0: {e}", exc_info=True)
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Error de conexión al intentar eliminar usuario de Auth0: {e}. No se eliminó localmente."
                )
        else:
            logger.warning(f"El usuario local {user_id} ({user_email_for_log}) no tiene Auth0 ID...")

        # 2. Eliminar localmente y devolver el objeto original
        try:
            logger.info(f"Procediendo a eliminar usuario {user_id} ({user_email_for_log}) localmente...")
            # Guardar el objeto antes de eliminarlo de la sesión con remove
            user_to_return = user 
            user_repository.remove(db, id=user_id) # Esto elimina el objeto de la sesión
            logger.info(f"Usuario {user_id} eliminado exitosamente de la base de datos local.")
            # Devolver el objeto que teníamos antes de eliminarlo
            return user_to_return
        except Exception as e:
            logger.critical(f"¡ERROR CRÍTICO! Usuario {auth0_id_to_delete or user_id} pudo ser eliminado de Auth0 pero falló la eliminación local: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Usuario eliminado de Auth0 pero ocurrió un error al eliminarlo localmente: {e}"
            )

    # --- Métodos obsoletos o de ayuda ---
    # authenticate_user, is_active, is_superuser, has_role (mantenerlos o eliminarlos si no se usan)
    def is_active(self, user: UserModel) -> bool:
        return user_repository.is_active(user)

    def is_superuser(self, user: UserModel) -> bool:
        return user_repository.is_superuser(user)

    # Nueva función para búsqueda específica por nombre en gym
    def search_gym_participants_by_name(
        self,
        db: Session,
        *,
        role: UserRole,
        gym_id: int,
        name_contains: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[UserModel]:
        """
        Busca usuarios por nombre (globalmente) y luego filtra los que pertenecen
        a un gimnasio específico y tienen el rol dado. Aplica paginación final.
        """
        logger = logging.getLogger("user_service")
        logger.info(f"Búsqueda de usuarios por nombre '{name_contains}' rol '{role.name}' en gimnasio {gym_id}")

        search_params = UserSearchParams(
            name_contains=name_contains,
            role=role,
            skip=0,  # No aplicar paginación aquí
            limit=1000  # Límite alto para obtener suficientes candidatos
        )

        # Buscar usuarios con el filtro de nombre y rol
        all_matching_users = self.search_users(db, search_params=search_params)

        # Obtener IDs de usuarios que pertenecen al gimnasio
        gym_user_ids = db.query(UserGym.user_id).filter(
            UserGym.gym_id == gym_id
        ).all()
        # Usar un set para búsqueda eficiente O(1) en el filtrado
        gym_user_ids_set = {id_tuple[0] for id_tuple in gym_user_ids}

        # Filtrar usuarios que pertenecen al gimnasio
        filtered_users = [
            user for user in all_matching_users
            if user.id in gym_user_ids_set
        ]

        # Aplicar paginación manualmente
        paginated_users = filtered_users[skip : skip + limit]
        logger.info(f"Encontrados {len(filtered_users)} usuarios que coinciden, devolviendo {len(paginated_users)} paginados.")
        return paginated_users

    # --- Lógica de Cambio de Email (Nueva) ---

    async def check_full_email_availability(self, email: str, calling_user_auth0_id: str, redis_client: Redis) -> bool:
        """
        Verifica si un email está disponible tanto en la base de datos SQL como en Auth0.
        
        Args:
            email: El email a verificar.
            calling_user_auth0_id: ID de Auth0 del usuario que realiza la solicitud (puede ser None si es usuario nuevo)
            redis_client: Cliente Redis para rate limiting
            
        Returns:
            bool: True si el email está disponible en ambos sistemas.
        """
        # Verificar disponibilidad en Auth0
        is_available_auth0 = await auth0_mgmt_service.check_email_availability(
            email=email,
            calling_user_id=calling_user_auth0_id,
            redis_client=redis_client
        )
        
        if not is_available_auth0:
            logger.info(f"Email {email} no disponible en Auth0")
            return False
            
        logger.info(f"Email {email} disponible")
        return True

    def _is_disposable_email_domain(self, domain: str) -> bool:
        """
        Verifica si un dominio es de email desechable o temporal.
        
        Args:
            domain: Dominio de email a verificar
            
        Returns:
            bool: True si el dominio es desechable, False si parece legítimo
        """
        # Lista común de dominios de email desechables/temporales
        disposable_domains = {
            'mailinator.com', 'temp-mail.org', 'guerrillamail.com', 'yopmail.com', 
            'tempmail.com', '10minutemail.com', 'throwawaymail.com', 'trashmail.com',
            'tempinbox.com', 'sharklasers.com', 'getairmail.com', 'dispostable.com',
            'mailnesia.com', 'maildrop.cc', 'getnada.com', 'emailondeck.com'
        }
        
        return domain.lower() in disposable_domains

    def check_local_email_availability(self, db: Session, email: str, exclude_user_id: Optional[int] = None) -> bool:
        """
        Comprueba si un email está disponible localmente.
        (Este era el antiguo check_email_availability)
        """
        query = db.query(UserModel).filter(UserModel.email == email)
        if exclude_user_id:
            query = query.filter(UserModel.id != exclude_user_id)
        existing_user = query.first()
        return existing_user is None

    async def initiate_auth0_email_change_flow(
        self,
        db: Session,
        auth0_id: str,
        new_email: str,
        *,
        redis_client: Redis
    ) -> tuple[Optional[UserModel], str]:
        """
        Inicia el flujo de cambio de email directamente en Auth0.
        
        Esto actualiza el email en Auth0, lo marca como no verificado y 
        desencadena el envío de un correo de verificación por parte de Auth0 
        al *nuevo* email.
        
        NO actualiza la base de datos local. Se necesita un mecanismo externo
        (webhook/action) para sincronizar la BD cuando Auth0 confirme la verificación.
        
        Args:
            db: Sesión de base de datos.
            auth0_id: ID de Auth0 del usuario.
            new_email: Nuevo email deseado.
            redis_client: Cliente Redis para rate limiting de Auth0.
            
        Returns:
            tuple[Optional[UserModel], str]: (usuario_local, nuevo_email)
            
        Raises:
            HTTPException: Si el usuario no existe localmente, si el email es el mismo,
                           o si Auth0 rechaza la actualización (p. ej., email ya usado).
        """
        user = self.get_user_by_auth0_id(db, auth0_id=auth0_id)
        if not user:
            logger.warning(f"Intento de iniciar cambio de email Auth0 para usuario inexistente localmente: {auth0_id}")
            # Aunque no exista localmente, podríamos proceder si queremos permitirlo,
            # pero es más seguro requerir la existencia local.
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado localmente")

        if user.email.lower() == new_email.lower():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El nuevo email es igual al actual.")

        logger.info(f"Iniciando flujo de cambio de email en Auth0 para {auth0_id}: {user.email} -> {new_email}")
        
        try:
            # Llamar al servicio de Auth0 para actualizar el email y pedir verificación.
            # El servicio auth0_mgmt_service ya maneja la disponibilidad y el rate limiting.
            await auth0_mgmt_service.update_user_email(
                auth0_id=auth0_id,
                new_email=new_email,
                verify_email=True, # Indicar a Auth0 que envíe la verificación
                redis_client=redis_client
            )
            logger.info(f"Solicitud de cambio de email enviada a Auth0 para {auth0_id}. Auth0 enviará verificación a {new_email}.")
            # Devolvemos el usuario local (sin modificar) y el nuevo email solicitado.
            return user, new_email 
        except HTTPException as e:
            # Relanzar excepciones HTTP (ej: 400 Bad Request si Auth0 dice email en uso, 429 Rate Limit)
            logger.error(f"Error HTTP desde Auth0 al iniciar cambio de email para {auth0_id}: {e.detail}")
            raise e
        except Exception as e:
            logger.error(f"Error inesperado al iniciar cambio de email en Auth0 para {auth0_id}: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error interno al contactar con el servicio de autenticación."
            )

    # --- Gestión Imagen Perfil (ya existente) --- 
    async def update_user_profile_image(self, db: Session, auth0_id: str, file: UploadFile) -> UserModel:
        """
        Actualizar la imagen de perfil de un usuario.
        """
        user = self.get_user_by_auth0_id(db, auth0_id=auth0_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
        
        if user.picture:
            from app.services.storage import SUPABASE_URL
            if SUPABASE_URL in user.picture:
                try:
                    logger.info(f"Eliminando imagen anterior: {user.picture}")
                    result = await storage_service.delete_profile_image(user.picture)
                    if result:
                        logger.info("Imagen anterior eliminada correctamente")
                    else:
                        logger.warning("No se pudo eliminar la imagen anterior")
                except Exception as e:
                    logger.warning(f"Error al eliminar la imagen anterior: {str(e)}")
        
        image_url = await storage_service.upload_profile_image(file, auth0_id)
        updated_user = user_repository.update(db, db_obj=user, obj_in={"picture": image_url})
        return updated_user
        
    # --- NUEVO MÉTODO PARA SINCRONIZACIÓN --- 
    async def sync_user_email_from_auth0(
        self,
        db: Session,
        *, 
        sync_data: UserSyncFromAuth0,
        redis_client: Optional[Redis] = None # Hacer redis_client opcional
    ) -> Optional[UserModel]:
        """
        Sincroniza el email de un usuario local con la información recibida de Auth0.
        Llamado típicamente desde un webhook o Action.
        
        Args:
            db: Sesión de base de datos.
            sync_data: Datos recibidos (auth0_id, email).
            redis_client: Cliente Redis para invalidación de caché (opcional).
            
        Returns:
            El usuario actualizado o None si no se encontró o no hubo cambios.
        """
        logger = logging.getLogger("user_service")
        logger.info(f"Recibida solicitud de sincronización para Auth0 ID: {sync_data.auth0_id}")
        
        user = self.get_user_by_auth0_id(db, auth0_id=sync_data.auth0_id)
        
        if not user:
            logger.warning(f"Sincronización fallida: Usuario con Auth0 ID {sync_data.auth0_id} no encontrado localmente.")
            return None # O podríamos crear el usuario si esa es la lógica deseada
            
        if user.email.lower() == sync_data.email.lower():
            logger.info(f"Sincronización no necesaria: Email local ya coincide para Auth0 ID {sync_data.auth0_id}")
            return user # Devolver el usuario existente sin cambios
        
        # Email diferente, actualizar localmente
        logger.info(f"Sincronizando email para Auth0 ID {sync_data.auth0_id}: '{user.email}' -> '{sync_data.email}'")
        update_payload = {"email": sync_data.email}
        
        # Actualizar el email en la BD local
        # La función update del repositorio maneja commit y refresh
        updated_user = user_repository.update(db, db_obj=user, obj_in=update_payload)
        logger.info(f"Email sincronizado localmente para usuario ID {updated_user.id}")
        
        # Invalidar caché si se proporcionó cliente Redis
        if redis_client:
            from app.services.cache_service import cache_service # Import local
            logger.info(f"Invalidando cachés para usuario ID {updated_user.id} tras sincronización de email.")
            await cache_service.invalidate_user_caches(redis_client, user_id=updated_user.id)
            # También invalidar caché de roles, ya que a menudo dependen del usuario
            if updated_user.role:
                await self.invalidate_role_cache(redis_client, role=updated_user.role)

        return updated_user

    # --- Métodos con Caché en Redis --- 
    async def get_users_by_role_cached(
        self, 
        db: Session, 
        role: UserRole, 
        *,
        gym_id: Optional[int] = None,
        skip: int = 0, 
        limit: int = 100,
        redis_client: Redis
    ) -> List[UserModel]:
        """
        Versión cacheada para obtener usuarios por rol.
        Utiliza Redis para mejorar el rendimiento en consultas frecuentes.
        
        Args:
            db: Sesión de base de datos
            role: Rol a buscar
            gym_id: ID opcional del gimnasio para filtrar
            skip: Omitir registros (paginación)
            limit: Límite de registros (paginación)
            redis_client: Cliente Redis para cachear resultados
            
        Returns:
            Lista de usuarios con el rol especificado
        """
        from app.services.cache_service import cache_service
        from app.schemas.user import User as UserSchema
        
        # Si no hay Redis disponible, usar método normal
        if not redis_client:
            return self.get_users_by_role(db, role=role, skip=skip, limit=limit, gym_id=gym_id)
        
        # Crear clave única de caché
        cache_key = f"users:role:{role.name}"
        if gym_id:
            cache_key += f":gym:{gym_id}"
        cache_key += f":skip:{skip}:limit:{limit}"
        
        # Definir función de consulta a la base de datos
        async def db_fetch():
            # La versión original no es async, envolverla para compatibilidad
            return self.get_users_by_role(db, role=role, skip=skip, limit=limit, gym_id=gym_id)
        
        try:
            # Usar el servicio de caché genérico
            users = await cache_service.get_or_set(
                redis_client=redis_client,
                cache_key=cache_key,
                db_fetch_func=db_fetch,
                model_class=UserSchema,
                expiry_seconds=300,  # 5 minutos
                is_list=True
            )
            
            # Convertir de esquema a modelo ORM si es necesario
            if users and isinstance(users[0], UserSchema):
                # Aquí deberíamos convertir de UserSchema a UserModel si necesario
                # Pero en este caso, los esquemas son suficientes para el endpoint
                pass
                
            return users
        except Exception as e:
            logger.error(f"Error al obtener usuarios cacheados para {role.name}: {str(e)}", exc_info=True)
            # Fallback al método directo en caso de error
            return self.get_users_by_role(db, role=role, skip=skip, limit=limit, gym_id=gym_id)
            
    async def invalidate_role_cache(self, redis_client: Redis, role: Optional[UserRole] = None, gym_id: Optional[int] = None) -> None:
        """
        Invalida caché de listados de usuarios por rol.
        Útil después de añadir/modificar/eliminar usuarios.
        
        Args:
            redis_client: Cliente Redis
            role: Rol específico a invalidar (o todos si es None)
            gym_id: ID del gimnasio específico a invalidar (o todos si es None)
        """
        from app.services.cache_service import cache_service
        
        if not redis_client:
            return
            
        # Construir patrón de invalidación
        pattern = "users:role:"
        if role:
            pattern += f"{role.name}"
        else:
            pattern += "*"
            
        if gym_id:
            pattern += f":gym:{gym_id}"
        else:
            pattern += ":gym:*"
            
        # Invalidar todas las variantes de paginación
        pattern += ":skip:*:limit:*"
        
        await cache_service.delete_pattern(redis_client, pattern)
        logger.info(f"Caché de roles invalidada con patrón: {pattern}")


user_service = UserService() 