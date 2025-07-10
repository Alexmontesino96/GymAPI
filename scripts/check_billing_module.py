#!/usr/bin/env python3
"""
Script para verificar y crear el módulo billing si no existe.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.module import Module
from app.services.module import module_service
from datetime import datetime

def check_and_create_billing_module():
    """Verificar si el módulo billing existe y crearlo si no existe"""
    db: Session = SessionLocal()
    
    try:
        # Verificar si el módulo billing existe
        billing_module = module_service.get_module_by_code(db, "billing")
        
        if billing_module:
            print(f"✅ El módulo billing ya existe:")
            print(f"   - ID: {billing_module.id}")
            print(f"   - Código: {billing_module.code}")
            print(f"   - Nombre: {billing_module.name}")
            print(f"   - Descripción: {billing_module.description}")
            print(f"   - Es premium: {billing_module.is_premium}")
            print(f"   - Creado: {billing_module.created_at}")
            return True
        
        print("❌ El módulo billing no existe. Creándolo...")
        
        # Crear el módulo billing
        new_module = Module(
            code="billing",
            name="Facturación y Pagos",
            description="Integración con Stripe para procesamiento de pagos, suscripciones y facturación automática",
            is_premium=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(new_module)
        db.commit()
        db.refresh(new_module)
        
        print(f"✅ Módulo billing creado exitosamente:")
        print(f"   - ID: {new_module.id}")
        print(f"   - Código: {new_module.code}")
        print(f"   - Nombre: {new_module.name}")
        print(f"   - Descripción: {new_module.description}")
        print(f"   - Es premium: {new_module.is_premium}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error al verificar/crear el módulo billing: {str(e)}")
        db.rollback()
        return False
    finally:
        db.close()

def list_all_modules():
    """Listar todos los módulos existentes"""
    db: Session = SessionLocal()
    
    try:
        modules = module_service.get_modules(db, skip=0, limit=100)
        
        print(f"\n📋 Módulos existentes ({len(modules)}):")
        for module in modules:
            print(f"   - {module.code}: {module.name} (Premium: {module.is_premium})")
            
    except Exception as e:
        print(f"❌ Error al listar módulos: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    print("🔍 Verificando módulo billing...")
    
    # Listar módulos existentes
    list_all_modules()
    
    # Verificar y crear el módulo billing
    success = check_and_create_billing_module()
    
    if success:
        print("\n✅ Verificación completada exitosamente.")
        print("\n💡 Ahora puedes intentar activar el módulo billing nuevamente.")
    else:
        print("\n❌ Hubo un error durante la verificación.")
        sys.exit(1) 