#!/usr/bin/env python3
"""
Script de prueba para el sistema híbrido de planes nutricionales.
Prueba la funcionalidad de planes template, live y archived.
"""

import requests
import json
from datetime import datetime, timedelta
from typing import Dict, Any

# Configuración
BASE_URL = "http://localhost:8000/api/v1/nutrition"  # Cambiar según tu configuración
HEADERS = {
    "Authorization": "Bearer YOUR_JWT_TOKEN",  # Reemplazar con token real
    "X-Gym-ID": "1",  # Reemplazar con gym ID real
    "Content-Type": "application/json"
}

def test_hybrid_nutrition_system():
    """Función principal de prueba del sistema híbrido."""
    
    print("🧪 === TESTING SISTEMA HÍBRIDO DE PLANES NUTRICIONALES ===")
    print()
    
    # 1. Probar creación de plan TEMPLATE
    print("1. 📋 Creando plan TEMPLATE...")
    template_plan = create_template_plan()
    
    if template_plan:
        print(f"   ✅ Plan template creado: ID {template_plan['id']}")
        
        # 2. Crear contenido para el plan template
        print("2. 🍽️ Creando contenido para plan template...")
        create_plan_content(template_plan['id'])
        
        # 3. Seguir plan template
        print("3. 👤 Siguiendo plan template...")
        follow_plan(template_plan['id'])
    
    # 4. Probar creación de plan LIVE
    print("\n4. 🔴 Creando plan LIVE...")
    live_plan = create_live_plan()
    
    if live_plan:
        print(f"   ✅ Plan live creado: ID {live_plan['id']}")
        
        # 5. Crear contenido para el plan live
        print("5. 🍽️ Creando contenido para plan live...")
        create_plan_content(live_plan['id'])
        
        # 6. Seguir plan live
        print("6. 👤 Siguiendo plan live...")
        follow_plan(live_plan['id'])
        
        # 7. Probar estado del plan live
        print("7. 📊 Probando estado del plan live...")
        test_plan_status(live_plan['id'])
    
    # 8. Probar dashboard híbrido
    print("\n8. 📱 Probando dashboard híbrido...")
    test_hybrid_dashboard()
    
    # 9. Probar plan de hoy híbrido
    print("9. 📅 Probando plan de hoy híbrido...")
    test_today_hybrid()
    
    # 10. Probar listado categorizado
    print("10. 📋 Probando listado por tipos...")
    test_categorized_listing()
    
    # 11. Probar archivado (simulado)
    if live_plan:
        print("11. 📦 Probando archivado de plan live...")
        test_archive_plan(live_plan['id'])
    
    print("\n✅ === TESTING COMPLETADO ===")


def create_template_plan() -> Dict[str, Any]:
    """Crear un plan template."""
    plan_data = {
        "title": "Plan Template de Volumen",
        "description": "Plan flexible que cada usuario puede empezar cuando quiera",
        "goal": "bulk",
        "difficulty_level": "beginner",
        "budget_level": "medium",
        "dietary_restrictions": "none",
        "duration_days": 7,
        "is_recurring": True,
        "target_calories": 3000,
        "target_protein_g": 150.0,
        "target_carbs_g": 375.0,
        "target_fat_g": 100.0,
        "is_public": True,
        "tags": ["volumen", "principiantes", "flexible"],
        "plan_type": "template"  # Tipo template
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/plans",
            headers=HEADERS,
            json=plan_data
        )
        
        if response.status_code == 201:
            return response.json()
        else:
            print(f"   ❌ Error creando plan template: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"   ❌ Error de conexión: {str(e)}")
        return None


def create_live_plan() -> Dict[str, Any]:
    """Crear un plan live."""
    # Fecha de inicio: mañana a las 08:00
    start_date = datetime.now() + timedelta(days=1)
    start_date = start_date.replace(hour=8, minute=0, second=0, microsecond=0)
    
    plan_data = {
        "title": "Plan Live de Definición - Enero 2025",
        "description": "Plan live sincronizado que todos los participantes siguen al mismo tiempo",
        "goal": "cut",
        "difficulty_level": "intermediate",
        "budget_level": "medium",
        "dietary_restrictions": "none",
        "duration_days": 14,
        "is_recurring": False,
        "target_calories": 2200,
        "target_protein_g": 160.0,
        "target_carbs_g": 200.0,
        "target_fat_g": 70.0,
        "is_public": True,
        "tags": ["definicion", "live", "enero2025"],
        "plan_type": "live",  # Tipo live
        "live_start_date": start_date.isoformat()  # Fecha de inicio
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/plans",
            headers=HEADERS,
            json=plan_data
        )
        
        if response.status_code == 201:
            return response.json()
        else:
            print(f"   ❌ Error creando plan live: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"   ❌ Error de conexión: {str(e)}")
        return None


def create_plan_content(plan_id: int):
    """Crear contenido (días y comidas) para un plan."""
    
    # Crear día 1
    daily_plan_data = {
        "nutrition_plan_id": plan_id,
        "day_number": 1,
        "total_calories": 3000,
        "total_protein_g": 150.0,
        "total_carbs_g": 375.0,
        "total_fat_g": 100.0,
        "notes": "Día 1 del plan"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/plans/{plan_id}/days",
            headers=HEADERS,
            json=daily_plan_data
        )
        
        if response.status_code == 201:
            daily_plan = response.json()
            print(f"   ✅ Día creado: {daily_plan['id']}")
            
            # Crear una comida de ejemplo
            meal_data = {
                "daily_plan_id": daily_plan['id'],
                "meal_type": "breakfast",
                "name": "Desayuno Energético",
                "description": "Avena con frutas y proteína",
                "preparation_time_minutes": 15,
                "cooking_instructions": "Mezclar todos los ingredientes",
                "calories": 450,
                "protein_g": 25.0,
                "carbs_g": 60.0,
                "fat_g": 12.0,
                "order_in_day": 1
            }
            
            meal_response = requests.post(
                f"{BASE_URL}/days/{daily_plan['id']}/meals",
                headers=HEADERS,
                json=meal_data
            )
            
            if meal_response.status_code == 201:
                meal = meal_response.json()
                print(f"   ✅ Comida creada: {meal['name']}")
            
        else:
            print(f"   ❌ Error creando día: {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")


def follow_plan(plan_id: int):
    """Seguir un plan nutricional."""
    try:
        response = requests.post(
            f"{BASE_URL}/plans/{plan_id}/follow",
            headers=HEADERS
        )
        
        if response.status_code == 201:
            follower = response.json()
            print(f"   ✅ Plan seguido exitosamente")
        else:
            print(f"   ❌ Error siguiendo plan: {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")


def test_plan_status(plan_id: int):
    """Probar el estado de un plan."""
    try:
        response = requests.get(
            f"{BASE_URL}/plans/{plan_id}/status",
            headers=HEADERS
        )
        
        if response.status_code == 200:
            status = response.json()
            print(f"   ✅ Estado del plan:")
            print(f"      📅 Día actual: {status['current_day']}")
            print(f"      🔄 Estado: {status['status']}")
            print(f"      ⏰ Días hasta inicio: {status['days_until_start']}")
            print(f"      🔴 Live activo: {status['is_live_active']}")
        else:
            print(f"   ❌ Error obteniendo estado: {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")


def test_hybrid_dashboard():
    """Probar el dashboard híbrido."""
    try:
        response = requests.get(
            f"{BASE_URL}/dashboard",
            headers=HEADERS
        )
        
        if response.status_code == 200:
            dashboard = response.json()
            print(f"   ✅ Dashboard híbrido:")
            print(f"      📋 Planes template: {len(dashboard['template_plans'])}")
            print(f"      🔴 Planes live: {len(dashboard['live_plans'])}")
            print(f"      📚 Planes disponibles: {len(dashboard['available_plans'])}")
            print(f"      📅 Plan de hoy: {'Sí' if dashboard['today_plan']['plan'] else 'No'}")
        else:
            print(f"   ❌ Error obteniendo dashboard: {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")


def test_today_hybrid():
    """Probar el plan de hoy híbrido."""
    try:
        response = requests.get(
            f"{BASE_URL}/today",
            headers=HEADERS
        )
        
        if response.status_code == 200:
            today = response.json()
            print(f"   ✅ Plan de hoy híbrido:")
            print(f"      📅 Día actual: {today['current_day']}")
            print(f"      🔄 Estado: {today['status']}")
            print(f"      🍽️ Comidas: {len(today['meals'])}")
            if today['plan']:
                print(f"      📋 Plan: {today['plan']['title']} ({today['plan']['plan_type']})")
        else:
            print(f"   ❌ Error obteniendo plan de hoy: {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")


def test_categorized_listing():
    """Probar el listado categorizado por tipos."""
    try:
        response = requests.get(
            f"{BASE_URL}/plans/hybrid",
            headers=HEADERS
        )
        
        if response.status_code == 200:
            listing = response.json()
            print(f"   ✅ Listado categorizado:")
            print(f"      🔴 Planes live: {len(listing['live_plans'])}")
            print(f"      📋 Planes template: {len(listing['template_plans'])}")
            print(f"      📦 Planes archivados: {len(listing['archived_plans'])}")
        else:
            print(f"   ❌ Error obteniendo listado: {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")


def test_archive_plan(plan_id: int):
    """Probar el archivado de un plan live (simulado)."""
    archive_data = {
        "create_template_version": True,
        "template_title": "Plan de Definición (Template)"
    }
    
    try:
        # Nota: Este endpoint probablemente falle porque el plan live está activo
        # En un escenario real, primero tendríamos que esperar a que termine
        response = requests.post(
            f"{BASE_URL}/plans/{plan_id}/archive",
            headers=HEADERS,
            json=archive_data
        )
        
        if response.status_code == 200:
            archived = response.json()
            print(f"   ✅ Plan archivado: {archived['title']}")
        else:
            print(f"   ⚠️ Archivado no disponible (plan activo): {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")


if __name__ == "__main__":
    print("🚀 Iniciando pruebas del sistema híbrido de nutrición...")
    print("📝 Asegúrate de configurar:")
    print("   - BASE_URL correcto")
    print("   - JWT Token válido en HEADERS")
    print("   - X-Gym-ID correcto")
    print()
    
    test_hybrid_nutrition_system() 