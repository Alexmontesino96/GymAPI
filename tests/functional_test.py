"""
Pruebas funcionales con token real.
Este script ejecuta pruebas contra el API usando un token de autenticación real.
"""
import sys
import json
import argparse
import requests
from datetime import datetime
from typing import Dict, Any, List, Optional

# Constantes
BASE_URL = "http://localhost:8080/api/v1"
OUTPUT_FILE = "test_results.json"

class APITester:
    """Clase para probar los endpoints de la API con un token real."""
    
    def __init__(self, token: str, base_url: str = BASE_URL):
        """
        Inicializa el tester con un token de autenticación.
        
        Args:
            token: Token de autenticación (JWT de Auth0)
            base_url: URL base de la API
        """
        self.token = token
        self.base_url = base_url
        self.headers = {"Authorization": f"Bearer {token}"}
        self.results = []
    
    def _request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """
        Envía una solicitud HTTP a un endpoint de la API.
        
        Args:
            method: Método HTTP (GET, POST, PUT, PATCH, DELETE)
            endpoint: Endpoint relativo (sin la URL base)
            **kwargs: Argumentos adicionales para la solicitud
            
        Returns:
            Objeto Response de la solicitud
        """
        url = f"{self.base_url}/{endpoint}"
        
        # Asegurar que los headers de autenticación estén presentes
        headers = kwargs.pop("headers", {})
        headers.update(self.headers)
        
        # Imprimir información sobre la solicitud
        print(f"\n🔹 {method.upper()} {url}")
        
        # Realizar la solicitud
        response = requests.request(method, url, headers=headers, **kwargs)
        
        # Guardar el resultado
        result = {
            "endpoint": endpoint,
            "method": method.upper(),
            "status_code": response.status_code,
            "success": 200 <= response.status_code < 300,
            "timestamp": datetime.now().isoformat()
        }
        
        # Intentar obtener el cuerpo de la respuesta como JSON
        try:
            result["response"] = response.json()
        except ValueError:
            result["response"] = response.text
        
        self.results.append(result)
        
        # Imprimir resultado resumido
        status_symbol = "✅" if result["success"] else "❌"
        print(f"{status_symbol} Status: {response.status_code}")
        
        return response
    
    def get(self, endpoint: str, **kwargs) -> requests.Response:
        """Envía una solicitud GET."""
        return self._request("get", endpoint, **kwargs)
    
    def post(self, endpoint: str, **kwargs) -> requests.Response:
        """Envía una solicitud POST."""
        return self._request("post", endpoint, **kwargs)
    
    def put(self, endpoint: str, **kwargs) -> requests.Response:
        """Envía una solicitud PUT."""
        return self._request("put", endpoint, **kwargs)
    
    def patch(self, endpoint: str, **kwargs) -> requests.Response:
        """Envía una solicitud PATCH."""
        return self._request("patch", endpoint, **kwargs)
    
    def delete(self, endpoint: str, **kwargs) -> requests.Response:
        """Envía una solicitud DELETE."""
        return self._request("delete", endpoint, **kwargs)
    
    def save_results(self, filename: str = OUTPUT_FILE) -> None:
        """
        Guarda los resultados de las pruebas en un archivo JSON.
        
        Args:
            filename: Nombre del archivo donde guardar los resultados
        """
        with open(filename, "w") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "total_tests": len(self.results),
                "successful_tests": sum(1 for r in self.results if r["success"]),
                "failed_tests": sum(1 for r in self.results if not r["success"]),
                "results": self.results
            }, f, indent=2)
        
        print(f"\n📊 Resultados guardados en {filename}")
    
    def print_summary(self) -> None:
        """Imprime un resumen de los resultados de las pruebas."""
        successful = sum(1 for r in self.results if r["success"])
        failed = sum(1 for r in self.results if not r["success"])
        total = len(self.results)
        
        print("\n📋 RESUMEN DE PRUEBAS")
        print(f"✅ Pruebas exitosas: {successful}")
        print(f"❌ Pruebas fallidas: {failed}")
        print(f"📈 Total de pruebas: {total}")
        print(f"🔄 Tasa de éxito: {successful/total*100:.1f}%")

def test_profile_endpoints(tester: APITester) -> None:
    """Prueba los endpoints relacionados con el perfil del usuario."""
    print("\n🧪 Probando endpoints de perfil")
    
    # Obtener información del perfil
    response = tester.get("auth/me")
    if response.status_code == 200:
        user_id = response.json().get("id")
        print(f"  ID del usuario: {user_id}")
    
    # Probar otros endpoints de perfil si existen

def test_gym_endpoints(tester: APITester) -> None:
    """Prueba los endpoints relacionados con gimnasios."""
    print("\n🧪 Probando endpoints de gimnasios")
    
    # Listar gimnasios
    response = tester.get("gyms")
    
    # Si hay gimnasios, probar obtener uno específico
    if response.status_code == 200 and response.json().get("items"):
        gym_id = response.json()["items"][0]["id"]
        print(f"  ID del gimnasio seleccionado: {gym_id}")
        
        # Obtener detalles del gimnasio
        tester.get(f"gyms/{gym_id}")
        
        # Probar crear un nuevo gimnasio
        new_gym = {
            "name": f"Gimnasio de Prueba {datetime.now().strftime('%Y%m%d%H%M%S')}",
            "subdomain": f"test-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "address": "Calle de Prueba 123",
            "email": "test@example.com",
            "description": "Gimnasio creado para pruebas"
        }
        tester.post("gyms", json=new_gym)

def test_event_endpoints(tester: APITester) -> None:
    """Prueba los endpoints relacionados con eventos."""
    print("\n🧪 Probando endpoints de eventos")
    
    # Listar eventos
    response = tester.get("events")
    
    # Si hay eventos, probar obtener uno específico
    if response.status_code == 200 and response.json().get("items"):
        event_id = response.json()["items"][0]["id"]
        print(f"  ID del evento seleccionado: {event_id}")
        
        # Obtener detalles del evento
        tester.get(f"events/{event_id}")

def test_schedule_endpoints(tester: APITester) -> None:
    """Prueba los endpoints relacionados con programación de horarios."""
    print("\n🧪 Probando endpoints de programación")
    
    # Listar horarios
    tester.get("schedule")

def run_tests(token: str) -> None:
    """
    Ejecuta todas las pruebas con el token proporcionado.
    
    Args:
        token: Token de autenticación
    """
    tester = APITester(token)
    
    try:
        # Ejecutar pruebas por módulo
        test_profile_endpoints(tester)
        test_gym_endpoints(tester)
        test_event_endpoints(tester)
        test_schedule_endpoints(tester)
        
        # Imprimir y guardar resultados
        tester.print_summary()
        tester.save_results()
        
    except Exception as e:
        print(f"\n❌ Error durante las pruebas: {str(e)}")
        raise

def main():
    """Función principal del script."""
    parser = argparse.ArgumentParser(description="Pruebas funcionales con token real")
    parser.add_argument("--token", "-t", required=True, help="Token de autenticación (JWT de Auth0)")
    parser.add_argument("--output", "-o", default=OUTPUT_FILE, help=f"Archivo de salida (por defecto: {OUTPUT_FILE})")
    
    args = parser.parse_args()
    
    print("🚀 Iniciando pruebas funcionales...")
    run_tests(args.token)
    print("✨ Pruebas completadas")

if __name__ == "__main__":
    main() 