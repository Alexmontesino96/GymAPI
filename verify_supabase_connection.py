#!/usr/bin/env python3
"""
Script para verificar que la conexión con Supabase Transaction Pooler funciona correctamente.
Ejecutar después de actualizar DATABASE_URL con puerto 6543.
"""

import os
import time
from sqlalchemy import create_engine, text, pool
from sqlalchemy.pool import NullPool, QueuePool
import sys

def verify_connection():
    """Verificar configuración de conexión con Supabase"""

    print("\n" + "="*60)
    print("🔍 VERIFICACIÓN DE CONEXIÓN SUPABASE TRANSACTION POOLER")
    print("="*60 + "\n")

    # 1. Verificar DATABASE_URL
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ ERROR: DATABASE_URL no está configurada")
        return False

    # Ocultar password para logging
    if '@' in db_url:
        visible_url = db_url.split('@')[1]
    else:
        visible_url = db_url

    print(f"📊 DATABASE_URL detectada: ...@{visible_url}")

    # 2. Verificar que usa puerto 6543 (Transaction Pooler)
    if "6543" in db_url:
        print("✅ Puerto 6543 detectado (Transaction Pooler)")
    else:
        print("⚠️  ADVERTENCIA: No se detecta puerto 6543")
        print("   Deberías usar: postgresql://...@....pooler.supabase.com:6543/postgres")

    # 3. Verificar que detecta Supabase correctamente
    is_supabase = "supabase" in db_url or "pooler" in db_url or "6543" in db_url

    if is_supabase:
        print("✅ Configuración Supabase/PgBouncer detectada")
        print("   → Usará NullPool (correcto para Transaction Pooler)")
    else:
        print("⚠️  No se detecta como Supabase - usará pool incorrecto")

    # 4. Test de conexión con configuración correcta
    print("\n🔧 Probando conexión con configuración optimizada...")

    try:
        if is_supabase:
            # Configuración para Supabase
            engine = create_engine(
                db_url,
                poolclass=NullPool,  # Crítico para PgBouncer
                connect_args={
                    "keepalives": 1,
                    "keepalives_idle": 10,
                    "keepalives_interval": 5,
                    "keepalives_count": 3,
                    "connect_timeout": 10,
                    "options": "-c statement_timeout=30000"
                },
                pool_pre_ping=False  # No ping con NullPool
            )
            print("   Configuración: NullPool (sin pool local)")
        else:
            # Configuración normal
            engine = create_engine(
                db_url,
                poolclass=QueuePool,
                pool_size=10,
                pool_pre_ping=True
            )
            print("   Configuración: QueuePool (con pool local)")

        # 5. Ejecutar queries de prueba
        print("\n📝 Ejecutando queries de prueba...")

        with engine.connect() as conn:
            # Test 1: Query simple
            start = time.time()
            result = conn.execute(text("SELECT 1"))
            latency1 = (time.time() - start) * 1000
            print(f"   Query 1: SELECT 1 → {latency1:.2f}ms")

            # Test 2: SET search_path (donde fallaba antes)
            start = time.time()
            conn.execute(text("SET search_path TO public"))
            latency2 = (time.time() - start) * 1000
            print(f"   Query 2: SET search_path → {latency2:.2f}ms")

            # Test 3: Query con información de conexión
            result = conn.execute(text("""
                SELECT
                    current_database() as database,
                    current_user as user,
                    inet_server_addr() as server,
                    pg_backend_pid() as pid,
                    version() as version
            """))
            info = result.fetchone()

            print(f"\n📊 Información de conexión:")
            print(f"   Database: {info[0]}")
            print(f"   Usuario: {info[1]}")
            print(f"   Servidor: {info[2]}")
            print(f"   PID: {info[3]}")
            print(f"   Version: {info[4][:50]}...")

            # Test 4: Verificar pooler
            result = conn.execute(text("SHOW server_version"))
            version = result.fetchone()[0]
            if "pgbouncer" in version.lower():
                print(f"   ✅ PgBouncer detectado: {version}")

            # Test 5: Múltiples conexiones rápidas (test de estabilidad)
            print("\n🔄 Test de estabilidad (10 conexiones rápidas)...")
            latencies = []
            for i in range(10):
                with engine.connect() as test_conn:
                    start = time.time()
                    test_conn.execute(text("SELECT 1"))
                    latency = (time.time() - start) * 1000
                    latencies.append(latency)
                    print(f"   Conexión {i+1}: {latency:.2f}ms", end="")
                    if latency > 100:
                        print(" ⚠️ LENTA")
                    else:
                        print(" ✅")

            avg_latency = sum(latencies) / len(latencies)
            max_latency = max(latencies)
            min_latency = min(latencies)

            print(f"\n📈 Estadísticas de latencia:")
            print(f"   Promedio: {avg_latency:.2f}ms")
            print(f"   Mínima: {min_latency:.2f}ms")
            print(f"   Máxima: {max_latency:.2f}ms")

            if avg_latency < 50:
                print("   ✅ Rendimiento EXCELENTE")
            elif avg_latency < 100:
                print("   ✅ Rendimiento BUENO")
            elif avg_latency < 200:
                print("   ⚠️ Rendimiento ACEPTABLE (considerar optimizar)")
            else:
                print("   ❌ Rendimiento POBRE (requiere optimización)")

        print("\n" + "="*60)
        print("✅ CONEXIÓN VERIFICADA EXITOSAMENTE")
        print("="*60)

        # 6. Recomendaciones finales
        print("\n💡 RECOMENDACIONES:")
        if is_supabase:
            print("✅ Configuración correcta para Supabase Transaction Pooler")
            print("✅ Usando NullPool (sin pool local)")
            print("✅ Puerto 6543 configurado")
        else:
            print("⚠️ Actualizar DATABASE_URL para usar puerto 6543")

        print("\n📝 Variables de entorno recomendadas para Render:")
        print("   SQLALCHEMY_POOL_SIZE=0  # Forzar NullPool")
        print("   SQLALCHEMY_MAX_OVERFLOW=0")
        print("   DATABASE_POOL_URL=<tu-url-con-6543>")

        return True

    except Exception as e:
        print(f"\n❌ ERROR al conectar: {e}")
        print("\nPosibles causas:")
        print("1. DATABASE_URL incorrecta")
        print("2. Credenciales inválidas")
        print("3. Firewall/Network issues")
        print("4. Límite de conexiones alcanzado")

        return False


def check_env_vars():
    """Verificar variables de entorno relacionadas"""
    print("\n📋 Variables de entorno detectadas:")

    important_vars = [
        "DATABASE_URL",
        "SQLALCHEMY_POOL_SIZE",
        "SQLALCHEMY_MAX_OVERFLOW",
        "REDIS_URL",
        "PORT",
        "TRUST_PROXY_HEADERS"
    ]

    for var in important_vars:
        value = os.getenv(var)
        if value:
            # Ocultar valores sensibles
            if "URL" in var and "@" in value:
                # Ocultar credenciales
                parts = value.split('@')
                if len(parts) > 1:
                    value = "***@" + parts[1]
            print(f"   {var}: {value}")
        else:
            print(f"   {var}: ❌ No configurada")


if __name__ == "__main__":
    # Si se pasa una DATABASE_URL como argumento, usarla
    if len(sys.argv) > 1:
        os.environ["DATABASE_URL"] = sys.argv[1]
        print(f"Usando DATABASE_URL proporcionada")

    check_env_vars()

    success = verify_connection()

    if success:
        print("\n✅ Todo listo para producción en Render!")
        sys.exit(0)
    else:
        print("\n❌ Hay problemas que resolver antes del deploy")
        sys.exit(1)