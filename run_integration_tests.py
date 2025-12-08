#!/usr/bin/env python3
"""
Runner de Tests de Integración - Migración Async

Este script ejecuta todos los tests de integración para validar
la migración async módulo por módulo.

Uso:
    python run_integration_tests.py --admin-token YOUR_ADMIN_TOKEN \
                                    --trainer-token YOUR_TRAINER_TOKEN \
                                    --member-token YOUR_MEMBER_TOKEN \
                                    --gym-id 1

O con variables de entorno:
    export TEST_ADMIN_TOKEN="your_admin_token"
    export TEST_TRAINER_TOKEN="your_trainer_token"
    export TEST_MEMBER_TOKEN="your_member_token"
    export TEST_GYM_ID="1"
    python run_integration_tests.py
"""
import sys
import os
import argparse
import subprocess
from pathlib import Path


def setup_env_vars(args):
    """Configurar variables de entorno desde argumentos"""
    if args.admin_token:
        os.environ["TEST_ADMIN_TOKEN"] = args.admin_token
    if args.trainer_token:
        os.environ["TEST_TRAINER_TOKEN"] = args.trainer_token
    if args.member_token:
        os.environ["TEST_MEMBER_TOKEN"] = args.member_token
    if args.gym_id:
        os.environ["TEST_GYM_ID"] = str(args.gym_id)
    if args.base_url:
        os.environ["TEST_API_BASE_URL"] = args.base_url


def check_configuration():
    """Verificar que la configuración esté completa"""
    required_vars = ["TEST_ADMIN_TOKEN", "TEST_TRAINER_TOKEN", "TEST_MEMBER_TOKEN"]
    missing = [var for var in required_vars if not os.getenv(var)]

    if missing:
        print("❌ ERROR: Faltan variables de entorno requeridas:")
        for var in missing:
            print(f"   - {var}")
        print("\nConfigure las variables de entorno o use argumentos:")
        print("   python run_integration_tests.py --admin-token TOKEN --trainer-token TOKEN --member-token TOKEN")
        return False

    print("✅ Configuración validada:")
    print(f"   API URL: {os.getenv('TEST_API_BASE_URL', 'https://gymapi-production.up.railway.app')}")
    print(f"   Gym ID: {os.getenv('TEST_GYM_ID', '1')}")
    print(f"   Admin Token: {os.getenv('TEST_ADMIN_TOKEN')[:20]}...")
    print(f"   Trainer Token: {os.getenv('TEST_TRAINER_TOKEN')[:20]}...")
    print(f"   Member Token: {os.getenv('TEST_MEMBER_TOKEN')[:20]}...")
    print()
    return True


def run_tests(modules=None, verbose=False):
    """Ejecutar tests con pytest"""
    cmd = ["pytest", "tests/integration/"]

    # Opciones de pytest
    cmd.extend(["-v"] if verbose else ["-q"])
    cmd.extend(["-s"])  # No capturar output (para ver prints)
    cmd.extend(["--tb=short"])  # Tracebacks cortos
    cmd.extend(["--asyncio-mode=auto"])  # Modo async automático

    # Filtrar por módulos específicos
    if modules:
        module_filters = [f"test_{m:02d}_" for m in modules]
        cmd.extend(["-k", " or ".join(module_filters)])

    print(f"🚀 Ejecutando: {' '.join(cmd)}\n")
    print("="*70)

    try:
        result = subprocess.run(cmd, cwd=Path(__file__).parent)
        return result.returncode == 0
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrumpidos por el usuario")
        return False


def print_summary():
    """Imprimir resumen y próximos pasos"""
    print("\n" + "="*70)
    print("📋 PRÓXIMOS PASOS")
    print("="*70)
    print("""
1. Revisar errores encontrados en los tests
2. Corregir código según errores detectados
3. Re-ejecutar tests hasta que todos pasen
4. Deploy a producción cuando tests estén en verde

Para ejecutar módulos específicos:
    python run_integration_tests.py --modules 1 2 3

Para modo verbose:
    python run_integration_tests.py --verbose

Módulos disponibles:
    1: Auth (CRÍTICO)
    2: Users (CRÍTICO)
    3: Gyms (CRÍTICO)
    4: Schedule (CRÍTICO)
    5: Events (IMPORTANTE)
    """)


def main():
    parser = argparse.ArgumentParser(
        description="Runner de tests de integración para migración async"
    )
    parser.add_argument(
        "--admin-token",
        help="Token de administrador de Auth0"
    )
    parser.add_argument(
        "--trainer-token",
        help="Token de entrenador de Auth0"
    )
    parser.add_argument(
        "--member-token",
        help="Token de miembro de Auth0"
    )
    parser.add_argument(
        "--gym-id",
        type=int,
        default=1,
        help="ID del gimnasio para tests (default: 1)"
    )
    parser.add_argument(
        "--base-url",
        help="URL base de la API (default: producción)"
    )
    parser.add_argument(
        "--modules",
        nargs="+",
        type=int,
        help="Módulos específicos a probar (ej: 1 2 3 4)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Modo verbose"
    )

    args = parser.parse_args()

    # Configurar variables de entorno
    setup_env_vars(args)

    # Verificar configuración
    if not check_configuration():
        sys.exit(1)

    # Ejecutar tests
    print("🧪 INICIANDO TESTS DE INTEGRACIÓN")
    print("="*70)

    if args.modules:
        print(f"📦 Ejecutando módulos: {', '.join(map(str, args.modules))}\n")
    else:
        print(f"📦 Ejecutando TODOS los módulos\n")

    success = run_tests(modules=args.modules, verbose=args.verbose)

    # Resumen
    print_summary()

    # Exit code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
