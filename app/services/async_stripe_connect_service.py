"""
AsyncStripeConnectService - Servicio async para Stripe Connect y vinculación de usuarios.

Este módulo resuelve el problema de duplicación de customers en entorno multitenant,
gestionando cuentas Stripe Connect por gimnasio y customers sin duplicados.

Migrado en FASE 3 de la conversión sync → async.
"""

import stripe
from typing import Optional, Dict, Any
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.config import get_settings
from app.models.stripe_profile import UserGymStripeProfile, GymStripeAccount
from app.models.user import User
from app.models.gym import Gym
import logging

logger = logging.getLogger("async_stripe_connect_service")
settings = get_settings()

# Configurar Stripe (sync - no hay cliente async oficial)
stripe.api_key = settings.STRIPE_SECRET_KEY


class AsyncStripeConnectService:
    """
    Servicio async para manejar Stripe Connect y vinculación de usuarios.

    Todos los métodos de BD son async. Stripe API es sync (sin cliente async oficial).

    Funcionalidades principales:
    - Crear cuentas de Stripe Connect para gyms
    - Gestionar customers sin duplicados (1 customer por user-gym)
    - Onboarding de gyms con Account Links
    - Sincronización de datos y estado
    - Gestión de suscripciones por user-gym

    Métodos principales:
    - create_gym_stripe_account() - Crea cuenta Connect para gym
    - create_onboarding_link() - Link de onboarding para gym
    - get_or_create_customer_for_user_gym() - Customer único por user-gym
    - update_subscription_for_user_gym() - Actualiza subscription_id
    """

    # === GESTIÓN DE CUENTAS DE GYM ===

    async def create_gym_stripe_account(
        self,
        db: AsyncSession,
        gym_id: int,
        country: str = "US",
        account_type: str = "express"
    ) -> GymStripeAccount:
        """
        Crear cuenta de Stripe Connect para un gym.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gym
            country: País del gym (código ISO, ej: "US", "MX")
            account_type: Tipo de cuenta (express, standard, custom)

        Returns:
            GymStripeAccount: Cuenta creada o actualizada

        Raises:
            ValueError: Si gym no existe o hay error de Stripe

        Note:
            - Detecta y actualiza cuentas placeholder (placeholder_*)
            - Reutiliza cuenta inactiva si existe
            - Stripe API es sync (no hay cliente async oficial)
            - MCC 7991: Physical Fitness Facilities
        """
        try:
            # Verificar si ya existe cuenta (activa o inactiva)
            result = await db.execute(
                select(GymStripeAccount).where(
                    GymStripeAccount.gym_id == gym_id
                )
            )
            existing_account = result.scalar_one_or_none()

            # VERIFICAR SI ES CUENTA PLACEHOLDER
            if existing_account and existing_account.stripe_account_id.startswith("placeholder_"):
                logger.info(f"Actualizando cuenta placeholder para gym {gym_id}: {existing_account.stripe_account_id}")
                # Continuar para crear cuenta real y actualizar el registro
            elif existing_account and existing_account.is_active:
                logger.info(f"Gym {gym_id} ya tiene cuenta de Stripe activa: {existing_account.stripe_account_id}")
                return existing_account
            elif existing_account:
                logger.info(f"Gym {gym_id} tiene cuenta inactiva: {existing_account.stripe_account_id}, is_active={existing_account.is_active}")
                # Continuar para reactivar la cuenta

            # Obtener información del gym
            result = await db.execute(
                select(Gym).where(Gym.id == gym_id)
            )
            gym = result.scalar_one_or_none()
            if not gym:
                raise ValueError(f"Gym {gym_id} no encontrado")

            # Crear cuenta en Stripe (sync - no hay cliente async)
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

            # ACTUALIZAR CUENTA EXISTENTE O CREAR NUEVA
            if existing_account:
                # Actualizar cuenta existente (placeholder o inactiva)
                old_account_id = existing_account.stripe_account_id
                existing_account.stripe_account_id = account.id
                existing_account.account_type = account_type
                existing_account.country = country
                existing_account.default_currency = account.default_currency.upper()
                existing_account.onboarding_completed = False
                existing_account.charges_enabled = False
                existing_account.payouts_enabled = False
                existing_account.details_submitted = False
                existing_account.is_active = True
                existing_account.updated_at = datetime.now(timezone.utc)

                await db.commit()
                await db.refresh(existing_account)
                gym_stripe_account = existing_account

                logger.info(f"Cuenta actualizada para gym {gym_id}: {old_account_id} -> {account.id}")
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
                await db.commit()
                await db.refresh(gym_stripe_account)

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
        db: AsyncSession,
        gym_id: int,
        refresh_url: Optional[str] = None,
        return_url: Optional[str] = None
    ) -> str:
        """
        Crear link de onboarding para que el gym complete su configuración.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gym
            refresh_url: URL de refresh (opcional, default: {base}/admin/stripe/reauth)
            return_url: URL de retorno (opcional, default: {base}/admin/stripe/return)

        Returns:
            str: URL de onboarding de Stripe

        Raises:
            ValueError: Si gym no tiene cuenta de Stripe

        Note:
            - Link expira en 1 hora (guardado en onboarding_expires_at)
            - Usa account_onboarding type
        """
        try:
            # Obtener cuenta del gym
            result = await db.execute(
                select(GymStripeAccount).where(
                    GymStripeAccount.gym_id == gym_id,
                    GymStripeAccount.is_active == True
                )
            )
            gym_account = result.scalar_one_or_none()

            if not gym_account:
                raise ValueError(f"Gym {gym_id} no tiene cuenta de Stripe")

            # URLs por defecto
            base_url = settings.FRONTEND_URL or settings.BASE_URL
            refresh_url = refresh_url or f"{base_url}/admin/stripe/reauth"
            return_url = return_url or f"{base_url}/admin/stripe/return"

            # Crear link de onboarding (sync)
            account_link = stripe.AccountLink.create(
                account=gym_account.stripe_account_id,
                refresh_url=refresh_url,
                return_url=return_url,
                type="account_onboarding"
            )

            # Actualizar información en BD
            gym_account.onboarding_url = account_link.url
            gym_account.onboarding_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)  # Expira en 1 hora
            await db.commit()

            logger.info(f"Link de onboarding creado para gym {gym_id}")
            return account_link.url

        except stripe.error.StripeError as e:
            logger.error(f"Error de Stripe al crear link de onboarding para gym {gym_id}: {str(e)}")
            raise ValueError(f"Error al crear link de onboarding: {str(e)}")
        except Exception as e:
            logger.error(f"Error inesperado al crear link de onboarding para gym {gym_id}: {str(e)}")
            raise

    async def update_gym_account_status(self, db: AsyncSession, gym_id: int) -> GymStripeAccount:
        """
        Actualizar el estado de la cuenta de Stripe del gym.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gym

        Returns:
            GymStripeAccount: Cuenta actualizada con estado de Stripe

        Raises:
            ValueError: Si gym no tiene cuenta de Stripe

        Note:
            - Sincroniza charges_enabled, payouts_enabled, details_submitted
            - onboarding_completed = charges AND payouts AND details_submitted
        """
        try:
            # Obtener cuenta del gym
            result = await db.execute(
                select(GymStripeAccount).where(
                    GymStripeAccount.gym_id == gym_id,
                    GymStripeAccount.is_active == True
                )
            )
            gym_account = result.scalar_one_or_none()

            if not gym_account:
                raise ValueError(f"Gym {gym_id} no tiene cuenta de Stripe")

            # Obtener información actualizada de Stripe (sync)
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
            gym_account.updated_at = datetime.now(timezone.utc)

            await db.commit()
            await db.refresh(gym_account)

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
        db: AsyncSession,
        user_id: int,
        gym_id: int
    ) -> str:
        """
        Obtener o crear customer de Stripe para un usuario en un gym específico.

        Esta función resuelve el problema de duplicación:
        - Busca primero en la tabla de vinculación UserGymStripeProfile
        - Si no existe, crea un nuevo customer en la cuenta del gym
        - Evita duplicados dentro del mismo gym (1 customer por user-gym)

        Args:
            db: Sesión async de base de datos
            user_id: ID del usuario
            gym_id: ID del gym

        Returns:
            str: ID del customer en Stripe (ej: "cus_...")

        Raises:
            ValueError: Si usuario o gym no existen, o gym sin cuenta Stripe

        Note:
            - Customer se crea en la cuenta Connect del gym (stripe_account=...)
            - Metadata incluye internal_user_id, gym_id, platform
        """
        try:
            # 1. Buscar vinculación existente
            result = await db.execute(
                select(UserGymStripeProfile).where(
                    UserGymStripeProfile.user_id == user_id,
                    UserGymStripeProfile.gym_id == gym_id,
                    UserGymStripeProfile.is_active == True
                )
            )
            stripe_profile = result.scalar_one_or_none()

            if stripe_profile:
                logger.info(f"Customer existente encontrado: {stripe_profile.stripe_customer_id} para user {user_id} en gym {gym_id}")
                return stripe_profile.stripe_customer_id

            # 2. Obtener información necesaria
            result = await db.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            if not user:
                raise ValueError(f"Usuario {user_id} no encontrado")

            result = await db.execute(
                select(GymStripeAccount).where(
                    GymStripeAccount.gym_id == gym_id,
                    GymStripeAccount.is_active == True
                )
            )
            gym_account = result.scalar_one_or_none()

            if not gym_account:
                raise ValueError(f"Gym {gym_id} no tiene cuenta de Stripe configurada")

            # 3. Crear customer en la cuenta del gym (sync)
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
                customer_created_at=datetime.now(timezone.utc),
                last_sync_at=datetime.now(timezone.utc)
            )
            db.add(stripe_profile)
            await db.commit()
            await db.refresh(stripe_profile)

            logger.info(f"Nuevo customer creado: {customer.id} para user {user_id} en gym {gym_id}")
            return customer.id

        except stripe.error.StripeError as e:
            logger.error(f"Error de Stripe al crear customer para user {user_id} en gym {gym_id}: {str(e)}")
            raise ValueError(f"Error al crear customer: {str(e)}")
        except Exception as e:
            logger.error(f"Error inesperado al crear customer para user {user_id} en gym {gym_id}: {str(e)}")
            raise

    # MÉTODO PARA MANEJAR SUSCRIPCIONES

    async def update_subscription_for_user_gym(
        self,
        db: AsyncSession,
        user_id: int,
        gym_id: int,
        subscription_id: Optional[str] = None
    ) -> UserGymStripeProfile:
        """
        Actualizar subscription_id en el perfil de Stripe del usuario.

        Args:
            db: Sesión async de base de datos
            user_id: ID del usuario
            gym_id: ID del gym
            subscription_id: ID de la suscripción (None para limpiar)

        Returns:
            UserGymStripeProfile: Perfil actualizado

        Raises:
            ValueError: Si no existe perfil de Stripe

        Note:
            - Actualiza last_sync_at automáticamente
            - subscription_id puede ser None para cancelaciones
        """
        try:
            # Buscar perfil existente
            result = await db.execute(
                select(UserGymStripeProfile).where(
                    UserGymStripeProfile.user_id == user_id,
                    UserGymStripeProfile.gym_id == gym_id,
                    UserGymStripeProfile.is_active == True
                )
            )
            stripe_profile = result.scalar_one_or_none()

            if not stripe_profile:
                raise ValueError(f"No se encontró perfil de Stripe para user {user_id} en gym {gym_id}")

            # Actualizar subscription_id
            old_subscription_id = stripe_profile.stripe_subscription_id
            stripe_profile.stripe_subscription_id = subscription_id
            stripe_profile.last_sync_at = datetime.now(timezone.utc)

            await db.commit()
            await db.refresh(stripe_profile)

            logger.info(f"Subscription actualizada para user {user_id} en gym {gym_id}: {old_subscription_id} -> {subscription_id}")
            return stripe_profile

        except Exception as e:
            logger.error(f"Error actualizando subscription para user {user_id} en gym {gym_id}: {str(e)}")
            raise

    async def get_subscription_for_user_gym(
        self,
        db: AsyncSession,
        user_id: int,
        gym_id: int
    ) -> Optional[str]:
        """
        Obtener subscription_id para un usuario en un gym específico.

        Args:
            db: Sesión async de base de datos
            user_id: ID del usuario
            gym_id: ID del gym

        Returns:
            Optional[str]: ID de la suscripción (ej: "sub_...") o None si no existe
        """
        try:
            result = await db.execute(
                select(UserGymStripeProfile).where(
                    UserGymStripeProfile.user_id == user_id,
                    UserGymStripeProfile.gym_id == gym_id,
                    UserGymStripeProfile.is_active == True
                )
            )
            stripe_profile = result.scalar_one_or_none()

            return stripe_profile.stripe_subscription_id if stripe_profile else None

        except Exception as e:
            logger.error(f"Error obteniendo subscription para user {user_id} en gym {gym_id}: {str(e)}")
            return None

    async def find_profile_by_subscription_id(
        self,
        db: AsyncSession,
        subscription_id: str
    ) -> Optional[UserGymStripeProfile]:
        """
        Buscar perfil de Stripe por subscription_id.

        Args:
            db: Sesión async de base de datos
            subscription_id: ID de la suscripción

        Returns:
            Optional[UserGymStripeProfile]: Perfil encontrado o None

        Note:
            Útil para webhooks que solo proporcionan subscription_id.
        """
        try:
            result = await db.execute(
                select(UserGymStripeProfile).where(
                    UserGymStripeProfile.stripe_subscription_id == subscription_id,
                    UserGymStripeProfile.is_active == True
                )
            )
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error(f"Error buscando perfil por subscription {subscription_id}: {str(e)}")
            return None

    async def sync_customer_with_stripe(
        self,
        db: AsyncSession,
        user_id: int,
        gym_id: int
    ) -> UserGymStripeProfile:
        """
        Sincronizar información del customer con Stripe.

        Args:
            db: Sesión async de base de datos
            user_id: ID del usuario
            gym_id: ID del gym

        Returns:
            UserGymStripeProfile: Perfil actualizado con datos de Stripe

        Raises:
            ValueError: Si no hay vinculación o error de Stripe

        Note:
            - Sincroniza email desde Stripe
            - Actualiza last_sync_at
        """
        try:
            # Obtener vinculación
            result = await db.execute(
                select(UserGymStripeProfile).where(
                    UserGymStripeProfile.user_id == user_id,
                    UserGymStripeProfile.gym_id == gym_id,
                    UserGymStripeProfile.is_active == True
                )
            )
            stripe_profile = result.scalar_one_or_none()

            if not stripe_profile:
                raise ValueError(f"No hay vinculación para user {user_id} en gym {gym_id}")

            # Obtener información de Stripe (sync)
            customer = stripe.Customer.retrieve(
                stripe_profile.stripe_customer_id,
                stripe_account=stripe_profile.stripe_account_id
            )

            # Actualizar información local
            stripe_profile.email = customer.email
            stripe_profile.last_sync_at = datetime.now(timezone.utc)

            await db.commit()
            await db.refresh(stripe_profile)

            logger.info(f"Customer {stripe_profile.stripe_customer_id} sincronizado para user {user_id} en gym {gym_id}")
            return stripe_profile

        except stripe.error.StripeError as e:
            logger.error(f"Error de Stripe al sincronizar customer para user {user_id} en gym {gym_id}: {str(e)}")
            raise ValueError(f"Error al sincronizar customer: {str(e)}")
        except Exception as e:
            logger.error(f"Error inesperado al sincronizar customer para user {user_id} en gym {gym_id}: {str(e)}")
            raise

    # === MÉTODOS DE UTILIDAD ===

    async def get_gym_stripe_account(self, db: AsyncSession, gym_id: int) -> Optional[GymStripeAccount]:
        """
        Obtener cuenta de Stripe de un gym.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gym

        Returns:
            Optional[GymStripeAccount]: Cuenta activa o None
        """
        result = await db.execute(
            select(GymStripeAccount).where(
                GymStripeAccount.gym_id == gym_id,
                GymStripeAccount.is_active == True
            )
        )
        return result.scalar_one_or_none()

    async def get_user_stripe_profile(
        self,
        db: AsyncSession,
        user_id: int,
        gym_id: int
    ) -> Optional[UserGymStripeProfile]:
        """
        Obtener perfil de Stripe de un usuario en un gym.

        Args:
            db: Sesión async de base de datos
            user_id: ID del usuario
            gym_id: ID del gym

        Returns:
            Optional[UserGymStripeProfile]: Perfil activo o None
        """
        result = await db.execute(
            select(UserGymStripeProfile).where(
                UserGymStripeProfile.user_id == user_id,
                UserGymStripeProfile.gym_id == gym_id,
                UserGymStripeProfile.is_active == True
            )
        )
        return result.scalar_one_or_none()


# Instancia singleton del servicio async
async_stripe_connect_service = AsyncStripeConnectService()
