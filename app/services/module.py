from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime, timezone

from app.models.module import Module
from app.models.gym_module import GymModule
from app.schemas.module import ModuleCreate, ModuleUpdate


class ModuleService:
    """
    Servicio para manejar operaciones CRUD de módulos y configuración por gimnasio
    """
    
    async def get_module_by_id(self, db: AsyncSession, module_id: int) -> Optional[Module]:
        """Obtener un módulo por su ID"""
        stmt = select(Module).where(Module.id == module_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_module_by_code(self, db: AsyncSession, code: str) -> Optional[Module]:
        """Obtener un módulo por su código"""
        stmt = select(Module).where(Module.code == code)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_modules(self, db: AsyncSession, skip: int = 0, limit: int = 100) -> List[Module]:
        """Obtener la lista de todos los módulos disponibles"""
        stmt = select(Module).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return result.scalars().all()
    
    async def create_module(self, db: AsyncSession, module: ModuleCreate) -> Module:
        """Crear un nuevo módulo"""
        db_module = Module(
            code=module.code,
            name=module.name,
            description=module.description,
            is_premium=module.is_premium
        )
        db.add(db_module)
        await db.commit()
        await db.refresh(db_module)
        return db_module
    
    async def update_module(self, db: AsyncSession, module_id: int, module: ModuleUpdate) -> Optional[Module]:
        """Actualizar un módulo existente"""
        db_module = await self.get_module_by_id(db, module_id)
        if db_module:
            from fastapi.encoders import jsonable_encoder
            for key, value in jsonable_encoder(module, exclude_unset=True).items():
                setattr(db_module, key, value)
            await db.commit()
            await db.refresh(db_module)
        return db_module
    
    async def delete_module(self, db: AsyncSession, module_id: int) -> bool:
        """Eliminar un módulo por su ID"""
        db_module = await self.get_module_by_id(db, module_id)
        if db_module:
            db.delete(db_module)
            await db.commit()
            return True
        return False
    
    # Métodos para gestionar activación por gimnasio
    
    async def get_active_modules_for_gym(self, db: AsyncSession, gym_id: int) -> List[Module]:
        """Obtener la lista de módulos activos para un gimnasio específico"""
        stmt = select(Module).join(
            GymModule,
            and_(
                GymModule.module_id == Module.id,
                GymModule.gym_id == gym_id,
                GymModule.active == True
            )
        )
        result = await db.execute(stmt)
        return result.scalars().all()
    
    async def get_gym_module_status(self, db: AsyncSession, gym_id: int, module_code: str) -> Optional[bool]:
        """Verificar si un módulo está activo para un gimnasio específico"""
        module = await self.get_module_by_code(db, module_code)
        if not module:
            return None

        stmt = select(GymModule).where(
            and_(
                GymModule.gym_id == gym_id,
                GymModule.module_id == module.id
            )
        )
        result = await db.execute(stmt)
        gym_module = result.scalar_one_or_none()

        if not gym_module:
            return False

        return gym_module.active
    
    async def activate_module_for_gym(self, db: AsyncSession, gym_id: int, module_code: str) -> bool:
        """Activar un módulo para un gimnasio específico"""
        module = await self.get_module_by_code(db, module_code)
        if not module:
            return False

        stmt = select(GymModule).where(
            and_(
                GymModule.gym_id == gym_id,
                GymModule.module_id == module.id
            )
        )
        result = await db.execute(stmt)
        gym_module = result.scalar_one_or_none()

        if gym_module:
            if not gym_module.active:
                gym_module.active = True
                gym_module.deactivated_at = None
                await db.commit()
            return True

        # Si no existe la relación, crearla
        new_gym_module = GymModule(
            gym_id=gym_id,
            module_id=module.id,
            active=True,
            activated_at=datetime.now(timezone.utc)
        )
        db.add(new_gym_module)
        await db.commit()
        return True
    
    async def deactivate_module_for_gym(self, db: AsyncSession, gym_id: int, module_code: str) -> bool:
        """Desactivar un módulo para un gimnasio específico"""
        module = await self.get_module_by_code(db, module_code)
        if not module:
            return False

        stmt = select(GymModule).where(
            and_(
                GymModule.gym_id == gym_id,
                GymModule.module_id == module.id
            )
        )
        result = await db.execute(stmt)
        gym_module = result.scalar_one_or_none()

        if gym_module and gym_module.active:
            gym_module.active = False
            gym_module.deactivated_at = datetime.now(timezone.utc)
            await db.commit()
            return True

        return False


module_service = ModuleService()
