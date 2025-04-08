#!/usr/bin/env python3
import requests
import json
from datetime import datetime, timedelta, date, time
import time as time_module
import random
import calendar
import os

# Configuración de la prueba
API_BASE_URL = "http://localhost:8080/api/v1"
# Token con permisos correctos - usar variable de entorno o un token reciente
AUTH_TOKEN = os.environ.get("TEST_AUTH_TOKEN", "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6InI2YXBIZVNOUEluaXpaeDlYN1NidyJ9.eyJlbWFpbCI6ImFsZXhtb250ZXNpbm85NkBpY2xvdWQuY29tIiwiaXNzIjoiaHR0cHM6Ly9kZXYtZ2Q1Y3JmZTZxYnFsdTIzcC51cy5hdXRoMC5jb20vIiwic3ViIjoiYXV0aDB8NjdkNWQ2NGQ2NGNjZjFjNTIyYTY5NTBiIiwiYXVkIjpbImh0dHBzOi8vZ3ltYXBpIiwiaHR0cHM6Ly9kZXYtZ2Q1Y3JmZTZxYnFsdTIzcC51cy5hdXRoMC5jb20vdXNlcmluZm8iXSwiaWF0IjoxNzQ0MDg4MDMwLCJleHAiOjE3NDQxNzQ0MzAsInNjb3BlIjoib3BlbmlkIHByb2ZpbGUgZW1haWwiLCJhenAiOiJPdUo2SUtFMGxKU2RhTUc2amFXMDRqZnB0c01SYnl2cCIsInBlcm1pc3Npb25zIjpbImFkbWluOmV2ZW50cyIsImFkbWluOmd5bXMiLCJhZG1pbjpyZWxhdGlvbnNoaXBzIiwiYWRtaW46dXNlcnMiLCJjcmVhdGU6Y2hhdF9yb29tcyIsImNyZWF0ZTpldmVudHMiLCJjcmVhdGU6cGFydGljaXBhdGlvbnMiLCJjcmVhdGU6cmVsYXRpb25zaGlwcyIsImNyZWF0ZTpzY2hlZHVsZXMiLCJkZWxldGU6ZXZlbnRzIiwiZGVsZXRlOm93bl9wYXJ0aWNpcGF0aW9ucyIsImRlbGV0ZTpyZWxhdGlvbnNoaXBzIiwiZGVsZXRlOnNjaGVkdWxlcyIsImRlbGV0ZTp1c2VycyIsIm1hbmFnZTpjaGF0X3Jvb21zIiwibWFuYWdlOmNsYXNzX3JlZ2lzdHJhdGlvbnMiLCJyZWFkX2V2ZW50cyIsInJlYWQ6Z3ltcyIsInJlYWQ6bWVtYmVycyIsInJlYWQ6b3duX2V2ZW50cyIsInJlYWQ6b3duX3BhcnRpY2lwYXRpb25zIiwicmVhZDpvd25fcmVsYXRpb25zaGlwcyIsInJlYWQ6b3duX3NjaGVkdWxlcyIsInJlYWQ6cGFydGljaXBhdGlvbnMiLCJyZWFkOnByb2ZpbGUiLCJyZWFkOnNjaGVkdWxlcyIsInJlYWQ6dXNlcnMiLCJyZWRhOmd5bV91c2VycyIsInJlZ2lzdGVyOmNsYXNzZXMiLCJ1cGRhdGU6cGFydGljaXBhdGlvbnMiLCJ1cGRhdGU6cmVsYXRpb25zaGlwcyIsInVwZGF0ZTpzY2hlZHVsZXMiLCJ1cGRhdGU6dXNlcnMiLCJ1c2U6Y2hhdCJdfQ.GhQJAMp9TVPJTj3rV8X9lplvBu0_mcISv4LHz3Tmtfsw8Iqtym-W_PgXmbAz3vXymX_nroWnv4wORvfNGtXa91AzEMZ8Iqh_XVqt3XgpPXaod7Fl1h-v-_2yQUQFxZWGj83049x9PQgqmb7K4zm_CHc_3VsxM-cpaTNCN6pVTXJqLxJbw00_dxJtr-8-YUx34A3TQf8z0hctgI6UHVQ_foZpLISuHP5i4AGGO1_BGE4Onb5EMp2l3Pj3ZbhPp92SlTuJPjJLigQZPUGg8-XexN9H4SjYnWyvyHrCXbnzpFntQSJU7h1VSveY36p-eJtle3e3xaDVxKk_RH6RMSjYxA")
GYM_ID = 1

# Headers comunes para todas las peticiones
HEADERS = {
    "Authorization": f"Bearer {AUTH_TOKEN}",
    "Content-Type": "application/json",
    "x-tenant-id": str(GYM_ID)
}

# Listas para almacenar los recursos creados
created_classes = []
created_sessions = []

# Datos fijos para los entrenadores
TRAINERS = {
    "yoga": 6,
    "crossfit": 6,
    "pilates": 6,
    "spinning": 6,
    "boxeo": 6
}

# Datos fijos para las salas
ROOMS = {
    "yoga": "Sala Zen",
    "crossfit": "Sala Funcional",
    "pilates": "Sala Reformers",
    "spinning": "Sala Cycling",
    "boxeo": "Sala de Boxeo"
}

# Definiciones de clases a crear
CLASS_TEMPLATES = [
    {
        "name": "Yoga Flow",
        "description": "Clase de yoga fluido para todos los niveles",
        "duration": 60,
        "category": "YOGA",
        "max_capacity": 15,
        "difficulty_level": "intermediate",
        "equipment_needed": "Esterilla, toalla, bloque de yoga",
        "is_active": True,
        "key": "yoga"
    },
    {
        "name": "CrossFit Training",
        "description": "Entrenamiento funcional de alta intensidad",
        "duration": 45,
        "category": "FUNCTIONAL",
        "max_capacity": 12,
        "difficulty_level": "advanced",
        "equipment_needed": "Peso libre, kettlebells, cajones de salto",
        "is_active": True,
        "key": "crossfit"
    },
    {
        "name": "Pilates Mat",
        "description": "Clase de pilates en colchoneta para fortalecer core",
        "duration": 55,
        "category": "PILATES",
        "max_capacity": 20,
        "difficulty_level": "beginner",
        "equipment_needed": "Esterilla, banda elástica",
        "is_active": True,
        "key": "pilates"
    },
    {
        "name": "Spinning Power",
        "description": "Clase de ciclismo indoor de alta intensidad",
        "duration": 45,
        "category": "CARDIO",
        "max_capacity": 25,
        "difficulty_level": "intermediate",
        "equipment_needed": "Bicicleta estática, toalla, botella de agua",
        "is_active": True,
        "key": "spinning"
    },
    {
        "name": "Box Training",
        "description": "Entrenamiento de boxeo para principiantes y nivel medio",
        "duration": 60,
        "category": "COMBAT",
        "max_capacity": 15,
        "difficulty_level": "intermediate",
        "equipment_needed": "Guantes de boxeo, vendas",
        "is_active": True,
        "key": "boxeo"
    }
]

# Configuración de horarios diarios (3 franjas por día)
DAILY_SCHEDULES = {
    0: [  # Lunes (0-6 donde 0 es lunes)
        {"hour": 9, "minute": 0, "classes": ["yoga", "pilates"]},
        {"hour": 13, "minute": 0, "classes": ["crossfit", "spinning"]},
        {"hour": 18, "minute": 30, "classes": ["boxeo", "yoga"]}
    ],
    1: [  # Martes
        {"hour": 8, "minute": 30, "classes": ["pilates", "spinning"]},
        {"hour": 14, "minute": 0, "classes": ["yoga", "boxeo"]},
        {"hour": 19, "minute": 0, "classes": ["crossfit", "pilates"]}
    ],
    2: [  # Miércoles
        {"hour": 9, "minute": 0, "classes": ["crossfit", "yoga"]},
        {"hour": 13, "minute": 0, "classes": ["boxeo", "spinning"]},
        {"hour": 18, "minute": 30, "classes": ["pilates", "crossfit"]}
    ],
    3: [  # Jueves
        {"hour": 8, "minute": 30, "classes": ["yoga", "boxeo"]},
        {"hour": 14, "minute": 0, "classes": ["spinning", "pilates"]},
        {"hour": 19, "minute": 0, "classes": ["crossfit", "yoga"]}
    ],
    4: [  # Viernes
        {"hour": 9, "minute": 0, "classes": ["pilates", "spinning"]},
        {"hour": 13, "minute": 0, "classes": ["yoga", "crossfit"]},
        {"hour": 18, "minute": 30, "classes": ["boxeo", "pilates"]}
    ],
    5: [  # Sábado
        {"hour": 10, "minute": 0, "classes": ["yoga", "crossfit"]},
        {"hour": 12, "minute": 0, "classes": ["spinning", "boxeo"]},
        {"hour": 17, "minute": 0, "classes": ["pilates", "yoga"]}
    ],
    6: [  # Domingo
        {"hour": 10, "minute": 0, "classes": ["yoga", "pilates"]},
        {"hour": 12, "minute": 0, "classes": ["crossfit", "spinning"]},
        {"hour": 16, "minute": 0, "classes": ["boxeo", "yoga"]}
    ]
}

def print_separator(title):
    """Imprime un separador con un título para mejor legibilidad en la consola"""
    print("\n" + "=" * 80)
    print(f" {title} ".center(80, "="))
    print("=" * 80 + "\n")

def get_classes():
    """Obtiene la lista de clases existentes"""
    print_separator("CONSULTANDO CLASES EXISTENTES")
    
    url = f"{API_BASE_URL}/schedule/classes"
    response = requests.get(url, headers=HEADERS)
    
    if response.status_code == 200:
        classes = response.json()
        print(f"✅ Clases obtenidas exitosamente. Cantidad: {len(classes)}")
        if classes:
            for cls in classes[:5]:  # Mostrar solo las primeras 5 para no saturar la consola
                print(f"   ID: {cls['id']} - Nombre: {cls['name']}")
            if len(classes) > 5:
                print(f"   ... y {len(classes) - 5} más")
        return classes
    else:
        print(f"❌ Error al obtener clases: {response.status_code}")
        print(response.text)
        return None

def create_class(class_data):
    """Crea una nueva clase"""
    print_separator(f"CREANDO CLASE: {class_data['name']}")
    
    # Copiar datos y eliminar la clave que no forma parte del esquema
    data_to_send = class_data.copy()
    if 'key' in data_to_send:
        del data_to_send['key']
    
    url = f"{API_BASE_URL}/schedule/classes"
    response = requests.post(url, headers=HEADERS, json=data_to_send)
    
    if response.status_code == 200:
        created_class = response.json()
        print(f"✅ Clase creada exitosamente con ID: {created_class['id']}")
        print(f"   Nombre: {created_class['name']}")
        print(f"   Duración: {created_class['duration']} minutos")
        print(f"   Capacidad máxima: {created_class['max_capacity']} personas")
        
        # Añadir a la lista de clases creadas
        created_classes.append({
            "id": created_class['id'],
            "name": created_class['name'],
            "key": class_data.get('key', ''),
            "duration": created_class['duration']
        })
        
        return created_class
    else:
        print(f"❌ Error al crear clase: {response.status_code}")
        print(response.text)
        return None

def create_session(class_id, session_date, session_time, duration, trainer_id, location, max_participants):
    """Crea una sesión individual"""
    # Combinar fecha y hora
    start_datetime = datetime.combine(session_date, session_time)
    end_datetime = start_datetime + timedelta(minutes=duration)
    
    # Imprimir mensaje informativo
    weekday_name = calendar.day_name[session_date.weekday()]
    print(f"▶️ Creando sesión: {weekday_name} {session_time} - Clase ID: {class_id}")
    
    session_data = {
        "class_id": class_id,
        "trainer_id": trainer_id,  # Ya actualizado a 6
        "location": location,
        "max_participants": max_participants,
        "notes": f"Sesión de {weekday_name}",
        "start_time": start_datetime.isoformat(),
        "end_time": end_datetime.isoformat(),
        "gym_id": GYM_ID
    }
    
    url = f"{API_BASE_URL}/schedule/sessions"
    response = requests.post(url, headers=HEADERS, json=session_data)
    
    if response.status_code == 200:
        session = response.json()
        # Guardar la sesión creada para limpiar después
        created_sessions.append({
            "id": session['id'],
            "class_id": class_id,
            "day": weekday_name,
            "time": session_time.strftime('%H:%M'),
            "class_name": next((cls['name'] for cls in created_classes if cls['id'] == class_id), "Desconocida")
        })
        return session
    else:
        print(f"     ❌ Error al crear sesión: {response.status_code}")
        if response.status_code == 500:
            print("       Error del servidor: Posiblemente problema con gym_id")
        return None

def setup_weekly_schedule(start_date=None, days=7):
    """Configura el horario para la próxima semana"""
    print_separator("CONFIGURANDO HORARIO SEMANAL")
    
    # Si no se especifica fecha de inicio, usar el próximo lunes
    if not start_date:
        today = date.today()
        days_ahead = 0 - today.weekday()  # 0 = lunes
        if days_ahead <= 0:  # Si hoy es lunes o después, ir al próximo lunes
            days_ahead += 7
        start_date = today + timedelta(days=days_ahead)
    
    print(f"Configurando horario desde: {start_date.strftime('%d/%m/%Y')} (Lunes)")
    
    # Mapear clases creadas por clave
    class_map = {cls['key']: cls['id'] for cls in created_classes if 'key' in cls}
    
    total_sessions = 0
    successful_sessions = 0
    
    # Para cada día de la semana
    for day_offset in range(days):
        current_date = start_date + timedelta(days=day_offset)
        weekday = current_date.weekday()  # 0 = lunes, 6 = domingo
        day_name = calendar.day_name[weekday]
        
        print(f"\n📆 Configurando sesiones para {day_name} ({current_date.strftime('%d/%m/%Y')})")
        
        # Obtener horarios para este día
        day_schedules = DAILY_SCHEDULES.get(weekday, [])
        
        # Para cada franja horaria de este día
        for time_slot in day_schedules:
            slot_hour, slot_minute = time_slot['hour'], time_slot['minute']
            slot_datetime = datetime.combine(current_date, time(slot_hour, slot_minute))
            
            print(f"  ⏰ Franja horaria: {slot_hour:02d}:{slot_minute:02d}")
            
            # Para cada clase en esta franja horaria
            for class_key in time_slot['classes']:
                if class_key in class_map:
                    class_id = class_map[class_key]
                    trainer_id = TRAINERS.get(class_key, 1)
                    location = ROOMS.get(class_key, "Sala Principal")
                    
                    # Crear la sesión
                    session = create_session(
                        class_id=class_id,
                        session_date=current_date,
                        session_time=slot_datetime.time(),
                        duration=next((cls['duration'] for cls in created_classes if cls['id'] == class_id), 60),
                        trainer_id=trainer_id,
                        location=location,
                        max_participants=15
                    )
                    
                    total_sessions += 1
                    if session:
                        successful_sessions += 1
    
    print(f"\n✅ Sesiones creadas: {successful_sessions}/{total_sessions}")
    return successful_sessions

def get_upcoming_sessions(limit=10):
    """Obtiene las próximas sesiones programadas"""
    print_separator("CONSULTANDO PRÓXIMAS SESIONES")
    
    url = f"{API_BASE_URL}/schedule/sessions?limit={limit}"
    response = requests.get(url, headers=HEADERS)
    
    if response.status_code == 200:
        sessions = response.json()
        print(f"✅ Sesiones obtenidas exitosamente. Cantidad: {len(sessions)}")
        
        if sessions:
            print("\nPróximas sesiones:")
            for session in sessions[:10]:  # Mostrar solo las primeras 10
                start_time = datetime.fromisoformat(session['start_time'].replace('Z', '+00:00'))
                print(f"   - ID: {session['id']} | Clase: {session['class_id']} | Fecha: {start_time.strftime('%d/%m/%Y %H:%M')}")
        
        return sessions
    else:
        print(f"❌ Error al obtener sesiones: {response.status_code}")
        print(response.text)
        return None

def get_sessions_by_date_range(start_date, end_date):
    """Obtiene sesiones en un rango de fechas"""
    print_separator(f"CONSULTANDO SESIONES ENTRE {start_date} Y {end_date}")
    
    url = f"{API_BASE_URL}/schedule/sessions?start_date={start_date}&end_date={end_date}"
    response = requests.get(url, headers=HEADERS)
    
    if response.status_code == 200:
        sessions = response.json()
        print(f"✅ Sesiones obtenidas exitosamente. Cantidad: {len(sessions)}")
        
        # Agrupar sesiones por día
        sessions_by_day = {}
        for session in sessions:
            start_time = datetime.fromisoformat(session['start_time'].replace('Z', '+00:00'))
            day_str = start_time.strftime('%Y-%m-%d')
            
            if day_str not in sessions_by_day:
                sessions_by_day[day_str] = []
            
            sessions_by_day[day_str].append(session)
        
        # Mostrar resumen por día
        for day, day_sessions in sorted(sessions_by_day.items()):
            day_date = datetime.strptime(day, '%Y-%m-%d')
            day_name = calendar.day_name[day_date.weekday()]
            print(f"\n📆 {day_name} {day}: {len(day_sessions)} sesiones")
            
            # Agrupar por hora
            sessions_by_hour = {}
            for session in day_sessions:
                start_time = datetime.fromisoformat(session['start_time'].replace('Z', '+00:00'))
                hour_str = start_time.strftime('%H:%M')
                
                if hour_str not in sessions_by_hour:
                    sessions_by_hour[hour_str] = []
                
                sessions_by_hour[hour_str].append(session)
            
            # Mostrar sesiones por hora
            for hour, hour_sessions in sorted(sessions_by_hour.items()):
                print(f"  ⏰ {hour}: {len(hour_sessions)} sesiones")
                for session in hour_sessions:
                    print(f"     - ID: {session['id']} | Clase: {session['class_id']}")
        
        return sessions
    else:
        print(f"❌ Error al obtener sesiones: {response.status_code}")
        print(response.text)
        return None

def update_session(session_id, update_data):
    """Actualiza una sesión existente"""
    print_separator(f"ACTUALIZANDO SESIÓN {session_id}")
    
    url = f"{API_BASE_URL}/schedule/sessions/{session_id}"
    response = requests.put(url, headers=HEADERS, json=update_data)
    
    if response.status_code == 200:
        updated_session = response.json()
        print(f"✅ Sesión {session_id} actualizada exitosamente")
        return updated_session
    else:
        print(f"❌ Error al actualizar sesión: {response.status_code}")
        print(response.text)
        return None

def cancel_session(session_id):
    """Cancela una sesión"""
    print_separator(f"CANCELANDO SESIÓN {session_id}")
    
    url = f"{API_BASE_URL}/schedule/sessions/{session_id}/cancel"
    response = requests.post(url, headers=HEADERS)
    
    if response.status_code == 200:
        cancelled_session = response.json()
        print(f"✅ Sesión {session_id} cancelada exitosamente")
        print(f"   Estado actual: {cancelled_session['status']}")
        return cancelled_session
    else:
        print(f"❌ Error al cancelar sesión: {response.status_code}")
        print(response.text)
        return None

def perform_weekly_adjustments():
    """Realiza ajustes comunes en el horario semanal"""
    print_separator("REALIZANDO AJUSTES EN EL HORARIO")
    
    if not created_sessions or len(created_sessions) < 5:
        print("❌ No hay suficientes sesiones creadas para hacer ajustes")
        return
    
    # 1. Cancelar una sesión (simular clase cancelada)
    session_to_cancel = created_sessions[0]
    print(f"1. Cancelando la sesión de {session_to_cancel['class_name']} ({session_to_cancel['day']} {session_to_cancel['time']})")
    cancel_result = cancel_session(session_to_cancel['id'])
    
    # 2. Cambiar ubicación de una sesión
    if len(created_sessions) > 1:
        session_to_update = created_sessions[1]
        print(f"2. Cambiando ubicación de la sesión de {session_to_update['class_name']} ({session_to_update['day']} {session_to_update['time']})")
        update_data = {
            "location": "Sala Temporal"
        }
        update_result = update_session(session_to_update['id'], update_data)
    
    # 3. Cambiar capacidad de una sesión
    if len(created_sessions) > 2:
        session_to_update = created_sessions[2]
        print(f"3. Aumentando capacidad de la sesión de {session_to_update['class_name']} ({session_to_update['day']} {session_to_update['time']})")
        update_data = {
            "max_participants": 25
        }
        update_result = update_session(session_to_update['id'], update_data)
    
    # 4. Añadir notas a una sesión
    if len(created_sessions) > 3:
        session_to_update = created_sessions[3]
        print(f"4. Añadiendo notas especiales a la sesión de {session_to_update['class_name']} ({session_to_update['day']} {session_to_update['time']})")
        update_data = {
            "notes": "¡Clase especial! Traer equipo adicional."
        }
        update_result = update_session(session_to_update['id'], update_data)

def cleanup():
    """Limpia los recursos creados durante las pruebas"""
    print_separator("LIMPIEZA DE RECURSOS")
    
    # Eliminar sesiones creadas
    print(f"Eliminando {len(created_sessions)} sesiones...")
    for session in created_sessions:
        session_id = session['id']
        print(f"  - Cancelando sesión ID: {session_id}")
        cancel_session(session_id)
    
    # Eliminar clases creadas
    print(f"Eliminando {len(created_classes)} clases...")
    for cls in created_classes:
        class_id = cls['id']
        print(f"  - Eliminando clase ID: {class_id} ({cls['name']})")
        
        url = f"{API_BASE_URL}/schedule/classes/{class_id}"
        response = requests.delete(url, headers=HEADERS)
        
        if response.status_code == 200:
            print(f"    ✅ Clase eliminada exitosamente")
        else:
            print(f"    ❌ Error al eliminar clase: {response.status_code}")
    
    print("✅ Limpieza completada")

def run_weekly_schedule_test():
    """Ejecuta la simulación completa de configuración de horario semanal"""
    print_separator("INICIANDO SIMULACIÓN DE CONFIGURACIÓN DE HORARIO SEMANAL")
    
    try:
        # Paso 1: Obtener clases existentes
        get_classes()
        
        # Paso 2: Crear plantillas de clases
        print_separator("CREANDO PLANTILLAS DE CLASE")
        for template in CLASS_TEMPLATES:
            create_class(template)
        
        # Verificar que se hayan creado las clases
        if not created_classes or len(created_classes) < 3:
            print("❌ No se pudieron crear suficientes plantillas de clase, abortando prueba")
            return
        
        # Paso 3: Configurar horario semanal
        next_monday = date.today() + timedelta(days=(7 - date.today().weekday()))
        setup_success = setup_weekly_schedule(start_date=next_monday)
        
        if not setup_success:
            print("❌ No se pudo configurar correctamente el horario semanal")
            return
        
        # Paso 4: Consultar próximas sesiones
        get_upcoming_sessions()
        
        # Paso 5: Consultar sesiones por rango de fechas
        start_date = next_monday.strftime('%Y-%m-%d')
        end_date = (next_monday + timedelta(days=6)).strftime('%Y-%m-%d')
        get_sessions_by_date_range(start_date, end_date)
        
        # Paso 6: Realizar ajustes comunes en el horario
        perform_weekly_adjustments()
        
        # Paso 7: Consultar de nuevo para ver los cambios
        print_separator("VERIFICANDO CAMBIOS EN EL HORARIO")
        get_sessions_by_date_range(start_date, end_date)
        
        # Resumen final
        print_separator("RESUMEN DE LA SIMULACIÓN")
        print(f"✅ Se han creado {len(created_classes)} plantillas de clase")
        print(f"✅ Se han programado {len(created_sessions)} sesiones para la semana")
        print(f"✅ Se han realizado ajustes en el horario (cancelaciones, cambios de ubicación, etc.)")
        print("\n🔍 La simulación ha completado todas las operaciones típicas de un administrador")
        print("   que configura el horario semanal del gimnasio")
    
    finally:
        # Limpiar recursos creados durante la prueba
        cleanup()

if __name__ == "__main__":
    run_weekly_schedule_test() 