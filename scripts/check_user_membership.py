#!/usr/bin/env python3
"""
Script para verificar la membresía de un usuario en un gimnasio específico.
"""

import os
import sys

# Añadir el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.user import User
from app.models.user_gym import UserGym, GymRoleType
from app.models.gym import Gym

def check_user_membership(user_id: int, gym_id: int):
    """Verifica la membresía de un usuario en un gimnasio."""
    db = SessionLocal()
    try:
        # Obtener información del usuario
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            print(f"❌ Usuario {user_id} no encontrado")
            return
        
        # Obtener información del gimnasio
        gym = db.query(Gym).filter(Gym.id == gym_id).first()
        if not gym:
            print(f"❌ Gimnasio {gym_id} no encontrado")
            return
        
        # Obtener membresía
        membership = db.query(UserGym).filter(
            UserGym.user_id == user_id,
            UserGym.gym_id == gym_id
        ).first()
        
        print(f"\n🔍 VERIFICACIÓN DE MEMBRESÍA")
        print(f"=" * 50)
        print(f"👤 Usuario: {user.first_name} {user.last_name} (ID: {user_id})")
        print(f"   Email: {user.email}")
        print(f"   Auth0 ID: {user.auth0_id}")
        print(f"   Rol global: {user.role.value if user.role else 'None'}")
        print(f"   Activo: {'Sí' if user.is_active else 'No'}")
        
        print(f"\n🏃 Gimnasio: {gym.name} (ID: {gym_id})")
        print(f"   Subdominio: {gym.subdomain}")
        print(f"   Activo: {'Sí' if gym.is_active else 'No'}")
        
        if membership:
            print(f"\n✅ MEMBRESÍA ENCONTRADA")
            print(f"   Rol en gimnasio: {membership.role.value}")
            print(f"   Activa: {'Sí' if membership.is_active else 'No'}")
            print(f"   Tipo: {membership.membership_type}")
            print(f"   Creada: {membership.created_at}")
            if membership.membership_expires_at:
                print(f"   Expira: {membership.membership_expires_at}")
            if membership.stripe_customer_id:
                print(f"   Stripe Customer: {membership.stripe_customer_id}")
        else:
            print(f"\n❌ MEMBRESÍA NO ENCONTRADA")
            print(f"   El usuario {user_id} no pertenece al gimnasio {gym_id}")
        
        # Verificar otras membresías del usuario
        other_memberships = db.query(UserGym).filter(UserGym.user_id == user_id).all()
        if other_memberships:
            print(f"\n📋 OTRAS MEMBRESÍAS DEL USUARIO:")
            for mem in other_memberships:
                other_gym = db.query(Gym).filter(Gym.id == mem.gym_id).first()
                gym_name = other_gym.name if other_gym else f"Gimnasio {mem.gym_id}"
                status = "✅ Activa" if mem.is_active else "❌ Inactiva"
                print(f"   • {gym_name} (ID: {mem.gym_id}) - {mem.role.value} - {status}")
        
    finally:
        db.close()

def main():
    """Función principal del script."""
    if len(sys.argv) != 3:
        print("Uso: python check_user_membership.py <user_id> <gym_id>")
        print("Ejemplo: python check_user_membership.py 10 4")
        sys.exit(1)
    
    try:
        user_id = int(sys.argv[1])
        gym_id = int(sys.argv[2])
    except ValueError:
        print("❌ Error: user_id y gym_id deben ser números enteros")
        sys.exit(1)
    
    check_user_membership(user_id, gym_id)

if __name__ == "__main__":
    main() 