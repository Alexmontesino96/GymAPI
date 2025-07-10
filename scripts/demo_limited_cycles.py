#!/usr/bin/env python3
"""
Script de demostración para el sistema de ciclos limitados de facturación.
Muestra cómo crear planes con duración limitada y sus características.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.membership import MembershipPlan
from datetime import datetime, timedelta
from typing import List

def create_demo_plan(db: Session, gym_id: int, plan_data: dict) -> MembershipPlan:
    """Crear un plan de demostración"""
    plan = MembershipPlan(
        gym_id=gym_id,
        name=plan_data['name'],
        description=plan_data['description'],
        price_cents=plan_data['price_cents'],
        currency=plan_data['currency'],
        billing_interval=plan_data['billing_interval'],
        duration_days=plan_data['duration_days'],
        max_billing_cycles=plan_data.get('max_billing_cycles'),
        is_active=True
    )
    
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan

def demo_limited_cycles():
    """Demostrar el sistema de ciclos limitados"""
    db: Session = SessionLocal()
    
    try:
        print("🎯 DEMO: Sistema de Ciclos Limitados de Facturación")
        print("=" * 60)
        
        # Supongamos que tenemos un gimnasio con ID 1
        gym_id = 1
        
        # 1. Plan mensual ilimitado (caso normal)
        print("\n1️⃣ Plan Mensual Ilimitado:")
        plan_unlimited = create_demo_plan(db, gym_id, {
            'name': 'Mensual Ilimitado',
            'description': 'Plan mensual que se renueva automáticamente',
            'price_cents': 2999,  # €29.99
            'currency': 'EUR',
            'billing_interval': 'month',
            'duration_days': 30,
            'max_billing_cycles': None  # Ilimitado
        })
        
        print(f"   ✅ Creado: {plan_unlimited.name}")
        print(f"   💰 Precio: €{plan_unlimited.price_amount}/mes")
        print(f"   🔄 Tipo: {plan_unlimited.subscription_description}")
        print(f"   ⏰ Duración limitada: {plan_unlimited.is_limited_duration}")
        
        # 2. Plan mensual por 3 meses (caso del usuario)
        print("\n2️⃣ Plan Mensual por 3 Meses:")
        plan_3_months = create_demo_plan(db, gym_id, {
            'name': 'Mensual x3',
            'description': 'Plan mensual que se paga 3 veces y se cancela automáticamente',
            'price_cents': 3999,  # €39.99
            'currency': 'EUR',
            'billing_interval': 'month',
            'duration_days': 30,
            'max_billing_cycles': 3  # Solo 3 meses
        })
        
        print(f"   ✅ Creado: {plan_3_months.name}")
        print(f"   💰 Precio: €{plan_3_months.price_amount}/mes")
        print(f"   🔄 Tipo: {plan_3_months.subscription_description}")
        print(f"   ⏰ Duración limitada: {plan_3_months.is_limited_duration}")
        print(f"   📅 Duración total: {plan_3_months.total_duration_days} días")
        
        # 3. Plan anual por 2 años
        print("\n3️⃣ Plan Anual por 2 Años:")
        plan_2_years = create_demo_plan(db, gym_id, {
            'name': 'Anual x2',
            'description': 'Plan anual que se paga 2 veces y se cancela automáticamente',
            'price_cents': 29999,  # €299.99
            'currency': 'EUR',
            'billing_interval': 'year',
            'duration_days': 365,
            'max_billing_cycles': 2  # Solo 2 años
        })
        
        print(f"   ✅ Creado: {plan_2_years.name}")
        print(f"   💰 Precio: €{plan_2_years.price_amount}/año")
        print(f"   🔄 Tipo: {plan_2_years.subscription_description}")
        print(f"   ⏰ Duración limitada: {plan_2_years.is_limited_duration}")
        print(f"   📅 Duración total: {plan_2_years.total_duration_days} días")
        
        # 4. Plan de un solo pago
        print("\n4️⃣ Plan de Pago Único:")
        plan_one_time = create_demo_plan(db, gym_id, {
            'name': 'Pase Diario',
            'description': 'Acceso por un día, pago único',
            'price_cents': 1500,  # €15.00
            'currency': 'EUR',
            'billing_interval': 'one_time',
            'duration_days': 1,
            'max_billing_cycles': None  # No aplica para one_time
        })
        
        print(f"   ✅ Creado: {plan_one_time.name}")
        print(f"   💰 Precio: €{plan_one_time.price_amount}")
        print(f"   🔄 Tipo: {plan_one_time.subscription_description}")
        print(f"   ⏰ Duración limitada: {plan_one_time.is_limited_duration}")
        
        # 5. Demostrar simulación de cancelación automática
        print("\n5️⃣ Simulación de Cancelación Automática:")
        print("   Para el plan 'Mensual x3':")
        
        # Simular fechas de cancelación
        now = datetime.now()
        
        if plan_3_months.billing_interval == 'month':
            cancel_date = now + timedelta(days=plan_3_months.max_billing_cycles * 30)
        elif plan_3_months.billing_interval == 'year':
            cancel_date = now + timedelta(days=plan_3_months.max_billing_cycles * 365)
        else:
            cancel_date = now + timedelta(days=plan_3_months.duration_days)
        
        print(f"   📅 Fecha de inicio: {now.strftime('%Y-%m-%d %H:%M')}")
        print(f"   📅 Fecha de cancelación automática: {cancel_date.strftime('%Y-%m-%d %H:%M')}")
        print(f"   ⏱️ Duración total: {(cancel_date - now).days} días")
        
        # 6. Comparación de precios
        print("\n6️⃣ Comparación de Precios:")
        print("   Plan Mensual Ilimitado: €29.99/mes (sin límite)")
        print("   Plan Mensual x3: €39.99/mes × 3 = €119.97 total")
        print("   Plan Anual x2: €299.99/año × 2 = €599.98 total")
        print("   Plan Pase Diario: €15.00 (único pago)")
        
        # 7. Casos de uso
        print("\n7️⃣ Casos de Uso:")
        print("   🏃 Mensual Ilimitado: Clientes habituales")
        print("   🎯 Mensual x3: Programas de 3 meses, desafíos temporales")
        print("   💪 Anual x2: Estudiantes con periodo académico definido")
        print("   ⚡ Pase Diario: Visitantes ocasionales")
        
        # 8. Ventajas del sistema
        print("\n8️⃣ Ventajas del Sistema:")
        print("   ✅ Cancelación automática (sin intervención manual)")
        print("   ✅ Planificación financiera predecible")
        print("   ✅ Flexibilidad para diferentes tipos de clientes")
        print("   ✅ Integración nativa con Stripe")
        print("   ✅ Transparencia total para el usuario")
        
        print("\n" + "=" * 60)
        print("✨ Demo completada exitosamente!")
        print("Los planes han sido creados en la base de datos.")
        
        return [plan_unlimited, plan_3_months, plan_2_years, plan_one_time]
        
    except Exception as e:
        print(f"❌ Error durante la demo: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()

def show_existing_plans():
    """Mostrar planes existentes con información de ciclos"""
    db: Session = SessionLocal()
    
    try:
        print("\n📋 Planes Existentes:")
        print("-" * 50)
        
        plans = db.query(MembershipPlan).filter(MembershipPlan.is_active == True).all()
        
        if not plans:
            print("   No hay planes activos.")
            return
        
        for plan in plans:
            print(f"\n📦 {plan.name}")
            print(f"   💰 Precio: €{plan.price_amount}")
            print(f"   🔄 Intervalo: {plan.billing_interval}")
            print(f"   📅 Duración: {plan.duration_days} días")
            print(f"   🔢 Máx. ciclos: {plan.max_billing_cycles or 'Ilimitado'}")
            print(f"   ⏰ Duración limitada: {'Sí' if plan.is_limited_duration else 'No'}")
            print(f"   📝 Descripción: {plan.subscription_description}")
            
            if plan.is_limited_duration:
                print(f"   📊 Duración total: {plan.total_duration_days} días")
        
    except Exception as e:
        print(f"❌ Error al mostrar planes: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    print("🚀 Iniciando demo del sistema de ciclos limitados...")
    
    try:
        # Mostrar planes existentes
        show_existing_plans()
        
        # Ejecutar demo
        demo_plans = demo_limited_cycles()
        
        print("\n" + "=" * 60)
        print("🎉 ¡Demo completada con éxito!")
        print("Los planes están listos para usar en el sistema.")
        
    except Exception as e:
        print(f"\n❌ Error en la demo: {str(e)}")
        sys.exit(1) 