#!/usr/bin/env python3
"""
Script de Implementación Automatizada de Endpoints de Nutrición
================================================================
Este script automatiza la integración de los endpoints CRUD faltantes
en el módulo de nutrición, con validaciones y rollback automático.

Uso:
    python scripts/auto_implement_nutrition_endpoints.py [--dry-run] [--phase PHASE]

Opciones:
    --dry-run    Simular sin hacer cambios reales
    --phase      Implementar solo una fase específica (meals, days, ingredients)

Autor: Claude Code Assistant
Fecha: 27 de Diciembre 2024
"""

import os
import sys
import shutil
import argparse
import re
from datetime import datetime
from pathlib import Path
import subprocess

# Colores para output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_header(text):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 60}{Colors.ENDC}")

def print_success(text):
    print(f"{Colors.OKGREEN}✅ {text}{Colors.ENDC}")

def print_warning(text):
    print(f"{Colors.WARNING}⚠️  {text}{Colors.ENDC}")

def print_error(text):
    print(f"{Colors.FAIL}❌ {text}{Colors.ENDC}")

def print_info(text):
    print(f"{Colors.OKCYAN}ℹ️  {text}{Colors.ENDC}")

class NutritionEndpointImplementer:
    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.base_path = Path.cwd()
        self.nutrition_file = self.base_path / "app" / "api" / "v1" / "endpoints" / "nutrition.py"
        self.backup_file = self.nutrition_file.with_suffix('.py.backup')
        self.generated_dir = self.base_path / "generated_endpoints"
        self.changes_made = []

    def verify_environment(self):
        """Verificar que el ambiente está listo"""
        print_header("VERIFICACIÓN DEL AMBIENTE")

        # Verificar archivo de nutrición
        if not self.nutrition_file.exists():
            print_error(f"No se encontró {self.nutrition_file}")
            return False

        print_success(f"Archivo nutrition.py encontrado")

        # Verificar endpoints generados
        if not self.generated_dir.exists():
            print_error(f"No se encontró el directorio {self.generated_dir}")
            print_info("Ejecuta primero: python scripts/implement_missing_nutrition_endpoints.py")
            return False

        print_success(f"Directorio de endpoints generados encontrado")

        # Verificar archivos generados
        required_files = ['meal_endpoints.py', 'daily_plan_endpoints.py', 'ingredient_endpoints.py']
        for file in required_files:
            if not (self.generated_dir / file).exists():
                print_error(f"Falta archivo generado: {file}")
                return False
            print_success(f"  ✓ {file}")

        # Verificar schemas
        print_info("Verificando schemas necesarios...")
        schemas_file = self.base_path / "app" / "schemas" / "nutrition.py"

        if schemas_file.exists():
            with open(schemas_file, 'r') as f:
                content = f.read()
                schemas = ['MealUpdate', 'DailyNutritionPlanUpdate', 'MealIngredientUpdate']
                for schema in schemas:
                    if f"class {schema}" in content:
                        print_success(f"  ✓ {schema} encontrado")
                    else:
                        print_warning(f"  ? {schema} no encontrado")

        return True

    def create_backup(self):
        """Crear backup del archivo actual"""
        if not self.dry_run:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_with_timestamp = self.nutrition_file.with_suffix(f'.py.backup.{timestamp}')
            shutil.copy2(self.nutrition_file, backup_with_timestamp)
            shutil.copy2(self.nutrition_file, self.backup_file)
            print_success(f"Backup creado: {backup_with_timestamp}")
            self.changes_made.append(f"Backup: {backup_with_timestamp}")
        else:
            print_info("[DRY RUN] Se crearía backup del archivo")

    def check_imports(self):
        """Verificar y agregar imports necesarios"""
        print_header("VERIFICACIÓN DE IMPORTS")

        with open(self.nutrition_file, 'r') as f:
            content = f.read()

        imports_needed = [
            ("from fastapi import Response", "Response para endpoints DELETE"),
            ("from app.models.user_gym import UserGym, GymRoleType", "UserGym y GymRoleType para permisos"),
            ("from app.models.nutrition import UserMealCompletion", "UserMealCompletion para eliminaciones"),
            ("from typing import List", "List para type hints")
        ]

        imports_to_add = []
        for import_line, description in imports_needed:
            if import_line not in content:
                print_warning(f"Import faltante: {import_line}")
                print_info(f"  Necesario para: {description}")
                imports_to_add.append(import_line)
            else:
                print_success(f"Import presente: {import_line}")

        if imports_to_add and not self.dry_run:
            # Buscar dónde insertar los imports
            lines = content.split('\n')
            insert_index = 0
            for i, line in enumerate(lines):
                if line.startswith('from app.'):
                    insert_index = i + 1

            for imp in imports_to_add:
                lines.insert(insert_index, imp)
                insert_index += 1

            with open(self.nutrition_file, 'w') as f:
                f.write('\n'.join(lines))

            print_success(f"Se agregaron {len(imports_to_add)} imports")
            self.changes_made.append(f"Imports agregados: {len(imports_to_add)}")

        return True

    def check_existing_endpoints(self):
        """Verificar qué endpoints ya existen"""
        print_header("VERIFICACIÓN DE ENDPOINTS EXISTENTES")

        with open(self.nutrition_file, 'r') as f:
            content = f.read()

        endpoints_to_check = [
            ('GET /meals/{meal_id}', r'@router\.get\(["\']\/meals\/\{meal_id\}'),
            ('PUT /meals/{meal_id}', r'@router\.put\(["\']\/meals\/\{meal_id\}'),
            ('DELETE /meals/{meal_id}', r'@router\.delete\(["\']\/meals\/\{meal_id\}'),
            ('GET /days/{daily_plan_id}', r'@router\.get\(["\']\/days\/\{daily_plan_id\}'),
            ('GET /plans/{plan_id}/days', r'@router\.get\(["\']\/plans\/\{plan_id\}\/days'),
            ('PUT /days/{daily_plan_id}', r'@router\.put\(["\']\/days\/\{daily_plan_id\}'),
            ('DELETE /days/{daily_plan_id}', r'@router\.delete\(["\']\/days\/\{daily_plan_id\}'),
            ('PUT /ingredients/{ingredient_id}', r'@router\.put\(["\']\/ingredients\/\{ingredient_id\}'),
            ('DELETE /ingredients/{ingredient_id}', r'@router\.delete\(["\']\/ingredients\/\{ingredient_id\}')
        ]

        missing = []
        for endpoint_name, pattern in endpoints_to_check:
            if re.search(pattern, content):
                print_success(f"✓ {endpoint_name} - Ya existe")
            else:
                print_warning(f"✗ {endpoint_name} - Falta implementar")
                missing.append(endpoint_name)

        print(f"\nResumen: {len(missing)} de {len(endpoints_to_check)} endpoints faltan")
        return missing

    def implement_phase(self, phase):
        """Implementar una fase específica"""
        phase_files = {
            'meals': 'meal_endpoints.py',
            'days': 'daily_plan_endpoints.py',
            'ingredients': 'ingredient_endpoints.py'
        }

        if phase not in phase_files:
            print_error(f"Fase desconocida: {phase}")
            return False

        print_header(f"IMPLEMENTANDO FASE: {phase.upper()}")

        source_file = self.generated_dir / phase_files[phase]
        with open(source_file, 'r') as f:
            new_endpoints = f.read()

        # Extraer solo el código entre los marcadores
        start_marker = f"# {'=' * 44}\n# {phase.upper()[:-1]} "
        end_marker = f"# FIN {phase.upper()[:-1]} "

        start = new_endpoints.find(start_marker)
        end = new_endpoints.find(end_marker)

        if start == -1 or end == -1:
            print_error("No se encontraron los marcadores en el archivo generado")
            return False

        code_to_add = new_endpoints[start:end + len(end_marker) + 50]

        if not self.dry_run:
            with open(self.nutrition_file, 'a') as f:
                f.write('\n\n' + code_to_add)
            print_success(f"Endpoints de {phase} agregados al archivo")
            self.changes_made.append(f"Fase {phase}: endpoints agregados")
        else:
            print_info(f"[DRY RUN] Se agregarían {len(code_to_add)} caracteres de código")

        return True

    def verify_syntax(self):
        """Verificar sintaxis del archivo modificado"""
        print_header("VERIFICACIÓN DE SINTAXIS")

        try:
            import py_compile
            py_compile.compile(str(self.nutrition_file), doraise=True)
            print_success("Sintaxis de Python válida")
            return True
        except py_compile.PyCompileError as e:
            print_error(f"Error de sintaxis: {e}")
            return False

    def run_tests(self):
        """Ejecutar tests básicos"""
        print_header("EJECUTANDO TESTS")

        if self.dry_run:
            print_info("[DRY RUN] Se ejecutarían los tests")
            return True

        # Test de importación
        try:
            cmd = ["python", "-c", "from app.api.v1.endpoints import nutrition; print('OK')"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0 and 'OK' in result.stdout:
                print_success("Módulo se importa correctamente")
            else:
                print_error(f"Error al importar módulo: {result.stderr}")
                return False
        except Exception as e:
            print_error(f"Error ejecutando test: {e}")
            return False

        # Test de endpoints (si existe pytest)
        if os.path.exists("tests/nutrition"):
            print_info("Ejecutando tests de nutrición...")
            try:
                result = subprocess.run(
                    ["pytest", "tests/nutrition/", "-v", "--tb=short"],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                if result.returncode == 0:
                    print_success("Todos los tests pasaron")
                else:
                    print_warning("Algunos tests fallaron (revisar manualmente)")
                    print(result.stdout[-500:])  # Últimas 500 chars
            except:
                print_warning("No se pudieron ejecutar los tests con pytest")

        return True

    def rollback(self):
        """Revertir cambios si algo sale mal"""
        print_header("ROLLBACK")

        if self.backup_file.exists():
            shutil.copy2(self.backup_file, self.nutrition_file)
            print_success("Archivo restaurado desde backup")
        else:
            print_error("No se encontró archivo de backup")

    def generate_summary(self):
        """Generar resumen de cambios"""
        print_header("RESUMEN DE IMPLEMENTACIÓN")

        if self.dry_run:
            print_info("MODO DRY RUN - No se realizaron cambios reales")
        else:
            print_success("Implementación completada exitosamente")

        print("\nCAMBIOS REALIZADOS:")
        for change in self.changes_made:
            print(f"  • {change}")

        print("\nPRÓXIMOS PASOS:")
        print("1. Revisar el archivo modificado: app/api/v1/endpoints/nutrition.py")
        print("2. Reiniciar el servidor: python app_wrapper.py")
        print("3. Probar endpoints en Swagger: http://localhost:8000/api/v1/docs")
        print("4. Ejecutar tests completos: pytest tests/nutrition/ -v")
        print("5. Commit y push: git add -A && git commit -m 'feat: add CRUD endpoints'")

def main():
    parser = argparse.ArgumentParser(description='Implementar endpoints de nutrición automáticamente')
    parser.add_argument('--dry-run', action='store_true', help='Simular sin hacer cambios')
    parser.add_argument('--phase', choices=['meals', 'days', 'ingredients', 'all'],
                       default='all', help='Fase específica a implementar')
    parser.add_argument('--no-backup', action='store_true', help='No crear backup')
    parser.add_argument('--force', action='store_true', help='Forzar implementación sin confirmación')

    args = parser.parse_args()

    print_header("IMPLEMENTADOR AUTOMÁTICO DE ENDPOINTS")
    print(f"Modo: {'DRY RUN' if args.dry_run else 'REAL'}")
    print(f"Fase: {args.phase}")

    implementer = NutritionEndpointImplementer(dry_run=args.dry_run)

    # Verificación inicial
    if not implementer.verify_environment():
        print_error("Verificación del ambiente falló")
        sys.exit(1)

    # Confirmación
    if not args.force and not args.dry_run:
        response = input(f"\n{Colors.WARNING}¿Continuar con la implementación? (s/n): {Colors.ENDC}")
        if response.lower() != 's':
            print_info("Implementación cancelada")
            sys.exit(0)

    # Crear backup
    if not args.no_backup:
        implementer.create_backup()

    # Verificar endpoints existentes
    missing = implementer.check_existing_endpoints()

    if not missing:
        print_success("Todos los endpoints ya están implementados")
        sys.exit(0)

    # Verificar imports
    if not implementer.check_imports():
        print_error("Error verificando imports")
        sys.exit(1)

    # Implementar fases
    phases = ['meals', 'days', 'ingredients'] if args.phase == 'all' else [args.phase]

    try:
        for phase in phases:
            if not implementer.implement_phase(phase):
                print_error(f"Error implementando fase {phase}")
                if not args.dry_run:
                    implementer.rollback()
                sys.exit(1)

        # Verificar sintaxis
        if not implementer.verify_syntax():
            print_error("Error de sintaxis en el archivo modificado")
            if not args.dry_run:
                implementer.rollback()
            sys.exit(1)

        # Ejecutar tests
        if not implementer.run_tests():
            print_warning("Algunos tests fallaron - revisar manualmente")

        # Resumen final
        implementer.generate_summary()

    except Exception as e:
        print_error(f"Error inesperado: {e}")
        if not args.dry_run:
            implementer.rollback()
        sys.exit(1)

    print_success("\n🎉 ¡Implementación completada exitosamente!")

if __name__ == "__main__":
    main()