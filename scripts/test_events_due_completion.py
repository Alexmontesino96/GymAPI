#!/usr/bin/env python3
"""
Script para probar el endpoint /api/v1/worker/events/due-completion
que verifica si hay eventos pendientes de completar.

Este script permite diagnosticar problemas de conexión, autenticación
y procesamiento en el endpoint.
"""

import sys
import os
import requests
import json
import argparse
from datetime import datetime
import time

# Añadir el directorio raíz al path para poder importar los módulos de la aplicación
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Intentar importar la configuración de la aplicación
try:
    from app.core.config import get_settings
    settings = get_settings()
    DEFAULT_API_URL = settings.API_URL or "http://localhost:8000"
    DEFAULT_API_KEY = settings.WORKER_API_KEY
    print(f"Cargada configuración de la aplicación")
except Exception as e:
    print(f"No se pudo cargar la configuración: {e}")
    DEFAULT_API_URL = "http://localhost:8000"
    DEFAULT_API_KEY = None

def test_events_due_completion(api_url, api_key, timeout=10, verbose=False):
    """
    Prueba el endpoint de eventos pendientes de completar.
    
    Args:
        api_url: URL base de la API (ej: https://api.ejemplo.com)
        api_key: Clave API para autenticación
        timeout: Tiempo máximo de espera para la respuesta (segundos)
        verbose: Si se debe mostrar información detallada
    
    Returns:
        dict: Información del resultado de la prueba
    """
    # Construir la URL del endpoint
    endpoint = f"{api_url}/api/v1/worker/events/due-completion"
    
    # Construir headers
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    if api_key:
        headers["X-API-Key"] = api_key
    
    print(f"\n{'='*50}")
    print(f"PRUEBA DE ENDPOINT: {endpoint}")
    print(f"{'='*50}")
    print(f"Fecha/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Headers:")
    for key, value in headers.items():
        if key == "X-API-Key":
            # Enmascarar la API key
            masked_key = value[:4] + "..." + value[-4:] if len(value) > 8 else "***"
            print(f"  {key}: {masked_key}")
        else:
            print(f"  {key}: {value}")
    
    # Realizar la solicitud
    start_time = time.time()
    try:
        print(f"\nRealizando solicitud GET...", flush=True)
        response = requests.get(
            endpoint,
            headers=headers,
            timeout=timeout
        )
        request_time = time.time() - start_time
        
        # Mostrar resultado
        print(f"\nRespuesta recibida en {request_time:.2f} segundos")
        print(f"Código de estado: {response.status_code}")
        print(f"Headers de respuesta:")
        for key, value in response.headers.items():
            print(f"  {key}: {value}")
        
        # Parsear respuesta JSON si es posible
        try:
            json_response = response.json()
            if verbose:
                print(f"\nContenido JSON de la respuesta:")
                print(json.dumps(json_response, indent=2, ensure_ascii=False))
            else:
                # Mostrar resumen
                if isinstance(json_response, list):
                    print(f"\nEventos encontrados: {len(json_response)}")
                    if json_response:
                        print(f"Primeros 3 eventos:")
                        for i, event in enumerate(json_response[:3]):
                            print(f"  {i+1}. ID: {event.get('id')}, Título: {event.get('title')}, Fin: {event.get('end_time')}")
                else:
                    print(f"\nRespuesta no es una lista de eventos:")
                    print(json.dumps(json_response, indent=2, ensure_ascii=False)[:500])
            
            return {
                "success": response.status_code < 400,
                "status_code": response.status_code,
                "time": request_time,
                "data": json_response
            }
            
        except json.JSONDecodeError:
            # Mostrar los primeros 1000 caracteres de la respuesta
            print(f"\nRespuesta no es JSON válido:")
            print(response.text[:1000])
            return {
                "success": False,
                "status_code": response.status_code,
                "time": request_time,
                "error": "Invalid JSON response"
            }
            
    except requests.RequestException as e:
        request_time = time.time() - start_time
        print(f"\nError de conexión: {str(e)}")
        return {
            "success": False,
            "time": request_time,
            "error": str(e)
        }
    except Exception as e:
        request_time = time.time() - start_time
        print(f"\nError inesperado: {str(e)}")
        return {
            "success": False,
            "time": request_time,
            "error": str(e)
        }

def main():
    parser = argparse.ArgumentParser(description='Prueba el endpoint de eventos pendientes de completar')
    
    parser.add_argument('--url', default=DEFAULT_API_URL,
                        help=f'URL base de la API (default: {DEFAULT_API_URL})')
    parser.add_argument('--api-key', default=DEFAULT_API_KEY,
                        help='API key para autenticación')
    parser.add_argument('--timeout', type=int, default=30,
                        help='Tiempo máximo de espera en segundos (default: 30)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Mostrar información detallada')
    
    args = parser.parse_args()
    
    # Verificar que se proporcionó una API key
    if not args.api_key:
        print("ADVERTENCIA: No se proporcionó una API key. La solicitud probablemente fallará con 401 Unauthorized.")
        choice = input("¿Desea continuar sin API key? (s/N): ")
        if choice.lower() != 's':
            print("Operación cancelada.")
            return
    
    # Ejecutar la prueba
    result = test_events_due_completion(
        api_url=args.url,
        api_key=args.api_key,
        timeout=args.timeout,
        verbose=args.verbose
    )
    
    # Mostrar resumen final
    print(f"\n{'='*50}")
    print(f"RESUMEN DE LA PRUEBA")
    print(f"{'='*50}")
    print(f"Éxito: {'Sí' if result.get('success') else 'No'}")
    print(f"Tiempo: {result.get('time', 0):.2f} segundos")
    if result.get('status_code'):
        print(f"Código de estado: {result['status_code']}")
    if result.get('error'):
        print(f"Error: {result['error']}")
    print(f"{'='*50}")

if __name__ == "__main__":
    main() 