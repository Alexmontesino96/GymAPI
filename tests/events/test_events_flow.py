#!/usr/bin/env python3
import requests
import json
from datetime import datetime, timedelta
import time

# Configuración de la prueba
API_BASE_URL = "http://localhost:8080/api/v1"
# Token con permisos correctos (read:events en lugar de read_events)
AUTH_TOKEN = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6InI2YXBIZVNOUEluaXpaeDlYN1NidyJ9.eyJlbWFpbCI6ImFsZXhtb250ZXNpbm85NkBpY2xvdWQuY29tIiwiaXNzIjoiaHR0cHM6Ly9kZXYtZ2Q1Y3JmZTZxYnFsdTIzcC51cy5hdXRoMC5jb20vIiwic3ViIjoiYXV0aDB8NjdkNWQ2NGQ2NGNjZjFjNTIyYTY5NTBiIiwiYXVkIjpbImh0dHBzOi8vZ3ltYXBpIiwiaHR0cHM6Ly9kZXYtZ2Q1Y3JmZTZxYnFsdTIzcC51cy5hdXRoMC5jb20vdXNlcmluZm8iXSwiaWF0IjoxNzQzNzM2MzY0LCJleHAiOjE3NDM4MjI3NjQsInNjb3BlIjoib3BlbmlkIHByb2ZpbGUgZW1haWwiLCJhenAiOiJPdUo2SUtFMGxKU2RhTUc2amFXMDRqZnB0c01SYnl2cCIsInBlcm1pc3Npb25zIjpbImFkbWluOmV2ZW50cyIsImFkbWluOmd5bXMiLCJhZG1pbjpyZWxhdGlvbnNoaXBzIiwiYWRtaW46dXNlcnMiLCJjcmVhdGU6Y2hhdF9yb29tcyIsImNyZWF0ZTpldmVudHMiLCJjcmVhdGU6cGFydGljaXBhdGlvbnMiLCJjcmVhdGU6cmVsYXRpb25zaGlwcyIsImNyZWF0ZTpzY2hlZHVsZXMiLCJkZWxldGU6ZXZlbnRzIiwiZGVsZXRlOm93bl9wYXJ0aWNpcGF0aW9ucyIsImRlbGV0ZTpyZWxhdGlvbnNoaXBzIiwiZGVsZXRlOnNjaGVkdWxlcyIsImRlbGV0ZTp1c2VycyIsIm1hbmFnZTpjaGF0X3Jvb21zIiwibWFuYWdlOmNsYXNzX3JlZ2lzdHJhdGlvbnMiLCJyZWFkX2V2ZW50cyIsInJlYWQ6Z3ltcyIsInJlYWQ6bWVtYmVycyIsInJlYWQ6b3duX2V2ZW50cyIsInJlYWQ6b3duX3BhcnRpY2lwYXRpb25zIiwicmVhZDpvd25fcmVsYXRpb25zaGlwcyIsInJlYWQ6b3duX3NjaGVkdWxlcyIsInJlYWQ6cGFydGljaXBhdGlvbnMiLCJyZWFkOnByb2ZpbGUiLCJyZWFkOnNjaGVkdWxlcyIsInJlYWQ6dXNlcnMiLCJyZWRhOmd5bV91c2VycyIsInJlZ2lzdGVyOmNsYXNzZXMiLCJ1cGRhdGU6cGFydGljaXBhdGlvbnMiLCJ1cGRhdGU6cmVsYXRpb25zaGlwcyIsInVwZGF0ZTpzY2hlZHVsZXMiLCJ1cGRhdGU6dXNlcnMiLCJ1c2U6Y2hhdCJdfQ.iZTaL4RhzGt3HbK1Jjm77HFEYCtLaPJCtJ50x-rTwOsFL5wx9XNhSAOUGZrpS3PmNRHmI0KJEdV2duxNc1UUsuSNA2iT744eeg79cBLJZGBcCAHI5KzGGTISOtKRky4uCw55JuYMxNXR75UU93sISQA_X4Di73392HBgbHC5H-lQTC07ECpjxtljFCbKH9ezkjLaoyDEXMUStiaM-wXwoNxOYqHVxv0RkTp4F3-dekyW7h2_1M0WrAK0ZX8tPDU88TYb11Nued-l2MZD7ICyUoVCSj-NnH_7k3dyp-CyDBILJxO4891_dCmEBmZXGddV7a6gzAiNUiUO4d-ndHnpEg"
GYM_ID = 1

# Headers comunes para todas las peticiones
HEADERS = {
    "Authorization": f"Bearer {AUTH_TOKEN}",
    "Content-Type": "application/json",
    "x-tenant-id": str(GYM_ID)
}

# Lista para almacenar los IDs de los eventos creados durante la prueba
created_events = []
created_participations = []

def print_separator(title):
    """Imprime un separador con un título para mejor legibilidad en la consola"""
    print("\n" + "=" * 80)
    print(f" {title} ".center(80, "="))
    print("=" * 80 + "\n")

def get_events():
    """Obtiene la lista de eventos"""
    print_separator("CONSULTANDO EVENTOS")
    
    url = f"{API_BASE_URL}/events/"
    response = requests.get(url, headers=HEADERS)
    
    if response.status_code == 200:
        events = response.json()
        print(f"✅ Eventos obtenidos exitosamente. Cantidad: {len(events)}")
        return events
    else:
        print(f"❌ Error al obtener eventos: {response.status_code}")
        print(response.text)
        return None

def create_event(days_offset=1, max_participants=15):
    """Crea un nuevo evento de prueba"""
    print_separator(f"CREANDO EVENTO (Inicio: +{days_offset} días, Capacidad: {max_participants})")
    
    # Crear fechas para el evento
    start_time = (datetime.now() + timedelta(days=days_offset)).replace(hour=10, minute=0, second=0)
    end_time = (datetime.now() + timedelta(days=days_offset)).replace(hour=12, minute=0, second=0)
    
    # Datos del evento
    event_data = {
        "title": f"Evento de Prueba {int(time.time())}",
        "description": "Este es un evento creado automáticamente para pruebas de integración",
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "location": "Sala de Pruebas",
        "max_participants": max_participants,
        "status": "SCHEDULED",
        "image_url": "",
        "details": {"equipamiento": "Ninguno", "nivel": "Todos los niveles"}
    }
    
    url = f"{API_BASE_URL}/events/"
    response = requests.post(url, headers=HEADERS, json=event_data)
    
    if response.status_code == 201:
        created_event = response.json()
        print(f"✅ Evento creado exitosamente con ID: {created_event['id']}")
        print(f"   Título: {created_event['title']}")
        print(f"   Descripción: {created_event['description']}")
        print(f"   Ubicación: {created_event['location']}")
        print(f"   Máximo participantes: {created_event['max_participants']}")
        
        # Añadir a la lista de eventos creados para limpiar después
        created_events.append(created_event['id'])
        
        return created_event
    else:
        print(f"❌ Error al crear evento: {response.status_code}")
        print(response.text)
        return None

def get_event_by_id(event_id):
    """Obtiene un evento específico por su ID"""
    print_separator(f"CONSULTANDO EVENTO {event_id}")
    
    url = f"{API_BASE_URL}/events/{event_id}"
    response = requests.get(url, headers=HEADERS)
    
    if response.status_code == 200:
        event = response.json()
        print(f"✅ Evento {event_id} obtenido exitosamente")
        print(f"   Título: {event['title']}")
        print(f"   Descripción: {event['description']}")
        print(f"   Ubicación: {event['location']}")
        return event
    else:
        print(f"❌ Error al obtener evento {event_id}: {response.status_code}")
        print(response.text)
        return None

def update_event(event_id, original_event):
    """Actualiza un evento existente"""
    print_separator(f"ACTUALIZANDO EVENTO {event_id}")
    
    # Datos para actualizar
    update_data = {
        "title": f"{original_event['title']} (Actualizado)",
        "description": f"{original_event['description']} - Esta descripción fue actualizada",
        "location": "Nueva Ubicación",
        "max_participants": 20
    }
    
    url = f"{API_BASE_URL}/events/{event_id}"
    response = requests.put(url, headers=HEADERS, json=update_data)
    
    if response.status_code == 200:
        updated_event = response.json()
        print(f"✅ Evento {event_id} actualizado exitosamente")
        print(f"   Título nuevo: {updated_event['title']}")
        print(f"   Descripción nueva: {updated_event['description']}")
        print(f"   Ubicación nueva: {updated_event['location']}")
        print(f"   Participantes máximos nuevos: {updated_event['max_participants']}")
        return updated_event
    else:
        print(f"❌ Error al actualizar evento {event_id}: {response.status_code}")
        print(response.text)
        return None

def register_for_event(event_id):
    """Registra al usuario en un evento"""
    print_separator(f"REGISTRANDO USUARIO EN EVENTO {event_id}")
    
    participation_data = {
        "event_id": event_id,
        "status": "REGISTERED",
        "notes": "Registro automático desde pruebas"
    }
    
    url = f"{API_BASE_URL}/events/participation"
    response = requests.post(url, headers=HEADERS, json=participation_data)
    
    if response.status_code == 201:
        participation = response.json()
        print(f"✅ Usuario registrado exitosamente en evento {event_id}")
        print(f"   ID de participación: {participation['id']}")
        print(f"   Estado: {participation['status']}")
        
        # Añadir a la lista de participaciones creadas
        created_participations.append(participation['id'])
        
        return participation
    else:
        print(f"❌ Error al registrar en evento {event_id}: {response.status_code}")
        print(response.text)
        return None

def get_my_participations():
    """Obtiene las participaciones del usuario actual"""
    print_separator("CONSULTANDO MIS PARTICIPACIONES")
    
    url = f"{API_BASE_URL}/events/participation/me"
    response = requests.get(url, headers=HEADERS)
    
    if response.status_code == 200:
        participations = response.json()
        print(f"✅ Participaciones obtenidas exitosamente. Cantidad: {len(participations)}")
        if participations:
            for p in participations:
                print(f"   Evento: {p['event_id']} - Estado: {p['status']}")
        return participations
    else:
        print(f"❌ Error al obtener participaciones: {response.status_code}")
        print(response.text)
        return None

def get_event_participations(event_id):
    """Obtiene las participaciones de un evento específico"""
    print_separator(f"CONSULTANDO PARTICIPACIONES DEL EVENTO {event_id}")
    
    url = f"{API_BASE_URL}/events/participation/event/{event_id}"
    response = requests.get(url, headers=HEADERS)
    
    if response.status_code == 200:
        participations = response.json()
        print(f"✅ Participaciones del evento obtenidas exitosamente. Cantidad: {len(participations)}")
        if participations:
            for p in participations:
                print(f"   Usuario: {p['member_id']} - Estado: {p['status']}")
        return participations
    else:
        print(f"❌ Error al obtener participaciones del evento: {response.status_code}")
        print(response.text)
        return None

def update_participation(participation_id, new_status="CANCELLED"):
    """Actualiza el estado de una participación"""
    print_separator(f"ACTUALIZANDO PARTICIPACIÓN {participation_id}")
    
    update_data = {
        "status": new_status,
        "notes": f"Estado actualizado a {new_status} por pruebas automáticas"
    }
    
    url = f"{API_BASE_URL}/events/participation/{participation_id}"
    response = requests.put(url, headers=HEADERS, json=update_data)
    
    if response.status_code == 200:
        updated = response.json()
        print(f"✅ Participación {participation_id} actualizada exitosamente")
        print(f"   Nuevo estado: {updated['status']}")
        print(f"   Notas: {updated['notes']}")
        return updated
    else:
        print(f"❌ Error al actualizar participación: {response.status_code}")
        print(response.text)
        return None

def cancel_participation(event_id):
    """Cancela la participación del usuario en un evento"""
    print_separator(f"CANCELANDO PARTICIPACIÓN EN EVENTO {event_id}")
    
    url = f"{API_BASE_URL}/events/participation/{event_id}"
    response = requests.delete(url, headers=HEADERS)
    
    if response.status_code == 204:
        print(f"✅ Participación en evento {event_id} cancelada exitosamente")
        return True
    else:
        print(f"❌ Error al cancelar participación: {response.status_code}")
        print(response.text)
        return False

def delete_event(event_id):
    """Elimina un evento existente"""
    print_separator(f"ELIMINANDO EVENTO {event_id}")
    
    url = f"{API_BASE_URL}/events/{event_id}"
    response = requests.delete(url, headers=HEADERS)
    
    if response.status_code == 204:
        print(f"✅ Evento {event_id} eliminado exitosamente")
        # Eliminar de la lista de eventos creados
        if event_id in created_events:
            created_events.remove(event_id)
        return True
    else:
        print(f"❌ Error al eliminar evento {event_id}: {response.status_code}")
        print(response.text)
        return False

def verify_event_deleted(event_id):
    """Verifica que un evento haya sido eliminado correctamente"""
    print_separator(f"VERIFICANDO ELIMINACIÓN DE EVENTO {event_id}")
    
    url = f"{API_BASE_URL}/events/{event_id}"
    response = requests.get(url, headers=HEADERS)
    
    if response.status_code == 404:
        print(f"✅ Evento {event_id} no se encuentra, lo que confirma que fue eliminado correctamente")
        return True
    else:
        print(f"❌ Error: El evento {event_id} aún existe o hay otro error: {response.status_code}")
        print(response.text)
        return False

def cleanup():
    """Limpia los recursos creados durante las pruebas"""
    print_separator("LIMPIEZA DE RECURSOS")
    
    # Eliminar eventos creados
    for event_id in list(created_events):
        print(f"Eliminando evento {event_id}...")
        delete_event(event_id)
    
    print("✅ Limpieza completada")

def test_capacity_limit():
    """Prueba el límite de capacidad de un evento"""
    print_separator("PRUEBA DE LÍMITE DE CAPACIDAD")
    
    # Crear evento con capacidad limitada (1 participante)
    event = create_event(days_offset=2, max_participants=1)
    if not event:
        print("❌ No se pudo crear el evento para la prueba de capacidad")
        return False
    
    event_id = event["id"]
    
    # Registrar al usuario (debería tener éxito)
    participation1 = register_for_event(event_id)
    if not participation1:
        print("❌ Error inesperado: No se pudo registrar al primer participante")
        return False
    
    # Intentar registrar al mismo usuario nuevamente (debería fallar)
    print("\nIntentando registrar al mismo usuario nuevamente...")
    duplicate = register_for_event(event_id)
    if duplicate:
        print("❌ Error: Se permitió registrar al mismo usuario dos veces")
        return False
    else:
        print("✅ Correctamente rechazado el registro duplicado")
    
    # Verificar que el estado de la participación es correcto
    participations = get_event_participations(event_id)
    if not participations or len(participations) != 1:
        print("❌ Error al verificar participaciones")
        return False
    
    if participations[0]["status"] != "REGISTERED":
        print(f"❌ Estado incorrecto: {participations[0]['status']}")
        return False
    
    print("✅ Prueba de capacidad completada exitosamente")
    return True

def run_events_flow_test():
    """Ejecuta el flujo completo de prueba CRUD para eventos y participaciones"""
    print_separator("INICIANDO PRUEBA DE FLUJO COMPLETO CRUD PARA EVENTOS Y PARTICIPACIONES")
    
    try:
        # Paso 1: Listar eventos existentes
        events = get_events()
        
        # Paso 2: Crear un nuevo evento
        new_event = create_event()
        if not new_event:
            print("❌ No se pudo crear el evento, abortando prueba")
            return
        
        event_id = new_event["id"]
        
        # Paso 3: Obtener detalles del evento creado
        event_details = get_event_by_id(event_id)
        if not event_details:
            print("❌ No se pudo obtener detalles del evento, abortando prueba")
            return
        
        # Paso 4: Actualizar el evento
        updated_event = update_event(event_id, new_event)
        if not updated_event:
            print("❌ No se pudo actualizar el evento, abortando prueba")
            return
        
        # Paso 5: Registrarse en el evento
        participation = register_for_event(event_id)
        if not participation:
            print("❌ No se pudo registrar en el evento, abortando prueba")
            return
        
        # Paso 6: Verificar mis participaciones
        my_participations = get_my_participations()
        if not my_participations:
            print("❌ No se pudieron obtener mis participaciones, abortando prueba")
            return
        
        # Paso 7: Verificar participaciones del evento
        event_participations = get_event_participations(event_id)
        if not event_participations:
            print("❌ No se pudieron obtener las participaciones del evento, abortando prueba")
            return
        
        # Paso 8: Actualizar estado de participación si es posible
        if participation and 'id' in participation:
            updated_participation = update_participation(participation['id'], "WAITING_LIST")
            if not updated_participation:
                print("❌ No se pudo actualizar la participación")
        
        # Paso 9: Cancelar participación
        cancel_result = cancel_participation(event_id)
        if not cancel_result:
            print("❌ No se pudo cancelar la participación")
        
        # Paso 10: Crear un evento para prueba de capacidad
        capacity_test_result = test_capacity_limit()
        
        # Paso 11: Eliminar el primer evento creado
        delete_result = delete_event(event_id)
        if not delete_result:
            print("❌ No se pudo eliminar el evento")
        
        # Paso 12: Verificar que el evento fue eliminado
        verify_result = verify_event_deleted(event_id)
        if not verify_result:
            print("❌ No se pudo verificar la eliminación del evento")
        
        # Resumen final
        print_separator("RESUMEN DE LA PRUEBA")
        print("✅ Prueba de flujo completo CRUD para eventos y participaciones ejecutada")
        
    finally:
        # Limpiar recursos creados durante la prueba
        cleanup()

if __name__ == "__main__":
    run_events_flow_test() 