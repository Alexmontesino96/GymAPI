#!/usr/bin/env python3
"""
Script para probar la API de Stripe y verificar el price_id de la suscripción
"""

import stripe
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configurar Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

def test_subscription():
    """Probar la suscripción específica"""
    subscription_id = 'sub_1RjY9rBVjiDLF0pBX9eo3LkP'
    account_id = 'acct_1RjXQ7BVjiDLF0pB'
    plan_price_id = 'price_1RjY2SBVjiDLF0pB2tjkn5hq'
    
    try:
        print(f"Obteniendo suscripción {subscription_id}...")
        
        # Obtener la suscripción
        subscription = stripe.Subscription.retrieve(
            subscription_id,
            stripe_account=account_id
        )
        
        print(f"Status: {subscription.status}")
        print(f"Customer: {subscription.customer}")
        
        # Obtener items como propiedad
        items_list = subscription.items
        print(f"Items list type: {type(items_list)}")
        
        # Verificar items
        subscription_price_ids = []
        if hasattr(items_list, 'data'):
            items_data = items_list.data
            print(f"Items data count: {len(items_data)}")
            
            for i, item in enumerate(items_data):
                print(f"  Item {i+1}:")
                print(f"    Price ID: {item.price.id}")
                print(f"    Amount: {item.price.unit_amount/100} {item.price.currency.upper()}")
                subscription_price_ids.append(item.price.id)
        else:
            print("Items no tiene atributo data")
        
        print(f"\nComparación:")
        print(f"  Plan price_id: {plan_price_id}")
        print(f"  Subscription price_ids: {subscription_price_ids}")
        print(f"  ¿Coinciden?: {plan_price_id in subscription_price_ids}")
        
        return plan_price_id in subscription_price_ids
        
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    test_subscription() 