#!/usr/bin/env python3
"""
Script para probar la validación multi-tenant en endpoints de chat analytics.
Simula las validaciones sin depender de Redis.
"""

import requests
import json
import os
from typing import Dict, Any

# Configuración
BASE_URL = "http://127.0.0.1:8080/api/v1"

def test_endpoint_with_different_gyms():
    """
    Prueba que los endpoints de analytics respetan la validación multi-tenant.
    """
    print("🔒 Probando validación multi-tenant en endpoints de chat analytics...")
    
    # Endpoints a probar (todos requieren admin excepto user-activity)
    endpoints = [
        {
            "path": "/chat/analytics/gym-summary",
            "method": "GET",
            "requires_admin": True,
            "description": "Resumen del gimnasio"
        },
        {
            "path": "/chat/analytics/popular-times",
            "method": "GET", 
            "requires_admin": True,
            "description": "Horarios populares"
        },
        {
            "path": "/chat/analytics/health-metrics",
            "method": "GET",
            "requires_admin": True,
            "description": "Métricas de salud"
        },
        {
            "path": "/chat/analytics/user-activity",
            "method": "GET",
            "requires_admin": False,
            "description": "Actividad de usuario"
        }
    ]
    
    # Casos de prueba
    test_cases = [
        {
            "name": "Usuario válido del gym 1",
            "gym_id": "1",
            "token_env": "TOKEN_ADMIN_GYM_1",
            "should_succeed": True
        },
        {
            "name": "Usuario del gym 6 intentando acceder al gym 1",
            "gym_id": "1", 
            "token_env": "TOKEN_OWNER_GYM_6",
            "should_succeed": False
        }
    ]
    
    results = []
    
    for endpoint in endpoints:
        print(f"\n📊 Probando endpoint: {endpoint['description']}")
        print(f"   Ruta: {endpoint['path']}")
        
        for test_case in test_cases:
            print(f"\n   🧪 Caso: {test_case['name']}")
            
            # Obtener token del ambiente
            token = os.getenv(test_case['token_env'])
            if not token:
                print(f"   ❌ Token {test_case['token_env']} no encontrado en variables de ambiente")
                continue
            
            # Preparar headers
            headers = {
                "Authorization": f"Bearer {token}",
                "X-Gym-ID": test_case['gym_id'],
                "Content-Type": "application/json"
            }
            
            # Hacer request
            try:
                url = f"{BASE_URL}{endpoint['path']}"
                response = requests.get(url, headers=headers, timeout=10)
                
                print(f"   📡 Status: {response.status_code}")
                
                # Verificar resultado esperado
                if test_case['should_succeed']:
                    if response.status_code == 200:
                        print(f"   ✅ CORRECTO: Acceso permitido como esperado")
                        success = True
                    elif response.status_code == 403:
                        print(f"   ❌ ERROR: Acceso denegado cuando debería permitirse")
                        print(f"      Respuesta: {response.text}")
                        success = False
                    else:
                        print(f"   ⚠️  OTRO ERROR: {response.text}")
                        success = False
                else:
                    if response.status_code == 403:
                        print(f"   ✅ CORRECTO: Acceso denegado como esperado")
                        success = True
                    elif response.status_code == 200:
                        print(f"   ❌ FALLO DE SEGURIDAD: Acceso permitido cuando debería denegarse")
                        success = False
                    else:
                        print(f"   ⚠️  OTRO ERROR: {response.text}")
                        success = False
                
                results.append({
                    "endpoint": endpoint['path'],
                    "test_case": test_case['name'],
                    "expected_success": test_case['should_succeed'],
                    "actual_success": success,
                    "status_code": response.status_code
                })
                
            except requests.exceptions.RequestException as e:
                print(f"   ❌ Error de conexión: {e}")
                results.append({
                    "endpoint": endpoint['path'],
                    "test_case": test_case['name'],
                    "expected_success": test_case['should_succeed'],
                    "actual_success": False,
                    "status_code": None,
                    "error": str(e)
                })
    
    # Resumen de resultados
    print(f"\n{'='*60}")
    print("📋 RESUMEN DE PRUEBAS DE VALIDACIÓN MULTI-TENANT")
    print(f"{'='*60}")
    
    total_tests = len(results)
    successful_tests = sum(1 for r in results if r.get('actual_success', False))
    
    print(f"Total de pruebas: {total_tests}")
    print(f"Pruebas exitosas: {successful_tests}")
    print(f"Pruebas fallidas: {total_tests - successful_tests}")
    
    if successful_tests == total_tests:
        print("🎉 ¡Todas las pruebas de seguridad multi-tenant pasaron!")
    else:
        print("⚠️  Algunas pruebas fallaron - revisar validación de seguridad")
        
        print("\n❌ Pruebas fallidas:")
        for result in results:
            if not result.get('actual_success', False):
                print(f"   - {result['endpoint']} | {result['test_case']}")
                if 'error' in result:
                    print(f"     Error: {result['error']}")

if __name__ == "__main__":
    test_endpoint_with_different_gyms() 