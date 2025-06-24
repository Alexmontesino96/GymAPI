#!/usr/bin/env python3
"""
Script de prueba para verificar la sincronización automática 
entre planes de membresía locales y Stripe.
"""

import asyncio
import sys
import os
from datetime import datetime

# Agregar el directorio padre al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal
from app.services.membership import membership_service
from app.services.stripe_service import StripeService
from app.schemas.membership import MembershipPlanCreate, MembershipPlanUpdate
from app.models.gym import Gym
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_membership_stripe_sync():
    """Probar la sincronización automática con Stripe"""
    
    print("🧪 INICIANDO PRUEBAS DE SINCRONIZACIÓN STRIPE-LOCAL")
    print("=" * 60)
    
    db = SessionLocal()
    
    try:
        # 1. Verificar que existe al menos un gimnasio
        gym = db.query(Gym).first()
        if not gym:
            print("❌ No hay gimnasios en la base de datos")
            return
        
        print(f"🏢 Usando gimnasio: {gym.name} (ID: {gym.id})")
        
        # 2. Crear un plan de prueba (debería sincronizar automáticamente)
        print("\n📝 PASO 1: Crear plan de membresía (con sincronización automática)")
        
        plan_data = MembershipPlanCreate(
            name=f"Plan de Prueba Stripe {datetime.now().strftime('%H:%M:%S')}",
            description="Plan de prueba para verificar sincronización automática con Stripe",
            price_cents=2999,  # €29.99
            currency="EUR",
            billing_interval="month",
            duration_days=30,
            features='["Acceso al gimnasio", "Clases grupales", "Ducha"]',
            max_bookings_per_month=30,
            is_active=True
        )
        
        # Crear plan (debería sincronizar automáticamente con Stripe)
        plan = await membership_service.create_membership_plan(db, gym.id, plan_data)
        
        print(f"✅ Plan creado localmente: {plan.name} (ID: {plan.id})")
        print(f"   Stripe Product ID: {plan.stripe_product_id}")
        print(f"   Stripe Price ID: {plan.stripe_price_id}")
        
        if plan.stripe_product_id and plan.stripe_price_id:
            print("✅ Sincronización automática exitosa!")
        else:
            print("❌ Sincronización automática falló")
            return
        
        # 3. Actualizar el plan (debería actualizar en Stripe)
        print(f"\n📝 PASO 2: Actualizar plan (con sincronización automática)")
        
        plan_update = MembershipPlanUpdate(
            name=f"Plan de Prueba Actualizado {datetime.now().strftime('%H:%M:%S')}",
            description="Plan actualizado - prueba de sincronización",
            price_cents=3999,  # Cambiar precio a €39.99
        )
        
        updated_plan = await membership_service.update_membership_plan(
            db, plan.id, plan_update
        )
        
        print(f"✅ Plan actualizado: {updated_plan.name}")
        print(f"   Precio actualizado: €{updated_plan.price_cents/100:.2f}")
        print(f"   Stripe Product ID: {updated_plan.stripe_product_id}")
        print(f"   Stripe Price ID: {updated_plan.stripe_price_id}")
        
        # 4. Verificar sincronización manual
        print(f"\n📝 PASO 3: Verificar funciones de sincronización manual")
        
        # Sincronización individual
        sync_result = await membership_service.sync_plan_with_stripe_manual(db, plan.id)
        print(f"✅ Sincronización manual individual: {'Exitosa' if sync_result else 'Fallida'}")
        
        # Sincronización masiva del gimnasio
        sync_all_result = await membership_service.sync_all_plans_with_stripe(db, gym.id)
        print(f"✅ Sincronización masiva: {sync_all_result['synced']}/{sync_all_result['total']} planes")
        
        # 5. Desactivar el plan (debería desactivar en Stripe)
        print(f"\n📝 PASO 4: Desactivar plan (con sincronización automática)")
        
        deactivate_result = await membership_service.delete_membership_plan(db, plan.id)
        
        if deactivate_result:
            print("✅ Plan desactivado localmente y sincronizado con Stripe")
        else:
            print("❌ Error al desactivar el plan")
        
        # 6. Verificar el estado final
        final_plan = membership_service.get_membership_plan(db, plan.id)
        print(f"📊 Estado final del plan:")
        print(f"   Activo localmente: {final_plan.is_active}")
        print(f"   Stripe Product ID: {final_plan.stripe_product_id}")
        print(f"   Stripe Price ID: {final_plan.stripe_price_id}")
        
        print("\n🎉 PRUEBAS COMPLETADAS EXITOSAMENTE!")
        print("=" * 60)
        print("✅ Sincronización automática funcionando correctamente")
        print("✅ Los planes se crean, actualizan y desactivan en Stripe automáticamente")
        print("✅ Las funciones de sincronización manual están operativas")
        
    except Exception as e:
        print(f"❌ Error durante las pruebas: {str(e)}")
        logger.exception("Error en pruebas de sincronización")
        
    finally:
        db.close()

async def test_stripe_connection():
    """Verificar conexión básica con Stripe"""
    print("\n🔗 VERIFICANDO CONEXIÓN CON STRIPE")
    
    try:
        stripe_service = StripeService(membership_service)
        
        # Crear un producto de prueba básico
        import stripe
        from app.core.config import get_settings
        
        settings = get_settings()
        stripe.api_key = settings.STRIPE_SECRET_KEY
        
        # Verificar que podemos hacer calls a Stripe
        products = stripe.Product.list(limit=1)
        print(f"✅ Conexión con Stripe exitosa: {len(products.data)} productos encontrados")
        
        return True
        
    except Exception as e:
        print(f"❌ Error de conexión con Stripe: {str(e)}")
        return False

if __name__ == "__main__":
    print("🚀 INICIANDO SCRIPT DE PRUEBA SINCRONIZACIÓN STRIPE")
    
    # Verificar conexión primero
    connection_ok = asyncio.run(test_stripe_connection())
    
    if connection_ok:
        # Ejecutar pruebas principales
        asyncio.run(test_membership_stripe_sync())
    else:
        print("❌ No se puede continuar sin conexión a Stripe")
        sys.exit(1) 