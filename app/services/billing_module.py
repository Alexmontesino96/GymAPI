"""
Servicio para gestionar el módulo de billing y su integración con Stripe.
Maneja la activación/desactivación y configuración específica del módulo.
"""

from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from app.services.module import module_service
from app.services.stripe_service import StripeService
from app.services.membership import membership_service
from app.models.gym import Gym
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class BillingModuleService:
    """
    Servicio para gestionar el módulo de billing de forma específica.
    """
    
    def __init__(self):
        self.stripe_service = StripeService(membership_service)
    
    async def activate_billing_for_gym(
        self, 
        db: Session, 
        gym_id: int,
        validate_stripe_config: bool = True
    ) -> Dict[str, Any]:
        """
        Activar el módulo de billing para un gimnasio específico.
        
        Args:
            db: Sesión de base de datos
            gym_id: ID del gimnasio
            validate_stripe_config: Si validar la configuración de Stripe
            
        Returns:
            dict: Resultado de la activación
        """
        try:
            # Verificar que el gimnasio existe
            gym = db.query(Gym).filter(Gym.id == gym_id).first()
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
            
            # Activar el módulo
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
                "activation_timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error activando billing para gym {gym_id}: {str(e)}")
            return {
                "success": False,
                "error": f"Error inesperado: {str(e)}"
            }
    
    async def deactivate_billing_for_gym(
        self, 
        db: Session, 
        gym_id: int,
        preserve_stripe_data: bool = True
    ) -> Dict[str, Any]:
        """
        Desactivar el módulo de billing para un gimnasio específico.
        
        Args:
            db: Sesión de base de datos
            gym_id: ID del gimnasio
            preserve_stripe_data: Si preservar los datos de Stripe (recomendado)
            
        Returns:
            dict: Resultado de la desactivación
        """
        try:
            # Verificar que el gimnasio existe
            gym = db.query(Gym).filter(Gym.id == gym_id).first()
            if not gym:
                return {
                    "success": False,
                    "error": f"Gimnasio {gym_id} no encontrado"
                }
            
            # Verificar si hay suscripciones activas
            active_subscriptions = await self._check_active_subscriptions(db, gym_id)
            
            if active_subscriptions["count"] > 0:
                logger.warning(f"Gym {gym_id} tiene {active_subscriptions['count']} suscripciones activas")
            
            # Desactivar el módulo
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
                "deactivation_timestamp": datetime.utcnow().isoformat(),
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
    
    async def get_billing_status(self, db: Session, gym_id: int) -> Dict[str, Any]:
        """
        Obtener el estado actual del módulo billing para un gimnasio.
        
        Args:
            db: Sesión de base de datos
            gym_id: ID del gimnasio
            
        Returns:
            dict: Estado detallado del módulo billing
        """
        try:
            # Verificar estado del módulo
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
        """Validar la configuración de Stripe."""
        try:
            if not settings.STRIPE_SECRET_KEY:
                return {"valid": False, "error": "STRIPE_SECRET_KEY no configurado"}
            
            if "your_sec" in str(settings.STRIPE_SECRET_KEY).lower():
                return {"valid": False, "error": "STRIPE_SECRET_KEY parece ser un placeholder"}
            
            # Intentar una llamada simple a Stripe para validar la key
            import stripe
            stripe.api_key = settings.STRIPE_SECRET_KEY
            
            # Test básico: listar productos (límite 1)
            stripe.Product.list(limit=1)
            
            return {"valid": True, "message": "Configuración de Stripe válida"}
            
        except stripe.error.AuthenticationError:
            return {"valid": False, "error": "STRIPE_SECRET_KEY inválido"}
        except Exception as e:
            return {"valid": False, "error": f"Error validando Stripe: {str(e)}"}
    
    async def _sync_existing_plans_with_stripe(self, db: Session, gym_id: int) -> Dict[str, Any]:
        """Sincronizar planes existentes con Stripe al activar el módulo."""
        try:
            result = await membership_service.sync_all_plans_with_stripe(db, gym_id)
            return result
        except Exception as e:
            logger.error(f"Error sincronizando planes con Stripe para gym {gym_id}: {str(e)}")
            return {"synced": 0, "error": str(e)}
    
    async def _check_active_subscriptions(self, db: Session, gym_id: int) -> Dict[str, Any]:
        """Verificar suscripciones activas para un gimnasio."""
        try:
            from app.models.user_gym import UserGym
            
            active_subs = db.query(UserGym).filter(
                UserGym.gym_id == gym_id,
                UserGym.stripe_subscription_id.isnot(None),
                UserGym.is_active == True
            ).count()
            
            return {"count": active_subs}
            
        except Exception as e:
            logger.error(f"Error verificando suscripciones activas para gym {gym_id}: {str(e)}")
            return {"count": 0, "error": str(e)}
    
    async def _get_plans_stripe_status(self, db: Session, gym_id: int) -> Dict[str, Any]:
        """Obtener información sobre el estado de Stripe de los planes."""
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
    
    async def _deactivate_stripe_products(self, db: Session, gym_id: int) -> Dict[str, Any]:
        """Desactivar productos de Stripe para un gimnasio."""
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


# Instancia global del servicio
billing_module_service = BillingModuleService() 