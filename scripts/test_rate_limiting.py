#!/usr/bin/env python3
"""
Script para probar que el rate limiting funciona correctamente.

Verifica que los endpoints críticos estén protegidos contra ataques DDoS
y que respondan con código 429 cuando se exceden los límites.
"""

import asyncio
import aiohttp
import time
import os
from typing import Dict, List, Tuple
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuración de la API
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
TEST_TOKEN = os.getenv("TEST_TOKEN", "")
GYM_ID = os.getenv("TEST_GYM_ID", "4")

# Headers para las pruebas
HEADERS = {
    "Content-Type": "application/json",
    "X-Gym-ID": GYM_ID
}

if TEST_TOKEN:
    HEADERS["Authorization"] = f"Bearer {TEST_TOKEN}"

# Endpoints a probar con sus límites esperados
ENDPOINTS_TO_TEST = {
    # Endpoints públicos (sin autenticación)
    "/api/v1/memberships/plans": {
        "method": "GET",
        "expected_limit": 200,  # api_read
        "requires_auth": False,
        "payload": None
    },
    
    # Endpoints de billing (críticos)
    "/api/v1/memberships/purchase": {
        "method": "POST", 
        "expected_limit": 5,  # billing_create
        "requires_auth": True,
        "payload": {
            "plan_id": 1,
            "success_url": "https://example.com/success",
            "cancel_url": "https://example.com/cancel"
        }
    },
    
    "/api/v1/memberships/webhooks/stripe": {
        "method": "POST",
        "expected_limit": 100,  # billing_webhook
        "requires_auth": False,
        "payload": {"test": "webhook"},
        "headers": {"stripe-signature": "test_signature"}
    },
    
    # Endpoints de usuarios
    "/api/v1/users/check-email-availability": {
        "method": "POST",
        "expected_limit": 10,  # rate limit específico
        "requires_auth": True,
        "payload": {"email": "test@example.com"}
    },
    
    "/api/v1/users/initiate-email-change": {
        "method": "POST", 
        "expected_limit": 3,  # rate limit específico
        "requires_auth": True,
        "payload": {"new_email": "newemail@example.com"}
    }
}

async def test_endpoint_rate_limit(
    session: aiohttp.ClientSession,
    endpoint: str,
    config: Dict,
    max_requests: int = 20
) -> Tuple[str, Dict]:
    """
    Probar rate limiting en un endpoint específico.
    
    Args:
        session: Sesión HTTP
        endpoint: URL del endpoint
        config: Configuración del endpoint
        max_requests: Número máximo de requests a enviar
        
    Returns:
        Tuple con el endpoint y resultados de la prueba
    """
    url = f"{API_BASE_URL}{endpoint}"
    method = config["method"]
    payload = config.get("payload")
    requires_auth = config.get("requires_auth", False)
    custom_headers = config.get("headers", {})
    
    # Preparar headers
    test_headers = HEADERS.copy()
    test_headers.update(custom_headers)
    
    # Si requiere autenticación pero no tenemos token, saltar
    if requires_auth and not TEST_TOKEN:
        return endpoint, {
            "status": "skipped",
            "reason": "No TEST_TOKEN provided for authenticated endpoint",
            "requests_sent": 0,
            "rate_limited": False
        }
    
    # Si no requiere autenticación, remover header de autorización
    if not requires_auth and "Authorization" in test_headers:
        del test_headers["Authorization"]
    
    results = {
        "status": "testing",
        "requests_sent": 0,
        "successful_requests": 0,
        "rate_limited_requests": 0,
        "error_requests": 0,
        "first_rate_limit_at": None,
        "rate_limited": False,
        "status_codes": []
    }
    
    logger.info(f"🧪 Probando {method} {endpoint} (límite esperado: {config['expected_limit']})")
    
    # Enviar requests rápidamente para activar rate limiting
    start_time = time.time()
    
    for i in range(max_requests):
        try:
            if method == "GET":
                async with session.get(url, headers=test_headers) as response:
                    status_code = response.status
            elif method == "POST":
                async with session.post(url, headers=test_headers, json=payload) as response:
                    status_code = response.status
            else:
                logger.warning(f"Método {method} no soportado para pruebas")
                break
            
            results["requests_sent"] += 1
            results["status_codes"].append(status_code)
            
            if status_code == 429:  # Rate limited
                results["rate_limited_requests"] += 1
                if not results["rate_limited"]:
                    results["rate_limited"] = True
                    results["first_rate_limit_at"] = i + 1
                    logger.info(f"   ✅ Rate limit activado en request #{i + 1}")
            elif 200 <= status_code < 300:
                results["successful_requests"] += 1
            else:
                results["error_requests"] += 1
                if i == 0:  # Primer request falló
                    logger.warning(f"   ⚠️  Primer request falló con {status_code}")
                    if status_code == 401:
                        results["status"] = "auth_error"
                        break
                    elif status_code == 404:
                        results["status"] = "not_found"
                        break
        
        except Exception as e:
            logger.error(f"   ❌ Error en request #{i + 1}: {e}")
            results["error_requests"] += 1
        
        # Pequeña pausa para no sobrecargar (pero suficientemente rápido para rate limiting)
        await asyncio.sleep(0.1)
    
    duration = time.time() - start_time
    
    # Evaluar resultados
    if results["rate_limited"]:
        results["status"] = "rate_limited_working"
        logger.info(f"   ✅ Rate limiting funcionando - primer límite en request #{results['first_rate_limit_at']}")
    elif results["successful_requests"] > 0:
        results["status"] = "no_rate_limit_detected"
        logger.warning(f"   ⚠️  No se detectó rate limiting después de {results['requests_sent']} requests")
    else:
        results["status"] = "failed"
        logger.error(f"   ❌ Endpoint no funcional")
    
    results["duration"] = duration
    results["requests_per_second"] = results["requests_sent"] / duration if duration > 0 else 0
    
    return endpoint, results

async def main():
    """Función principal para ejecutar todas las pruebas."""
    print("🚦 PRUEBAS DE RATE LIMITING - GYMAPI")
    print("=" * 60)
    
    if not TEST_TOKEN:
        print("⚠️  Advertencia: TEST_TOKEN no configurado - endpoints autenticados serán omitidos")
        print("   Para probar endpoints autenticados, configura: export TEST_TOKEN='tu_token_aqui'")
    
    print(f"🎯 Probando contra: {API_BASE_URL}")
    print(f"🏋️  Gimnasio ID: {GYM_ID}")
    print()
    
    # Crear sesión HTTP
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        
        # Ejecutar pruebas en paralelo para mayor eficiencia
        tasks = []
        for endpoint, config in ENDPOINTS_TO_TEST.items():
            task = test_endpoint_rate_limit(session, endpoint, config)
            tasks.append(task)
        
        # Esperar a que todas las pruebas terminen
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Procesar y mostrar resultados
        print("\n" + "=" * 60)
        print("📊 RESUMEN DE RESULTADOS")
        print("=" * 60)
        
        total_tests = 0
        working_rate_limits = 0
        failed_tests = 0
        skipped_tests = 0
        
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Error en prueba: {result}")
                failed_tests += 1
                continue
            
            endpoint, test_result = result
            total_tests += 1
            status = test_result["status"]
            
            if status == "rate_limited_working":
                print(f"✅ {endpoint}")
                print(f"   Rate limiting FUNCIONA - límite en request #{test_result['first_rate_limit_at']}")
                print(f"   Requests: {test_result['successful_requests']} exitosos, {test_result['rate_limited_requests']} limitados")
                working_rate_limits += 1
                
            elif status == "no_rate_limit_detected":
                print(f"⚠️  {endpoint}")
                print(f"   Rate limiting NO DETECTADO - {test_result['requests_sent']} requests enviados")
                print(f"   Todos los requests fueron exitosos - posible vulnerabilidad")
                
            elif status == "skipped":
                print(f"⏭️  {endpoint}")
                print(f"   OMITIDO - {test_result['reason']}")
                skipped_tests += 1
                
            elif status == "auth_error":
                print(f"🔐 {endpoint}")
                print(f"   Error de autenticación - verificar token")
                
            elif status == "not_found":
                print(f"❓ {endpoint}")
                print(f"   Endpoint no encontrado - verificar URL")
                
            else:
                print(f"❌ {endpoint}")
                print(f"   FALLÓ - {test_result.get('error_requests', 0)} errores")
                failed_tests += 1
            
            print()
        
        # Resumen final
        print("=" * 60)
        print("🎯 RESUMEN FINAL")
        print(f"   Total de pruebas: {total_tests}")
        print(f"   Rate limiting funcionando: {working_rate_limits}")
        print(f"   Fallos: {failed_tests}")
        print(f"   Omitidas: {skipped_tests}")
        
        if working_rate_limits == total_tests - skipped_tests - failed_tests:
            print("\n🎉 ¡Todas las pruebas de rate limiting pasaron!")
            return True
        else:
            print(f"\n⚠️  {total_tests - working_rate_limits - skipped_tests} endpoints sin rate limiting detectado")
            return False

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1) 