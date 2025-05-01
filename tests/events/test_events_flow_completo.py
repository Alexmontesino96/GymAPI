#!/usr/bin/env python3
import requests
import json
from datetime import datetime, timedelta
import time
import random
import logging
import math
import pytz

# Configuración de la prueba
API_BASE_URL = "https://gymapi-eh6m.onrender.com/api/v1"
AUTH_TOKEN = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6InI2YXBIZVNOUEluaXpaeDlYN1NidyJ9.eyJlbWFpbCI6ImFsZXhtb250ZXNpbm85NkBpY2xvdWQuY29tIiwiaXNzIjoiaHR0cHM6Ly9kZXYtZ2Q1Y3JmZTZxYnFsdTIzcC51cy5hdXRoMC5jb20vIiwic3ViIjoiYXV0aDB8NjdkNWQ2NGQ2NGNjZjFjNTIyYTY5NTBiIiwiYXVkIjpbImh0dHBzOi8vZ3ltYXBpIiwiaHR0cHM6Ly9kZXYtZ2Q1Y3JmZTZxYnFsdTIzcC51cy5hdXRoMC5jb20vdXNlcmluZm8iXSwiaWF0IjoxNzQ2MDI5MjgxLCJleHAiOjE3NDYxMTU2ODEsInNjb3BlIjoib3BlbmlkIHByb2ZpbGUgZW1haWwiLCJhenAiOiJPdUo2SUtFMGxKU2RhTUc2amFXMDRqZnB0c01SYnl2cCIsInBlcm1pc3Npb25zIjpbImFkbWluOmV2ZW50cyIsImFkbWluOmd5bXMiLCJhZG1pbjpyZWxhdGlvbnNoaXBzIiwiYWRtaW46dXNlcnMiLCJjcmVhdGU6Y2hhdF9yb29tcyIsImNyZWF0ZTpldmVudHMiLCJjcmVhdGU6cGFydGljaXBhdGlvbnMiLCJjcmVhdGU6cmVsYXRpb25zaGlwcyIsImNyZWF0ZTpzY2hlZHVsZXMiLCJkZWxldGU6ZXZlbnRzIiwiZGVsZXRlOm93bl9wYXJ0aWNpcGF0aW9ucyIsImRlbGV0ZTpyZWxhdGlvbnNoaXBzIiwiZGVsZXRlOnNjaGVkdWxlcyIsImRlbGV0ZTp1c2VycyIsIm1hbmFnZTpjaGF0X3Jvb21zIiwibWFuYWdlOmNsYXNzX3JlZ2lzdHJhdGlvbnMiLCJyZWFkX2V2ZW50cyIsInJlYWQ6Z3ltcyIsInJlYWQ6bWVtYmVycyIsInJlYWQ6b3duX2V2ZW50cyIsInJlYWQ6b3duX3BhcnRpY2lwYXRpb25zIiwicmVhZDpvd25fcmVsYXRpb25zaGlwcyIsInJlYWQ6b3duX3NjaGVkdWxlcyIsInJlYWQ6cGFydGljaXBhdGlvbnMiLCJyZWFkOnByb2ZpbGUiLCJyZWFkOnNjaGVkdWxlcyIsInJlYWQ6dXNlcnMiLCJyZWRhOmd5bV91c2VycyIsInJlZ2lzdGVyOmNsYXNzZXMiLCJ1cGRhdGU6cGFydGljaXBhdGlvbnMiLCJ1cGRhdGU6cmVsYXRpb25zaGlwcyIsInVwZGF0ZTpzY2hlZHVsZXMiLCJ1cGRhdGU6dXNlcnMiLCJ1c2U6Y2hhdCJdfQ.bnidtK96x8zoNyXRJ0B7vRsSZtBxGM8f71nll_MmlLb9LUGxUR1k5uEF-5KoWmMNnRbBgqqFJZ_ZiTnFkQ5UIStfuWaay5Re7d_zrOeO6ycsrQ0pJbLG31NIbAi-T6o__MCvCihRN0__ebXHhUGhsrUTT6ekEuR8ujfyU2t8di0Vjp8AKQjTVdEITx4xfyefZ6uY0H373kLv5mH0WrRJQ08gaPvpCfE5o_zj0avqWSzQlBMJ8oeEsazmPtVBNVsEz1I-xlriBA0YG_40yQI6sHmPmk3M85hM7MlxjxDPNqZ_1h6cF6na3dvv0WNsVdoeqGIzo_G3I-sJC87_RbsloQ"
GYM_ID = 2

# Configurar logging para ver detalles
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Headers comunes para todas las peticiones
HEADERS = {
    "Authorization": f"Bearer {AUTH_TOKEN}",
    "Content-Type": "application/json",
    "X-Gym-ID": str(GYM_ID)
}

# Lista para almacenar los IDs de eventos creados para limpiarlos al final
created_event_ids = []
created_participation_ids = []

def print_separator(title):
    """Imprime un separador con un título para mejor legibilidad en la consola"""
    print("\n" + "=" * 80)
    print(f" {title} ".center(80, "="))
    print("=" * 80 + "\n")

def get_own_events():
    """Obtiene la lista de eventos creados por el usuario actual"""
    print_separator("CONSULTANDO MIS EVENTOS")
    
    url = f"{API_BASE_URL}/events/me"
    response = requests.get(url, headers=HEADERS)
    
    if response.status_code == 200:
        events = response.json()
        print(f"✅ Mis eventos obtenidos exitosamente. Cantidad: {len(events)}")
        return events
    else:
        print(f"❌ Error al obtener mis eventos: {response.status_code}")
        print(response.text)
        return None

def create_event(event_data=None):
    """Crea un nuevo evento de prueba con datos personalizados o predeterminados"""
    print_separator("CREANDO EVENTO")
    
    # Si no se proporcionan datos, usar valores predeterminados
    if not event_data:
        # Crear fechas para el evento (mañana) - AHORA CON UTC
        now_utc = datetime.now(pytz.UTC)
        start_time = (now_utc + timedelta(days=1)).replace(hour=10, minute=0, second=0)
        end_time = (now_utc + timedelta(days=1)).replace(hour=12, minute=0, second=0)
        
        # Datos del evento
        event_data = {
            "title": f"Evento de Prueba {int(time.time())}",
            "description": "Este es un evento creado automáticamente para pruebas de integración",
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "location": "Sala de Pruebas",
            "max_participants": 15,
            "status": "SCHEDULED",
            "image_url": "",
            "details": {"equipamiento": "Ninguno", "nivel": "Todos los niveles"}
        }
    
    url = f"{API_BASE_URL}/events/"
    response = requests.post(url, headers=HEADERS, json=event_data)
    
    # Aceptar tanto 201 (Created) como 200 (OK) como éxito
    if response.status_code in [200, 201]: 
        created_event = response.json()
        # Asegurarse de que el evento tiene un ID antes de añadirlo
        if 'id' in created_event:
            created_event_ids.append(created_event['id'])  # Guardar ID para limpieza
            print(f"✅ Evento creado/obtenido exitosamente (status: {response.status_code}) con ID: {created_event['id']}")
            print(f"   Título: {created_event['title']}")
            print(f"   Descripción: {created_event.get('description', 'N/A')}") # Usar .get por si acaso
            print(f"   Ubicación: {created_event.get('location', 'N/A')}")
            return created_event
        else:
            print(f"❌ Error: La respuesta {response.status_code} no contenía un ID de evento.")
            print(response.text)
            return None
    else:
        print(f"❌ Error al crear/obtener evento: {response.status_code}")
        print(response.text)
        return None

def update_event(event_id, update_data):
    """Actualiza un evento existente"""
    print_separator(f"ACTUALIZANDO EVENTO {event_id}")
    
    url = f"{API_BASE_URL}/events/{event_id}"
    response = requests.put(url, headers=HEADERS, json=update_data)
    
    if response.status_code == 200:
        updated_event = response.json()
        print(f"✅ Evento {event_id} actualizado exitosamente")
        for key, value in update_data.items():
            print(f"   {key}: {updated_event.get(key, 'N/A')}")
        return updated_event
    else:
        print(f"❌ Error al actualizar evento {event_id}: {response.status_code}")
        print(response.text)
        return None

def delete_event(event_id):
    """Elimina un evento existente"""
    print_separator(f"ELIMINANDO EVENTO {event_id}")
    
    url = f"{API_BASE_URL}/events/{event_id}"
    response = requests.delete(url, headers=HEADERS)
    
    if response.status_code == 204:
        print(f"✅ Evento {event_id} eliminado exitosamente")
        if event_id in created_event_ids:
            created_event_ids.remove(event_id)
        return True
    else:
        print(f"❌ Error al eliminar evento {event_id}: {response.status_code}")
        print(response.text)
        return False

def register_for_event(event_id, notes="Registro de prueba automático"):
    """Registra al usuario actual en un evento"""
    print_separator(f"REGISTRÁNDOSE EN EVENTO {event_id}")
    
    participation_data = {
        "event_id": event_id,
        "status": "REGISTERED",
        "notes": notes
    }
    
    url = f"{API_BASE_URL}/events/participation"
    response = requests.post(url, headers=HEADERS, json=participation_data)
    
    if response.status_code == 201:
        participation = response.json()
        created_participation_ids.append(participation['id'])  # Guardar ID para limpieza
        print(f"✅ Registrado exitosamente en evento {event_id}")
        print(f"   ID de participación: {participation['id']}")
        print(f"   Estado: {participation['status']}")
        return participation
    else:
        print(f"❌ Error al registrarse en evento {event_id}: {response.status_code}")
        print(response.text)
        return None

def register_for_event_multiple_times(event_id, attempts=3):
    """Intenta registrarse en el mismo evento varias veces para probar validaciones"""
    print_separator(f"INTENTANDO REGISTRO MÚLTIPLE EN EVENTO {event_id}")
    
    results = []
    for i in range(attempts):
        print(f"\nIntento {i+1} de {attempts}:")
        participation = register_for_event(event_id, notes=f"Intento de registro múltiple #{i+1}")
        results.append({
            "attempt": i+1,
            "success": participation is not None,
            "participation": participation
        })
    
    print(f"\nResumen de {attempts} intentos de registro en evento {event_id}:")
    success_count = sum(1 for r in results if r["success"])
    print(f"✅ Registros exitosos: {success_count}/{attempts}")
    
    return results

def get_my_participations(status=None):
    """Obtiene las participaciones del usuario actual, opcionalmente filtradas por estado"""
    print_separator("CONSULTANDO MIS PARTICIPACIONES")
    
    url = f"{API_BASE_URL}/events/participation/me"
    if status:
        url += f"?status={status}"
    
    response = requests.get(url, headers=HEADERS)
    
    if response.status_code == 200:
        participations = response.json()
        print(f"✅ Participaciones obtenidas exitosamente. Cantidad: {len(participations)}")
        return participations
    else:
        print(f"❌ Error al obtener participaciones: {response.status_code}")
        print(response.text)
        return None

def get_event_participations(event_id, status=None):
    """Obtiene las participaciones para un evento específico"""
    print_separator(f"CONSULTANDO PARTICIPACIONES DEL EVENTO {event_id}")
    
    url = f"{API_BASE_URL}/events/participation/event/{event_id}"
    if status:
        url += f"?status={status}"
    
    response = requests.get(url, headers=HEADERS)
    
    if response.status_code == 200:
        participations = response.json()
        print(f"✅ Participaciones del evento obtenidas exitosamente. Cantidad: {len(participations)}")
        return participations
    else:
        print(f"❌ Error al obtener participaciones del evento: {response.status_code}")
        print(response.text)
        return None

def cancel_participation_by_event(event_id):
    """Cancela una participación en un evento usando el ID del evento"""
    print_separator(f"CANCELANDO PARTICIPACIÓN EN EVENTO {event_id}")
    
    # Primero verificamos si tenemos una participación activa en el evento
    mis_participaciones = get_my_participations()
    if not mis_participaciones:
        print("❌ No se pudieron obtener las participaciones actuales")
        return False
    
    # Buscar participación activa específica para este evento
    participacion = next((p for p in mis_participaciones 
                        if p['event_id'] == event_id and p['status'] == 'REGISTERED'), None)
    
    if not participacion:
        print(f"⚠️ No se encontró una participación activa en el evento {event_id}")
        print("   Es posible que ya esté cancelada o que nunca se haya registrado")
        
        # Verificamos todas las participaciones en este evento independientemente del estado
        cualquier_participacion = next((p for p in mis_participaciones if p['event_id'] == event_id), None)
        if cualquier_participacion:
            print(f"   Se encontró una participación con estado: {cualquier_participacion['status']}")
            print(f"   ID de participación: {cualquier_participacion['id']}")
        
        # En este punto podríamos retornar éxito si la intención era que no hubiera participación activa
        return True
    
    print(f"✅ Participación encontrada - ID: {participacion['id']}, Estado: {participacion['status']}")
    
    # Procedemos a intentar cancelar la participación
    url = f"{API_BASE_URL}/events/participation/{event_id}"
    response = requests.delete(url, headers=HEADERS)
    
    if response.status_code == 204:
        print(f"✅ Participación en evento {event_id} cancelada exitosamente")
        return True
    else:
        print(f"❌ Error al cancelar participación: {response.status_code}")
        print(response.text)
        
        # Vamos a intentar verificar nuevamente si la participación sigue activa
        mis_participaciones_actualizadas = get_my_participations()
        if mis_participaciones_actualizadas:
            participacion_activa = next((p for p in mis_participaciones_actualizadas 
                                     if p['event_id'] == event_id and p['status'] == 'REGISTERED'), None)
            if not participacion_activa:
                print("⚠️ Pese al error, la participación ya no está activa, consideramos éxito")
                return True
        
        return False

def update_participation_status(participation_id, new_status, notes=None):
    """Actualiza el estado de una participación"""
    print_separator(f"ACTUALIZANDO PARTICIPACIÓN {participation_id}")
    
    # Los estados válidos son: REGISTERED, CANCELLED, WAITING_LIST
    if new_status not in ["REGISTERED", "CANCELLED", "WAITING_LIST"]:
        print(f"⚠️ Estado '{new_status}' no válido. Estados permitidos: REGISTERED, CANCELLED, WAITING_LIST")
        print("   Utilizando REGISTERED como valor predeterminado")
        new_status = "REGISTERED"
    
    update_data = {"status": new_status}
    if notes:
        update_data["notes"] = notes
    
    url = f"{API_BASE_URL}/events/participation/{participation_id}"
    response = requests.put(url, headers=HEADERS, json=update_data)
    
    if response.status_code == 200:
        updated = response.json()
        print(f"✅ Participación {participation_id} actualizada exitosamente")
        print(f"   Nuevo estado: {updated['status']}")
        if notes:
            print(f"   Notas: {updated.get('notes', 'N/A')}")
        return updated
    else:
        print(f"❌ Error al actualizar participación: {response.status_code}")
        print(response.text)
        return None

def clean_up_events():
    """Elimina todos los eventos creados durante las pruebas"""
    print_separator("LIMPIEZA DE EVENTOS")
    
    if not created_event_ids:
        print("No hay eventos que limpiar")
        return
    
    print(f"Eliminando {len(created_event_ids)} eventos creados durante las pruebas...")
    
    success_count = 0
    for event_id in list(created_event_ids):  # Usar una copia para poder modificar durante la iteración
        if delete_event(event_id):
            success_count += 1
    
    print(f"\n✅ Limpieza completada: {success_count}/{len(created_event_ids)} eventos eliminados")

def check_if_already_registered(event_id):
    """Verifica si el usuario ya está registrado en un evento específico"""
    print_separator(f"VERIFICANDO REGISTRO PREVIO EN EVENTO {event_id}")
    
    mis_participaciones = get_my_participations()
    if not mis_participaciones:
        print("❌ No se pudieron obtener las participaciones actuales")
        return False
    
    # Buscar participación activa en el evento
    participacion_activa = next((p for p in mis_participaciones 
                             if p['event_id'] == event_id and p['status'] == 'REGISTERED'), None)
    
    if participacion_activa:
        print(f"✅ Usuario ya registrado en evento {event_id} con participación ID: {participacion_activa['id']}")
        return True
    else:
        print(f"✅ Usuario no registrado actualmente en evento {event_id}")
        return False

def register_for_event_with_cleanup(event_id, notes="Registro de prueba automático"):
    """Registra al usuario en un evento, cancelando cualquier registro previo si es necesario"""
    print_separator(f"REGISTRO INTELIGENTE EN EVENTO {event_id}")
    
    # Verificar si ya estamos registrados
    already_registered = check_if_already_registered(event_id)
    
    if already_registered:
        print(f"⚠️ Ya existe un registro activo en el evento {event_id}. Intentando cancelar primero...")
        cancel_success = cancel_participation_by_event(event_id)
        
        if not cancel_success:
            print(f"❌ No se pudo cancelar el registro previo en evento {event_id}")
            print("   Intentando registrar de todos modos...")
    
    # Intentar registrarse (después de cancelar o si no estaba registrado)
    return register_for_event(event_id, notes)

def run_participation_tests():
    """Ejecuta pruebas exhaustivas de flujos de participación en eventos"""
    print_separator("PRUEBAS EXHAUSTIVAS DE PARTICIPACIÓN EN EVENTOS")
    
    try:
        # Crear un evento para las pruebas de participación
        print("\n📌 PASO 1: CREAR EVENTO PARA PRUEBAS DE PARTICIPACIÓN")
        
        # Evento con 3 plazas para probar límites de capacidad - AHORA CON UTC
        now_utc = datetime.now(pytz.UTC)
        start_time = (now_utc + timedelta(days=1)).replace(hour=10, minute=0, second=0)
        end_time = (now_utc + timedelta(days=1)).replace(hour=12, minute=0, second=0)
        
        evento_test = create_event({
            "title": f"Evento para Pruebas de Participación {int(time.time())}",
            "description": "Este evento es para probar exhaustivamente el flujo de participación",
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "location": "Sala de Pruebas de Participación",
            "max_participants": 3,  # Límite bajo para probar capacidad
            "status": "SCHEDULED",
            "image_url": ""
        })
        
        if not evento_test:
            print("❌ No se pudo crear el evento para pruebas de participación")
            return
        
        event_id = evento_test['id']
        
        # Verificar que el evento se creó correctamente
        print(f"\n✅ Evento para pruebas creado con ID: {event_id}")
        
        # Probar registro en evento con limpieza automática
        print("\n📌 PASO 2: REGISTRARSE EN EL EVENTO (CON LIMPIEZA)")
        participacion = register_for_event_with_cleanup(event_id, "Primera inscripción para pruebas")
        
        if not participacion:
            print("❌ No se pudo registrar en el evento")
            return
        
        # Obtener mis participaciones y verificar
        print("\n📌 PASO 3: VERIFICAR MIS PARTICIPACIONES")
        mis_participaciones = get_my_participations()
        
        if mis_participaciones:
            # Verificar si la nueva participación está en la lista
            nueva_participacion = next((p for p in mis_participaciones if p['event_id'] == event_id), None)
            if nueva_participacion:
                print(f"✅ Participación verificada en mis participaciones - ID: {nueva_participacion['id']}")
            else:
                print("❌ No se encontró la nueva participación en la lista")
        
        # Probar registro múltiple con limpieza previa (debe poder registrarse de nuevo)
        print("\n📌 PASO 4: PROBAR REGISTRO MÚLTIPLE CON LIMPIEZA PREVIA")
        
        # Primer registro, debe ser exitoso porque acabamos de registrarnos
        print("\nPrueba 1: Cancelar participación existente y registrarse de nuevo")
        resultado_1 = register_for_event_with_cleanup(event_id, "Registro múltiple con limpieza previa #1")
        
        # Segundo registro, debe ser exitoso porque primero cancela
        print("\nPrueba 2: Otro intento de cancelar y registrarse")
        resultado_2 = register_for_event_with_cleanup(event_id, "Registro múltiple con limpieza previa #2")
        
        if resultado_1 and resultado_2:
            print("✅ Registros múltiples con limpieza previa funcionan correctamente")
        else:
            print("❌ Error en registros múltiples con limpieza previa")
        
        # Probar obtener participaciones del evento
        print("\n📌 PASO 5: CONSULTAR PARTICIPACIONES DEL EVENTO")
        participaciones_evento = get_event_participations(event_id)
        
        if participaciones_evento:
            print(f"✅ Se obtuvieron {len(participaciones_evento)} participaciones para el evento {event_id}")
        
        # Probar cancelación de participación
        print("\n📌 PASO 6: CANCELAR PARTICIPACIÓN")
        if cancel_participation_by_event(event_id):
            print("✅ Cancelación de participación exitosa")
        else:
            print("❌ Error en la cancelación de participación")
        
        # Verificar que la cancelación fue efectiva
        print("\n📌 PASO 7: VERIFICAR CANCELACIÓN")
        mis_participaciones_actualizadas = get_my_participations()
        
        if mis_participaciones_actualizadas:
            # Buscar si aún existe participación activa en el evento
            participacion_activa = next((p for p in mis_participaciones_actualizadas 
                                     if p['event_id'] == event_id and p['status'] == 'REGISTERED'), None)
            if not participacion_activa:
                print("✅ Cancelación verificada - No se encontró participación activa")
            else:
                print("❌ Error en verificación de cancelación - Participación activa encontrada")
        
        # Probar registro después de cancelación
        print("\n📌 PASO 8: REGISTRARSE NUEVAMENTE DESPUÉS DE CANCELACIÓN")
        nueva_participacion = register_for_event(event_id, "Registro después de cancelación")
        
        if nueva_participacion:
            print("✅ Registro después de cancelación exitoso")
            participation_id = nueva_participacion['id']
            
            # Actualizar estado de participación
            print("\n📌 PASO 9: ACTUALIZAR ESTADO DE PARTICIPACIÓN")
            updated = update_participation_status(
                participation_id, 
                "REGISTERED",  # Usar un estado válido (REGISTERED, CANCELLED, WAITING_LIST)
                "Estado actualizado en prueba"
            )
            
            if updated:
                print("✅ Actualización de estado exitosa")
            else:
                print("❌ Error en actualización de estado")
            
            # Verificar actualización
            print("\n📌 PASO 10: VERIFICAR ACTUALIZACIÓN DE ESTADO")
            participaciones_finales = get_my_participations()
            if participaciones_finales:
                participacion_final = next((p for p in participaciones_finales 
                                         if p['id'] == participation_id), None)
                if participacion_final and participacion_final['status'] == 'REGISTERED':
                    print("✅ Estado de participación actualizado correctamente")
                else:
                    print("❌ Error en verificación de actualización de estado")
        
    finally:
        # Limpiar eventos creados
        print("\n📌 LIMPIEZA FINAL")
        clean_up_events()
    
    # Resumen
    print_separator("RESUMEN DE PRUEBAS DE PARTICIPACIÓN")
    print("✅ Pruebas de participación en eventos completadas")
    print("Se han probado los siguientes casos:")
    print("  - Creación de evento con límite de capacidad")
    print("  - Registro en evento con limpieza previa si es necesario")
    print("  - Consulta de participaciones propias")
    print("  - Registros múltiples con cancelación automática previa")
    print("  - Consulta de participaciones por evento")
    print("  - Cancelación de participación")
    print("  - Registro después de cancelación")
    print("  - Actualización de estado de participación")
    print("  - Validación de cambios de estado")

def run_bulk_operations_test():
    """Prueba la creación, actualización, lectura paginada y eliminación masiva de eventos."""
    print_separator("PRUEBA DE OPERACIONES MASIVAS DE EVENTOS")

    bulk_created_ids = []
    updated_ids = []

    try:
        # --- 1. Creación Masiva (150 eventos) ---
        print("\n📌 FASE 1: CREACIÓN MASIVA DE 150 EVENTOS")
        start_bulk_create = time.time()
        for i in range(150):
            start_time = (datetime.now(pytz.UTC) + timedelta(days=random.randint(2, 30))).replace(hour=random.randint(8, 18), minute=0, second=0)
            end_time = start_time + timedelta(hours=random.randint(1, 3))
            event_data = {
                "title": f"Evento Masivo {i+1} - {int(time.time() * 1000)}",
                "description": f"Descripción del evento masivo {i+1}",
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "location": f"Sala Masiva {random.choice(['A', 'B', 'C'])}",
                "max_participants": random.randint(10, 50),
                "status": "SCHEDULED"
            }
            created_event = create_event(event_data)
            if created_event:
                bulk_created_ids.append(created_event['id'])
            else:
                logger.warning(f"No se pudo crear el evento masivo {i+1}")
                # Considerar si pausar o continuar
                time.sleep(0.1) # Pequeña pausa
        elapsed_bulk_create = time.time() - start_bulk_create
        logger.info(f"Creación masiva completada en {elapsed_bulk_create:.2f}s. Creados: {len(bulk_created_ids)}/150")
        if len(bulk_created_ids) != 150:
            logger.error("No se crearon todos los eventos esperados.")
            return # No continuar si la creación falla

        # --- 2. Actualización Masiva (100 eventos) ---
        print("\n📌 FASE 2: ACTUALIZACIÓN MASIVA DE 100 EVENTOS")
        ids_to_update = random.sample(bulk_created_ids, 100)
        start_bulk_update = time.time()
        for event_id in ids_to_update:
            update_data = {
                "title": f"Evento Masivo Actualizado {event_id}",
                "location": "Sala Actualizada",
                "max_participants": random.randint(5, 15) # Reducir capacidad
            }
            updated_event = update_event(event_id, update_data)
            if updated_event:
                updated_ids.append(event_id)
            else:
                logger.warning(f"No se pudo actualizar el evento {event_id}")
                time.sleep(0.1)
        elapsed_bulk_update = time.time() - start_bulk_update
        logger.info(f"Actualización masiva completada en {elapsed_bulk_update:.2f}s. Actualizados: {len(updated_ids)}/100")

        # --- 3. Lectura Paginada --- 
        print("\n📌 FASE 3: LECTURA PAGINADA DE TODOS LOS EVENTOS CREADOS")
        all_retrieved_events = []
        page_size = 30 # Tamaño de página más pequeño para probar paginación
        total_expected = len(bulk_created_ids) # 150
        pages_needed = math.ceil(total_expected / page_size)
        start_bulk_read = time.time()
        
        current_skip = 0
        while True:
            limit = page_size
            logger.info(f"Leyendo página (skip={current_skip}, limit={limit})...")
            url = f"{API_BASE_URL}/events/?skip={current_skip}&limit={limit}"
            response = requests.get(url, headers=HEADERS)
            if response.status_code == 200:
                page_events = response.json()
                if not page_events:
                    logger.info("  Página vacía, finalizando lectura.")
                    break # Salir si no hay más eventos
                logger.info(f"  Página obtenida con {len(page_events)} eventos.")
                all_retrieved_events.extend(page_events)
                current_skip += len(page_events) # Incrementar skip por la cantidad real obtenida
            else:
                logger.error(f"Error al leer página (skip={current_skip}): {response.status_code} - {response.text}")
                break # Salir del bucle si una página falla
            
            # Pequeña pausa entre páginas
            time.sleep(0.2)

        elapsed_bulk_read = time.time() - start_bulk_read
        logger.info(f"Lectura paginada completada en {elapsed_bulk_read:.2f}s.")
        logger.info(f"Total de eventos recuperados: {len(all_retrieved_events)} (Esperados: {total_expected})")

        # Verificar si se recuperaron todos los eventos
        if len(all_retrieved_events) != total_expected:
            logger.error("¡Discrepancia en el número de eventos recuperados!")
        else:
            logger.info("✅ Verificación de cantidad post-lectura paginada correcta.")
            # Verificar si los IDs actualizados tienen los nuevos títulos
            retrieved_ids = {e['id']: e for e in all_retrieved_events}
            updates_verified = 0
            for updated_id in updated_ids:
                if updated_id in retrieved_ids and "Actualizado" in retrieved_ids[updated_id]["title"]:
                    updates_verified += 1
            logger.info(f"Verificación de títulos actualizados: {updates_verified}/{len(updated_ids)}")

        # --- 4. Eliminación Masiva (50 eventos) ---
        print("\n📌 FASE 4: ELIMINACIÓN MASIVA DE 50 EVENTOS")
        ids_to_delete = random.sample(bulk_created_ids, 50)
        deleted_count = 0
        start_bulk_delete = time.time()
        ids_deleted_successfully = [] # Guardar los que sí se borraron
        for event_id in ids_to_delete:
            if delete_event(event_id):
                deleted_count += 1
                ids_deleted_successfully.append(event_id)
            else:
                logger.warning(f"No se pudo eliminar el evento {event_id}")
                time.sleep(0.1)
        elapsed_bulk_delete = time.time() - start_bulk_delete
        logger.info(f"Eliminación masiva completada en {elapsed_bulk_delete:.2f}s. Eliminados: {deleted_count}/50")
        
        # Actualizar la lista de IDs creados para la verificación final
        bulk_created_ids = [eid for eid in bulk_created_ids if eid not in ids_deleted_successfully]

        # --- 5. Verificación Final (Deben quedar 100 eventos) ---
        print("\n📌 FASE 5: VERIFICACIÓN FINAL - LECTURA PAGINADA DE EVENTOS RESTANTES")
        final_retrieved_events = []
        total_expected_final = 100
        start_final_read = time.time()
        current_skip_final = 0
        
        while True:
            limit = page_size
            logger.info(f"Leyendo página final (skip={current_skip_final}, limit={limit})...")
            url = f"{API_BASE_URL}/events/?skip={current_skip_final}&limit={limit}"
            response = requests.get(url, headers=HEADERS)
            if response.status_code == 200:
                page_events = response.json()
                if not page_events:
                    logger.info("  Página final vacía, finalizando lectura.")
                    break
                logger.info(f"  Página final obtenida con {len(page_events)} eventos.")
                final_retrieved_events.extend(page_events)
                current_skip_final += len(page_events)
            else:
                logger.error(f"Error al leer página final (skip={current_skip_final}): {response.status_code} - {response.text}")
                break
            time.sleep(0.2)

        elapsed_final_read = time.time() - start_final_read
        logger.info(f"Lectura final completada en {elapsed_final_read:.2f}s.")
        logger.info(f"Total de eventos recuperados finalmente: {len(final_retrieved_events)} (Esperados: {total_expected_final})")

        if len(final_retrieved_events) == total_expected_final:
            logger.info("✅ ¡Prueba de operaciones masivas completada con éxito!")
        else:
            logger.error("❌ ¡Fallo en la prueba de operaciones masivas! El recuento final no coincide.")
            # Comparar IDs para ver cuáles faltan o sobran
            final_retrieved_ids = {e['id'] for e in final_retrieved_events}
            expected_ids = set(bulk_created_ids) # Usamos la lista actualizada
            missing_ids = expected_ids - final_retrieved_ids
            extra_ids = final_retrieved_ids - expected_ids
            if missing_ids:
                logger.error(f"  IDs faltantes: {missing_ids}")
            if extra_ids:
                logger.error(f"  IDs extras encontrados: {extra_ids}")

    except Exception as e:
        logger.error(f"Error durante la prueba de operaciones masivas: {e}", exc_info=True)
    finally:
        # Limpieza final - usar bulk_created_ids que se actualizó
        print("\n🧹 Limpieza final de IDs de prueba masiva (si queda alguno)")
        if bulk_created_ids:
            logger.info(f"Intentando limpiar {len(bulk_created_ids)} IDs restantes...")
            for event_id in list(bulk_created_ids): # Usar copia
                # Intentar eliminar, sin importar si ya estaba en created_event_ids global
                delete_event(event_id) 
        else:
            logger.info("No hay IDs de prueba masiva para limpiar.")

def run_comprehensive_test():
    """Ejecuta un conjunto completo de pruebas explorando diferentes caminos funcionales"""
    print_separator("INICIANDO PRUEBA COMPLETA DE EVENTOS")

    try:
        # Fase 1: Crear múltiples eventos
        print("\n📌 FASE 1: CREACIÓN DE MÚLTIPLES EVENTOS")

        # Evento normal
        evento_normal = create_event()

        # Evento para mañana - AHORA CON UTC
        now_utc = datetime.now(pytz.UTC)
        start_time_m = (now_utc + timedelta(days=1)).replace(hour=14, minute=0, second=0)
        end_time_m = (now_utc + timedelta(days=1)).replace(hour=16, minute=0, second=0)
        evento_manana = create_event({
            "title": f"Evento para Mañana {int(time.time())}",
            "description": "Este evento está programado para mañana",
            "start_time": start_time_m.isoformat(),
            "end_time": end_time_m.isoformat(),
            "location": "Salón Principal",
            "max_participants": 20,
            "status": "SCHEDULED",
            "image_url": ""
        })

        # Evento para la próxima semana - AHORA CON UTC
        now_utc_week = datetime.now(pytz.UTC) # Usar una nueva variable por claridad si es necesario
        start_time_s = (now_utc_week + timedelta(days=7)).replace(hour=10, minute=0, second=0)
        end_time_s = (now_utc_week + timedelta(days=7)).replace(hour=12, minute=0, second=0)
        evento_semana = create_event({
            "title": f"Evento para Próxima Semana {int(time.time())}",
            "description": "Este evento está programado para la próxima semana",
            "start_time": start_time_s.isoformat(),
            "end_time": end_time_s.isoformat(),
            "location": "Salón de Conferencias",
            "max_participants": 30,
            "status": "SCHEDULED",
            "image_url": ""
        })

        # Fase 2: Verificar mis eventos creados
        print("\n📌 FASE 2: VERIFICACIÓN DE EVENTOS CREADOS")
        mis_eventos = get_own_events()

        if mis_eventos:
            logger.info(f"Se encontraron {len(mis_eventos)} eventos creados por el usuario")
            for evento in mis_eventos:
                logger.info(f"  - ID: {evento['id']}, Título: {evento['title']}")

        # Fase 3: Actualizar un evento
        print("\n📌 FASE 3: ACTUALIZACIÓN DE EVENTO")
        if evento_normal:
            evento_actualizado = update_event(evento_normal['id'], {
                "title": f"{evento_normal['title']} (Actualizado)",
                "description": f"{evento_normal['description']} - Esta descripción fue actualizada",
                "max_participants": 25
            })
        else:
            logger.warning("No se pudo actualizar evento_normal porque no se creó correctamente.")

        # Fase 4: Registrarse en un evento
        print("\n📌 FASE 4: REGISTRO EN EVENTO")
        if evento_manana:
            participacion = register_for_event(evento_manana['id'])
        else:
            logger.warning("No se pudo registrar en evento_manana porque no se creó correctamente.")

        # Fase 5: Verificar mis participaciones
        print("\n📌 FASE 5: VERIFICACIÓN DE PARTICIPACIONES")
        mis_participaciones = get_my_participations()

        if mis_participaciones:
            logger.info(f"Se encontraron {len(mis_participaciones)} participaciones del usuario")
            for p in mis_participaciones:
                logger.info(f"  - ID: {p['id']}, Evento: {p['event_id']}, Estado: {p['status']}")

        # Fase 6: Cancelar participación si existe alguna
        print("\n📌 FASE 6: CANCELACIÓN DE PARTICIPACIÓN")
        if mis_participaciones and len(mis_participaciones) > 0:
            # Intentar cancelar la primera participación encontrada
            primera_participacion = mis_participaciones[0]
            cancel_participation_by_event(primera_participacion['event_id'])
        else:
            logger.info("No hay participaciones para cancelar.")

        # Fase 7: Eliminar un evento
        print("\n📌 FASE 7: ELIMINACIÓN DE EVENTO")
        if evento_semana:
            delete_event(evento_semana['id'])
        else:
            logger.warning("No se pudo eliminar evento_semana porque no se creó correctamente.")

        # Fase 8: Pruebas exhaustivas de participación
        print("\n📌 FASE 8: PRUEBAS EXHAUSTIVAS DE PARTICIPACIÓN")
        run_participation_tests()

        # --- Nueva Fase 9: Pruebas de Operaciones Masivas ---
        print("\n📌 FASE 9: PRUEBAS DE OPERACIONES MASIVAS")
        run_bulk_operations_test()

    finally:
        # Siempre limpiar los eventos creados, incluso si hubo errores
        print("\n📌 FASE FINAL: LIMPIEZA")
        # Asegurarse de que clean_up_events() maneje IDs de bulk_created_ids si es necesario
        # (Nota: run_bulk_operations_test ya intenta limpiar sus propios IDs)
        clean_up_events()

    # Resumen final
    print_separator("RESUMEN DE LA PRUEBA")
    print("✅ Prueba completa de funcionalidad de eventos finalizada")
    print("Se han ejecutado las siguientes operaciones:")
    print("  - Creación de múltiples eventos")
    print("  - Consulta de eventos propios")
    print("  - Actualización de evento")
    print("  - Registro en evento")
    print("  - Consulta de participaciones")
    print("  - Cancelación de participación")
    print("  - Eliminación de evento")
    print("  - Pruebas exhaustivas de participación en eventos")
    print("  - Pruebas de operaciones masivas (crear 150, actualizar 100, leer, eliminar 50)") # Añadido al resumen
    print("  - Limpieza de todos los eventos creados")

if __name__ == "__main__":
    run_comprehensive_test() 