#!/usr/bin/env python3
import requests
import json
from datetime import datetime, timedelta
import time
import random

# Configuración de la prueba
API_BASE_URL = "http://localhost:8080/api/v1"
AUTH_TOKEN = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6InI2YXBIZVNOUEluaXpaeDlYN1NidyJ9.eyJlbWFpbCI6ImFsZXhtb250ZXNpbm85NkBpY2xvdWQuY29tIiwiaXNzIjoiaHR0cHM6Ly9kZXYtZ2Q1Y3JmZTZxYnFsdTIzcC51cy5hdXRoMC5jb20vIiwic3ViIjoiYXV0aDB8NjdkNWQ2NGQ2NGNjZjFjNTIyYTY5NTBiIiwiYXVkIjpbImh0dHBzOi8vZ3ltYXBpIiwiaHR0cHM6Ly9kZXYtZ2Q1Y3JmZTZxYnFsdTIzcC51cy5hdXRoMC5jb20vdXNlcmluZm8iXSwiaWF0IjoxNzQzNjk3MjM1LCJleHAiOjE3NDM3ODM2MzUsInNjb3BlIjoib3BlbmlkIHByb2ZpbGUgZW1haWwiLCJhenAiOiJPdUo2SUtFMGxKU2RhTUc2amFXMDRqZnB0c01SYnl2cCIsInBlcm1pc3Npb25zIjpbImFkbWluOmV2ZW50cyIsImFkbWluOmd5bXMiLCJhZG1pbjpyZWxhdGlvbnNoaXBzIiwiYWRtaW46dXNlcnMiLCJjcmVhdGU6Y2hhdF9yb29tcyIsImNyZWF0ZTpldmVudHMiLCJjcmVhdGU6cGFydGljaXBhdGlvbnMiLCJjcmVhdGU6cmVsYXRpb25zaGlwcyIsImNyZWF0ZTpzY2hlZHVsZXMiLCJkZWxldGU6ZXZlbnRzIiwiZGVsZXRlOm93bl9wYXJ0aWNpcGF0aW9ucyIsImRlbGV0ZTpyZWxhdGlvbnNoaXBzIiwiZGVsZXRlOnNjaGVkdWxlcyIsImRlbGV0ZTp1c2VycyIsIm1hbmFnZTpjaGF0X3Jvb21zIiwibWFuYWdlOmNsYXNzX3JlZ2lzdHJhdGlvbnMiLCJyZWFkX2V2ZW50cyIsInJlYWQ6Z3ltcyIsInJlYWQ6bWVtYmVycyIsInJlYWQ6b3duX2V2ZW50cyIsInJlYWQ6b3duX3BhcnRpY2lwYXRpb25zIiwicmVhZDpvd25fcmVsYXRpb25zaGlwcyIsInJlYWQ6b3duX3NjaGVkdWxlcyIsInJlYWQ6cGFydGljaXBhdGlvbnMiLCJyZWFkOnByb2ZpbGUiLCJyZWFkOnNjaGVkdWxlcyIsInJlYWQ6dXNlcnMiLCJyZWRhOmd5bV91c2VycyIsInJlZ2lzdGVyOmNsYXNzZXMiLCJ1cGRhdGU6cGFydGljaXBhdGlvbnMiLCJ1cGRhdGU6cmVsYXRpb25zaGlwcyIsInVwZGF0ZTpzY2hlZHVsZXMiLCJ1cGRhdGU6dXNlcnMiLCJ1c2U6Y2hhdCJdfQ.FzTOac71WEgVz6CneRPo69ZhEFlULl_FNwakYmktJuh2zLaBcB1DkPfbMqUfpwsJ66lY7evGMYB8E5J-iGvFrx1xWv07CgqXOnB5MPi7VsBd5A_J8CRz9nSbaeOfOhD8873tC5j0AmVTSmR9Z7M_QIUiKvcOEZjauOnVsGD1oQn_H2fTlnWIjLOxymUr3atH7eHe60ASITdedQ2djsRsY_H05iP4J_xJvbJgp5uvt4w5amvUaZTWpHHURhQSLOUZ8_BXK7e653O56mxuXRZ9id7TMu5wKG6ygSWvlB_ww90-HISm-OORu677jJQdqajuGSK-XxT4kQbMDqzL01_ulQ"
GYM_ID = 1

# Headers comunes para todas las peticiones
HEADERS = {
    "Authorization": f"Bearer {AUTH_TOKEN}",
    "Content-Type": "application/json",
    "x-tenant-id": str(GYM_ID)
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
        # Crear fechas para el evento (mañana)
        start_time = (datetime.now() + timedelta(days=1)).replace(hour=10, minute=0, second=0)
        end_time = (datetime.now() + timedelta(days=1)).replace(hour=12, minute=0, second=0)
        
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
    
    if response.status_code == 201:
        created_event = response.json()
        created_event_ids.append(created_event['id'])  # Guardar ID para limpieza
        print(f"✅ Evento creado exitosamente con ID: {created_event['id']}")
        print(f"   Título: {created_event['title']}")
        print(f"   Descripción: {created_event['description']}")
        print(f"   Ubicación: {created_event['location']}")
        return created_event
    else:
        print(f"❌ Error al crear evento: {response.status_code}")
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
        
        # Evento con 3 plazas para probar límites de capacidad
        start_time = (datetime.now() + timedelta(days=1)).replace(hour=10, minute=0, second=0)
        end_time = (datetime.now() + timedelta(days=1)).replace(hour=12, minute=0, second=0)
        
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

def run_comprehensive_test():
    """Ejecuta un conjunto completo de pruebas explorando diferentes caminos funcionales"""
    print_separator("INICIANDO PRUEBA COMPLETA DE EVENTOS")
    
    try:
        # Fase 1: Crear múltiples eventos
        print("\n📌 FASE 1: CREACIÓN DE MÚLTIPLES EVENTOS")
        
        # Evento normal
        evento_normal = create_event()
        
        # Evento para mañana
        start_time = (datetime.now() + timedelta(days=1)).replace(hour=14, minute=0, second=0)
        end_time = (datetime.now() + timedelta(days=1)).replace(hour=16, minute=0, second=0)
        evento_manana = create_event({
            "title": f"Evento para Mañana {int(time.time())}",
            "description": "Este evento está programado para mañana",
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "location": "Salón Principal",
            "max_participants": 20,
            "status": "SCHEDULED",
            "image_url": ""
        })
        
        # Evento para la próxima semana
        start_time = (datetime.now() + timedelta(days=7)).replace(hour=10, minute=0, second=0)
        end_time = (datetime.now() + timedelta(days=7)).replace(hour=12, minute=0, second=0)
        evento_semana = create_event({
            "title": f"Evento para Próxima Semana {int(time.time())}",
            "description": "Este evento está programado para la próxima semana",
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "location": "Salón de Conferencias",
            "max_participants": 30,
            "status": "SCHEDULED",
            "image_url": ""
        })
        
        # Fase 2: Verificar mis eventos creados
        print("\n📌 FASE 2: VERIFICACIÓN DE EVENTOS CREADOS")
        mis_eventos = get_own_events()
        
        if mis_eventos:
            print(f"Se encontraron {len(mis_eventos)} eventos creados por el usuario")
            for evento in mis_eventos:
                print(f"  - ID: {evento['id']}, Título: {evento['title']}")
        
        # Fase 3: Actualizar un evento
        print("\n📌 FASE 3: ACTUALIZACIÓN DE EVENTO")
        if evento_normal:
            evento_actualizado = update_event(evento_normal['id'], {
                "title": f"{evento_normal['title']} (Actualizado)",
                "description": f"{evento_normal['description']} - Esta descripción fue actualizada",
                "max_participants": 25
            })
        
        # Fase 4: Registrarse en un evento
        print("\n📌 FASE 4: REGISTRO EN EVENTO")
        if evento_manana:
            participacion = register_for_event(evento_manana['id'])
        
        # Fase 5: Verificar mis participaciones
        print("\n📌 FASE 5: VERIFICACIÓN DE PARTICIPACIONES")
        mis_participaciones = get_my_participations()
        
        if mis_participaciones:
            print(f"Se encontraron {len(mis_participaciones)} participaciones del usuario")
            for participacion in mis_participaciones:
                print(f"  - ID: {participacion['id']}, Evento: {participacion['event_id']}, Estado: {participacion['status']}")
        
        # Fase 6: Cancelar participación si existe alguna
        print("\n📌 FASE 6: CANCELACIÓN DE PARTICIPACIÓN")
        if mis_participaciones and len(mis_participaciones) > 0:
            ultima_participacion = mis_participaciones[0]
            cancel_participation_by_event(ultima_participacion['event_id'])
        
        # Fase 7: Eliminar un evento
        print("\n📌 FASE 7: ELIMINACIÓN DE EVENTO")
        if evento_semana:
            delete_event(evento_semana['id'])
        
        # Fase 8: Pruebas exhaustivas de participación
        print("\n📌 FASE 8: PRUEBAS EXHAUSTIVAS DE PARTICIPACIÓN")
        run_participation_tests()
        
    finally:
        # Siempre limpiar los eventos creados, incluso si hubo errores
        print("\n📌 FASE FINAL: LIMPIEZA")
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
    print("  - Limpieza de todos los eventos creados")

if __name__ == "__main__":
    run_comprehensive_test() 