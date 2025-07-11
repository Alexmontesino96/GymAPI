"""
Servicio para manejar Stripe Connect y la vinculación de usuarios con customers.
Resuelve el problema de duplicación de customers en un entorno multitenant.
"""

import stripe
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.models.stripe_profile import UserGymStripeProfile, GymStripeAccount
from app.models.user import User
from app.models.gym import Gym
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

# Configurar Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


class StripeConnectService:
    """
    Servicio para manejar Stripe Connect y la vinculación de usuarios.
    
    Funcionalidades principales:
    - Crear cuentas de Stripe Connect para gyms
    - Gestionar customers sin duplicados
    - Onboarding de gyms
    - Sincronización de datos
    """
    
    # === GESTIÓN DE CUENTAS DE GYM ===
    
    async def create_gym_stripe_account(
        self, 
        db: Session, 
        gym_id: int,
        country: str = "US",
        account_type: str = "express"
    ) -> GymStripeAccount:
        """
        Crear cuenta de Stripe Connect para un gym.
        
        Args:
            db: Sesión de base de datos
            gym_id: ID del gym
            country: País del gym (código ISO)
            account_type: Tipo de cuenta (express, standard, custom)
            
        Returns:
            GymStripeAccount: Cuenta creada o actualizada
        """
        try:
            # Verificar si ya existe cuenta
            existing_account = db.query(GymStripeAccount).filter(
                GymStripeAccount.gym_id == gym_id,
                GymStripeAccount.is_active == True
            ).first()
            
            # 🆕 VERIFICAR SI ES CUENTA PLACEHOLDER
            if existing_account and existing_account.stripe_account_id.startswith("placeholder_"):
                logger.info(f"Actualizando cuenta placeholder para gym {gym_id}")
                # Continuar para crear cuenta real y actualizar el registro
            elif existing_account:
                logger.info(f"Gym {gym_id} ya tiene cuenta de Stripe: {existing_account.stripe_account_id}")
                return existing_account
            
            # Obtener información del gym
            gym = db.query(Gym).filter(Gym.id == gym_id).first()
            if not gym:
                raise ValueError(f"Gym {gym_id} no encontrado")
            
            # Crear cuenta en Stripe
            account = stripe.Account.create(
                type=account_type,
                country=country,
                email=gym.email or "user@example.com",  # Usar email del gym o placeholder
                business_profile={
                    "name": gym.name,
                    "url": gym.website if hasattr(gym, 'website') else None,
                    "mcc": "7991"  # Physical Fitness Facilities
                },
                metadata={
                    "gym_id": str(gym_id),
                    "gym_name": gym.name,
                    "platform": "gymapi"
                }
            )
            
            # 🆕 ACTUALIZAR CUENTA EXISTENTE O CREAR NUEVA
            if existing_account:
                # Actualizar cuenta placeholder
                existing_account.stripe_account_id = account.id
                existing_account.account_type = account_type
                existing_account.country = country
                existing_account.default_currency = account.default_currency.upper()
                existing_account.onboarding_completed = False
                existing_account.charges_enabled = False
                existing_account.payouts_enabled = False
                existing_account.details_submitted = False
                existing_account.is_active = True
                existing_account.updated_at = datetime.utcnow()
                
                db.commit()
                db.refresh(existing_account)
                gym_stripe_account = existing_account
                
                logger.info(f"Cuenta placeholder actualizada para gym {gym_id}: {account.id}")
            else:
                # Crear nueva cuenta
                gym_stripe_account = GymStripeAccount(
                    gym_id=gym_id,
                    stripe_account_id=account.id,
                    account_type=account_type,
                    country=country,
                    default_currency=account.default_currency.upper()
                )
                db.add(gym_stripe_account)
                db.commit()
                db.refresh(gym_stripe_account)
                
                logger.info(f"Nueva cuenta de Stripe creada para gym {gym_id}: {account.id}")
            
            return gym_stripe_account
            
        except stripe.error.StripeError as e:
            logger.error(f"Error de Stripe al crear cuenta para gym {gym_id}: {str(e)}")
            raise ValueError(f"Error al crear cuenta de Stripe: {str(e)}")
        except Exception as e:
            logger.error(f"Error inesperado al crear cuenta de Stripe para gym {gym_id}: {str(e)}")
            raise
    
    async def create_onboarding_link(
        self, 
        db: Session, 
        gym_id: int,
        refresh_url: Optional[str] = None,
        return_url: Optional[str] = None
    ) -> str:
        """
        Crear link de onboarding para que el gym complete su configuración.
        
        Args:
            db: Sesión de base de datos
            gym_id: ID del gym
            refresh_url: URL de refresh (opcional)
            return_url: URL de retorno (opcional)
            
        Returns:
            str: URL de onboarding
        """
        try:
            # Obtener cuenta del gym
            gym_account = db.query(GymStripeAccount).filter(
                GymStripeAccount.gym_id == gym_id,
                GymStripeAccount.is_active == True
            ).first()
            
            if not gym_account:
                raise ValueError(f"Gym {gym_id} no tiene cuenta de Stripe")
            
            # URLs por defecto
            base_url = settings.FRONTEND_URL or settings.BASE_URL
            refresh_url = refresh_url or f"{base_url}/admin/stripe/reauth"
            return_url = return_url or f"{base_url}/admin/stripe/return"
            
            # Crear link de onboarding
            account_link = stripe.AccountLink.create(
                account=gym_account.stripe_account_id,
                refresh_url=refresh_url,
                return_url=return_url,
                type="account_onboarding"
            )
            
            # Actualizar información en BD
            gym_account.onboarding_url = account_link.url
            gym_account.onboarding_expires_at = datetime.utcnow() + timedelta(hours=1)  # Expira en 1 hora
            db.commit()
            
            logger.info(f"Link de onboarding creado para gym {gym_id}")
            return account_link.url
            
        except stripe.error.StripeError as e:
            logger.error(f"Error de Stripe al crear link de onboarding para gym {gym_id}: {str(e)}")
            raise ValueError(f"Error al crear link de onboarding: {str(e)}")
        except Exception as e:
            logger.error(f"Error inesperado al crear link de onboarding para gym {gym_id}: {str(e)}")
            raise
    
    async def update_gym_account_status(self, db: Session, gym_id: int) -> GymStripeAccount:
        """
        Actualizar el estado de la cuenta de Stripe del gym.
        
        Args:
            db: Sesión de base de datos
            gym_id: ID del gym
            
        Returns:
            GymStripeAccount: Cuenta actualizada
        """
        try:
            # Obtener cuenta del gym
            gym_account = db.query(GymStripeAccount).filter(
                GymStripeAccount.gym_id == gym_id,
                GymStripeAccount.is_active == True
            ).first()
            
            if not gym_account:
                raise ValueError(f"Gym {gym_id} no tiene cuenta de Stripe")
            
            # Obtener información actualizada de Stripe
            account = stripe.Account.retrieve(gym_account.stripe_account_id)
            
            # Actualizar estado en BD
            gym_account.charges_enabled = account.charges_enabled
            gym_account.payouts_enabled = account.payouts_enabled
            gym_account.details_submitted = account.details_submitted
            gym_account.onboarding_completed = (
                account.charges_enabled and 
                account.payouts_enabled and 
                account.details_submitted
            )
            gym_account.updated_at = datetime.utcnow()
            
            db.commit()
            db.refresh(gym_account)
            
            logger.info(f"Estado de cuenta actualizado para gym {gym_id}: onboarding_completed={gym_account.onboarding_completed}")
            return gym_account
            
        except stripe.error.StripeError as e:
            logger.error(f"Error de Stripe al actualizar estado de gym {gym_id}: {str(e)}")
            raise ValueError(f"Error al actualizar estado de cuenta: {str(e)}")
        except Exception as e:
            logger.error(f"Error inesperado al actualizar estado de gym {gym_id}: {str(e)}")
            raise
    
    # === GESTIÓN DE CUSTOMERS (SOLUCIÓN A DUPLICACIÓN) ===
    
    async def get_or_create_customer_for_user_gym(
        self, 
        db: Session, 
        user_id: int, 
        gym_id: int
    ) -> str:
        """
        Obtener o crear customer de Stripe para un usuario en un gym específico.
        
        Esta función resuelve el problema de duplicación:
        - Busca primero en la tabla de vinculación
        - Si no existe, crea un nuevo customer
        - Evita duplicados dentro del mismo gym
        
        Args:
            db: Sesión de base de datos
            user_id: ID del usuario
            gym_id: ID del gym
            
        Returns:
            str: ID del customer en Stripe
        """
        try:
            # 1. Buscar vinculación existente
            stripe_profile = db.query(UserGymStripeProfile).filter(
                UserGymStripeProfile.user_id == user_id,
                UserGymStripeProfile.gym_id == gym_id,
                UserGymStripeProfile.is_active == True
            ).first()
            
            if stripe_profile:
                logger.info(f"Customer existente encontrado: {stripe_profile.stripe_customer_id} para user {user_id} en gym {gym_id}")
                return stripe_profile.stripe_customer_id
            
            # 2. Obtener información necesaria
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError(f"Usuario {user_id} no encontrado")
            
            gym_account = db.query(GymStripeAccount).filter(
                GymStripeAccount.gym_id == gym_id,
                GymStripeAccount.is_active == True
            ).first()
            
            if not gym_account:
                raise ValueError(f"Gym {gym_id} no tiene cuenta de Stripe configurada")
            
            # 3. Crear customer en la cuenta del gym
            customer = stripe.Customer.create(
                email=user.email,
                name=f"{user.first_name} {user.last_name}".strip(),
                metadata={
                    "internal_user_id": str(user_id),
                    "gym_id": str(gym_id),
                    "platform": "gymapi"
                },
                stripe_account=gym_account.stripe_account_id  # Crear en la cuenta del gym
            )
            
            # 4. Guardar vinculación en BD local
            stripe_profile = UserGymStripeProfile(
                user_id=user_id,
                gym_id=gym_id,
                stripe_customer_id=customer.id,
                stripe_account_id=gym_account.stripe_account_id,
                email=user.email,
                customer_created_at=datetime.utcnow(),
                last_sync_at=datetime.utcnow()
            )
            db.add(stripe_profile)
            db.commit()
            db.refresh(stripe_profile)
            
            logger.info(f"Nuevo customer creado: {customer.id} para user {user_id} en gym {gym_id}")
            return customer.id
            
        except stripe.error.StripeError as e:
            logger.error(f"Error de Stripe al crear customer para user {user_id} en gym {gym_id}: {str(e)}")
            raise ValueError(f"Error al crear customer: {str(e)}")
        except Exception as e:
            logger.error(f"Error inesperado al crear customer para user {user_id} en gym {gym_id}: {str(e)}")
            raise
    
    # 🆕 MÉTODO PARA MANEJAR SUSCRIPCIONES
    async def update_subscription_for_user_gym(
        self,
        db: Session,
        user_id: int,
        gym_id: int,
        subscription_id: Optional[str] = None
    ) -> UserGymStripeProfile:
        """
        Actualizar subscription_id en el perfil de Stripe del usuario.
        
        Args:
            db: Sesión de base de datos
            user_id: ID del usuario
            gym_id: ID del gym
            subscription_id: ID de la suscripción (None para limpiar)
            
        Returns:
            UserGymStripeProfile: Perfil actualizado
        """
        try:
            # Buscar perfil existente
            stripe_profile = db.query(UserGymStripeProfile).filter(
                UserGymStripeProfile.user_id == user_id,
                UserGymStripeProfile.gym_id == gym_id,
                UserGymStripeProfile.is_active == True
            ).first()
            
            if not stripe_profile:
                raise ValueError(f"No se encontró perfil de Stripe para user {user_id} en gym {gym_id}")
            
            # Actualizar subscription_id
            old_subscription_id = stripe_profile.stripe_subscription_id
            stripe_profile.stripe_subscription_id = subscription_id
            stripe_profile.last_sync_at = datetime.utcnow()
            
            db.commit()
            db.refresh(stripe_profile)
            
            logger.info(f"Subscription actualizada para user {user_id} en gym {gym_id}: {old_subscription_id} -> {subscription_id}")
            return stripe_profile
            
        except Exception as e:
            logger.error(f"Error actualizando subscription para user {user_id} en gym {gym_id}: {str(e)}")
            raise
    
    async def get_subscription_for_user_gym(
        self,
        db: Session,
        user_id: int,
        gym_id: int
    ) -> Optional[str]:
        """
        Obtener subscription_id para un usuario en un gym específico.
        
        Args:
            db: Sesión de base de datos
            user_id: ID del usuario
            gym_id: ID del gym
            
        Returns:
            Optional[str]: ID de la suscripción o None si no existe
        """
        try:
            stripe_profile = db.query(UserGymStripeProfile).filter(
                UserGymStripeProfile.user_id == user_id,
                UserGymStripeProfile.gym_id == gym_id,
                UserGymStripeProfile.is_active == True
            ).first()
            
            return stripe_profile.stripe_subscription_id if stripe_profile else None
            
        except Exception as e:
            logger.error(f"Error obteniendo subscription para user {user_id} en gym {gym_id}: {str(e)}")
            return None
    
    async def find_profile_by_subscription_id(
        self,
        db: Session,
        subscription_id: str
    ) -> Optional[UserGymStripeProfile]:
        """
        Buscar perfil de Stripe por subscription_id.
        
        Args:
            db: Sesión de base de datos
            subscription_id: ID de la suscripción
            
        Returns:
            Optional[UserGymStripeProfile]: Perfil encontrado o None
        """
        try:
            return db.query(UserGymStripeProfile).filter(
                UserGymStripeProfile.stripe_subscription_id == subscription_id,
                UserGymStripeProfile.is_active == True
            ).first()
            
        except Exception as e:
            logger.error(f"Error buscando perfil por subscription {subscription_id}: {str(e)}")
            return None
    
    async def sync_customer_with_stripe(
        self, 
        db: Session, 
        user_id: int, 
        gym_id: int
    ) -> UserGymStripeProfile:
        """
        Sincronizar información del customer con Stripe.
        
        Args:
            db: Sesión de base de datos
            user_id: ID del usuario
            gym_id: ID del gym
            
        Returns:
            UserGymStripeProfile: Perfil actualizado
        """
        try:
            # Obtener vinculación
            stripe_profile = db.query(UserGymStripeProfile).filter(
                UserGymStripeProfile.user_id == user_id,
                UserGymStripeProfile.gym_id == gym_id,
                UserGymStripeProfile.is_active == True
            ).first()
            
            if not stripe_profile:
                raise ValueError(f"No hay vinculación para user {user_id} en gym {gym_id}")
            
            # Obtener información de Stripe
            customer = stripe.Customer.retrieve(
                stripe_profile.stripe_customer_id,
                stripe_account=stripe_profile.stripe_account_id
            )
            
            # Actualizar información local
            stripe_profile.email = customer.email
            stripe_profile.last_sync_at = datetime.utcnow()
            
            db.commit()
            db.refresh(stripe_profile)
            
            logger.info(f"Customer {stripe_profile.stripe_customer_id} sincronizado para user {user_id} en gym {gym_id}")
            return stripe_profile
            
        except stripe.error.StripeError as e:
            logger.error(f"Error de Stripe al sincronizar customer para user {user_id} en gym {gym_id}: {str(e)}")
            raise ValueError(f"Error al sincronizar customer: {str(e)}")
        except Exception as e:
            logger.error(f"Error inesperado al sincronizar customer para user {user_id} en gym {gym_id}: {str(e)}")
            raise
    
    # === MÉTODOS DE UTILIDAD ===
    
    def get_gym_stripe_account(self, db: Session, gym_id: int) -> Optional[GymStripeAccount]:
        """Obtener cuenta de Stripe de un gym"""
        return db.query(GymStripeAccount).filter(
            GymStripeAccount.gym_id == gym_id,
            GymStripeAccount.is_active == True
        ).first()
    
    def get_user_stripe_profile(
        self, 
        db: Session, 
        user_id: int, 
        gym_id: int
    ) -> Optional[UserGymStripeProfile]:
        """Obtener perfil de Stripe de un usuario en un gym"""
        return db.query(UserGymStripeProfile).filter(
            UserGymStripeProfile.user_id == user_id,
            UserGymStripeProfile.gym_id == gym_id,
            UserGymStripeProfile.is_active == True
        ).first()


# Instancia del servicio
stripe_connect_service = StripeConnectService() 