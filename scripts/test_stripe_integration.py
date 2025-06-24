#!/usr/bin/env python3
"""
Script para probar la integración con Stripe.

Este script verifica que las credenciales de Stripe funcionan correctamente
y que podemos crear productos y precios de prueba.
"""

import os
import stripe
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configurar Stripe
stripe.api_key = os.getenv("SECRET_KEY")

def test_stripe_connection():
    """Probar conexión básica con Stripe"""
    print("🔍 Probando conexión con Stripe...")
    
    try:
        # Intentar listar productos
        products = stripe.Product.list(limit=3)
        print(f"✅ Conexión exitosa! Productos encontrados: {len(products.data)}")
        return True
    except stripe.error.AuthenticationError:
        print("❌ Error de autenticación. Verificar SECRET_KEY.")
        return False
    except Exception as e:
        print(f"❌ Error inesperado: {str(e)}")
        return False

def create_test_product():
    """Crear un producto de prueba"""
    print("\n📦 Creando producto de prueba...")
    
    try:
        # Crear producto
        product = stripe.Product.create(
            name="Membresía Gym Test",
            description="Plan de membresía mensual para testing",
            metadata={"gym_id": "test", "created_by": "test_script"}
        )
        
        print(f"✅ Producto creado: {product.id}")
        
        # Crear precio para el producto
        price = stripe.Price.create(
            unit_amount=2999,  # €29.99
            currency="eur",
            recurring={"interval": "month"},
            product=product.id,
            metadata={"gym_id": "test", "plan_type": "monthly"}
        )
        
        print(f"✅ Precio creado: {price.id}")
        
        return {
            "product_id": product.id,
            "price_id": price.id
        }
        
    except Exception as e:
        print(f"❌ Error al crear producto: {str(e)}")
        return None

def create_test_checkout_session(price_id):
    """Crear una sesión de checkout de prueba"""
    print(f"\n💳 Creando sesión de checkout de prueba...")
    
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url='http://localhost:8080/membership/success?session_id={CHECKOUT_SESSION_ID}',
            cancel_url='http://localhost:8080/membership/cancel',
            metadata={
                'user_id': 'test_user',
                'gym_id': 'test_gym',
                'plan_id': 'test_plan'
            }
        )
        
        print(f"✅ Sesión de checkout creada: {session.id}")
        print(f"🔗 URL de checkout: {session.url}")
        
        return session.id
        
    except Exception as e:
        print(f"❌ Error al crear checkout: {str(e)}")
        return None

def cleanup_test_resources(product_id):
    """Limpiar recursos de prueba"""
    print(f"\n🧹 Limpiando recursos de prueba...")
    
    try:
        # Desactivar producto (no se puede eliminar completamente)
        stripe.Product.modify(
            product_id,
            active=False
        )
        print(f"✅ Producto {product_id} desactivado")
        
    except Exception as e:
        print(f"❌ Error al limpiar recursos: {str(e)}")

def main():
    """Función principal del script"""
    print("🚀 Iniciando prueba de integración con Stripe")
    print("=" * 50)
    
    # 1. Probar conexión
    if not test_stripe_connection():
        print("\n❌ La conexión con Stripe falló. Verificar credenciales.")
        return
    
    # 2. Crear producto de prueba
    test_resources = create_test_product()
    if not test_resources:
        print("\n❌ No se pudo crear el producto de prueba.")
        return
    
    # 3. Crear sesión de checkout
    session_id = create_test_checkout_session(test_resources["price_id"])
    if not session_id:
        print("\n❌ No se pudo crear la sesión de checkout.")
    
    # 4. Mostrar resumen
    print("\n" + "=" * 50)
    print("📋 RESUMEN DE LA PRUEBA")
    print("=" * 50)
    print(f"✅ Conexión a Stripe: OK")
    print(f"✅ Producto de prueba: {test_resources['product_id']}")
    print(f"✅ Precio de prueba: {test_resources['price_id']}")
    print(f"✅ Sesión de checkout: {session_id}")
    print(f"🌐 Servidor en: http://localhost:8080")
    print(f"📄 Página de éxito: http://localhost:8080/membership/success")
    print(f"📄 Página de cancelación: http://localhost:8080/membership/cancel")
    
    # 5. Limpiar recursos
    cleanup_test_resources(test_resources["product_id"])
    
    print("\n🎉 ¡Prueba completada exitosamente!")
    print("💡 Tu integración con Stripe está funcionando correctamente.")

if __name__ == "__main__":
    main() 