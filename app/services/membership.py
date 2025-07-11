from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.membership import MembershipPlan
from app.models.user_gym import UserGym, GymRoleType
from app.models.gym import Gym
from app.schemas.membership import (
    MembershipPlanCreate, 
    MembershipPlanUpdate,
    UserMembershipUpdate,
    MembershipStatus,
    MembershipSummary
)

logger = logging.getLogger(__name__)


class MembershipService:
    """Servicio para gestionar planes de membresía y membresías de usuarios"""

    # === Gestión de Planes de Membresía ===

    async def create_membership_plan(
        self, 
        db: Session, 
        gym_id: int,
        plan_data: MembershipPlanCreate
    ) -> MembershipPlan:
        """Crear un nuevo plan de membresía"""
        
        # Verificar que el gimnasio existe
        gym = db.query(Gym).filter(Gym.id == gym_id).first()
        if not gym:
            raise ValueError(f"Gimnasio con ID {gym_id} no encontrado")
        
        # Crear el plan con gym_id del middleware
        plan_dict = plan_data.model_dump()
        plan_dict['gym_id'] = gym_id
        db_plan = MembershipPlan(**plan_dict)
        db.add(db_plan)
        db.commit()
        db.refresh(db_plan)
        
        logger.info(f"Plan de membresía creado: {db_plan.name} (ID: {db_plan.id}) para gym {gym_id}")
        
        # 🆕 SINCRONIZACIÓN AUTOMÁTICA CON STRIPE
        try:
            # Importación lazy para evitar circular imports
            from app.services.stripe_service import get_stripe_service
            stripe_service = get_stripe_service()
            
            # Crear producto y precio en Stripe automáticamente
            stripe_result = await stripe_service.create_stripe_product_for_plan(db, db_plan)
            logger.info(f"Plan {db_plan.id} sincronizado con Stripe: {stripe_result}")
            
        except Exception as stripe_error:
            logger.error(f"Error al sincronizar plan {db_plan.id} con Stripe: {str(stripe_error)}")
            # No fallamos la creación del plan por un error de Stripe
            # El plan se puede sincronizar manualmente después
        
        return db_plan

    def get_membership_plans(
        self, 
        db: Session, 
        gym_id: int, 
        active_only: bool = True,
        skip: int = 0, 
        limit: int = 100
    ) -> List[MembershipPlan]:
        """Obtener planes de membresía de un gimnasio"""
        
        query = db.query(MembershipPlan).filter(MembershipPlan.gym_id == gym_id)
        
        if active_only:
            query = query.filter(MembershipPlan.is_active == True)
        
        return query.offset(skip).limit(limit).all()

    def get_membership_plan(self, db: Session, plan_id: int) -> Optional[MembershipPlan]:
        """Obtener un plan específico"""
        return db.query(MembershipPlan).filter(MembershipPlan.id == plan_id).first()

    async def update_membership_plan(
        self, 
        db: Session, 
        plan_id: int, 
        plan_update: MembershipPlanUpdate
    ) -> Optional[MembershipPlan]:
        """Actualizar un plan de membresía"""
        
        db_plan = self.get_membership_plan(db, plan_id)
        if not db_plan:
            return None
        
        update_data = plan_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_plan, field, value)
        
        db_plan.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(db_plan)
        
        logger.info(f"Plan de membresía actualizado: {db_plan.id}")
        
        # 🆕 SINCRONIZACIÓN AUTOMÁTICA CON STRIPE
        try:
            # Importación lazy para evitar circular imports
            from app.services.stripe_service import get_stripe_service
            stripe_service = get_stripe_service()
            
            # Actualizar producto en Stripe
            success = await stripe_service.update_stripe_product_for_plan(db, db_plan)
            if success:
                logger.info(f"Plan {db_plan.id} actualizado en Stripe")
            else:
                logger.warning(f"Falló la actualización en Stripe para plan {db_plan.id}")
                
        except Exception as stripe_error:
            logger.error(f"Error al actualizar plan {db_plan.id} en Stripe: {str(stripe_error)}")
            # No fallamos la actualización por un error de Stripe
        
        return db_plan

    async def delete_membership_plan(self, db: Session, plan_id: int) -> bool:
        """Eliminar (desactivar) un plan de membresía"""
        
        db_plan = self.get_membership_plan(db, plan_id)
        if not db_plan:
            return False
        
        # En lugar de eliminar, desactivamos
        db_plan.is_active = False
        db_plan.updated_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"Plan de membresía desactivado: {plan_id}")
        
        # 🆕 SINCRONIZACIÓN AUTOMÁTICA CON STRIPE
        try:
            # Importación lazy para evitar circular imports
            from app.services.stripe_service import get_stripe_service
            stripe_service = get_stripe_service()
            
            # Desactivar producto en Stripe
            success = await stripe_service.deactivate_stripe_product_for_plan(db_plan)
            if success:
                logger.info(f"Plan {plan_id} desactivado en Stripe")
            else:
                logger.warning(f"Falló la desactivación en Stripe para plan {plan_id}")
                
        except Exception as stripe_error:
            logger.error(f"Error al desactivar plan {plan_id} en Stripe: {str(stripe_error)}")
            # No fallamos la desactivación por un error de Stripe
        
        return True

    # === Gestión de Membresías de Usuario ===

    def get_user_membership(
        self, 
        db: Session, 
        user_id: int, 
        gym_id: int
    ) -> Optional[UserGym]:
        """Obtener membresía de un usuario en un gimnasio específico"""
        
        return db.query(UserGym).filter(
            UserGym.user_id == user_id,
            UserGym.gym_id == gym_id
        ).first()

    def get_membership_status(
        self, 
        db: Session, 
        user_id: int, 
        gym_id: int
    ) -> MembershipStatus:
        """Obtener estado detallado de membresía"""
        
        user_gym = self.get_user_membership(db, user_id, gym_id)
        gym = db.query(Gym).filter(Gym.id == gym_id).first()
        
        if not user_gym or not gym:
            return MembershipStatus(
                user_id=user_id,
                gym_id=gym_id,
                gym_name=gym.name if gym else "Desconocido",
                is_active=False,
                membership_type="none",
                can_access=False
            )
        
        # Verificar si está expirada
        is_expired = False
        days_remaining = None
        
        if user_gym.membership_expires_at:
            now = datetime.now()
            is_expired = user_gym.membership_expires_at < now
            if not is_expired:
                days_remaining = (user_gym.membership_expires_at - now).days
        
        can_access = user_gym.is_active and not is_expired
        
        return MembershipStatus(
            user_id=user_id,
            gym_id=gym_id,
            gym_name=gym.name,
            is_active=user_gym.is_active,
            membership_type=user_gym.membership_type,
            expires_at=user_gym.membership_expires_at,
            days_remaining=days_remaining,
            can_access=can_access
        )

    def update_user_membership(
        self, 
        db: Session, 
        user_id: int, 
        gym_id: int, 
        membership_update: UserMembershipUpdate
    ) -> Optional[UserGym]:
        """Actualizar membresía de usuario"""
        
        user_gym = self.get_user_membership(db, user_id, gym_id)
        if not user_gym:
            return None
        
        update_data = membership_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user_gym, field, value)
        
        db.commit()
        db.refresh(user_gym)
        
        logger.info(f"Membresía actualizada para user {user_id} en gym {gym_id}")
        return user_gym

    async def activate_membership(
        self, 
        db: Session, 
        user_id: int, 
        gym_id: int,
        plan_id: Optional[int] = None,
        membership_type: str = "paid",
        duration_days: Optional[int] = None,
        # 🆕 PARÁMETROS OBSOLETOS - Ya no se usan
        stripe_customer_id: Optional[str] = None,
        stripe_subscription_id: Optional[str] = None
    ) -> UserGym:
        """
        Activar o crear una membresía de usuario.
        
        ⚠️ NOTA: stripe_customer_id y stripe_subscription_id ya no se guardan en UserGym.
        Esta información se maneja a través de UserGymStripeProfile en la nueva arquitectura.
        """
        
        # 🆕 ADVERTENCIA SI SE USAN PARÁMETROS OBSOLETOS
        if stripe_customer_id or stripe_subscription_id:
            logger.warning(f"⚠️ Parámetros obsoletos en activate_membership para user {user_id}")
            logger.warning("⚠️ stripe_customer_id y stripe_subscription_id ya no se guardan en UserGym")
            logger.warning("⚠️ Esta información se maneja automáticamente en UserGymStripeProfile")
        
        # Obtener duración desde el plan si no se especifica
        if plan_id and not duration_days:
            plan = self.get_membership_plan(db, plan_id)
            if plan:
                duration_days = plan.duration_days
                logger.info(f"Usando duración del plan {plan_id}: {duration_days} días")
            else:
                logger.warning(f"Plan {plan_id} no encontrado, usando duración por defecto")
                duration_days = 30
        elif not duration_days:
            duration_days = 30
        
        user_gym = self.get_user_membership(db, user_id, gym_id)
        
        if not user_gym:
            # Crear nueva relación usuario-gym con membresía
            user_gym = UserGym(
                user_id=user_id,
                gym_id=gym_id,
                role=GymRoleType.MEMBER,
                is_active=True,
                membership_type=membership_type,
                membership_expires_at=datetime.now() + timedelta(days=duration_days),
                # 🆕 NO GUARDAR DATOS DE STRIPE EN USERGYM
                # stripe_customer_id=stripe_customer_id,
                # stripe_subscription_id=stripe_subscription_id,
                last_payment_at=datetime.now(),
                notes=f"Membresía activada - {datetime.now().isoformat()}"
            )
            db.add(user_gym)
        else:
            # Actualizar membresía existente
            user_gym.is_active = True
            user_gym.membership_type = membership_type
            user_gym.membership_expires_at = datetime.now() + timedelta(days=duration_days)
            # 🆕 NO ACTUALIZAR DATOS DE STRIPE EN USERGYM
            # user_gym.stripe_customer_id = stripe_customer_id or user_gym.stripe_customer_id
            # user_gym.stripe_subscription_id = stripe_subscription_id or user_gym.stripe_subscription_id
            user_gym.last_payment_at = datetime.now()
            user_gym.notes = f"Membresía renovada - {datetime.now().isoformat()}"
        
        db.commit()
        db.refresh(user_gym)
        
        logger.info(f"Membresía activada para user {user_id} en gym {gym_id} por {duration_days} días")
        
        # 🆕 VERIFICAR QUE EXISTE PERFIL DE STRIPE SI ES PAGO
        if membership_type == "paid":
            try:
                from app.services.stripe_connect_service import stripe_connect_service
                stripe_profile = stripe_connect_service.get_user_stripe_profile(db, user_id, gym_id)
                if stripe_profile:
                    logger.info(f"✅ Perfil de Stripe encontrado para user {user_id} en gym {gym_id}")
                else:
                    logger.warning(f"⚠️ No se encontró perfil de Stripe para user {user_id} en gym {gym_id}")
                    logger.warning("⚠️ Esto podría indicar un problema en el flujo de pago")
            except Exception as e:
                logger.error(f"Error verificando perfil de Stripe: {str(e)}")
        
        return user_gym

    def deactivate_membership(
        self, 
        db: Session, 
        user_id: int, 
        gym_id: int,
        reason: str = "expired"
    ) -> bool:
        """Desactivar membresía de usuario"""
        
        user_gym = self.get_user_membership(db, user_id, gym_id)
        if not user_gym:
            return False
        
        user_gym.is_active = False
        user_gym.notes = f"Desactivada: {reason} - {datetime.now().isoformat()}"
        
        db.commit()
        
        logger.info(f"Membresía desactivada para user {user_id} en gym {gym_id}. Razón: {reason}")
        return True

    # === Funciones de Utilidad ===

    async def sync_plan_with_stripe_manual(
        self, 
        db: Session, 
        plan_id: int
    ) -> bool:
        """Sincronizar manualmente un plan específico con Stripe"""
        try:
            # Importación lazy para evitar circular imports
            from app.services.stripe_service import get_stripe_service
            stripe_service = get_stripe_service()
            
            return await stripe_service.sync_plan_with_stripe(db, plan_id)
            
        except Exception as e:
            logger.error(f"Error en sincronización manual del plan {plan_id}: {str(e)}")
            return False

    async def sync_all_plans_with_stripe(
        self, 
        db: Session, 
        gym_id: int
    ) -> Dict[str, Any]:
        """Sincronizar todos los planes de un gimnasio con Stripe"""
        try:
            # Importación lazy para evitar circular imports
            from app.services.stripe_service import get_stripe_service
            stripe_service = get_stripe_service()
            
            plans = self.get_membership_plans(db, gym_id, active_only=False)
            results = {
                'total': len(plans),
                'synced': 0,
                'failed': 0,
                'details': []
            }
            
            for plan in plans:
                try:
                    success = await stripe_service.sync_plan_with_stripe(db, plan.id)
                    if success:
                        results['synced'] += 1
                        results['details'].append({
                            'plan_id': plan.id,
                            'name': plan.name,
                            'status': 'synced'
                        })
                    else:
                        results['failed'] += 1
                        results['details'].append({
                            'plan_id': plan.id,
                            'name': plan.name,
                            'status': 'failed'
                        })
                except Exception as e:
                    results['failed'] += 1
                    results['details'].append({
                        'plan_id': plan.id,
                        'name': plan.name,
                        'status': 'error',
                        'error': str(e)
                    })
            
            logger.info(f"Sincronización masiva gym {gym_id}: {results['synced']}/{results['total']} exitosos")
            return results
            
        except Exception as e:
            logger.error(f"Error en sincronización masiva gym {gym_id}: {str(e)}")
            return {
                'total': 0,
                'synced': 0,
                'failed': 0,
                'error': str(e)
            }

    def expire_memberships(self, db: Session) -> int:
        """Expirar membresías vencidas (para tarea programada)"""
        
        now = datetime.now()
        expired_memberships = db.query(UserGym).filter(
            UserGym.is_active == True,
            UserGym.membership_expires_at < now,
            UserGym.membership_type.in_(["paid", "trial"])
        ).all()
        
        count = 0
        for membership in expired_memberships:
            membership.is_active = False
            membership.notes = f"Expirada automáticamente: {now.isoformat()}"
            count += 1
        
        if count > 0:
            db.commit()
            logger.info(f"Expiradas {count} membresías automáticamente")
        
        return count

    def get_gym_membership_summary(
        self, 
        db: Session, 
        gym_id: int
    ) -> MembershipSummary:
        """Obtener resumen de membresías para un gimnasio"""
        
        # Consultas básicas
        total_members = db.query(UserGym).filter(UserGym.gym_id == gym_id).count()
        
        active_members = db.query(UserGym).filter(
            UserGym.gym_id == gym_id,
            UserGym.is_active == True
        ).count()
        
        paid_members = db.query(UserGym).filter(
            UserGym.gym_id == gym_id,
            UserGym.membership_type == "paid",
            UserGym.is_active == True
        ).count()
        
        trial_members = db.query(UserGym).filter(
            UserGym.gym_id == gym_id,
            UserGym.membership_type == "trial",
            UserGym.is_active == True
        ).count()
        
        expired_members = db.query(UserGym).filter(
            UserGym.gym_id == gym_id,
            UserGym.is_active == False
        ).count()
        
        # Miembros nuevos este mes
        start_of_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        new_members_this_month = db.query(UserGym).filter(
            UserGym.gym_id == gym_id,
            UserGym.created_at >= start_of_month
        ).count()
        
        return MembershipSummary(
            total_members=total_members,
            active_members=active_members,
            paid_members=paid_members,
            trial_members=trial_members,
            expired_members=expired_members,
            revenue_current_month=0.0,  # Se calculará con Stripe en Fase 2
            new_members_this_month=new_members_this_month
        )


# Instancia global del servicio
membership_service = MembershipService() 