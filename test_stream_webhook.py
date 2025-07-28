#!/usr/bin/env python3
"""
Script para probar los webhooks de Stream y verificar conectividad
"""
import requests
import json
import time
from datetime import datetime

# URL base de tu API
BASE_URL = "https://gymapi-eh6m.onrender.com/api/v1/webhooks"

def test_health_check():
    """Probar el health check del webhook"""
    print("🩺 Testing health check...")
    
    try:
        response = requests.get(f"{BASE_URL}/stream/health", timeout=10)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error en health check: {e}")
        return False

def test_basic_webhook():
    """Probar el endpoint de test sin verificación de firma"""
    print("\n🧪 Testing basic webhook...")
    
    test_payload = {
        "type": "test",
        "message": "Test desde script de diagnóstico",
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/stream/test",
            json=test_payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error en test webhook: {e}")
        return False

def test_debug_webhook():
    """Probar el endpoint de debug"""
    print("\n🐛 Testing debug webhook...")
    
    debug_payload = {
        "debug": True,
        "test_headers": True,
        "timestamp": datetime.now().isoformat(),
        "source": "test_script"
    }
    
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "StreamWebhookTester/1.0",
        "X-Test-Header": "TestValue",
        "X-Source": "DiagnosticScript"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/stream/debug",
            json=debug_payload,
            headers=headers,
            timeout=10
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error en debug webhook: {e}")
        return False

def test_main_webhook_without_signature():
    """Intentar llamar al webhook principal (fallará por signature pero veremos logs)"""
    print("\n⚠️  Testing main webhook (sin signature - esperamos error 401)...")
    
    mock_stream_payload = {
        "type": "message.new",
        "message": {
            "id": "test-msg-123",
            "text": "Mensaje de prueba desde script",
            "user": {
                "id": "user_123",
                "name": "Test User"
            },
            "created_at": datetime.now().isoformat()
        },
        "channel": {
            "id": "test-channel-123",
            "type": "messaging"
        }
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/stream/new-message",
            json=mock_stream_payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        # Esperamos 401 porque no hay signature
        return response.status_code == 401
    except Exception as e:
        print(f"❌ Error en main webhook: {e}")
        return False

def main():
    """Ejecutar todas las pruebas"""
    print("🚀 Iniciando pruebas de webhooks de Stream...")
    print(f"🌐 Base URL: {BASE_URL}")
    print("=" * 60)
    
    tests = [
        ("Health Check", test_health_check),
        ("Basic Webhook", test_basic_webhook), 
        ("Debug Webhook", test_debug_webhook),
        ("Main Webhook (sin signature)", test_main_webhook_without_signature)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n📋 Ejecutando: {test_name}")
        try:
            result = test_func()
            results.append((test_name, result))
            status = "✅ PASSED" if result else "❌ FAILED"
            print(f"Resultado: {status}")
        except Exception as e:
            results.append((test_name, False))
            print(f"❌ FAILED: {e}")
        
        time.sleep(1)  # Pausa entre tests
    
    # Resumen
    print("\n" + "=" * 60)
    print("📊 RESUMEN DE PRUEBAS:")
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"  {test_name}: {status}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    print(f"\n🎯 Resultado: {passed}/{total} pruebas exitosas")
    
    if passed == total:
        print("🎉 Todos los tests pasaron! El endpoint está funcionando correctamente.")
    else:
        print("⚠️  Algunos tests fallaron. Revisa los logs del servidor para más detalles.")

if __name__ == "__main__":
    main()