"""
Base repository async para operaciones CRUD genéricas.
Soporta multi-tenancy con filtrado automático por gym_id.
"""
from typing import TypeVar, Generic, Optional, List, Dict, Any, Type, Union
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, exists
from sqlalchemy.future import select as future_select
from pydantic import BaseModel
from fastapi.encoders import jsonable_encoder
import logging

logger = logging.getLogger(__name__)

ModelType = TypeVar("ModelType")
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class AsyncBaseRepository(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """
    Repositorio base genérico con operaciones CRUD async.

    Características:
    - Operaciones CRUD completamente async
    - Multi-tenant aware (gym_id filtering automático)
    - Type-safe con TypeVars
    - Compatible con SQLAlchemy 2.0

    Uso:
        class UserRepository(AsyncBaseRepository[User, UserCreate, UserUpdate]):
            # Métodos específicos del modelo
            pass
    """

    def __init__(self, model: Type[ModelType]):
        """
        Inicializar repositorio con el modelo SQLAlchemy.

        Args:
            model: Clase del modelo SQLAlchemy (ej: User, Event, etc)
        """
        self.model = model

    async def get(
        self,
        db: AsyncSession,
        id: Any,
        gym_id: Optional[int] = None
    ) -> Optional[ModelType]:
        """
        Obtener un objeto por ID con filtro opcional de gym_id.

        Args:
            db: Sesión async de base de datos
            id: ID del objeto a buscar
            gym_id: ID del gimnasio para filtrar (multi-tenant)

        Returns:
            El objeto encontrado o None si no existe

        Example:
            user = await user_repository.get(db, id=123, gym_id=1)
        """
        stmt = select(self.model).where(self.model.id == id)

        # Filtrar por gym_id si el modelo lo soporta y se proporciona
        if gym_id is not None and hasattr(self.model, "gym_id"):
            stmt = stmt.where(self.model.gym_id == gym_id)

        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_multi(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100,
        gym_id: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[ModelType]:
        """
        Obtener múltiples objetos con paginación y filtros opcionales.

        Args:
            db: Sesión async de base de datos
            skip: Número de registros a omitir (paginación)
            limit: Número máximo de registros a devolver
            gym_id: ID del gimnasio para filtrar (multi-tenant)
            filters: Diccionario de filtros adicionales {campo: valor}

        Returns:
            Lista de objetos que cumplen los criterios

        Example:
            users = await user_repository.get_multi(
                db,
                skip=0,
                limit=20,
                gym_id=1,
                filters={"is_active": True}
            )
        """
        stmt = select(self.model)

        # Filtrar por gym_id si el modelo lo soporta y se proporciona
        if gym_id is not None and hasattr(self.model, "gym_id"):
            stmt = stmt.where(self.model.gym_id == gym_id)

        # Aplicar filtros adicionales
        if filters:
            for field, value in filters.items():
                if hasattr(self.model, field):
                    stmt = stmt.where(getattr(self.model, field) == value)
                else:
                    logger.warning(
                        f"Filtro ignorado: {self.model.__name__} no tiene campo '{field}'"
                    )

        # Aplicar paginación
        stmt = stmt.offset(skip).limit(limit)

        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: Union[CreateSchemaType, Dict[str, Any]],
        gym_id: Optional[int] = None
    ) -> ModelType:
        """
        Crear un nuevo objeto en la base de datos.

        Args:
            db: Sesión async de base de datos
            obj_in: Datos del objeto a crear (schema Pydantic o dict)
            gym_id: ID del gimnasio (se asigna automáticamente si modelo lo soporta)

        Returns:
            El objeto creado con ID asignado

        Example:
            user = await user_repository.create(
                db,
                obj_in=UserCreate(email="test@example.com"),
                gym_id=1
            )
        """
        # Convertir a dict si es schema Pydantic
        if hasattr(obj_in, 'model_dump'):
            obj_in_data = obj_in.model_dump(exclude_unset=True)
        elif hasattr(obj_in, 'dict'):
            obj_in_data = obj_in.dict(exclude_unset=True)
        elif isinstance(obj_in, dict):
            obj_in_data = obj_in
        else:
            obj_in_data = jsonable_encoder(obj_in)

        # Filtrar solo los campos que existen en el modelo
        valid_fields = {}
        for field, value in obj_in_data.items():
            if hasattr(self.model, field):
                valid_fields[field] = value
            else:
                logger.warning(
                    f"Campo ignorado en create: {self.model.__name__} no tiene campo '{field}'"
                )

        # Asignar gym_id automáticamente si el modelo lo soporta
        if gym_id is not None and hasattr(self.model, "gym_id"):
            valid_fields["gym_id"] = gym_id

        # Crear instancia del modelo
        db_obj = self.model(**valid_fields)

        # Guardar en BD
        db.add(db_obj)
        await db.flush()
        await db.refresh(db_obj)

        return db_obj

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: ModelType,
        obj_in: Union[UpdateSchemaType, Dict[str, Any]],
        gym_id: Optional[int] = None
    ) -> ModelType:
        """
        Actualizar un objeto existente.

        Args:
            db: Sesión async de base de datos
            db_obj: Objeto existente a actualizar
            obj_in: Datos de actualización (schema Pydantic o dict)
            gym_id: ID del gimnasio para validar pertenencia (multi-tenant)

        Returns:
            El objeto actualizado

        Raises:
            ValueError: Si el objeto no pertenece al gym_id especificado

        Example:
            updated = await user_repository.update(
                db,
                db_obj=user,
                obj_in=UserUpdate(email="new@example.com"),
                gym_id=1
            )
        """
        # Validar que el objeto pertenece al gimnasio correcto (multi-tenant)
        if gym_id is not None and hasattr(db_obj, "gym_id"):
            if db_obj.gym_id != gym_id:
                raise ValueError(
                    f"El objeto con ID {db_obj.id} no pertenece al gimnasio {gym_id}"
                )

        # Convertir a dict si es schema Pydantic
        if isinstance(obj_in, dict):
            update_data = obj_in
        elif hasattr(obj_in, 'model_dump'):
            update_data = obj_in.model_dump(exclude_unset=True)
        elif hasattr(obj_in, 'dict'):
            update_data = obj_in.dict(exclude_unset=True)
        else:
            update_data = jsonable_encoder(obj_in)

        # Aplicar actualizaciones
        for field, value in update_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)
            else:
                logger.warning(
                    f"Campo ignorado en update: {self.model.__name__} no tiene campo '{field}'"
                )

        # Guardar cambios
        db.add(db_obj)
        await db.flush()
        await db.refresh(db_obj)

        return db_obj

    async def remove(
        self,
        db: AsyncSession,
        *,
        id: int,
        gym_id: Optional[int] = None
    ) -> ModelType:
        """
        Eliminar un objeto de la base de datos.

        Args:
            db: Sesión async de base de datos
            id: ID del objeto a eliminar
            gym_id: ID del gimnasio para validar pertenencia (multi-tenant)

        Returns:
            El objeto eliminado

        Raises:
            ValueError: Si el objeto no existe o no pertenece al gym_id

        Example:
            deleted = await user_repository.remove(db, id=123, gym_id=1)
        """
        # Obtener el objeto primero para validar existencia y pertenencia
        obj = await self.get(db, id=id, gym_id=gym_id)

        if not obj:
            if gym_id:
                raise ValueError(
                    f"{self.model.__name__} con ID {id} no encontrado en el gimnasio {gym_id}"
                )
            else:
                raise ValueError(
                    f"{self.model.__name__} con ID {id} no encontrado"
                )

        # Eliminar
        db.delete(obj)
        await db.flush()

        return obj

    async def exists(
        self,
        db: AsyncSession,
        id: int,
        gym_id: Optional[int] = None
    ) -> bool:
        """
        Verificar si un objeto existe en la base de datos.

        Args:
            db: Sesión async de base de datos
            id: ID del objeto a verificar
            gym_id: ID del gimnasio para filtrar (multi-tenant)

        Returns:
            True si el objeto existe, False en caso contrario

        Example:
            if await user_repository.exists(db, id=123, gym_id=1):
                print("El usuario existe en el gimnasio 1")
        """
        stmt = select(self.model.id).where(self.model.id == id)

        # Filtrar por gym_id si el modelo lo soporta y se proporciona
        if gym_id is not None and hasattr(self.model, "gym_id"):
            stmt = stmt.where(self.model.gym_id == gym_id)

        result = await db.execute(stmt)
        return result.scalar_one_or_none() is not None
