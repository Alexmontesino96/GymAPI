from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union, Callable

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.base_class import Base

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class BaseRepository(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model: Type[ModelType]):
        """
        Repository con operaciones CRUD por defecto y soporte para multi-tenant.
        """
        self.model = model

    def get(self, db: Session, id: Any, gym_id: Optional[int] = None) -> Optional[ModelType]:
        """
        Obtener un objeto por su ID con filtro opcional de tenant.
        
        Args:
            db: Sesión de base de datos
            id: ID del objeto a obtener
            gym_id: ID opcional del gimnasio (tenant) para filtrar
            
        Returns:
            El objeto solicitado o None si no existe
        """
        query = db.query(self.model).filter(self.model.id == id)
        
        # Filtrar por gimnasio si el modelo tiene el atributo gym_id y se proporciona un gym_id
        if gym_id is not None and hasattr(self.model, "gym_id"):
            query = query.filter(self.model.gym_id == gym_id)
            
        return query.first()

    def get_multi(
        self, db: Session, *, skip: int = 0, limit: int = 100, gym_id: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[ModelType]:
        """
        Obtener múltiples registros con filtros opcionales.
        
        Args:
            db: Sesión de base de datos
            skip: Número de registros a omitir (paginación)
            limit: Número máximo de registros a devolver
            gym_id: ID opcional del gimnasio para filtrar resultados
            filters: Diccionario de filtros adicionales {campo: valor}
            
        Returns:
            Lista de objetos que coinciden con los criterios
        """
        query = db.query(self.model)
        
        # Filtrar por gimnasio si el modelo tiene el atributo gym_id y se proporciona un gym_id
        if gym_id is not None and hasattr(self.model, "gym_id"):
            query = query.filter(self.model.gym_id == gym_id)
            
        # Aplicar filtros adicionales si se proporcionan
        if filters:
            for field, value in filters.items():
                if hasattr(self.model, field):
                    query = query.filter(getattr(self.model, field) == value)
                    
        return query.offset(skip).limit(limit).all()

    def create(self, db: Session, *, obj_in: CreateSchemaType, gym_id: Optional[int] = None) -> ModelType:
        """
        Crear un nuevo registro con soporte para tenant.
        
        Args:
            db: Sesión de base de datos
            obj_in: Datos del objeto a crear
            gym_id: ID opcional del gimnasio (tenant)
            
        Returns:
            El objeto creado
        """
        # Usar model_dump() en lugar de jsonable_encoder() para preservar datetime aware
        if hasattr(obj_in, 'model_dump'):
            obj_in_data = obj_in.model_dump()
        elif hasattr(obj_in, '__dict__'):
            obj_in_data = obj_in.__dict__.copy()
        else:
            # Fallback a jsonable_encoder solo si no hay otras opciones
            obj_in_data = jsonable_encoder(obj_in)
        
        # Añadir gym_id si se proporciona y el modelo tiene ese campo
        if gym_id is not None and hasattr(self.model, "gym_id"):
            obj_in_data["gym_id"] = gym_id
            
        db_obj = self.model(**obj_in_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(
        self,
        db: Session,
        *,
        db_obj: ModelType,
        obj_in: Union[UpdateSchemaType, Dict[str, Any]],
        gym_id: Optional[int] = None
    ) -> ModelType:
        """
        Actualizar un registro con verificación opcional de tenant.
        
        Args:
            db: Sesión de base de datos
            db_obj: Objeto existente a actualizar
            obj_in: Datos de actualización
            gym_id: ID opcional del gimnasio para verificar pertenencia
            
        Returns:
            El objeto actualizado
            
        Raises:
            ValueError: Si se proporciona gym_id y el objeto no pertenece a ese gimnasio
        """
        # Verificar pertenencia al gimnasio si se proporciona
        if gym_id is not None and hasattr(db_obj, "gym_id") and db_obj.gym_id != gym_id:
            raise ValueError(f"El objeto con ID {db_obj.id} no pertenece al gimnasio {gym_id}")
            
        obj_data = jsonable_encoder(db_obj)
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = jsonable_encoder(obj_in, exclude_unset=True)
        for field in obj_data:
            if field in update_data:
                setattr(db_obj, field, update_data[field])
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def remove(self, db: Session, *, id: int, gym_id: Optional[int] = None) -> ModelType:
        """
        Eliminar un registro con verificación opcional de tenant.
        
        Args:
            db: Sesión de base de datos
            id: ID del objeto a eliminar
            gym_id: ID opcional del gimnasio para verificar pertenencia
            
        Returns:
            El objeto eliminado
            
        Raises:
            ValueError: Si el objeto no existe o no pertenece al gimnasio especificado
        """
        obj = self.get(db, id=id, gym_id=gym_id)
        if not obj:
            if gym_id:
                raise ValueError(f"Objeto con ID {id} no encontrado en el gimnasio {gym_id}")
            else:
                raise ValueError(f"Objeto con ID {id} no encontrado")
                
        db.delete(obj)
        db.commit()
        return obj
        
    def exists(self, db: Session, id: int, gym_id: Optional[int] = None) -> bool:
        """
        Verificar si un objeto existe con verificación opcional de tenant.
        
        Args:
            db: Sesión de base de datos
            id: ID del objeto a verificar
            gym_id: ID opcional del gimnasio para verificar pertenencia
            
        Returns:
            True si el objeto existe, False en caso contrario
        """
        query = db.query(self.model.id).filter(self.model.id == id)
        
        if gym_id is not None and hasattr(self.model, "gym_id"):
            query = query.filter(self.model.gym_id == gym_id)
            
        return db.query(query.exists()).scalar() 