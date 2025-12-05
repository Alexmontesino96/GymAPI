from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import logging
import json

from fastapi import HTTPException, UploadFile, status, Depends
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload, joinedload
from jose import JWTError, jwt
from redis.asyncio import Redis

from app.repositories.user import user_repository
from app.schemas.user import UserCreate, UserUpdate, User, UserRoleUpdate, UserProfileUpdate, UserSearchParams, UserSyncFromAuth0, UserPublicProfile, User as UserSchema
from app.models.user import User as UserModel, UserRole
from app.models.user_gym import UserGym, GymRoleType
from app.services.storage import get_storage_service
from app.core.config import get_settings
from app.db.redis_client import get_redis_client
from app.core.auth0_mgmt import auth0_mgmt_service
from app.core.profiling import time_redis_operation, time_db_query, time_deserialize_operation, register_cache_hit, register_cache_miss, async_db_query_timer
from app.services.attendance import attendance_service
from app.core.async_utils import async_timed



logger = logging.getLogger(__name__) # Logger a nivel de módulo


class UserService:

    # ==========================================
    # MÉTODOS ASYNC (FASE 2 - NUEVO)
    # ==========================================

    @async_timed(log_level="debug")
    async def get_user_async(
        self,
        db: AsyncSession,
        user_id: int,
        eager_load: bool = False
    ) -> Optional[UserModel]:
        """
        Obtiene un usuario por ID (versión async).

        Args:
            db: Sesión async de SQLAlchemy
            user_id: ID del usuario
            eager_load: Si True, carga relaciones (gyms, etc.)

        Returns:
            Usuario o None
        """
        query = select(UserModel).where(UserModel.id == user_id)

        if eager_load:
            query = query.options(
                selectinload(UserModel.gyms),
                selectinload(UserModel.profile)
            )

        result = await db.execute(query)
        user = result.scalar_one_or_none()

        if user:
            logger.debug(f"Usuario encontrado: {user.id}")
        else:
            logger.debug(f"Usuario no encontrado: {user_id}")

        return user

    @async_timed(log_level="debug")
    async def get_user_by_email_async(
        self,
        db: AsyncSession,
        email: str,
        eager_load: bool = False
    ) -> Optional[UserModel]:
        """
        Obtiene un usuario por email (versión async).

        Args:
            db: Sesión async
            email: Email del usuario
            eager_load: Cargar relaciones

        Returns:
            Usuario o None
        """
        query = select(UserModel).where(UserModel.email == email)

        if eager_load:
            query = query.options(
                selectinload(UserModel.gyms),
                selectinload(UserModel.profile)
            )

        result = await db.execute(query)
        user = result.scalar_one_or_none()

        if user:
            logger.debug(f"Usuario encontrado por email: {user.id} ({email})")
        else:
            logger.debug(f"Usuario no encontrado por email: {email}")

        return user

    @async_timed(log_level="debug")
    async def get_user_by_auth0_id_async_direct(
        self,
        db: AsyncSession,
        auth0_id: str,
        eager_load: bool = False
    ) -> Optional[UserModel]:
        """
        Obtiene un usuario por Auth0 ID (versión async directa, sin caché).

        Para versión con caché, usar get_user_by_auth0_id_cached().

        Args:
            db: Sesión async
            auth0_id: ID de Auth0
            eager_load: Cargar relaciones

        Returns:
            Usuario o None
        """
        query = select(UserModel).where(UserModel.auth0_id == auth0_id)

        if eager_load:
            query = query.options(
                selectinload(UserModel.gyms),
                selectinload(UserModel.profile)
            )

        result = await db.execute(query)
        user = result.scalar_one_or_none()

        if user:
            logger.debug(f"Usuario encontrado por auth0_id: {user.id} ({auth0_id})")
        else:
            logger.debug(f"Usuario no encontrado por auth0_id: {auth0_id}")

        return user

    @async_timed(log_level="debug")
    async def get_users_async(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        eager_load: bool = False
    ) -> List[UserModel]:
        """
        Obtiene múltiples usuarios (versión async).

        Args:
            db: Sesión async
            skip: Registros a omitir
            limit: Límite de registros
            eager_load: Cargar relaciones

        Returns:
            Lista de usuarios
        """
        query = select(UserModel).offset(skip).limit(limit)

        if eager_load:
            query = query.options(
                selectinload(UserModel.gyms),
                selectinload(UserModel.profile)
            )

        result = await db.execute(query)
        users = result.scalars().all()

        logger.debug(f"Usuarios encontrados: {len(users)}")
        return list(users)

    @async_timed(log_level="debug")
    async def create_user_async_full(
        self,
        db: AsyncSession,
        user_data: UserCreate,
        redis_client: Optional[Redis] = None
    ) -> UserModel:
        """
        Crea un nuevo usuario y genera su código QR único (versión async completa).

        Args:
            db: Sesión async
            user_data: Datos del usuario a crear
            redis_client: Cliente Redis para invalidar caché

        Returns:
            Usuario creado con QR code
        """
        # Crear el usuario
        db_user = UserModel(**user_data.model_dump())
        db.add(db_user)
        await db.commit()
        await db.refresh(db_user)

        logger.info(f"Usuario creado: {db_user.id} ({db_user.email})")

        # Generar código QR único para el usuario
        try:
            qr_code = await attendance_service.generate_qr_code(db_user.id)
            db_user.qr_code = qr_code

            db.add(db_user)
            await db.commit()
            await db.refresh(db_user)

            logger.info(f"QR code generado para usuario {db_user.id}: {qr_code}")
        except Exception as e:
            logger.error(f"Error generando QR para usuario {db_user.id}: {e}")
            # No fallar la creación si el QR falla

        # Invalidar caché si existe
        if redis_client:
            await self._invalidate_user_cache_async(redis_client, db_user.id, db_user.auth0_id)

        return db_user

    @async_timed(log_level="debug")
    async def update_user_async_full(
        self,
        db: AsyncSession,
        user_id: int,
        user_in: UserUpdate,
        redis_client: Optional[Redis] = None
    ) -> UserModel:
        """
        Actualiza un usuario (versión async completa).

        Args:
            db: Sesión async
            user_id: ID del usuario
            user_in: Datos a actualizar
            redis_client: Cliente Redis para invalidar caché

        Returns:
            Usuario actualizado

        Raises:
            HTTPException: Si el usuario no existe
        """
        # Obtener usuario
        user = await self.get_user_async(db, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )

        # Email update requiere actualización en Auth0
        if user_in.email and user_in.email != user.email and user.auth0_id:
            logger.warning(
                f"Actualización administrativa directa de email para usuario {user_id}: "
                f"{user.email} -> {user_in.email}"
            )
            try:
                await auth0_mgmt_service.update_user_email(
                    auth0_id=user.auth0_id,
                    new_email=user_in.email,
                    verify_email=True,
                    redis_client=redis_client
                )
                logger.info(f"Email actualizado en Auth0 para usuario {user_id}")
            except HTTPException as http_exc:
                logger.error(
                    f"HTTP Error al actualizar email en Auth0 durante update_user "
                    f"para {user_id}: {http_exc.detail}"
                )
                raise http_exc
            except Exception as e:
                logger.error(
                    f"Error al actualizar email en Auth0 durante update_user "
                    f"para {user_id}: {e}"
                )

        # Actualizar campos
        update_data = user_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)

        try:
            await db.commit()
            await db.refresh(user)
            logger.info(f"Usuario actualizado: {user.id}")
        except Exception as e:
            await db.rollback()
            logger.error(f"Error actualizando usuario {user_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error actualizando usuario: {e}"
            )

        # Invalidar caché
        if user.auth0_id and redis_client:
            await self._invalidate_user_cache_async(redis_client, user.id, user.auth0_id)

        return user

    async def _invalidate_user_cache_async(
        self,
        redis_client: Redis,
        user_id: int,
        auth0_id: Optional[str] = None
    ) -> None:
        """
        Invalida todas las claves de caché relacionadas con un usuario (async).

        Args:
            redis_client: Cliente Redis
            user_id: ID del usuario
            auth0_id: Auth0 ID del usuario (opcional)
        """
        try:
            keys_to_delete = [
                f"user_public_profile:{user_id}",
                f"user_gym_membership_obj:{user_id}:*",  # Pattern
            ]

            if auth0_id:
                keys_to_delete.append(f"user_by_auth0_id:{auth0_id}")

            # Eliminar claves individuales
            for key in keys_to_delete:
                if "*" in key:
                    # Pattern - usar scan
                    pattern_keys = await redis_client.keys(key)
                    if pattern_keys:
                        await redis_client.delete(*pattern_keys)
                        logger.debug(f"Invalidadas {len(pattern_keys)} claves con patrón {key}")
                else:
                    await redis_client.delete(key)
                    logger.debug(f"Invalidada caché: {key}")

        except Exception as e:
            logger.error(f"Error invalidando caché de usuario {user_id}: {e}")

    # ==========================================
    # MÉTODOS SYNC (EXISTENTES - MANTENER)
    # ==========================================

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

    @time_db_query
    def get_user(self, db: Session, user_id: int) -> Optional[UserModel]:
        """
        Obtener un usuario por ID.
        """
        user = user_repository.get(db, id=user_id)
        if not user:
            # No lanzar excepción aquí, dejar que el endpoint decida
            return None
        return user

    @time_db_query
    def get_user_by_email(self, db: Session, email: str) -> Optional[UserModel]:
        """
        Obtener un usuario por email.
        """
        return user_repository.get_by_email(db, email=email)

    @time_db_query
    def get_user_by_auth0_id(self, db: Session, auth0_id: str) -> Optional[UserModel]:
        """
        Obtener un usuario por ID de Auth0.
        """
        return user_repository.get_by_auth0_id(db, auth0_id=auth0_id)

    @time_db_query
    def get_users(self, db: Session, skip: int = 0, limit: int = 100) -> List[UserModel]:
        """
        Obtener múltiples usuarios.
        """
        return user_repository.get_multi(db, skip=skip, limit=limit)

    @time_db_query
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

    @time_db_query
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

    def create_user(self, db: Session, user_data: UserCreate, redis_client: Optional[Redis] = None) -> UserModel:
        """
        Crea un nuevo usuario y genera su código QR único.
        """
        import asyncio

        # Crear el usuario
        db_user = UserModel(**user_data.model_dump())
        db.add(db_user)
        db.commit()
        db.refresh(db_user)

        # Generar código QR único para el usuario (async envuelto)
        qr_code = asyncio.run(attendance_service.generate_qr_code(db_user.id))
        db_user.qr_code = qr_code

        db.add(db_user)
        db.commit()
        db.refresh(db_user)

        # Invalidar caché si existe (async envuelto)
        if redis_client:
            asyncio.run(self._invalidate_user_cache(redis_client, db_user.id, db_user.auth0_id))

        return db_user

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
        new_user = user_repository.create_from_auth0(db, auth0_user=auth0_user)
        
        return new_user
    
    def create_or_update_auth0_user_async(self, db: Session, auth0_user: Dict) -> UserModel:
        """
        Versión async de create_or_update_auth0_user que incluye generación de QR.
        NOTA: Nombre con _async se corregirá en fase de cleanup (mantener por compatibilidad).
        """
        import asyncio

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
                return user_repository.update(db, db_obj=user, obj_in={"email": auth0_email})
            return user

        if auth0_email:
            user = self.get_user_by_email(db, email=auth0_email)
            if user:
                # Encontrado por email, actualizar Auth0 ID si falta
                if not user.auth0_id:
                    logger.info(f"Asociando Auth0 ID {auth0_id} al usuario existente {user.id} encontrado por email {auth0_email}")
                    updated_user = user_repository.update(db, db_obj=user, obj_in={"auth0_id": auth0_id})
                    # Generar QR si no tiene
                    if not updated_user.qr_code:
                        try:
                            from app.services.attendance import attendance_service
                            qr_code = asyncio.run(attendance_service.generate_qr_code(updated_user.id))
                            updated_user.qr_code = qr_code
                            db.add(updated_user)
                            db.commit()
                            db.refresh(updated_user)
                            logger.info(f"QR code generado para usuario existente {updated_user.id}: {qr_code}")
                        except Exception as e:
                            logger.error(f"Error generando QR para usuario existente {updated_user.id}: {e}")
                    return updated_user
                else:
                    # Conflicto: usuario encontrado por email pero ya tiene otro Auth0 ID
                    logger.error(f"Conflicto de sincronización Auth0: Email {auth0_email} ya está asociado al usuario {user.id} (Auth0 ID local: {user.auth0_id}), pero se intentó asociar con {auth0_id}")
                    return user

        # Si no se encuentra, crear nuevo usuario
        logger.info(f"Creando nuevo usuario local para Auth0 ID {auth0_id} con email {auth0_email}")
        new_user = user_repository.create_from_auth0(db, auth0_user=auth0_user)

        # Generar código QR para el nuevo usuario
        try:
            from app.services.attendance import attendance_service
            qr_code = asyncio.run(attendance_service.generate_qr_code(new_user.id))
            new_user.qr_code = qr_code
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            logger.info(f"Usuario {new_user.id} creado desde Auth0 con QR code: {qr_code}")
        except Exception as e:
            logger.error(f"Error generando QR para nuevo usuario {new_user.id}: {e}")

        return new_user

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
        @time_db_query
        def _update_db(session, db_obj, obj_in_data):
             return user_repository.update(session, db_obj=db_obj, obj_in=obj_in_data)
        updated_user = _update_db(db, user, user_in)
        
        # <<< Invalidar caché user_by_auth0_id si el usuario tiene auth0_id >>>
        if updated_user.auth0_id and redis_client:
            auth0_cache_key = f"user_by_auth0_id:{updated_user.auth0_id}"
            @time_redis_operation
            async def _redis_delete(key): return await redis_client.delete(key)
            try:
                await _redis_delete(auth0_cache_key)
                logger.info(f"Invalidada caché {auth0_cache_key} tras update_user")
            except Exception as e:
                logger.error(f"Error invalidando caché {auth0_cache_key}: {e}")
        
        return updated_user

    @time_db_query
    def update_user_profile(self, db: Session, user_id: int, profile_in: UserProfileUpdate) -> UserModel:
        """
        Actualizar solo el perfil de un usuario.
        """
        user = self.get_user(db, user_id=user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
        return user_repository.update(db, db_obj=user, obj_in=profile_in)

    @time_db_query
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
            @time_db_query # Decorar la operación remove
            def _remove_db(session, id_to_remove):
                user_repository.remove(session, id=id_to_remove)
            _remove_db(db, user_id)
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
        """Verifica si un usuario es superadmin."""
        return user.role == UserRole.SUPERADMIN
        
    def get_all_gym_user_ids(self, db: Session, gym_id: int) -> List[str]:
        """
        Obtiene todos los IDs de usuarios asociados a un gimnasio específico para notificaciones.
        
        Args:
            db: Sesión de base de datos
            gym_id: ID del gimnasio
            
        Returns:
            Lista de auth0_ids de usuarios del gimnasio para enviar notificaciones
        """
        # La implementación depende de cómo están asociados los usuarios al gimnasio
        # Típicamente a través de la tabla user_gym 
        users = user_repository.get_all_gym_users(db, gym_id)
        
        # Filtrar usuarios con auth0_id (necesario para notificaciones)
        # y convertir a lista de IDs
        return [user.auth0_id for user in users if user.auth0_id]

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

    @time_db_query
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
        
        # Obtener la instancia del servicio de almacenamiento
        storage_service_instance = get_storage_service()
        _settings = get_settings()
        
        if user.picture:
            # Determinar si la URL es de Supabase (si está configurado)
            is_supabase_url = False
            if storage_service_instance.api_url and user.picture.startswith(storage_service_instance.api_url):
                is_supabase_url = True
            
            if is_supabase_url:
                try:
                    logger.info(f"Eliminando imagen anterior de Supabase: {user.picture}")
                    result = await storage_service_instance.delete_profile_image(user.picture)
                    if result:
                        logger.info("Imagen anterior de Supabase eliminada correctamente")
                    else:
                        logger.warning("No se pudo eliminar la imagen anterior de Supabase")
                except Exception as e:
                    logger.warning(f"Error al eliminar la imagen anterior de Supabase: {str(e)}")
            else:
                # Podríamos añadir lógica para eliminar de S3 si la URL no es de Supabase
                logger.info(f"Imagen anterior ({user.picture}) no parece ser de Supabase, no se intentará eliminar.")
        
        # Subir la nueva imagen usando la instancia del servicio
        image_url = await storage_service_instance.upload_profile_image(auth0_id, file=file)
        updated_user = user_repository.update(db, db_obj=user, obj_in={"picture": image_url})

        # Sincronizar picture con Auth0
        try:
            from app.core.auth0_mgmt import auth0_mgmt_service
            auth0_mgmt_service.update_user_picture(auth0_id, image_url)
            logger.info(f"Imagen de perfil sincronizada exitosamente con Auth0 para usuario {user.id} ({auth0_id})")
        except Exception as e:
            # Log el error pero no fallar la operación principal
            # La imagen ya está guardada en Supabase y en la BD local
            logger.error(f"Error al sincronizar picture con Auth0 (usuario {user.id}, auth0_id {auth0_id}): {str(e)}")
            logger.warning("La imagen se guardó localmente pero no se pudo sincronizar con Auth0. El usuario puede reautenticarse para ver la nueva imagen.")

        return updated_user
        
    # --- NUEVO MÉTODO PARA SINCRONIZACIÓN --- 
    async def sync_user_email_from_auth0(
        self, 
        db: Session, 
        auth0_user: UserSyncFromAuth0,
        redis_client: Optional[Redis] = None
    ) -> Optional[UserModel]:
        """
        Sincroniza el email de un usuario desde Auth0.
        
        Args:
            db: Sesión de base de datos.
            auth0_user: Datos del usuario de Auth0.
            redis_client: Cliente Redis opcional para invalidar caché.
            
        Returns:
            El modelo de usuario actualizado o None si no se encuentra.
        """
        try:
            # Buscar usuario por auth0_id
            user = self.get_user_by_auth0_id(db, auth0_id=auth0_user.user_id)
            if not user:
                logger.warning(f"Usuario con auth0_id {auth0_user.user_id} no encontrado para actualizar email")
                return None
                
            # Si el email no ha cambiado, no hacer nada
            if user.email == auth0_user.email:
                logger.info(f"Email de usuario {auth0_user.user_id} no ha cambiado, omitiendo actualización")
                return user
                
            # Actualizar email
            user.email = auth0_user.email
            db.commit()
            
            updated_user = self.get_user_by_auth0_id(db, auth0_id=auth0_user.user_id)
            logger.info(f"Email de usuario {auth0_user.user_id} actualizado a {auth0_user.email}")
            
            # Invalidar caché si Redis está disponible
            if redis_client:
                try:
                    # Invalidar clave de usuario por auth0_id
                    auth0_cache_key = f"user_by_auth0_id:{updated_user.auth0_id}"
                    await redis_client.delete(auth0_cache_key)
                    logger.debug(f"Caché invalidada para {auth0_cache_key}")
                    
                    # Invalidar perfil público
                    public_profile_cache_key = f"user_public_profile:{updated_user.id}"
                    await redis_client.delete(public_profile_cache_key)
                    logger.debug(f"Caché invalidada para {public_profile_cache_key}")
                except Exception as e:
                    logger.error(f"Error al invalidar caché para usuario {auth0_user.user_id}: {e}")
            
            return updated_user
        except Exception as e:
            logger.error(f"Error al sincronizar email de usuario {auth0_user.user_id}: {e}")
            db.rollback()
            return None

    # --- Métodos con Caché en Redis --- 
    # <<< RENOMBRAR Y MODIFICAR get_users_by_role_cached >>>
    async def get_gym_participants_cached(
        self, 
        db: Session, 
        *,
        gym_id: int, # No es opcional aquí
        roles: List[UserRole], # Recibe lista de roles
        skip: int = 0, 
        limit: int = 100,
        redis_client: Redis
    ) -> List[UserModel]:
        """
        Versión cacheada para obtener participantes de un gimnasio (modelo User).
        Utiliza Redis y aplica paginación eficientemente.
        """
        from app.services.cache_service import cache_service
        from app.schemas.user import User as UserSchema # El modelo de caché será UserSchema
        
        # Si no hay Redis disponible, usar método async del repositorio
        if not redis_client:
            logger.warning(f"Redis no disponible, obteniendo participantes de gym {gym_id} desde BD")
            return await user_repository.get_gym_participants_async(db, gym_id=gym_id, roles=roles, skip=skip, limit=limit)
        
        # Crear clave única de caché combinada
        role_str = "_".join(sorted([r.name for r in roles]))
        cache_key = f"users:full_profile:gym:{gym_id}:roles:{role_str}:skip:{skip}:limit:{limit}"
        
        # Definir función de consulta a la base de datos (asíncrona)
        @time_db_query
        async def db_fetch():
            logger.info(f"DB Fetch for gym participants cache miss: key={cache_key}")
            # Llama al método async del repositorio
            return await user_repository.get_gym_participants_async(
                db, gym_id=gym_id, roles=roles, skip=skip, limit=limit
            )
        
        try:
            # Usar el servicio de caché genérico
            users = await cache_service.get_or_set(
                redis_client=redis_client,
                cache_key=cache_key,
                db_fetch_func=db_fetch, # Pasar función async
                model_class=UserSchema, # Usar UserSchema para caché
                expiry_seconds=300,  # 5 minutos
                is_list=True
            )
            return users
        except Exception as e:
            logger.error(f"Error al obtener participantes cacheados para gym {gym_id} (roles={roles}): {str(e)}", exc_info=True)
            # Fallback al método async directo del repositorio en caso de error
            logger.info(f"Fallback a BD para gym {gym_id} (roles={roles}) debido a error de caché")
            return await user_repository.get_gym_participants_async(db, gym_id=gym_id, roles=roles, skip=skip, limit=limit)
            
    # <<< FIN MODIFICACIÓN >>>

    async def invalidate_role_cache(self, redis_client: Redis, role: Optional[UserRole] = None, gym_id: Optional[int] = None) -> None:
        """
        Invalida caché de listados de usuarios por rol.
        NECESITA ACTUALIZACIÓN: Debería invalidar las nuevas claves combinadas.
        """
        from app.services.cache_service import cache_service
        
        if not redis_client:
            return
            
        # --- NUEVA LÓGICA DE INVALIDACIÓN --- 
        # Invalidar cachés de perfiles completos para el gym afectado
        base_pattern = f"users:full_profile:gym:{gym_id if gym_id else '*'}:roles:*"
        # Invalidar todas las combinaciones de roles y paginación
        pattern = f"{base_pattern}:skip:*:limit:*"
        count = await cache_service.delete_pattern(redis_client, pattern)
        logger.info(f"Caché de participantes de gym invalidada con patrón: {pattern} ({count} claves)")

    # <<< NUEVO MÉTODO CACHEADO PARA TODOS LOS USUARIOS >>>
    async def get_users_cached(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        redis_client: Redis
    ) -> List[UserModel]:
        """
        Versión cacheada para obtener todos los usuarios de la plataforma.
        """
        from app.services.cache_service import cache_service
        from app.schemas.user import User as UserSchema

        if not redis_client:
            return self.get_users(db, skip=skip, limit=limit)

        cache_key = f"users:all:skip:{skip}:limit:{limit}"

        @time_db_query
        async def db_fetch():
            # La función get_users ya es síncrona
            return self.get_users(db, skip=skip, limit=limit)

        try:
            users = await cache_service.get_or_set(
                redis_client=redis_client,
                cache_key=cache_key,
                db_fetch_func=db_fetch,
                model_class=UserSchema,
                expiry_seconds=300,  # 5 minutos
                is_list=True
            )
            return users
        except Exception as e:
            logger.error(f"Error al obtener todos los usuarios cacheados: {str(e)}", exc_info=True)
            return self.get_users(db, skip=skip, limit=limit) # Fallback

    # <<< AÑADIR NUEVO MÉTODO get_public_gym_participants_combined >>>
    async def get_public_gym_participants_combined(
        self,
        db: Session,
        *,
        gym_id: int,
        roles: List[UserRole],
        name_contains: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
        redis_client: Redis
    ) -> List[UserPublicProfile]:
        """
        Obtiene perfiles públicos de participantes de un gym, combinados y cacheados.
        Aplica filtros y paginación eficientemente.
        """
        from app.services.cache_service import cache_service

        if name_contains:
            # Búsqueda directa en BD sin caché cuando hay filtro de nombre
            logger.info(f"DB Search for public participants: gym={gym_id}, roles={roles}, name={name_contains}, skip={skip}, limit={limit}")
            # Llama al método async del repositorio que devuelve UserPublicProfile
            return await user_repository.get_public_participants_async(
                db, gym_id=gym_id, roles=roles, name=name_contains, skip=skip, limit=limit
            )
        else:
            # Lógica de caché cuando no hay filtro de nombre
            if not redis_client:
                logger.warning("Redis client not available, fetching public participants directly from DB")
                return await user_repository.get_public_participants_async(
                    db, gym_id=gym_id, roles=roles, skip=skip, limit=limit
                )

            # Crear clave de caché consistente
            role_str = "_".join(sorted([r.name for r in roles])) # Ej: MEMBER_TRAINER o MEMBER
            cache_key = f"users:public_profile:gym:{gym_id}:roles:{role_str}:skip:{skip}:limit:{limit}"

            # Definir la función asíncrona para obtener datos de la BD en caso de cache miss
            @time_db_query
            async def db_fetch():
                logger.info(f"DB Fetch for public participants cache miss: key={cache_key}")
                # Usar el método async del repositorio
                return await user_repository.get_public_participants_async(
                    db, gym_id=gym_id, roles=roles, name=None, skip=skip, limit=limit
                )

            try:
                # Usar el método optimizado del servicio de caché
                participants = await cache_service.get_or_set_profiles_optimized(
                    redis_client=redis_client,
                    cache_key=cache_key,
                    db_fetch_func=db_fetch,
                    expiry_seconds=300  # 5 minutos
                )
                return participants
            except Exception as e:
                logger.error(f"Error getting/setting public participants cache (key={cache_key}): {str(e)}", exc_info=True)
                # Fallback a la BD en caso de error de caché
                logger.info("Fallback to DB due to cache error")
                return await user_repository.get_public_participants_async(
                    db, gym_id=gym_id, roles=roles, skip=skip, limit=limit
                )
    # <<< FIN NUEVO MÉTODO >>>

    # <<< NUEVO MÉTODO PARA PERFIL PÚBLICO CACHEADO >>>
    async def get_public_profile_cached(
        self,
        user_id: int,
        db: Session,
        redis_client: Redis
    ) -> Optional[UserPublicProfile]:
        """
        Obtiene el UserPublicProfile de un usuario, utilizando caché Redis.
        """
        from app.services.cache_service import cache_service

        if not redis_client:
            logger.warning(f"Redis no disponible, obteniendo perfil público para user {user_id} desde BD")
            user_model = user_repository.get(db, id=user_id)
            return UserPublicProfile.from_orm(user_model) if user_model else None

        cache_key = f"user_public_profile:{user_id}"

        @time_db_query
        async def db_fetch():
            logger.info(f"DB Fetch for public profile cache miss: key={cache_key}")
            user_model = user_repository.get(db, id=user_id)
            if user_model:
                # Mapear a UserPublicProfile antes de devolver para caché
                return UserPublicProfile.from_orm(user_model)
            return None

        try:
            public_profile = await cache_service.get_or_set(
                redis_client=redis_client,
                cache_key=cache_key,
                db_fetch_func=db_fetch,
                model_class=UserPublicProfile, # El modelo Pydantic que queremos cachear/devolver
                expiry_seconds=get_settings().CACHE_TTL_USER_MEMBERSHIP, # Reutilizar TTL estándar
                is_list=False # Es un objeto único
            )
            return public_profile
        except Exception as e:
            logger.error(f"Error al obtener perfil público cacheado para user {user_id}: {str(e)}", exc_info=True)
            # Fallback a BD
            logger.info(f"Fallback a BD para perfil público user {user_id} debido a error de caché")
            user_model = user_repository.get(db, id=user_id)
            return UserPublicProfile.from_orm(user_model) if user_model else None
    # <<< FIN NUEVO MÉTODO >>>

    # <<< NUEVO MÉTODO CACHEADO PARA BUSCAR USER POR AUTH0_ID >>>
    async def get_user_by_auth0_id_cached(
        self,
        db: AsyncSession,
        auth0_id: str,
        redis_client: Optional[Redis] = None
    ) -> Optional[UserSchema]:
        """
        Versión cacheada para obtener un usuario por su Auth0 ID.
        """
        if not redis_client:
            # Si no hay Redis disponible, usar método directo async
            logger.warning(f"Redis no disponible para get_user_by_auth0_id {auth0_id}")
            user = await user_repository.get_by_auth0_id_async(db, auth0_id=auth0_id)
            return UserSchema.model_validate(user) if user else None
        
        cache_key = f"user_by_auth0_id:{auth0_id}"
        
        try:
            # Intentar obtener de caché primero
            @time_redis_operation
            async def _redis_get(key):
                return await redis_client.get(key)
                
            cached_data = await _redis_get(cache_key)
            
            if cached_data:
                # Caché hit
                register_cache_hit(cache_key) 
                logger.debug(f"Cache HIT para {cache_key}")
                
                @time_deserialize_operation
                def _deserialize(data):
                    return json.loads(data)
                    
                user_dict = _deserialize(cached_data)
                return UserSchema.model_validate(user_dict)
            else:
                # Caché miss
                register_cache_miss(cache_key)

                # Función para obtener de la BD
                async def db_fetch():
                    async with async_db_query_timer():
                        user = await user_repository.get_by_auth0_id_async(db, auth0_id=auth0_id)
                        return user

                user = await db_fetch()
                
                if user:
                    # Serializar y guardar en caché
                    user_schema = UserSchema.model_validate(user)
                    
                    @time_redis_operation
                    async def _redis_set(key, value, ex):
                        await redis_client.set(key, value, ex=ex)
                    
                    await _redis_set(
                        cache_key,
                        user_schema.model_dump_json(),
                        ex=300  # 5 minutos TTL
                    )
                    
                    return user_schema
                return None
                
        except Exception as e:
            logger.error(f"Error al obtener usuario cacheado por auth0_id {auth0_id}: {str(e)}", exc_info=True)

            # Fallback a consulta directa
            async def db_fallback():
                async with async_db_query_timer():
                    user = await user_repository.get_by_auth0_id_async(db, auth0_id=auth0_id)
                    return UserSchema.model_validate(user) if user else None

            return await db_fallback()
            
    # Nuevo método para verificar membresía de gimnasio con caché
    async def check_user_gym_membership_cached(
        self,
        db: Session,
        user_id: int,
        gym_id: int,
        redis_client: Optional[Redis] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Verifica si un usuario pertenece a un gimnasio utilizando caché.
        
        Args:
            db: Sesión de base de datos
            user_id: ID del usuario
            gym_id: ID del gimnasio
            redis_client: Cliente Redis opcional
            
        Returns:
            Diccionario con la información de membresía o None si no existe
        """
        from app.services.gym import gym_service
        
        if not redis_client:
            # Si no hay Redis disponible, usar método directo
            logger.warning(f"Redis no disponible para check_user_gym_membership user_id={user_id}, gym_id={gym_id}")
            user_gym = gym_service.check_user_in_gym(db, user_id=user_id, gym_id=gym_id)
            if user_gym:
                return {
                    "user_id": user_gym.user_id,
                    "gym_id": user_gym.gym_id,
                    "role": user_gym.role.value,
                    "created_at": user_gym.created_at.isoformat() if user_gym.created_at else None
                }
            return None
        
        # Usar un prefijo distinto al de tenant.py para evitar colisiones de formato.
        # tenant.py usa 'user_gym_membership:{user_id}:{gym_id}' para guardar solo el rol (string).
        # Aquí almacenamos un objeto JSON con más campos.
        cache_key = f"user_gym_membership_obj:{user_id}:{gym_id}"
        
        try:
            # Intentar obtener de caché primero
            cached_data = await redis_client.get(cache_key)
            
            if cached_data:
                # Caché hit
                register_cache_hit(cache_key)
                logger.debug(f"Cache HIT para {cache_key}")
                try:
                    return json.loads(cached_data)
                except Exception:
                    # Si el contenido no es JSON válido, purgar y continuar como MISS
                    logger.warning(f"Datos inválidos en caché para {cache_key}. Purging y reconsultando BD.")
                    try:
                        await redis_client.delete(cache_key)
                    except Exception:
                        pass

            # Caché miss (o datos inválidos purgados)
            register_cache_miss(cache_key)
            
            # Obtener de la BD
            user_gym = gym_service.check_user_in_gym(db, user_id=user_id, gym_id=gym_id)
            
            if user_gym:
                # Convertir a diccionario
                membership = {
                    "user_id": user_gym.user_id,
                    "gym_id": user_gym.gym_id,
                    "role": user_gym.role.value,
                    "created_at": user_gym.created_at.isoformat() if user_gym.created_at else None
                }
                
                # Guardar en caché
                await redis_client.set(
                    cache_key,
                    json.dumps(membership),
                    ex=300  # 5 minutos TTL
                )
                
                return membership
            
            # No existe la membresía
            # Guardar caché negativa con TTL más corto
            await redis_client.set(cache_key, "null", ex=60)  # 1 minuto TTL
            return None
                
        except Exception as e:
            logger.error(f"Error al verificar membresía cacheada user_id={user_id}, gym_id={gym_id}: {str(e)}", exc_info=True)
            
            # Fallback a consulta directa
            user_gym = gym_service.check_user_in_gym(db, user_id=user_id, gym_id=gym_id)
            if user_gym:
                return {
                    "user_id": user_gym.user_id,
                    "gym_id": user_gym.gym_id,
                    "role": user_gym.role.value,
                    "created_at": user_gym.created_at.isoformat() if user_gym.created_at else None
                }
            return None


user_service = UserService() 
