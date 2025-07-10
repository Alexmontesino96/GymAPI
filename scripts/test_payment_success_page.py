#!/usr/bin/env python3
"""
Script para probar la página de éxito mejorada con procesamiento automático
"""
import os
import sys
import requests
import time
from datetime import datetime

# Agregar el directorio padre al path para importar módulos
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_settings

def main():
    print("🧪 Probando página de éxito mejorada...")
    print("=" * 50)
    
    settings = get_settings()
    base_url = settings.BASE_URL or "http://localhost:8000"
    
    # Casos de prueba
    test_cases = [
        {
            "name": "Página sin session_id",
            "url": f"{base_url}/membership/success",
            "expected_content": ["¡Pago Completado!", "Tu pago ha sido procesado exitosamente"]
        },
        {
            "name": "Página con session_id inválido",
            "url": f"{base_url}/membership/success?session_id=cs_invalid_session",
            "expected_content": ["Error Procesando Pago", "Hubo un problema procesando tu pago"]
        },
        {
            "name": "Página con session_id de prueba",
            "url": f"{base_url}/membership/success?session_id=cs_test_b1lEiGNhCdNibHT1WX7IQkKdgO0ZJBB1P4LosQc9yeGNA0CqPUqervc3uV",
            "expected_content": ["ID de Sesión:", "cs_test_"]
        }
    ]
    
    print("\n🔍 Ejecutando casos de prueba:")
    print("-" * 30)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. {test_case['name']}")
        print(f"   URL: {test_case['url']}")
        
        try:
            # Hacer petición GET a la página
            response = requests.get(test_case['url'], timeout=10)
            
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                content = response.text
                
                # Verificar contenido esperado
                found_content = []
                missing_content = []
                
                for expected in test_case['expected_content']:
                    if expected in content:
                        found_content.append(expected)
                    else:
                        missing_content.append(expected)
                
                if found_content:
                    print(f"   ✅ Contenido encontrado: {found_content}")
                
                if missing_content:
                    print(f"   ❌ Contenido faltante: {missing_content}")
                
                # Verificar elementos específicos
                if "success-icon" in content:
                    print("   ✅ Icono de éxito presente")
                elif "error-icon" in content:
                    print("   ⚠️ Icono de error presente")
                elif "processing-icon" in content:
                    print("   ⏳ Icono de procesamiento presente")
                
                # Verificar botones
                if 'href="/"' in content:
                    print("   ✅ Botón 'Volver a la App' presente")
                if 'href="/membership/my-status"' in content:
                    print("   ✅ Botón 'Ver Mi Membresía' presente")
                
                # Verificar JavaScript de auto-recarga
                if "setTimeout" in content and "window.location.reload" in content:
                    print("   ✅ Auto-recarga configurada")
                
            else:
                print(f"   ❌ Error HTTP: {response.status_code}")
                print(f"   Respuesta: {response.text[:200]}...")
                
        except requests.exceptions.RequestException as e:
            print(f"   ❌ Error de conexión: {e}")
        except Exception as e:
            print(f"   ❌ Error inesperado: {e}")
    
    print("\n" + "=" * 50)
    print("🧪 Pruebas de funcionalidad específica:")
    print("-" * 30)
    
    # Probar procesamiento automático (simulado)
    print("\n🔄 Simulando procesamiento automático...")
    test_url = f"{base_url}/membership/success?session_id=cs_test_example"
    
    try:
        start_time = time.time()
        response = requests.get(test_url, timeout=15)
        processing_time = time.time() - start_time
        
        print(f"   Tiempo de procesamiento: {processing_time:.2f}s")
        
        if response.status_code == 200:
            content = response.text
            
            # Analizar tipo de respuesta
            if "Tu membresía ha sido activada exitosamente" in content:
                print("   ✅ Membresía activada exitosamente")
            elif "Error procesando el pago" in content:
                print("   ⚠️ Error en procesamiento (esperado para session_id de prueba)")
            elif "Procesando Pago..." in content:
                print("   ⏳ Página en estado de procesamiento")
            
            # Verificar metadatos
            if "membership-info" in content:
                print("   ✅ Información de membresía presente")
            if "error-info" in content:
                print("   ⚠️ Información de error presente")
            
        else:
            print(f"   ❌ Error HTTP: {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Error en prueba de procesamiento: {e}")
    
    print("\n" + "=" * 50)
    print("📊 Análisis de rendimiento:")
    print("-" * 30)
    
    # Probar múltiples peticiones
    print("\n⚡ Probando múltiples peticiones...")
    
    times = []
    success_count = 0
    
    for i in range(5):
        try:
            start_time = time.time()
            response = requests.get(f"{base_url}/membership/success", timeout=5)
            end_time = time.time()
            
            if response.status_code == 200:
                success_count += 1
                times.append(end_time - start_time)
                
        except Exception as e:
            print(f"   ❌ Error en petición {i+1}: {e}")
    
    if times:
        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)
        
        print(f"   ✅ Peticiones exitosas: {success_count}/5")
        print(f"   ⏱️ Tiempo promedio: {avg_time:.3f}s")
        print(f"   🚀 Tiempo mínimo: {min_time:.3f}s")
        print(f"   🐌 Tiempo máximo: {max_time:.3f}s")
    
    print("\n" + "=" * 50)
    print("🔍 Recomendaciones:")
    print("-" * 30)
    
    print("\n✅ Funcionalidades implementadas:")
    print("   • Procesamiento automático del session_id")
    print("   • Páginas dinámicas según estado del pago")
    print("   • Manejo de errores con reintentos")
    print("   • Información detallada de membresía")
    print("   • Auto-recarga en caso de procesamiento pendiente")
    print("   • Botones de navegación contextuales")
    
    print("\n🔧 Para producción:")
    print("   • Configurar URLs de success_url en Stripe")
    print("   • Verificar que el webhook esté funcionando")
    print("   • Monitorear logs de procesamiento")
    print("   • Probar con session_ids reales de Stripe")
    print("   • Configurar notificaciones de error")
    
    print("\n✅ Pruebas completadas!")

if __name__ == "__main__":
    main() 