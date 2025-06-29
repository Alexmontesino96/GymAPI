from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime

from app.models.module import Module
from app.models.gym_module import GymModule
from app.schemas.module import ModuleCreate, ModuleUpdate


class ModuleService:
    """
    Servicio para manejar operaciones CRUD de módulos y configuración por gimnasio
    """
    
    def get_module_by_id(self, db: Session, module_id: int) -> Optional[Module]:
        """Obtener un módulo por su ID"""
        return db.query(Module).filter(Module.id == module_id).first()
    
    def get_module_by_code(self, db: Session, code: str) -> Optional[Module]:
        """Obtener un módulo por su código"""
        return db.query(Module).filter(Module.code == code).first()
    
    def get_modules(self, db: Session, skip: int = 0, limit: int = 100) -> List[Module]:
        """Obtener la lista de todos los módulos disponibles"""
        return db.query(Module).offset(skip).limit(limit).all()
    
    def create_module(self, db: Session, module: ModuleCreate) -> Module:
        """Crear un nuevo módulo"""
        db_module = Module(
            code=module.code,
            name=module.name,
            description=module.description,
            is_premium=module.is_premium
        )
        db.add(db_module)
        db.commit()
        db.refresh(db_module)
        return db_module
    
    def update_module(self, db: Session, module_id: int, module: ModuleUpdate) -> Optional[Module]:
        """Actualizar un módulo existente"""
        db_module = self.get_module_by_id(db, module_id)
        if db_module:
            from fastapi.encoders import jsonable_encoder
            for key, value in jsonable_encoder(module, exclude_unset=True).items():
                setattr(db_module, key, value)
            db.commit()
            db.refresh(db_module)
        return db_module
    
    def delete_module(self, db: Session, module_id: int) -> bool:
        """Eliminar un módulo por su ID"""
        db_module = self.get_module_by_id(db, module_id)
        if db_module:
            db.delete(db_module)
            db.commit()
            return True
        return False
    
    # Métodos para gestionar activación por gimnasio
    
    def get_active_modules_for_gym(self, db: Session, gym_id: int) -> List[Module]:
        """Obtener la lista de módulos activos para un gimnasio específico"""
        return db.query(Module).join(
            GymModule, 
            and_(
                GymModule.module_id == Module.id,
                GymModule.gym_id == gym_id, 
                GymModule.active == True
            )
        ).all()
    
    def get_gym_module_status(self, db: Session, gym_id: int, module_code: str) -> Optional[bool]:
        """Verificar si un módulo está activo para un gimnasio específico"""
        module = self.get_module_by_code(db, module_code)
        if not module:
            return None
            
        gym_module = db.query(GymModule).filter(
            and_(
                GymModule.gym_id == gym_id,
                GymModule.module_id == module.id
            )
        ).first()
        
        if not gym_module:
            return False
            
        return gym_module.active
    
    def activate_module_for_gym(self, db: Session, gym_id: int, module_code: str) -> bool:
        """Activar un módulo para un gimnasio específico"""
        module = self.get_module_by_code(db, module_code)
        if not module:
            return False
            
        gym_module = db.query(GymModule).filter(
            and_(
                GymModule.gym_id == gym_id,
                GymModule.module_id == module.id
            )
        ).first()
        
        if gym_module:
            if not gym_module.active:
                gym_module.active = True
                gym_module.deactivated_at = None
                db.commit()
            return True
            
        # Si no existe la relación, crearla
        new_gym_module = GymModule(
            gym_id=gym_id,
            module_id=module.id,
            active=True,
            activated_at=datetime.utcnow()
        )
        db.add(new_gym_module)
        db.commit()
        return True
    
    def deactivate_module_for_gym(self, db: Session, gym_id: int, module_code: str) -> bool:
        """Desactivar un módulo para un gimnasio específico"""
        module = self.get_module_by_code(db, module_code)
        if not module:
            return False
            
        gym_module = db.query(GymModule).filter(
            and_(
                GymModule.gym_id == gym_id,
                GymModule.module_id == module.id
            )
        ).first()
        
        if gym_module and gym_module.active:
            gym_module.active = False
            gym_module.deactivated_at = datetime.utcnow()
            db.commit()
            return True
            
        return False


module_service = ModuleService()
