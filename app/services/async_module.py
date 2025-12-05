"""
AsyncModuleService - Servicio async para gestión de módulos del gimnasio.

Este módulo proporciona un servicio totalmente async para operaciones CRUD de módulos
del sistema y su activación/desactivación por gimnasio.

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

    Módulos del sistema:
    - nutrition: Módulo de nutrición con IA
    - billing: Facturación y pagos con Stripe
    - events: Eventos del gimnasio
    - schedule: Clases y horarios
    - chat: Sistema de chat con Stream
    - surveys: Encuestas y feedback
    - health: Tracking de medidas corporales
    - metrics: Dashboard de estadísticas

    Métodos principales:
    - get_module_by_id() - Obtener módulo por ID
    - get_module_by_code() - Obtener módulo por código único
    - get_modules() - Listar todos los módulos
    - create_module() - Crear nuevo módulo (admin)
    - update_module() - Actualizar módulo existente
    - delete_module() - Eliminar módulo (hard delete)
    - get_active_modules_for_gym() - Módulos activos de un gym
    - get_gym_module_status() - Verificar estado de módulo
    - activate_module_for_gym() - Activar módulo para gym
    - deactivate_module_for_gym() - Desactivar módulo para gym
    """

    async def get_module_by_id(
        self,
        db: AsyncSession,
        module_id: int
    ) -> Optional[Module]:
        """
        Obtener un módulo por su ID.

        Args:
            db: Sesión async de base de datos
            module_id: ID del módulo

        Returns:
            Módulo encontrado o None
        """
        result = await db.execute(
            select(Module).where(Module.id == module_id)
        )
        return result.scalar_one_or_none()

    async def get_module_by_code(
        self,
        db: AsyncSession,
        code: str
    ) -> Optional[Module]:
        """
        Obtener un módulo por su código único.

        Args:
            db: Sesión async de base de datos
            code: Código del módulo (ej: "nutrition", "billing")

        Returns:
            Módulo encontrado o None

        Note:
            Los códigos de módulo son únicos en el sistema.
        """
        result = await db.execute(
            select(Module).where(Module.code == code)
        )
        return result.scalar_one_or_none()

    async def get_modules(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100
    ) -> List[Module]:
        """
        Obtener la lista de todos los módulos disponibles en el sistema.

        Args:
            db: Sesión async de base de datos
            skip: Registros a omitir (paginación)
            limit: Máximo de registros a devolver

        Returns:
            Lista de módulos del sistema
        """
        result = await db.execute(
            select(Module).offset(skip).limit(limit)
        )
        return result.scalars().all()

    async def create_module(
        self,
        db: AsyncSession,
        module: ModuleCreate
    ) -> Module:
        """
        Crear un nuevo módulo en el sistema (solo admin).

        Args:
            db: Sesión async de base de datos
            module: Datos del módulo a crear

        Returns:
            Módulo creado

        Note:
            El código del módulo debe ser único en el sistema.
            is_premium determina si requiere suscripción especial.
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

    async def update_module(
        self,
        db: AsyncSession,
        module_id: int,
        module: ModuleUpdate
    ) -> Optional[Module]:
        """
        Actualizar un módulo existente.

        Args:
            db: Sesión async de base de datos
            module_id: ID del módulo a actualizar
            module: Datos de actualización

        Returns:
            Módulo actualizado o None si no existe

        Note:
            Solo actualiza campos no nulos del schema ModuleUpdate.
        """
        db_module = await self.get_module_by_id(db, module_id)
        if db_module:
            from fastapi.encoders import jsonable_encoder
            for key, value in jsonable_encoder(module, exclude_unset=True).items():
                setattr(db_module, key, value)
            await db.commit()
            await db.refresh(db_module)
        return db_module

    async def delete_module(
        self,
        db: AsyncSession,
        module_id: int
    ) -> bool:
        """
        Eliminar un módulo por su ID (hard delete).

        Args:
            db: Sesión async de base de datos
            module_id: ID del módulo a eliminar

        Returns:
            True si se eliminó, False si no existe

        Warning:
            Hard delete - elimina permanentemente el módulo y todas
            sus relaciones GymModule asociadas (CASCADE).
        """
        db_module = await self.get_module_by_id(db, module_id)
        if db_module:
            await db.delete(db_module)
            await db.commit()
            return True
        return False

    # Métodos para gestionar activación por gimnasio

    async def get_active_modules_for_gym(
        self,
        db: AsyncSession,
        gym_id: int
    ) -> List[Module]:
        """
        Obtener la lista de módulos activos para un gimnasio específico.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio

        Returns:
            Lista de módulos activos del gimnasio

        Note:
            Solo retorna módulos con GymModule.active=True.
            Útil para validar features disponibles por gimnasio.
        """
        result = await db.execute(
            select(Module).join(
                GymModule,
                and_(
                    GymModule.module_id == Module.id,
                    GymModule.gym_id == gym_id,
                    GymModule.active == True
                )
            )
        )
        return result.scalars().all()

    async def get_gym_module_status(
        self,
        db: AsyncSession,
        gym_id: int,
        module_code: str
    ) -> Optional[bool]:
        """
        Verificar si un módulo está activo para un gimnasio específico.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio
            module_code: Código del módulo

        Returns:
            True si activo, False si inactivo, None si módulo no existe

        Note:
            Si el módulo no tiene GymModule, retorna False (inactivo por defecto).
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

    async def activate_module_for_gym(
        self,
        db: AsyncSession,
        gym_id: int,
        module_code: str
    ) -> bool:
        """
        Activar un módulo para un gimnasio específico.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio
            module_code: Código del módulo

        Returns:
            True si se activó exitosamente, False si módulo no existe

        Note:
            - Si ya existe GymModule inactivo, lo reactiva
            - Si no existe GymModule, lo crea con active=True
            - Establece activated_at = now()
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

    async def deactivate_module_for_gym(
        self,
        db: AsyncSession,
        gym_id: int,
        module_code: str
    ) -> bool:
        """
        Desactivar un módulo para un gimnasio específico.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio
            module_code: Código del módulo

        Returns:
            True si se desactivó exitosamente, False si módulo no existe o ya inactivo

        Note:
            Establece deactivated_at = now() para auditoría.
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
