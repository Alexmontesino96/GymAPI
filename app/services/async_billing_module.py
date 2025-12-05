"""
AsyncBillingModuleService - Servicio async para gestionar módulo de billing.

Este módulo proporciona funcionalidades async para activar/desactivar el módulo
de billing y gestionar su integración con Stripe.

Migrado en FASE 3 de la conversión sync → async.
"""

from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from datetime import datetime, timezone
import logging
import stripe

from app.services.module import module_service
from app.services.stripe_service import StripeService
from app.services.membership import membership_service
from app.models.gym import Gym
from app.models.user_gym import UserGym
from app.core.config import get_settings

logger = logging.getLogger("async_billing_module_service")
settings = get_settings()


class AsyncBillingModuleService:
    """
    Servicio async para gestionar el módulo de billing de forma específica.

    Todos los métodos son async y utilizan AsyncSession.

    Características:
    - Activación/desactivación del módulo billing
    - Validación de configuración de Stripe
    - Sincronización de planes con Stripe
    - Verificación de suscripciones activas
    - Analytics de revenue

    Métodos principales:
    - activate_billing_for_gym() - Activa billing con validación Stripe
    - deactivate_billing_for_gym() - Desactiva billing preservando datos
    - get_billing_status() - Estado completo del módulo
    """

    def __init__(self):
        """
        Inicializa el servicio con StripeService.

        Note:
            StripeService puede tener métodos sync internamente.
        """
        self.stripe_service = StripeService(membership_service)

    async def activate_billing_for_gym(
        self,
        db: AsyncSession,
        gym_id: int,
        validate_stripe_config: bool = True
    ) -> Dict[str, Any]:
        """
        Activar el módulo de billing para un gimnasio específico.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio
            validate_stripe_config: Si validar la configuración de Stripe

        Returns:
            Dict con resultado de la activación:
            - success: bool
            - message: str
            - stripe_config_valid: bool
            - plans_synced: int

        Note:
            - Valida configuración de Stripe antes de activar
            - Sincroniza planes existentes con Stripe automáticamente
        """
        try:
            # Verificar que el gimnasio existe
            result = await db.execute(
                select(Gym).where(Gym.id == gym_id)
            )
            gym = result.scalar_one_or_none()

            if not gym:
                return {
                    "success": False,
                    "error": f"Gimnasio {gym_id} no encontrado"
                }

            # Validar configuración de Stripe si es requerido
            if validate_stripe_config:
                stripe_validation = await self._validate_stripe_configuration()
                if not stripe_validation["valid"]:
                    return {
                        "success": False,
                        "error": f"Configuración de Stripe inválida: {stripe_validation['error']}"
                    }

            # Activar el módulo (sync - TODO: migrar module_service a async)
            success = module_service.activate_module_for_gym(db, gym_id, "billing")

            if not success:
                return {
                    "success": False,
                    "error": "Error al activar el módulo billing en la base de datos"
                }

            # Sincronizar planes existentes con Stripe (opcional)
            sync_result = await self._sync_existing_plans_with_stripe(db, gym_id)

            logger.info(f"Módulo billing activado para gym {gym_id}")

            return {
                "success": True,
                "message": f"Módulo de billing activado exitosamente para {gym.name}",
                "gym_id": gym_id,
                "gym_name": gym.name,
                "stripe_config_valid": stripe_validation.get("valid", False) if validate_stripe_config else None,
                "plans_synced": sync_result.get("synced", 0),
                "activation_timestamp": datetime.now(timezone.utc).isoformat()
            }

        except Exception as e:
            logger.error(f"Error activando billing para gym {gym_id}: {str(e)}")
            return {
                "success": False,
                "error": f"Error inesperado: {str(e)}"
            }

    async def deactivate_billing_for_gym(
        self,
        db: AsyncSession,
        gym_id: int,
        preserve_stripe_data: bool = True
    ) -> Dict[str, Any]:
        """
        Desactivar el módulo de billing para un gimnasio específico.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio
            preserve_stripe_data: Si preservar los datos de Stripe (recomendado)

        Returns:
            Dict con resultado de la desactivación:
            - success: bool
            - active_subscriptions: int
            - stripe_data_preserved: bool
            - warning: str (si hay suscripciones activas)

        Note:
            - Verifica suscripciones activas antes de desactivar
            - Por defecto preserva datos de Stripe (recomendado)
            - Las suscripciones activas seguirán funcionando
        """
        try:
            # Verificar que el gimnasio existe
            result = await db.execute(
                select(Gym).where(Gym.id == gym_id)
            )
            gym = result.scalar_one_or_none()

            if not gym:
                return {
                    "success": False,
                    "error": f"Gimnasio {gym_id} no encontrado"
                }

            # Verificar si hay suscripciones activas
            active_subscriptions = await self._check_active_subscriptions(db, gym_id)

            if active_subscriptions["count"] > 0:
                logger.warning(f"Gym {gym_id} tiene {active_subscriptions['count']} suscripciones activas")

            # Desactivar el módulo (sync - TODO: migrar module_service a async)
            success = module_service.deactivate_module_for_gym(db, gym_id, "billing")

            if not success:
                return {
                    "success": False,
                    "error": "Error al desactivar el módulo billing en la base de datos"
                }

            # Opcionalmente desactivar productos en Stripe (pero no eliminar)
            if not preserve_stripe_data:
                deactivation_result = await self._deactivate_stripe_products(db, gym_id)
            else:
                deactivation_result = {"message": "Datos de Stripe preservados"}

            logger.info(f"Módulo billing desactivado para gym {gym_id}")

            return {
                "success": True,
                "message": f"Módulo de billing desactivado para {gym.name}",
                "gym_id": gym_id,
                "gym_name": gym.name,
                "active_subscriptions": active_subscriptions["count"],
                "stripe_data_preserved": preserve_stripe_data,
                "stripe_action": deactivation_result.get("message"),
                "deactivation_timestamp": datetime.now(timezone.utc).isoformat(),
                "warning": (
                    f"Hay {active_subscriptions['count']} suscripciones activas que seguirán funcionando"
                    if active_subscriptions["count"] > 0 else None
                )
            }

        except Exception as e:
            logger.error(f"Error desactivando billing para gym {gym_id}: {str(e)}")
            return {
                "success": False,
                "error": f"Error inesperado: {str(e)}"
            }

    async def get_billing_status(
        self,
        db: AsyncSession,
        gym_id: int
    ) -> Dict[str, Any]:
        """
        Obtener el estado actual del módulo billing para un gimnasio.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio

        Returns:
            Dict con estado detallado:
            - billing_enabled: bool
            - stripe_config_valid: bool
            - total_plans: int
            - active_subscriptions: int
            - capabilities: Dict con features disponibles

        Note:
            Si el módulo está activo, incluye información completa de Stripe,
            planes y suscripciones.
        """
        try:
            # Verificar estado del módulo (sync - TODO: migrar module_service a async)
            is_active = module_service.get_gym_module_status(db, gym_id, "billing")

            if is_active is None:
                return {
                    "billing_enabled": False,
                    "error": "Módulo billing no existe en el sistema"
                }

            # Obtener información adicional si está activo
            if is_active:
                stripe_config = await self._validate_stripe_configuration()
                plans_info = await self._get_plans_stripe_status(db, gym_id)
                subscriptions_info = await self._check_active_subscriptions(db, gym_id)

                return {
                    "billing_enabled": True,
                    "stripe_config_valid": stripe_config["valid"],
                    "total_plans": plans_info["total"],
                    "plans_with_stripe": plans_info["with_stripe"],
                    "active_subscriptions": subscriptions_info["count"],
                    "last_sync": plans_info.get("last_sync"),
                    "capabilities": {
                        "payment_processing": stripe_config["valid"],
                        "subscription_management": stripe_config["valid"],
                        "webhook_handling": bool(settings.STRIPE_WEBHOOK_SECRET),
                        "automated_billing": stripe_config["valid"],
                        "revenue_analytics": True
                    }
                }
            else:
                return {
                    "billing_enabled": False,
                    "message": "Módulo billing está desactivado para este gimnasio"
                }

        except Exception as e:
            logger.error(f"Error obteniendo estado billing para gym {gym_id}: {str(e)}")
            return {
                "billing_enabled": False,
                "error": f"Error obteniendo estado: {str(e)}"
            }

    # Métodos privados de utilidad

    async def _validate_stripe_configuration(self) -> Dict[str, Any]:
        """
        Validar la configuración de Stripe.

        Returns:
            Dict con validación:
            - valid: bool
            - error/message: str

        Note:
            Hace una llamada real a Stripe API para verificar la key.
            Stripe SDK es sync, pero la llamada es rápida.
        """
        try:
            if not settings.STRIPE_SECRET_KEY:
                return {"valid": False, "error": "STRIPE_SECRET_KEY no configurado"}

            if "your_sec" in str(settings.STRIPE_SECRET_KEY).lower():
                return {"valid": False, "error": "STRIPE_SECRET_KEY parece ser un placeholder"}

            # Intentar una llamada simple a Stripe para validar la key
            stripe.api_key = settings.STRIPE_SECRET_KEY

            # Test básico: listar productos (límite 1)
            stripe.Product.list(limit=1)

            return {"valid": True, "message": "Configuración de Stripe válida"}

        except stripe.error.AuthenticationError:
            return {"valid": False, "error": "STRIPE_SECRET_KEY inválido"}
        except Exception as e:
            return {"valid": False, "error": f"Error validando Stripe: {str(e)}"}

    async def _sync_existing_plans_with_stripe(
        self,
        db: AsyncSession,
        gym_id: int
    ) -> Dict[str, Any]:
        """
        Sincronizar planes existentes con Stripe al activar el módulo.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio

        Returns:
            Dict con resultado de sincronización:
            - synced: int (número de planes sincronizados)

        Note:
            Usa membership_service que puede tener métodos sync.
        """
        try:
            result = await membership_service.sync_all_plans_with_stripe(db, gym_id)
            return result
        except Exception as e:
            logger.error(f"Error sincronizando planes con Stripe para gym {gym_id}: {str(e)}")
            return {"synced": 0, "error": str(e)}

    async def _check_active_subscriptions(
        self,
        db: AsyncSession,
        gym_id: int
    ) -> Dict[str, Any]:
        """
        Verificar suscripciones activas para un gimnasio.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio

        Returns:
            Dict con count de suscripciones activas
        """
        try:
            result = await db.execute(
                select(func.count(UserGym.id)).where(
                    and_(
                        UserGym.gym_id == gym_id,
                        UserGym.stripe_subscription_id.isnot(None),
                        UserGym.is_active == True
                    )
                )
            )
            active_subs = result.scalar()

            return {"count": active_subs}

        except Exception as e:
            logger.error(f"Error verificando suscripciones activas para gym {gym_id}: {str(e)}")
            return {"count": 0, "error": str(e)}

    async def _get_plans_stripe_status(
        self,
        db: AsyncSession,
        gym_id: int
    ) -> Dict[str, Any]:
        """
        Obtener información sobre el estado de Stripe de los planes.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio

        Returns:
            Dict con información de planes:
            - total: int
            - with_stripe: int
            - sync_percentage: float

        Note:
            Usa membership_service.get_membership_plans (puede ser sync).
        """
        try:
            plans = membership_service.get_membership_plans(
                db, gym_id=gym_id, active_only=False, skip=0, limit=1000
            )

            total = len(plans)
            with_stripe = sum(1 for plan in plans if plan.stripe_price_id)

            return {
                "total": total,
                "with_stripe": with_stripe,
                "sync_percentage": (with_stripe / total * 100) if total > 0 else 0
            }

        except Exception as e:
            logger.error(f"Error obteniendo estado de planes para gym {gym_id}: {str(e)}")
            return {"total": 0, "with_stripe": 0, "error": str(e)}

    async def _deactivate_stripe_products(
        self,
        db: AsyncSession,
        gym_id: int
    ) -> Dict[str, Any]:
        """
        Desactivar productos de Stripe para un gimnasio.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio

        Returns:
            Dict con resultado:
            - message: str
            - deactivated_count: int

        Note:
            No elimina productos, solo los marca como inactivos en Stripe.
        """
        try:
            plans = membership_service.get_membership_plans(
                db, gym_id=gym_id, active_only=False, skip=0, limit=1000
            )

            deactivated = 0
            for plan in plans:
                if plan.stripe_product_id:
                    success = await self.stripe_service.deactivate_stripe_product_for_plan(plan)
                    if success:
                        deactivated += 1

            return {
                "message": f"Desactivados {deactivated} productos de Stripe",
                "deactivated_count": deactivated
            }

        except Exception as e:
            logger.error(f"Error desactivando productos Stripe para gym {gym_id}: {str(e)}")
            return {"message": f"Error: {str(e)}", "deactivated_count": 0}


# Instancia singleton del servicio async
async_billing_module_service = AsyncBillingModuleService()
