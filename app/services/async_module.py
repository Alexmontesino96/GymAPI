"""
AsyncModuleService - Servicio async para gestión de módulos del sistema.

Este módulo maneja operaciones CRUD de módulos y su configuración por gimnasio.

Migrado en FASE 3 de la conversión sync → async.
"""

from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime, timezone

from app.models.module import Module
from app.models.gym_module import GymModule
from app.schemas.module import ModuleCreate, ModuleUpdate


class AsyncModuleService:
    """
    Servicio async para manejar operaciones CRUD de módulos y configuración por gimnasio.

    Todos los métodos son async y utilizan AsyncSession.

    Funcionalidades:
    - CRUD de módulos del sistema
    - Activación/desactivación por gimnasio
    - Verificación de estado de módulos
    - Listado de módulos activos por gym

    Métodos principales:
    - get_module_by_code() - Buscar módulo por código
    - get_active_modules_for_gym() - Módulos activos del gym
    - activate_module_for_gym() - Activar módulo
    - deactivate_module_for_gym() - Desactivar módulo
    """

    async def get_module_by_id(self, db: AsyncSession, module_id: int) -> Optional[Module]:
        """
        Obtener un módulo por su ID.

        Args:
            db: Sesión async de base de datos
            module_id: ID del módulo

        Returns:
            Optional[Module]: Módulo encontrado o None
        """
        result = await db.execute(
            select(Module).where(Module.id == module_id)
        )
        return result.scalar_one_or_none()

    async def get_module_by_code(self, db: AsyncSession, code: str) -> Optional[Module]:
        """
        Obtener un módulo por su código.

        Args:
            db: Sesión async de base de datos
            code: Código del módulo (ej: "billing", "chat")

        Returns:
            Optional[Module]: Módulo encontrado o None
        """
        result = await db.execute(
            select(Module).where(Module.code == code)
        )
        return result.scalar_one_or_none()

    async def get_modules(self, db: AsyncSession, skip: int = 0, limit: int = 100) -> List[Module]:
        """
        Obtener la lista de todos los módulos disponibles.

        Args:
            db: Sesión async de base de datos
            skip: Número de registros a saltar (paginación)
            limit: Límite de registros a retornar

        Returns:
            List[Module]: Lista de módulos del sistema
        """
        result = await db.execute(
            select(Module).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def create_module(self, db: AsyncSession, module: ModuleCreate) -> Module:
        """
        Crear un nuevo módulo.

        Args:
            db: Sesión async de base de datos
            module: Datos del módulo a crear

        Returns:
            Module: Módulo creado con ID asignado

        Note:
            - code debe ser único
            - is_premium determina si requiere plan de pago
        """
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
        """
        Actualizar un módulo existente.

        Args:
            db: Sesión async de base de datos
            module_id: ID del módulo a actualizar
            module: Datos a actualizar (solo campos proporcionados)

        Returns:
            Optional[Module]: Módulo actualizado o None si no existe
        """
        db_module = await self.get_module_by_id(db, module_id)
        if db_module:
            from fastapi.encoders import jsonable_encoder
            for key, value in jsonable_encoder(module, exclude_unset=True).items():
                setattr(db_module, key, value)
            await db.commit()
            await db.refresh(db_module)
        return db_module

    async def delete_module(self, db: AsyncSession, module_id: int) -> bool:
        """
        Eliminar un módulo por su ID.

        Args:
            db: Sesión async de base de datos
            module_id: ID del módulo a eliminar

        Returns:
            bool: True si se eliminó, False si no existía

        Note:
            - Esto NO desactiva el módulo en gyms, lo elimina del sistema
            - Use con precaución
        """
        db_module = await self.get_module_by_id(db, module_id)
        if db_module:
            db.delete(db_module)
            await db.commit()
            return True
        return False

    # Métodos para gestionar activación por gimnasio

    async def get_active_modules_for_gym(self, db: AsyncSession, gym_id: int) -> List[Module]:
        """
        Obtener la lista de módulos activos para un gimnasio específico.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio

        Returns:
            List[Module]: Lista de módulos activos en el gym

        Note:
            - Solo retorna módulos con GymModule.active = True
            - Join con GymModule para filtrar
        """
        result = await db.execute(
            select(Module)
            .join(
                GymModule,
                and_(
                    GymModule.module_id == Module.id,
                    GymModule.gym_id == gym_id,
                    GymModule.active == True
                )
            )
        )
        return list(result.scalars().all())

    async def get_gym_module_status(self, db: AsyncSession, gym_id: int, module_code: str) -> Optional[bool]:
        """
        Verificar si un módulo está activo para un gimnasio específico.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio
            module_code: Código del módulo

        Returns:
            Optional[bool]:
            - True si está activo
            - False si existe pero está desactivado
            - None si el módulo no existe en el sistema
        """
        module = await self.get_module_by_code(db, module_code)
        if not module:
            return None

        result = await db.execute(
            select(GymModule).where(
                and_(
                    GymModule.gym_id == gym_id,
                    GymModule.module_id == module.id
                )
            )
        )
        gym_module = result.scalar_one_or_none()

        if not gym_module:
            return False

        return gym_module.active

    async def activate_module_for_gym(self, db: AsyncSession, gym_id: int, module_code: str) -> bool:
        """
        Activar un módulo para un gimnasio específico.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio
            module_code: Código del módulo a activar

        Returns:
            bool: True si se activó, False si el módulo no existe

        Note:
            - Si GymModule ya existe, solo actualiza active = True
            - Si no existe, crea nueva relación GymModule
            - Limpia deactivated_at al activar
        """
        module = await self.get_module_by_code(db, module_code)
        if not module:
            return False

        result = await db.execute(
            select(GymModule).where(
                and_(
                    GymModule.gym_id == gym_id,
                    GymModule.module_id == module.id
                )
            )
        )
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
        """
        Desactivar un módulo para un gimnasio específico.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio
            module_code: Código del módulo a desactivar

        Returns:
            bool: True si se desactivó, False si no estaba activo o no existe

        Note:
            - Marca deactivated_at con timestamp actual
            - No elimina la relación, solo la marca como inactiva
        """
        module = await self.get_module_by_code(db, module_code)
        if not module:
            return False

        result = await db.execute(
            select(GymModule).where(
                and_(
                    GymModule.gym_id == gym_id,
                    GymModule.module_id == module.id
                )
            )
        )
        gym_module = result.scalar_one_or_none()

        if gym_module and gym_module.active:
            gym_module.active = False
            gym_module.deactivated_at = datetime.now(timezone.utc)
            await db.commit()
            return True

        return False


# Instancia singleton del servicio async
async_module_service = AsyncModuleService()
