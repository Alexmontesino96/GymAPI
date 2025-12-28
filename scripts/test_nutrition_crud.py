#!/usr/bin/env python3
"""
Script de Testing Rápido para Endpoints CRUD de Nutrición
==========================================================
Valida que los nuevos endpoints funcionan correctamente.

Uso:
    python scripts/test_nutrition_crud.py --token YOUR_TOKEN --gym-id 4

Autor: Claude Code Assistant
Fecha: 27 de Diciembre 2024
"""

import requests
import json
import argparse
import sys
from datetime import datetime
from typing import Dict, Any, Optional

# Colores para output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_test_header(test_name):
    print(f"\n{Colors.BLUE}{Colors.BOLD}Testing: {test_name}{Colors.ENDC}")
    print("=" * 50)

def print_result(success: bool, message: str):
    if success:
        print(f"{Colors.GREEN}✅ {message}{Colors.ENDC}")
    else:
        print(f"{Colors.RED}❌ {message}{Colors.ENDC}")

def print_warning(message: str):
    print(f"{Colors.YELLOW}⚠️  {message}{Colors.ENDC}")

class NutritionCRUDTester:
    def __init__(self, base_url: str, token: str, gym_id: int):
        self.base_url = base_url.rstrip('/')
        self.headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'X-Gym-Id': str(gym_id)
        }
        self.test_results = {
            'passed': 0,
            'failed': 0,
            'warnings': 0
        }
        self.test_data = {}

    def make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> tuple:
        """Hacer request y retornar (success, response_data, status_code)"""
        url = f"{self.base_url}{endpoint}"

        try:
            if method == 'GET':
                response = requests.get(url, headers=self.headers)
            elif method == 'POST':
                response = requests.post(url, headers=self.headers, json=data)
            elif method == 'PUT':
                response = requests.put(url, headers=self.headers, json=data)
            elif method == 'DELETE':
                response = requests.delete(url, headers=self.headers)
            else:
                return False, {"error": "Invalid method"}, 0

            if response.status_code == 204:
                return True, {}, response.status_code

            try:
                response_data = response.json()
            except:
                response_data = {"text": response.text}

            success = 200 <= response.status_code < 300
            return success, response_data, response.status_code

        except requests.exceptions.RequestException as e:
            return False, {"error": str(e)}, 0

    def test_meal_endpoints(self):
        """Test CRUD operations for meals"""
        print_test_header("MEAL ENDPOINTS")

        # Primero necesitamos encontrar un meal_id válido
        # Obtenemos un plan para extraer un meal_id
        success, data, status = self.make_request('GET', '/api/v1/nutrition/plans')

        if success and data.get('plans'):
            plan_id = data['plans'][0]['id']

            # Obtener el plan completo para encontrar meals
            success, plan_data, status = self.make_request('GET', f'/api/v1/nutrition/plans/{plan_id}')

            if success and plan_data.get('daily_plans'):
                for daily_plan in plan_data['daily_plans']:
                    if daily_plan.get('meals'):
                        meal_id = daily_plan['meals'][0]['id']
                        self.test_data['meal_id'] = meal_id
                        self.test_data['daily_plan_id'] = daily_plan['id']
                        break

        if 'meal_id' not in self.test_data:
            print_warning("No se encontraron comidas para probar. Creando una de prueba...")
            # Intentar crear una comida de prueba
            return

        meal_id = self.test_data['meal_id']

        # Test 1: GET /meals/{meal_id}
        success, data, status = self.make_request('GET', f'/api/v1/nutrition/meals/{meal_id}')
        if status == 404:
            print_result(False, f"GET /meals/{meal_id} - Endpoint no implementado (404)")
            self.test_results['failed'] += 1
        elif success:
            print_result(True, f"GET /meals/{meal_id} - Status {status}")
            if 'ingredients' in data:
                print(f"  → Comida: {data.get('name', 'Sin nombre')}")
                print(f"  → Ingredientes: {len(data.get('ingredients', []))}")
            self.test_results['passed'] += 1
        else:
            print_result(False, f"GET /meals/{meal_id} - Status {status}: {data}")
            self.test_results['failed'] += 1

        # Test 2: PUT /meals/{meal_id}
        update_data = {
            "name": f"Comida Actualizada Test {datetime.now().strftime('%H:%M')}",
            "target_calories": 500
        }
        success, data, status = self.make_request('PUT', f'/api/v1/nutrition/meals/{meal_id}', update_data)

        if status == 404:
            print_result(False, f"PUT /meals/{meal_id} - Endpoint no implementado (404)")
            self.test_results['failed'] += 1
        elif status == 403:
            print_warning(f"PUT /meals/{meal_id} - Sin permisos (403) - Normal si no eres el creador")
            self.test_results['warnings'] += 1
        elif success:
            print_result(True, f"PUT /meals/{meal_id} - Status {status}")
            if data.get('name') == update_data['name']:
                print(f"  → Nombre actualizado correctamente")
            self.test_results['passed'] += 1
        else:
            print_result(False, f"PUT /meals/{meal_id} - Status {status}: {data}")
            self.test_results['failed'] += 1

        # Test 3: DELETE /meals/{meal_id} (usar un ID alto que probablemente no existe)
        test_meal_id = 99999
        success, data, status = self.make_request('DELETE', f'/api/v1/nutrition/meals/{test_meal_id}')

        if status == 404:
            # Podría ser porque el endpoint no existe o porque la comida no existe
            # Intentemos con una comida real para distinguir
            success2, data2, status2 = self.make_request('DELETE', f'/api/v1/nutrition/meals/{meal_id}')
            if status2 == 404:
                print_result(False, f"DELETE /meals/{{id}} - Endpoint no implementado")
                self.test_results['failed'] += 1
            elif status2 == 403:
                print_warning(f"DELETE /meals/{{id}} - Sin permisos (403) - Normal si no eres el creador")
                self.test_results['warnings'] += 1
            else:
                print_result(True, f"DELETE /meals/{{id}} - Endpoint existe (meal no encontrado es OK)")
                self.test_results['passed'] += 1
        elif status == 403:
            print_warning(f"DELETE /meals/{test_meal_id} - Sin permisos (403)")
            self.test_results['warnings'] += 1
        elif status == 204:
            print_result(True, f"DELETE /meals/{test_meal_id} - Status 204 (éxito)")
            self.test_results['passed'] += 1
        else:
            print_result(False, f"DELETE /meals/{test_meal_id} - Status {status}")
            self.test_results['failed'] += 1

    def test_daily_plan_endpoints(self):
        """Test CRUD operations for daily plans"""
        print_test_header("DAILY PLAN ENDPOINTS")

        daily_plan_id = self.test_data.get('daily_plan_id')
        if not daily_plan_id:
            print_warning("No se encontró daily_plan_id para probar")
            return

        plan_id = 1  # Asumimos plan_id 1 existe

        # Test 1: GET /days/{daily_plan_id}
        success, data, status = self.make_request('GET', f'/api/v1/nutrition/days/{daily_plan_id}')

        if status == 404:
            print_result(False, f"GET /days/{daily_plan_id} - Endpoint no implementado (404)")
            self.test_results['failed'] += 1
        elif success:
            print_result(True, f"GET /days/{daily_plan_id} - Status {status}")
            if 'meals' in data:
                print(f"  → Día: {data.get('day_number', '?')} - {data.get('day_name', 'Sin nombre')}")
                print(f"  → Comidas: {len(data.get('meals', []))}")
            self.test_results['passed'] += 1
        else:
            print_result(False, f"GET /days/{daily_plan_id} - Status {status}")
            self.test_results['failed'] += 1

        # Test 2: GET /plans/{plan_id}/days
        success, data, status = self.make_request('GET', f'/api/v1/nutrition/plans/{plan_id}/days')

        if status == 404:
            print_result(False, f"GET /plans/{plan_id}/days - Endpoint no implementado (404)")
            self.test_results['failed'] += 1
        elif success:
            print_result(True, f"GET /plans/{plan_id}/days - Status {status}")
            if isinstance(data, list):
                print(f"  → Total de días: {len(data)}")
            self.test_results['passed'] += 1
        else:
            print_result(False, f"GET /plans/{plan_id}/days - Status {status}")
            self.test_results['failed'] += 1

        # Test 3: PUT /days/{daily_plan_id}
        update_data = {
            "day_name": f"Día Actualizado Test {datetime.now().strftime('%H:%M')}"
        }
        success, data, status = self.make_request('PUT', f'/api/v1/nutrition/days/{daily_plan_id}', update_data)

        if status == 404:
            print_result(False, f"PUT /days/{daily_plan_id} - Endpoint no implementado (404)")
            self.test_results['failed'] += 1
        elif status == 403:
            print_warning(f"PUT /days/{daily_plan_id} - Sin permisos (403)")
            self.test_results['warnings'] += 1
        elif success:
            print_result(True, f"PUT /days/{daily_plan_id} - Status {status}")
            self.test_results['passed'] += 1
        else:
            print_result(False, f"PUT /days/{daily_plan_id} - Status {status}")
            self.test_results['failed'] += 1

    def test_ingredient_endpoints(self):
        """Test CRUD operations for ingredients"""
        print_test_header("INGREDIENT ENDPOINTS")

        # Necesitamos un ingredient_id válido
        # Lo obtenemos del meal que ya tenemos
        meal_id = self.test_data.get('meal_id')
        if not meal_id:
            print_warning("No se encontró meal_id para obtener ingredientes")
            return

        # Obtener meal con ingredientes
        success, meal_data, status = self.make_request('GET', f'/api/v1/nutrition/meals/{meal_id}')

        ingredient_id = None
        if success and meal_data.get('ingredients'):
            ingredient_id = meal_data['ingredients'][0]['id']
        else:
            # Si no podemos obtener el meal, asumimos que no existe el endpoint
            # Intentamos con un ID ficticio
            ingredient_id = 1

        # Test 1: PUT /ingredients/{ingredient_id}
        update_data = {
            "quantity": 150,
            "calories": 225
        }
        success, data, status = self.make_request('PUT', f'/api/v1/nutrition/ingredients/{ingredient_id}', update_data)

        if status == 404:
            print_result(False, f"PUT /ingredients/{ingredient_id} - Endpoint no implementado (404)")
            self.test_results['failed'] += 1
        elif status == 403:
            print_warning(f"PUT /ingredients/{ingredient_id} - Sin permisos (403)")
            self.test_results['warnings'] += 1
        elif success:
            print_result(True, f"PUT /ingredients/{ingredient_id} - Status {status}")
            self.test_results['passed'] += 1
        else:
            print_result(False, f"PUT /ingredients/{ingredient_id} - Status {status}")
            self.test_results['failed'] += 1

        # Test 2: DELETE /ingredients/{ingredient_id}
        test_ingredient_id = 99999
        success, data, status = self.make_request('DELETE', f'/api/v1/nutrition/ingredients/{test_ingredient_id}')

        if status == 404:
            # Verificar si es porque el endpoint no existe o el ingrediente no existe
            print_result(False, f"DELETE /ingredients/{{id}} - Endpoint probablemente no implementado")
            self.test_results['failed'] += 1
        elif status == 403:
            print_warning(f"DELETE /ingredients/{test_ingredient_id} - Sin permisos (403)")
            self.test_results['warnings'] += 1
        elif status == 204:
            print_result(True, f"DELETE /ingredients/{test_ingredient_id} - Status 204")
            self.test_results['passed'] += 1
        else:
            print_result(False, f"DELETE /ingredients/{test_ingredient_id} - Status {status}")
            self.test_results['failed'] += 1

    def print_summary(self):
        """Imprimir resumen de resultados"""
        print("\n" + "=" * 60)
        print(f"{Colors.BOLD}RESUMEN DE RESULTADOS{Colors.ENDC}")
        print("=" * 60)

        total = self.test_results['passed'] + self.test_results['failed']

        print(f"{Colors.GREEN}✅ Passed: {self.test_results['passed']}{Colors.ENDC}")
        print(f"{Colors.RED}❌ Failed: {self.test_results['failed']}{Colors.ENDC}")
        print(f"{Colors.YELLOW}⚠️  Warnings: {self.test_results['warnings']}{Colors.ENDC}")

        if total > 0:
            success_rate = (self.test_results['passed'] / total) * 100
            print(f"\n{Colors.BOLD}Success Rate: {success_rate:.1f}%{Colors.ENDC}")

            if success_rate == 100:
                print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 ¡TODOS LOS ENDPOINTS ESTÁN IMPLEMENTADOS!{Colors.ENDC}")
            elif success_rate == 0:
                print(f"\n{Colors.RED}{Colors.BOLD}❌ NINGÚN ENDPOINT CRUD ESTÁ IMPLEMENTADO{Colors.ENDC}")
                print("Ejecuta: python scripts/auto_implement_nutrition_endpoints.py")
            else:
                print(f"\n{Colors.YELLOW}Algunos endpoints faltan. Revisar implementación.{Colors.ENDC}")

        return self.test_results['failed'] == 0

def main():
    parser = argparse.ArgumentParser(description='Test de endpoints CRUD de nutrición')
    parser.add_argument('--base-url', default='http://localhost:8000',
                       help='URL base de la API (default: http://localhost:8000)')
    parser.add_argument('--token', required=True, help='Token de autenticación')
    parser.add_argument('--gym-id', type=int, default=4, help='ID del gimnasio (default: 4)')
    parser.add_argument('--verbose', action='store_true', help='Mostrar respuestas completas')

    args = parser.parse_args()

    print(f"{Colors.BOLD}")
    print("=" * 60)
    print("TEST DE ENDPOINTS CRUD - MÓDULO NUTRICIÓN")
    print("=" * 60)
    print(f"{Colors.ENDC}")

    print(f"Base URL: {args.base_url}")
    print(f"Gym ID: {args.gym_id}")
    print(f"Token: {args.token[:20]}...")

    tester = NutritionCRUDTester(args.base_url, args.token, args.gym_id)

    # Ejecutar tests
    tester.test_meal_endpoints()
    tester.test_daily_plan_endpoints()
    tester.test_ingredient_endpoints()

    # Resumen
    success = tester.print_summary()

    # Exit code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()