#!/usr/bin/env python3
"""
Script para migrar datos existentes de Stripe a la nueva arquitectura.

Este script:
1. Busca registros en user_gyms que tengan stripe_customer_id
2. Crea los perfiles correspondientes en user_gym_stripe_profiles
3. Limpia los campos de Stripe de user_gyms
4. Reporta estadísticas de migración
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.user_gym import UserGym
from app.models.stripe_profile import UserGymStripeProfile, GymStripeAccount
from app.models.user import User
from app.models.gym import Gym
from datetime import datetime
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate_stripe_data():
    """
    Migrar datos existentes de Stripe a la nueva arquitectura.
    """
    db = SessionLocal()
    
    try:
        # Estadísticas
        total_processed = 0
        total_migrated = 0
        total_skipped = 0
        errors = []
        
        logger.info("🚀 Iniciando migración de datos de Stripe...")
        
        # Buscar todos los UserGym con datos de Stripe
        user_gyms_with_stripe = db.query(UserGym).filter(
            UserGym.stripe_customer_id.isnot(None)
        ).all()
        
        logger.info(f"📊 Encontrados {len(user_gyms_with_stripe)} registros con datos de Stripe")
        
        for user_gym in user_gyms_with_stripe:
            total_processed += 1
            
            try:
                # Verificar si ya existe un perfil
                existing_profile = db.query(UserGymStripeProfile).filter(
                    UserGymStripeProfile.user_id == user_gym.user_id,
                    UserGymStripeProfile.gym_id == user_gym.gym_id
                ).first()
                
                if existing_profile:
                    logger.info(f"⏭️  Saltando user {user_gym.user_id} gym {user_gym.gym_id} - ya existe perfil")
                    total_skipped += 1
                    continue
                
                # Obtener información del usuario
                user = db.query(User).filter(User.id == user_gym.user_id).first()
                if not user:
                    logger.error(f"❌ Usuario {user_gym.user_id} no encontrado")
                    errors.append(f"Usuario {user_gym.user_id} no encontrado")
                    continue
                
                # Obtener información del gym
                gym = db.query(Gym).filter(Gym.id == user_gym.gym_id).first()
                if not gym:
                    logger.error(f"❌ Gym {user_gym.gym_id} no encontrado")
                    errors.append(f"Gym {user_gym.gym_id} no encontrado")
                    continue
                
                # Buscar cuenta de Stripe del gym
                gym_account = db.query(GymStripeAccount).filter(
                    GymStripeAccount.gym_id == user_gym.gym_id
                ).first()
                
                if not gym_account:
                    logger.warning(f"⚠️  Gym {user_gym.gym_id} no tiene cuenta de Stripe - creando entrada placeholder")
                    # Crear entrada placeholder para poder migrar los datos
                    gym_account = GymStripeAccount(
                        gym_id=user_gym.gym_id,
                        stripe_account_id=f"placeholder_{user_gym.gym_id}",
                        account_type="express",
                        onboarding_completed=False,
                        charges_enabled=False,
                        payouts_enabled=False,
                        details_submitted=False,
                        country="US",
                        default_currency="USD",
                        is_active=False  # Marcar como inactivo hasta configurar
                    )
                    db.add(gym_account)
                    db.flush()  # Para obtener el ID
                
                # Crear perfil de Stripe
                stripe_profile = UserGymStripeProfile(
                    user_id=user_gym.user_id,
                    gym_id=user_gym.gym_id,
                    stripe_customer_id=user_gym.stripe_customer_id,
                    stripe_account_id=gym_account.stripe_account_id,
                    stripe_subscription_id=user_gym.stripe_subscription_id,
                    email=user.email,
                    customer_created_at=user_gym.created_at,
                    last_sync_at=datetime.utcnow(),
                    is_active=True
                )
                
                db.add(stripe_profile)
                
                # Limpiar campos de Stripe en UserGym
                user_gym.stripe_customer_id = None
                user_gym.stripe_subscription_id = None
                user_gym.notes = f"Migrado a nueva arquitectura Stripe - {datetime.now().isoformat()}"
                
                total_migrated += 1
                logger.info(f"✅ Migrado user {user_gym.user_id} gym {user_gym.gym_id}")
                
            except Exception as e:
                logger.error(f"❌ Error migrando user {user_gym.user_id} gym {user_gym.gym_id}: {str(e)}")
                errors.append(f"user {user_gym.user_id} gym {user_gym.gym_id}: {str(e)}")
                continue
        
        # Confirmar cambios
        db.commit()
        
        # Reportar estadísticas
        logger.info("=" * 60)
        logger.info("📈 RESUMEN DE MIGRACIÓN")
        logger.info("=" * 60)
        logger.info(f"📊 Total procesados: {total_processed}")
        logger.info(f"✅ Total migrados: {total_migrated}")
        logger.info(f"⏭️  Total saltados: {total_skipped}")
        logger.info(f"❌ Total errores: {len(errors)}")
        
        if errors:
            logger.info("\n🚨 ERRORES ENCONTRADOS:")
            for error in errors:
                logger.info(f"   - {error}")
        
        logger.info("\n🎉 Migración completada exitosamente!")
        
        # Verificar integridad
        verify_migration_integrity(db)
        
    except Exception as e:
        logger.error(f"❌ Error crítico durante la migración: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


def verify_migration_integrity(db: Session):
    """
    Verificar la integridad de la migración.
    """
    logger.info("\n🔍 Verificando integridad de la migración...")
    
    # Verificar que no queden datos de Stripe en UserGym
    remaining_stripe_data = db.query(UserGym).filter(
        UserGym.stripe_customer_id.isnot(None)
    ).count()
    
    if remaining_stripe_data > 0:
        logger.warning(f"⚠️  Quedan {remaining_stripe_data} registros con datos de Stripe en UserGym")
    else:
        logger.info("✅ No quedan datos de Stripe en UserGym")
    
    # Contar perfiles creados
    total_profiles = db.query(UserGymStripeProfile).count()
    logger.info(f"📊 Total perfiles de Stripe creados: {total_profiles}")
    
    # Contar cuentas de gym
    total_gym_accounts = db.query(GymStripeAccount).count()
    logger.info(f"📊 Total cuentas de gym: {total_gym_accounts}")
    
    # Verificar perfiles activos
    active_profiles = db.query(UserGymStripeProfile).filter(
        UserGymStripeProfile.is_active == True
    ).count()
    logger.info(f"📊 Perfiles activos: {active_profiles}")
    
    # Verificar perfiles con suscripciones
    profiles_with_subscriptions = db.query(UserGymStripeProfile).filter(
        UserGymStripeProfile.stripe_subscription_id.isnot(None)
    ).count()
    logger.info(f"📊 Perfiles con suscripciones: {profiles_with_subscriptions}")


def rollback_migration():
    """
    Rollback de la migración (solo para emergencias).
    """
    logger.warning("🚨 INICIANDO ROLLBACK DE LA MIGRACIÓN")
    logger.warning("⚠️  Esta operación es irreversible!")
    
    confirm = input("¿Está seguro de que desea hacer rollback? (escriba 'ROLLBACK' para confirmar): ")
    if confirm != 'ROLLBACK':
        logger.info("❌ Rollback cancelado")
        return
    
    db = SessionLocal()
    
    try:
        # Buscar todos los perfiles migrados
        profiles = db.query(UserGymStripeProfile).all()
        
        logger.info(f"📊 Encontrados {len(profiles)} perfiles para rollback")
        
        for profile in profiles:
            # Buscar el UserGym correspondiente
            user_gym = db.query(UserGym).filter(
                UserGym.user_id == profile.user_id,
                UserGym.gym_id == profile.gym_id
            ).first()
            
            if user_gym:
                # Restaurar datos de Stripe
                user_gym.stripe_customer_id = profile.stripe_customer_id
                user_gym.stripe_subscription_id = profile.stripe_subscription_id
                user_gym.notes = f"Rollback migración - {datetime.now().isoformat()}"
                
                logger.info(f"🔄 Rollback user {profile.user_id} gym {profile.gym_id}")
            
            # Eliminar perfil
            db.delete(profile)
        
        # Eliminar cuentas placeholder
        placeholder_accounts = db.query(GymStripeAccount).filter(
            GymStripeAccount.stripe_account_id.like("placeholder_%")
        ).all()
        
        for account in placeholder_accounts:
            db.delete(account)
            logger.info(f"🗑️  Eliminada cuenta placeholder para gym {account.gym_id}")
        
        db.commit()
        logger.info("✅ Rollback completado")
        
    except Exception as e:
        logger.error(f"❌ Error durante rollback: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Migrar datos de Stripe a nueva arquitectura")
    parser.add_argument("--rollback", action="store_true", help="Hacer rollback de la migración")
    parser.add_argument("--dry-run", action="store_true", help="Ejecutar sin hacer cambios")
    
    args = parser.parse_args()
    
    if args.rollback:
        rollback_migration()
    else:
        if args.dry_run:
            logger.info("🧪 MODO DRY-RUN - No se harán cambios")
            # TODO: Implementar modo dry-run
        else:
            migrate_stripe_data() 