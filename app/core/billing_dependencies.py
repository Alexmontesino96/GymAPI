"""
Dependencias específicas para el módulo de billing.
Verifica que el módulo esté activo antes de permitir operaciones de facturación.
"""

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional

from app.db.session import get_db
from app.services.module import module_service
from app.core.tenant import get_tenant_id
from app.schemas.gym import GymSchema
from app.core.tenant import verify_gym_access


def billing_module_required(
    db: Session = Depends(get_db),
    gym_id: int = Depends(get_tenant_id),
    current_gym: GymSchema = Depends(verify_gym_access)
) -> None:
    """
    Dependencia que verifica si el módulo de billing está activo para el gimnasio.
    
    Args:
        db: Sesión de base de datos
        gym_id: ID del gimnasio actual
        current_gym: Datos del gimnasio actual
        
    Raises:
        HTTPException 403: Si el módulo billing no está activo
        HTTPException 404: Si el módulo billing no existe
    """
    is_active = module_service.get_gym_module_status(db, gym_id, "billing")
    
    if is_active is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El módulo de facturación no está disponible en el sistema"
        )
    
    if not is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El módulo de facturación no está activado para este gimnasio. "
                   "Contacta al administrador para activar la funcionalidad de pagos."
        )


def billing_module_optional(
    db: Session = Depends(get_db),
    gym_id: int = Depends(get_tenant_id)
) -> bool:
    """
    Dependencia que verifica si el módulo de billing está activo, pero no falla si no lo está.
    
    Args:
        db: Sesión de base de datos
        gym_id: ID del gimnasio actual
        
    Returns:
        bool: True si el módulo está activo, False en caso contrario
    """
    is_active = module_service.get_gym_module_status(db, gym_id, "billing")
    return is_active is True


class BillingFeatureGate:
    """
    Clase para controlar el acceso a funcionalidades específicas del billing.
    """
    
    @staticmethod
    def check_stripe_integration(
        billing_active: bool = Depends(billing_module_optional)
    ) -> bool:
        """
        Verifica si la integración con Stripe está disponible.
        
        Args:
            billing_active: Estado del módulo billing
            
        Returns:
            bool: True si Stripe está disponible
        """
        return billing_active
    
    @staticmethod
    def check_subscription_management(
        billing_active: bool = Depends(billing_module_optional)
    ) -> bool:
        """
        Verifica si la gestión de suscripciones está disponible.
        
        Args:
            billing_active: Estado del módulo billing
            
        Returns:
            bool: True si la gestión de suscripciones está disponible
        """
        return billing_active
    
    @staticmethod
    def check_payment_processing(
        billing_active: bool = Depends(billing_module_optional)
    ) -> bool:
        """
        Verifica si el procesamiento de pagos está disponible.
        
        Args:
            billing_active: Estado del módulo billing
            
        Returns:
            bool: True si el procesamiento de pagos está disponible
        """
        return billing_active


def get_billing_capabilities(
    billing_active: bool = Depends(billing_module_optional)
) -> dict:
    """
    Obtiene las capacidades de billing disponibles para el gimnasio.
    
    Args:
        billing_active: Estado del módulo billing
        
    Returns:
        dict: Diccionario con las capacidades disponibles
    """
    return {
        "billing_enabled": billing_active,
        "stripe_integration": billing_active,
        "subscription_management": billing_active,
        "payment_processing": billing_active,
        "automated_billing": billing_active,
        "webhook_handling": billing_active,
        "revenue_analytics": billing_active,
        "refund_management": billing_active,
        "trial_periods": billing_active,
        "promo_codes": billing_active
    } 