"""
Test específico para el módulo de eventos con token real.
Este script prueba todas las operaciones CRUD en eventos.
"""
import json
import argparse
import requests
from datetime import datetime, timedelta
import random
import time

# Constantes
BASE_URL = "http://localhost:8080/api/v1"

class EventTester:
    """Clase para probar el módulo de eventos."""
    
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
        self.created_event_id = None
    
    def request(self, method: str, endpoint: str, **kwargs):
        """Realiza una solicitud HTTP con log."""
        url = f"{self.base_url}/{endpoint}"
        
        # Asegurar que los headers de autenticación estén presentes
        headers = kwargs.pop("headers", {})
        headers.update(self.headers)
        
        # Realizar solicitud con log
        print(f"\n🔹 {method.upper()} {url}")
        
        response = requests.request(method, url, headers=headers, **kwargs)
        
        # Mostrar resultado
        status_symbol = "✅" if 200 <= response.status_code < 300 else "❌"
        print(f"{status_symbol} Status: {response.status_code}")
        
        return response
    
    def run_event_test(self):
        """Ejecuta el flujo completo de pruebas de eventos."""
        print("\n========== INICIANDO PRUEBA DE EVENTOS ==========")
        
        try:
            # 1. Listar eventos (verificar que la API funciona)
            self.list_events()
            
            # 2. Crear un nuevo evento
            self.create_event()
            
            # 3. Obtener detalles del evento creado
            self.get_event_details()
            
            # 4. Actualizar el evento
            self.update_event()
            
            # 5. Listar participantes (si el evento tiene participantes)
            self.list_participants()
            
            # 6. Finalmente eliminar el evento
            self.delete_event()
            
            print("\n✨ Prueba de eventos completada con éxito")
        
        except Exception as e:
            print(f"\n❌ Error durante la prueba de eventos: {str(e)}")
            
            # Intentar limpiar el evento creado si hay un error
            if self.created_event_id:
                print(f"\n🧹 Limpiando evento creado: {self.created_event_id}")
                try:
                    self.delete_event()
                except Exception as cleanup_error:
                    print(f"Error durante la limpieza: {str(cleanup_error)}")
    
    def list_events(self):
        """Lista todos los eventos disponibles."""
        print("\n🔍 Listando eventos...")
        
        response = self.request("get", "events")
        
        if response.status_code == 200:
            events = response.json().get("items", [])
            print(f"  📋 Total de eventos encontrados: {len(events)}")
            
            if events:
                print("  Eventos disponibles:")
                for event in events[:3]:  # Mostrar solo los primeros 3 para no saturar la consola
                    print(f"  - {event.get('title')} (ID: {event.get('id')})")
                
                if len(events) > 3:
                    print(f"  ... y {len(events) - 3} más")
        else:
            print(f"  ❌ Error al listar eventos: {response.status_code}")
    
    def create_event(self):
        """Crea un nuevo evento de prueba."""
        print("\n➕ Creando nuevo evento...")
        
        # Generar fechas para el evento (comenzando mañana)
        start_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        end_date = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
        
        # Datos para crear el evento
        event_data = {
            "title": f"Test Event {datetime.now().strftime('%Y%m%d%H%M%S')}",
            "description": "Evento creado automáticamente para pruebas",
            "start_date": start_date,
            "end_date": end_date,
            "start_time": "10:00:00",
            "end_time": "12:00:00",
            "is_public": True,
            "max_participants": random.randint(5, 20),
            "location": "Sala de pruebas",
            "type": "TEST"
        }
        
        response = self.request("post", "events", json=event_data)
        
        if response.status_code == 201:
            created_event = response.json()
            self.created_event_id = created_event.get("id")
            print(f"  ✅ Evento creado exitosamente con ID: {self.created_event_id}")
            print(f"  📝 Título: {created_event.get('title')}")
        else:
            print(f"  ❌ Error al crear evento: {response.status_code}")
            if response.headers.get("content-type") == "application/json":
                print(f"  Detalles: {response.json()}")
            raise Exception("No se pudo crear el evento")
    
    def get_event_details(self):
        """Obtiene los detalles del evento creado."""
        if not self.created_event_id:
            print("  ⚠️ No hay ID de evento para obtener detalles")
            return
        
        print(f"\n🔎 Obteniendo detalles del evento {self.created_event_id}...")
        
        response = self.request("get", f"events/{self.created_event_id}")
        
        if response.status_code == 200:
            event = response.json()
            print(f"  ✅ Detalles obtenidos correctamente")
            print(f"  📝 Título: {event.get('title')}")
            print(f"  📆 Fecha inicio: {event.get('start_date')}")
            print(f"  📍 Ubicación: {event.get('location')}")
        else:
            print(f"  ❌ Error al obtener detalles: {response.status_code}")
    
    def update_event(self):
        """Actualiza el evento creado."""
        if not self.created_event_id:
            print("  ⚠️ No hay ID de evento para actualizar")
            return
        
        print(f"\n✏️ Actualizando evento {self.created_event_id}...")
        
        # Datos para actualizar
        update_data = {
            "title": f"Updated Test Event {datetime.now().strftime('%Y%m%d%H%M%S')}",
            "description": "Evento actualizado durante pruebas",
            "location": "Sala de pruebas actualizada"
        }
        
        response = self.request("patch", f"events/{self.created_event_id}", json=update_data)
        
        if response.status_code == 200:
            updated_event = response.json()
            print(f"  ✅ Evento actualizado correctamente")
            print(f"  📝 Nuevo título: {updated_event.get('title')}")
            print(f"  📍 Nueva ubicación: {updated_event.get('location')}")
        else:
            print(f"  ❌ Error al actualizar evento: {response.status_code}")
    
    def list_participants(self):
        """Lista los participantes del evento."""
        if not self.created_event_id:
            print("  ⚠️ No hay ID de evento para listar participantes")
            return
        
        print(f"\n👥 Listando participantes del evento {self.created_event_id}...")
        
        response = self.request("get", f"events/{self.created_event_id}/participants")
        
        if response.status_code == 200:
            participants = response.json().get("items", [])
            print(f"  👥 Total de participantes: {len(participants)}")
            
            if participants:
                print("  Participantes:")
                for participant in participants[:5]:  # Mostrar hasta 5 participantes
                    user = participant.get("user", {})
                    print(f"  - {user.get('full_name')} ({user.get('email')})")
                
                if len(participants) > 5:
                    print(f"  ... y {len(participants) - 5} más")
            else:
                print("  📝 El evento no tiene participantes todavía")
        else:
            print(f"  ❌ Error al listar participantes: {response.status_code}")
    
    def delete_event(self):
        """Elimina el evento creado."""
        if not self.created_event_id:
            print("  ⚠️ No hay ID de evento para eliminar")
            return
        
        print(f"\n🗑️ Eliminando evento {self.created_event_id}...")
        
        response = self.request("delete", f"events/{self.created_event_id}")
        
        if response.status_code in [200, 204]:
            print(f"  ✅ Evento eliminado correctamente")
            self.created_event_id = None
        else:
            print(f"  ❌ Error al eliminar evento: {response.status_code}")
            if response.headers.get("content-type") == "application/json":
                print(f"  Detalles: {response.json()}")

def main():
    """Función principal del script."""
    parser = argparse.ArgumentParser(description="Test del módulo de eventos")
    parser.add_argument("--token", "-t", required=True, help="Token de autenticación (JWT de Auth0)")
    parser.add_argument("--base-url", "-u", default=BASE_URL, help=f"URL base de la API (por defecto: {BASE_URL})")
    
    args = parser.parse_args()
    
    # Iniciar prueba
    print("🚀 Iniciando prueba de eventos...")
    event_tester = EventTester(args.token, args.base_url)
    event_tester.run_event_test()

if __name__ == "__main__":
    main() 