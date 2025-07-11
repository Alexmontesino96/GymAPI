#!/usr/bin/env python3
"""
Script para limpiar cuentas duplicadas de Stripe Connect.

Este script:
1. Lista todas las cuentas de Stripe Connect
2. Identifica cuentas duplicadas por gym_id en metadata
3. Mantiene solo la cuenta más reciente por gym
4. Elimina las cuentas duplicadas restantes
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import stripe
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.stripe_profile import GymStripeAccount
from datetime import datetime
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configurar Stripe
settings = get_settings()
stripe.api_key = settings.STRIPE_SECRET_KEY

def get_all_stripe_accounts():
    """Obtener todas las cuentas de Stripe Connect"""
    try:
        accounts = stripe.Account.list(limit=100)
        return accounts.data
    except Exception as e:
        logger.error(f"Error obteniendo cuentas de Stripe: {e}")
        return []

def group_accounts_by_gym(accounts):
    """Agrupar cuentas por gym_id"""
    gym_accounts = {}
    
    for account in accounts:
        metadata = account.get('metadata', {})
        gym_id = metadata.get('gym_id')
        
        if gym_id:
            if gym_id not in gym_accounts:
                gym_accounts[gym_id] = []
            gym_accounts[gym_id].append(account)
    
    return gym_accounts

def delete_stripe_account(account_id):
    """Eliminar cuenta de Stripe Connect"""
    try:
        # Nota: En el entorno de pruebas, las cuentas se pueden eliminar
        # En producción, generalmente se desactivan
        stripe.Account.delete(account_id)
        logger.info(f"✅ Cuenta eliminada: {account_id}")
        return True
    except Exception as e:
        logger.error(f"❌ Error eliminando cuenta {account_id}: {e}")
        return False

def cleanup_duplicate_accounts():
    """Limpiar cuentas duplicadas"""
    logger.info("🔍 Iniciando limpieza de cuentas duplicadas...")
    
    # Obtener todas las cuentas de Stripe
    all_accounts = get_all_stripe_accounts()
    logger.info(f"📊 Total de cuentas encontradas: {len(all_accounts)}")
    
    # Agrupar por gym_id
    gym_accounts = group_accounts_by_gym(all_accounts)
    
    # Obtener cuentas válidas de la base de datos
    db = SessionLocal()
    try:
        valid_accounts = db.query(GymStripeAccount).filter(
            GymStripeAccount.is_active == True
        ).all()
        
        valid_account_ids = {acc.stripe_account_id for acc in valid_accounts}
        logger.info(f"📋 Cuentas válidas en BD: {len(valid_account_ids)}")
        
        total_deleted = 0
        
        for gym_id, accounts in gym_accounts.items():
            if len(accounts) > 1:
                logger.info(f"🔄 Gym {gym_id} tiene {len(accounts)} cuentas duplicadas")
                
                # Ordenar por fecha de creación (más reciente primero)
                accounts.sort(key=lambda x: x.created, reverse=True)
                
                # Mantener solo la cuenta más reciente que esté en la BD
                kept_account = None
                for account in accounts:
                    if account.id in valid_account_ids:
                        kept_account = account
                        logger.info(f"✅ Manteniendo cuenta válida: {account.id}")
                        break
                
                # Si no hay cuenta válida, mantener la más reciente
                if not kept_account:
                    kept_account = accounts[0]
                    logger.info(f"⚠️ Manteniendo cuenta más reciente: {kept_account.id}")
                
                # Eliminar las demás cuentas
                for account in accounts:
                    if account.id != kept_account.id:
                        logger.info(f"🗑️ Eliminando cuenta duplicada: {account.id}")
                        if delete_stripe_account(account.id):
                            total_deleted += 1
            else:
                logger.info(f"✅ Gym {gym_id} tiene solo 1 cuenta (correcto)")
        
        logger.info(f"🎉 Limpieza completada. Cuentas eliminadas: {total_deleted}")
        
    finally:
        db.close()

def main():
    """Función principal"""
    print("🧹 Script de limpieza de cuentas duplicadas de Stripe Connect")
    print("=" * 60)
    
    # Confirmar acción
    response = input("¿Está seguro de que desea continuar? (s/N): ").strip().lower()
    if response != 's':
        print("❌ Operación cancelada")
        return
    
    cleanup_duplicate_accounts()
    print("✅ Script completado")

if __name__ == "__main__":
    main() 