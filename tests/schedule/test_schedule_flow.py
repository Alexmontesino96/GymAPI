#!/usr/bin/env python3
import requests
import json
from datetime import datetime, timedelta, date
import time
import random
import os

# Configuración de la prueba
API_BASE_URL = "https://gymapi-eh6m.onrender.com/api/v1"
# Token con permisos correctos - usar variable de entorno o un token reciente
AUTH_TOKEN =  "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6InI2YXBIZVNOUEluaXpaeDlYN1NidyJ9.eyJlbWFpbCI6ImFsZXhtb250ZXNpbm85NkBpY2xvdWQuY29tIiwiaXNzIjoiaHR0cHM6Ly9kZXYtZ2Q1Y3JmZTZxYnFsdTIzcC51cy5hdXRoMC5jb20vIiwic3ViIjoiYXV0aDB8NjdkNWQ2NGQ2NGNjZjFjNTIyYTY5NTBiIiwiYXVkIjpbImh0dHBzOi8vZ3ltYXBpIiwiaHR0cHM6Ly9kZXYtZ2Q1Y3JmZTZxYnFsdTIzcC51cy5hdXRoMC5jb20vdXNlcmluZm8iXSwiaWF0IjoxNzQ2MDI5MjgxLCJleHAiOjE3NDYxMTU2ODEsInNjb3BlIjoib3BlbmlkIHByb2ZpbGUgZW1haWwiLCJhenAiOiJPdUo2SUtFMGxKU2RhTUc2amFXMDRqZnB0c01SYnl2cCIsInBlcm1pc3Npb25zIjpbImFkbWluOmV2ZW50cyIsImFkbWluOmd5bXMiLCJhZG1pbjpyZWxhdGlvbnNoaXBzIiwiYWRtaW46dXNlcnMiLCJjcmVhdGU6Y2hhdF9yb29tcyIsImNyZWF0ZTpldmVudHMiLCJjcmVhdGU6cGFydGljaXBhdGlvbnMiLCJjcmVhdGU6cmVsYXRpb25zaGlwcyIsImNyZWF0ZTpzY2hlZHVsZXMiLCJkZWxldGU6ZXZlbnRzIiwiZGVsZXRlOm93bl9wYXJ0aWNpcGF0aW9ucyIsImRlbGV0ZTpyZWxhdGlvbnNoaXBzIiwiZGVsZXRlOnNjaGVkdWxlcyIsImRlbGV0ZTp1c2VycyIsIm1hbmFnZTpjaGF0X3Jvb21zIiwibWFuYWdlOmNsYXNzX3JlZ2lzdHJhdGlvbnMiLCJyZWFkX2V2ZW50cyIsInJlYWQ6Z3ltcyIsInJlYWQ6bWVtYmVycyIsInJlYWQ6b3duX2V2ZW50cyIsInJlYWQ6b3duX3BhcnRpY2lwYXRpb25zIiwicmVhZDpvd25fcmVsYXRpb25zaGlwcyIsInJlYWQ6b3duX3NjaGVkdWxlcyIsInJlYWQ6cGFydGljaXBhdGlvbnMiLCJyZWFkOnByb2ZpbGUiLCJyZWFkOnNjaGVkdWxlcyIsInJlYWQ6dXNlcnMiLCJyZWRhOmd5bV91c2VycyIsInJlZ2lzdGVyOmNsYXNzZXMiLCJ1cGRhdGU6cGFydGljaXBhdGlvbnMiLCJ1cGRhdGU6cmVsYXRpb25zaGlwcyIsInVwZGF0ZTpzY2hlZHVsZXMiLCJ1cGRhdGU6dXNlcnMiLCJ1c2U6Y2hhdCJdfQ.bnidtK96x8zoNyXRJ0B7vRsSZtBxGM8f71nll_MmlLb9LUGxUR1k5uEF-5KoWmMNnRbBgqqFJZ_ZiTnFkQ5UIStfuWaay5Re7d_zrOeO6ycsrQ0pJbLG31NIbAi-T6o__MCvCihRN0__ebXHhUGhsrUTT6ekEuR8ujfyU2t8di0Vjp8AKQjTVdEITx4xfyefZ6uY0H373kLv5mH0WrRJQ08gaPvpCfE5o_zj0avqWSzQlBMJ8oeEsazmPtVBNVsEz1I-xlriBA0YG_40yQI6sHmPmk3M85hM7MlxjxDPNqZ_1h6cF6na3dvv0WNsVdoeqGIzo_G3I-sJC87_RbsloQ"
GYM_ID = 1

# Headers comunes para todas las peticiones
HEADERS = {
    "Authorization": f"Bearer {AUTH_TOKEN}",
    "Content-Type": "application/json",
    "X-Gym-ID": str(GYM_ID),     # Header principal que espera el backend
    "x-tenant-id": str(GYM_ID)   # Mantener por compatibilidad
}

# Lista para almacenar los IDs de los recursos creados durante la prueba
created_categories = []
created_classes = []
created_sessions = []
created_participations = []

def print_separator(title):
    """Imprime un separador con un título para mejor legibilidad en la consola"""
    print("\n" + "=" * 80)
    print(f" {title} ".center(80, "="))
    print("=" * 80 + "\n")

# ===== OPERACIONES CON CATEGORÍAS =====

def get_categories(active_only=True):
    """Obtiene la lista de categorías de clases"""
    print_separator("CONSULTANDO CATEGORÍAS DE CLASES")
    
    params = {"active_only": str(active_only).lower()}
    url = f"{API_BASE_URL}/schedule/categories/categories"
    response = requests.get(url, headers=HEADERS, params=params)
    
    if response.status_code == 200:
        categories = response.json()
        print(f"✅ Categorías obtenidas exitosamente. Cantidad: {len(categories)}")
        if categories:
            for cat in categories[:3]:  # Mostrar solo las primeras 3 para no saturar la consola
                print(f"   ID: {cat['id']} - Nombre: {cat['name']}")
            if len(categories) > 3:
                print(f"   ... y {len(categories) - 3} más")
        return categories
    else:
        print(f"❌ Error al obtener categorías: {response.status_code}")
        print(response.text)
        return None

def create_category():
    """Crea una nueva categoría de clase"""
    print_separator("CREANDO CATEGORÍA DE CLASE")
    
    # Imprimir los headers para depuración
    print("Headers enviados:")
    for key, value in HEADERS.items():
        print(f"   {key}: {value}")
    
    # Datos de la categoría
    category_data = {
        "name": f"Categoría de Prueba {int(time.time())}",
        "description": "Esta es una categoría creada automáticamente para pruebas de integración",
        "color": "#" + ''.join([random.choice('0123456789ABCDEF') for _ in range(6)]),
        "icon": "fitness",
        "is_active": True,
        "gym_id": GYM_ID  # Incluir explícitamente el gym_id en el cuerpo de la petición
    }
    
    print(f"Datos de categoría enviados: {json.dumps(category_data, indent=2, ensure_ascii=False)}")
    
    url = f"{API_BASE_URL}/schedule/categories/categories"
    response = requests.post(url, headers=HEADERS, json=category_data)
    
    if response.status_code == 200:
        created_category = response.json()
        print(f"✅ Categoría creada exitosamente con ID: {created_category['id']}")
        print(f"   Nombre: {created_category['name']}")
        print(f"   Descripción: {created_category['description']}")
        print(f"   Color: {created_category['color']}")
        
        # Añadir a la lista de categorías creadas para limpiar después
        created_categories.append(created_category['id'])
        
        return created_category
    else:
        print(f"❌ Error al crear categoría: {response.status_code}")
        print(response.text)
        return None

def update_category(category_id, original_category):
    """Actualiza una categoría existente"""
    print_separator(f"ACTUALIZANDO CATEGORÍA {category_id}")
    
    # Datos para actualizar
    update_data = {
        "name": f"{original_category['name']} (Actualizada)",
        "description": f"{original_category['description']} - Esta descripción fue actualizada",
        "color": "#" + ''.join([random.choice('0123456789ABCDEF') for _ in range(6)])
    }
    
    url = f"{API_BASE_URL}/schedule/categories/categories/{category_id}"
    response = requests.put(url, headers=HEADERS, json=update_data)
    
    if response.status_code == 200:
        updated_category = response.json()
        print(f"✅ Categoría {category_id} actualizada exitosamente")
        print(f"   Nombre nuevo: {updated_category['name']}")
        print(f"   Descripción nueva: {updated_category['description']}")
        print(f"   Color nuevo: {updated_category['color']}")
        return updated_category
    else:
        print(f"❌ Error al actualizar categoría {category_id}: {response.status_code}")
        print(response.text)
        return None

def delete_category(category_id):
    """Elimina una categoría existente"""
    print_separator(f"ELIMINANDO CATEGORÍA {category_id}")
    
    url = f"{API_BASE_URL}/schedule/categories/categories/{category_id}"
    response = requests.delete(url, headers=HEADERS)
    
    if response.status_code == 200:
        print(f"✅ Categoría {category_id} eliminada exitosamente")
        # Eliminar de la lista de categorías creadas
        if category_id in created_categories:
            created_categories.remove(category_id)
        return True
    else:
        print(f"❌ Error al eliminar categoría {category_id}: {response.status_code}")
        print(response.text)
        return False

# ===== OPERACIONES CON CLASES =====

def get_classes():
    """Obtiene la lista de clases"""
    print_separator("CONSULTANDO CLASES")
    
    url = f"{API_BASE_URL}/schedule/classes/classes"
    response = requests.get(url, headers=HEADERS)
    
    if response.status_code == 200:
        classes = response.json()
        print(f"✅ Clases obtenidas exitosamente. Cantidad: {len(classes)}")
        if classes:
            for cls in classes[:3]:  # Mostrar solo las primeras 3 para no saturar la consola
                print(f"   ID: {cls['id']} - Nombre: {cls['name']}")
            if len(classes) > 3:
                print(f"   ... y {len(classes) - 3} más")
        return classes
    else:
        print(f"❌ Error al obtener clases: {response.status_code}")
        print(response.text)
        return None

def create_class(category_id):
    """Crea una nueva clase"""
    print_separator("CREANDO CLASE")
    
    # Datos de la clase
    class_data = {
        "name": f"Clase de Prueba {int(time.time())}",
        "description": "Esta es una clase creada automáticamente para pruebas de integración",
        "duration": 60,  # Duración en minutos
        "category_enum": "YOGA",  # Categoría predefinida
        "category_id": category_id,  # Categoría personalizada
        "max_capacity": 20,
        "difficulty_level": "intermediate",
        "is_active": True
    }
    
    url = f"{API_BASE_URL}/schedule/classes/classes"
    response = requests.post(url, headers=HEADERS, json=class_data)
    
    if response.status_code == 201:  # Código 201 para creaciones exitosas
        created_class = response.json()
        print(f"✅ Clase creada exitosamente con ID: {created_class['id']}")
        print(f"   Nombre: {created_class['name']}")
        print(f"   Descripción: {created_class['description']}")
        print(f"   Duración: {created_class['duration']} minutos")
        print(f"   Capacidad máxima: {created_class['max_capacity']} personas")
        
        # Añadir a la lista de clases creadas para limpiar después
        created_classes.append(created_class['id'])
        
        return created_class
    else:
        print(f"❌ Error al crear clase: {response.status_code}")
        print(response.text)
        return None

def update_class(class_id, original_class):
    """Actualiza una clase existente"""
    print_separator(f"ACTUALIZANDO CLASE {class_id}")
    
    # Datos para actualizar
    update_data = {
        "name": f"{original_class['name']} (Actualizada)",
        "description": f"{original_class['description']} - Esta descripción fue actualizada",
        "duration": original_class['duration'] + 15,  # Aumentar duración en 15 minutos
        "max_capacity": original_class['max_capacity'] + 5  # Aumentar capacidad en 5 personas
    }
    
    url = f"{API_BASE_URL}/schedule/classes/classes/{class_id}"
    response = requests.put(url, headers=HEADERS, json=update_data)
    
    if response.status_code == 200:
        updated_class = response.json()
        print(f"✅ Clase {class_id} actualizada exitosamente")
        print(f"   Nombre nuevo: {updated_class['name']}")
        print(f"   Descripción nueva: {updated_class['description']}")
        print(f"   Duración nueva: {updated_class['duration']} minutos")
        print(f"   Capacidad máxima nueva: {updated_class['max_capacity']} personas")
        return updated_class
    else:
        print(f"❌ Error al actualizar clase {class_id}: {response.status_code}")
        print(response.text)
        return None

def delete_class(class_id):
    """Elimina una clase existente"""
    print_separator(f"ELIMINANDO CLASE {class_id}")
    
    url = f"{API_BASE_URL}/schedule/classes/classes/{class_id}"
    response = requests.delete(url, headers=HEADERS)
    
    if response.status_code == 200:
        print(f"✅ Clase {class_id} eliminada exitosamente")
        # Eliminar de la lista de clases creadas
        if class_id in created_classes:
            created_classes.remove(class_id)
        return True
    else:
        print(f"❌ Error al eliminar clase {class_id}: {response.status_code}")
        print(response.text)
        return False

# ===== OPERACIONES CON SESIONES =====

def get_sessions():
    """Obtiene la lista de sesiones próximas"""
    print_separator("CONSULTANDO SESIONES PRÓXIMAS")
    
    url = f"{API_BASE_URL}/schedule/sessions/sessions"
    response = requests.get(url, headers=HEADERS)
    
    if response.status_code == 200:
        sessions = response.json()
        print(f"✅ Sesiones obtenidas exitosamente. Cantidad: {len(sessions)}")
        if sessions:
            for session in sessions[:3]:  # Mostrar solo las primeras 3
                start_time = datetime.fromisoformat(session['start_time'].replace('Z', '+00:00'))
                end_time = datetime.fromisoformat(session['end_time'].replace('Z', '+00:00'))
                print(f"   ID: {session['id']} - Clase: {session.get('class_definition', {}).get('name', 'N/A')}")
                print(f"   Fecha: {start_time.strftime('%d/%m/%Y')} - Hora: {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}")
                print(f"   Estado: {session['status']}")
                print()
            if len(sessions) > 3:
                print(f"   ... y {len(sessions) - 3} más")
        return sessions
    else:
        print(f"❌ Error al obtener sesiones: {response.status_code}")
        print(response.text)
        return None

def create_session(class_id):
    """Crea una nueva sesión de clase"""
    print_separator(f"CREANDO SESIÓN PARA CLASE {class_id}")
    
    # Fechas para la sesión (próxima semana)
    start_date = datetime.now() + timedelta(days=7)
    # Ajustar a las 10:00 AM
    start_time = datetime(
        start_date.year, start_date.month, start_date.day, 
        10, 0, 0, tzinfo=start_date.tzinfo or None
    )
    # Sesión de 1 hora
    end_time = start_time + timedelta(hours=1)
    
    # Obtener un ID de entrenador válido (normalmente este sería un entrenador real del gimnasio)
    trainer_id = 5  # ID de ejemplo - en producción obtener un entrenador real
    
    # Datos de la sesión
    session_data = {
        "class_id": class_id,
        "trainer_id": trainer_id,
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "room": "Sala Principal",
        "is_recurring": False,
        "status": "scheduled",
        "notes": "Sesión creada automáticamente para pruebas",
        "override_capacity": 25  # Sobreescribir capacidad específica para esta sesión
    }
    
    url = f"{API_BASE_URL}/schedule/sessions/sessions"
    response = requests.post(url, headers=HEADERS, json=session_data)
    
    if response.status_code == 201:
        created_session = response.json()
        print(f"✅ Sesión creada exitosamente con ID: {created_session['id']}")
        start_time = datetime.fromisoformat(created_session['start_time'].replace('Z', '+00:00'))
        end_time = datetime.fromisoformat(created_session['end_time'].replace('Z', '+00:00'))
        print(f"   Clase ID: {created_session['class_id']}")
        print(f"   Fecha: {start_time.strftime('%d/%m/%Y')}")
        print(f"   Horario: {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}")
        print(f"   Sala: {created_session['room']}")
        
        # Añadir a la lista de sesiones creadas para limpiar después
        created_sessions.append(created_session['id'])
        
        return created_session
    else:
        print(f"❌ Error al crear sesión: {response.status_code}")
        print(response.text)
        return None

def create_recurring_sessions(class_id):
    """Crea sesiones recurrentes para una clase"""
    print_separator(f"CREANDO SESIONES RECURRENTES PARA CLASE {class_id}")
    
    # Fechas para la sesión base (próxima semana)
    start_date = datetime.now() + timedelta(days=7)
    # Ajustar a las 18:00 (6 PM)
    start_time = datetime(
        start_date.year, start_date.month, start_date.day, 
        18, 0, 0, tzinfo=start_date.tzinfo or None
    )
    # Sesión de 1 hora
    end_time = start_time + timedelta(hours=1)
    
    # Obtener un ID de entrenador válido
    trainer_id = 5  # ID de ejemplo - en producción obtener un entrenador real
    
    # Definir el rango de fechas para la recurrencia (4 semanas)
    start_date_str = start_date.date().isoformat()
    end_date_str = (start_date + timedelta(days=28)).date().isoformat()
    
    # Días de la semana para recurrencia (0=Lunes, 1=Martes, 2=Miércoles, etc.)
    days_of_week = [0, 2, 4]  # Lunes, Miércoles, Viernes
    
    # Datos para la sesión base y recurrencia
    session_data = {
        "base_session": {
            "class_id": class_id,
            "trainer_id": trainer_id,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "room": "Sala de Entrenamiento",
            "status": "scheduled",
            "notes": "Sesión recurrente creada automáticamente para pruebas"
        },
        "start_date": start_date_str,
        "end_date": end_date_str,
        "days_of_week": days_of_week
    }
    
    url = f"{API_BASE_URL}/schedule/sessions/sessions/recurring"
    response = requests.post(url, headers=HEADERS, json=session_data)
    
    if response.status_code == 201 or response.status_code == 200:
        created_sessions_data = response.json()
        print(f"✅ Sesiones recurrentes creadas exitosamente")
        print(f"   Cantidad de sesiones creadas: {len(created_sessions_data)}")
        print(f"   Días de la semana: Lunes, Miércoles, Viernes")
        print(f"   Periodo: {start_date_str} hasta {end_date_str}")
        
        # Añadir a la lista de sesiones creadas para limpiar después
        for session in created_sessions_data:
            created_sessions.append(session['id'])
            
        return created_sessions_data
    else:
        print(f"❌ Error al crear sesiones recurrentes: {response.status_code}")
        print(response.text)
        return None

def update_session(session_id):
    """Actualiza una sesión existente"""
    print_separator(f"ACTUALIZANDO SESIÓN {session_id}")
    
    # Datos para actualizar
    update_data = {
        "room": "Sala Actualizada",
        "notes": f"Sesión actualizada el {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    }
    
    url = f"{API_BASE_URL}/schedule/sessions/sessions/{session_id}"
    response = requests.put(url, headers=HEADERS, json=update_data)
    
    if response.status_code == 200:
        updated_session = response.json()
        print(f"✅ Sesión {session_id} actualizada exitosamente")
        print(f"   Sala nueva: {updated_session['room']}")
        print(f"   Notas nuevas: {updated_session['notes']}")
        return updated_session
    else:
        print(f"❌ Error al actualizar sesión {session_id}: {response.status_code}")
        print(response.text)
        return None

def cancel_session(session_id):
    """Cancela una sesión"""
    print_separator(f"CANCELANDO SESIÓN {session_id}")
    
    url = f"{API_BASE_URL}/schedule/sessions/sessions/{session_id}/cancel"
    response = requests.post(url, headers=HEADERS)
    
    if response.status_code == 200:
        cancelled_session = response.json()
        print(f"✅ Sesión {session_id} cancelada exitosamente")
        print(f"   Estado actual: {cancelled_session['status']}")
        return cancelled_session
    else:
        print(f"❌ Error al cancelar sesión {session_id}: {response.status_code}")
        print(response.text)
        return None

# ===== OPERACIONES CON PARTICIPACIONES =====

def register_for_session(session_id):
    """Registra al usuario actual para una sesión"""
    print_separator(f"REGISTRANDO PARA LA SESIÓN {session_id}")
    
    url = f"{API_BASE_URL}/schedule/participation/register/{session_id}"
    response = requests.post(url, headers=HEADERS)
    
    if response.status_code == 201 or response.status_code == 200:
        participation = response.json()
        print(f"✅ Registro exitoso: {json.dumps(participation, indent=2, ensure_ascii=False)}")
        created_participations.append(participation.get('id'))
        return participation
    else:
        print(f"❌ Error al registrarse: {response.status_code}")
        print(response.text)
        return None

def register_member_for_session(session_id, member_id):
    """Registra a un miembro específico para una sesión (función administrativa)"""
    print_separator(f"REGISTRANDO MIEMBRO {member_id} PARA LA SESIÓN {session_id}")
    
    url = f"{API_BASE_URL}/schedule/participation/register/{session_id}/{member_id}"
    response = requests.post(url, headers=HEADERS)
    
    if response.status_code == 201 or response.status_code == 200:
        participation = response.json()
        print(f"✅ Registro de miembro exitoso: {json.dumps(participation, indent=2, ensure_ascii=False)}")
        created_participations.append(participation.get('id'))
        return participation
    else:
        print(f"❌ Error al registrar miembro: {response.status_code}")
        print(response.text)
        return None

def get_my_classes():
    """Obtiene las clases en las que está registrado el usuario actual"""
    print_separator("CONSULTANDO MIS CLASES")
    
    url = f"{API_BASE_URL}/schedule/participation/my-classes"
    response = requests.get(url, headers=HEADERS)
    
    if response.status_code == 200:
        participations = response.json()
        print(f"✅ Se encontraron {len(participations)} participaciones")
        for p in participations:
            print(f"  - Participación ID: {p.get('participation', {}).get('id')}")
            print(f"    Clase: {p.get('gym_class', {}).get('name')}")
            print(f"    Sesión: {p.get('session', {}).get('id')} - {p.get('session', {}).get('start_time')}")
            print(f"    Estado: {p.get('participation', {}).get('status')}")
        return participations
    else:
        print(f"❌ Error al obtener clases: {response.status_code}")
        print(response.text)
        return []

def get_member_classes(member_id):
    """Obtiene las clases en las que está registrado un miembro específico"""
    print_separator(f"CONSULTANDO CLASES DEL MIEMBRO {member_id}")
    
    url = f"{API_BASE_URL}/schedule/participation/member-classes/{member_id}"
    response = requests.get(url, headers=HEADERS)
    
    if response.status_code == 200:
        participations = response.json()
        print(f"✅ Se encontraron {len(participations)} participaciones para el miembro {member_id}")
        for p in participations:
            print(f"  - Participación ID: {p.get('participation', {}).get('id')}")
            print(f"    Clase: {p.get('gym_class', {}).get('name')}")
            print(f"    Sesión: {p.get('session', {}).get('id')} - {p.get('session', {}).get('start_time')}")
            print(f"    Estado: {p.get('participation', {}).get('status')}")
        return participations
    else:
        print(f"❌ Error al obtener clases del miembro: {response.status_code}")
        print(response.text)
        return []

def get_my_attendance_history():
    """Obtiene el historial de asistencia del usuario actual"""
    print_separator("CONSULTANDO MI HISTORIAL DE ASISTENCIA")
    
    url = f"{API_BASE_URL}/schedule/participation/my-history"
    response = requests.get(url, headers=HEADERS)
    
    if response.status_code == 200:
        history = response.json()
        print(f"✅ Se encontraron {len(history)} registros de asistencia")
        for entry in history[:3]:  # Mostrar solo los primeros 3 para brevedad
            print(f"  - Sesión: {entry.get('session_info', {}).get('id')}")
            print(f"    Clase: {entry.get('class_info', {}).get('name')}")
            print(f"    Fecha: {entry.get('session_info', {}).get('start_time')}")
            print(f"    Estado: {entry.get('status')}")
        if len(history) > 3:
            print(f"    ... y {len(history) - 3} registros más")
        return history
    else:
        print(f"❌ Error al obtener historial: {response.status_code}")
        print(response.text)
        return []

def get_member_attendance_history(member_id):
    """Obtiene el historial de asistencia de un miembro específico"""
    print_separator(f"CONSULTANDO HISTORIAL DE ASISTENCIA DEL MIEMBRO {member_id}")
    
    url = f"{API_BASE_URL}/schedule/participation/member/{member_id}/history"
    response = requests.get(url, headers=HEADERS)
    
    if response.status_code == 200:
        history = response.json()
        print(f"✅ Se encontraron {len(history)} registros de asistencia para el miembro {member_id}")
        for entry in history[:3]:  # Mostrar solo los primeros 3 para brevedad
            print(f"  - Sesión: {entry.get('session_info', {}).get('id')}")
            print(f"    Clase: {entry.get('class_info', {}).get('name')}")
            print(f"    Fecha: {entry.get('session_info', {}).get('start_time')}")
            print(f"    Estado: {entry.get('status')}")
        if len(history) > 3:
            print(f"    ... y {len(history) - 3} registros más")
        return history
    else:
        print(f"❌ Error al obtener historial: {response.status_code}")
        print(response.text)
        return []

def get_session_participants(session_id):
    """Obtiene la lista de participantes de una sesión"""
    print_separator(f"CONSULTANDO PARTICIPANTES DE LA SESIÓN {session_id}")
    
    url = f"{API_BASE_URL}/schedule/participation/participants/{session_id}"
    response = requests.get(url, headers=HEADERS)
    
    if response.status_code == 200:
        participants = response.json()
        print(f"✅ Participantes obtenidos exitosamente. Cantidad: {len(participants)}")
        return participants
    else:
        print(f"❌ Error al obtener participantes: {response.status_code}")
        print(response.text)
        return None

def cancel_registration(session_id):
    """Cancela el registro del usuario actual para una sesión"""
    print_separator(f"CANCELANDO REGISTRO PARA LA SESIÓN {session_id}")
    
    url = f"{API_BASE_URL}/schedule/participation/cancel-registration/{session_id}"
    response = requests.post(url, headers=HEADERS)
    
    if response.status_code == 200:
        cancelled = response.json()
        print(f"✅ Registro cancelado exitosamente para la sesión {session_id}")
        print(f"   Estado actual: {cancelled['status']}")
        return cancelled
    else:
        print(f"❌ Error al cancelar registro: {response.status_code}")
        print(response.text)
        return None

def cancel_member_registration(session_id, member_id):
    """Cancela el registro de un miembro específico para una sesión"""
    print_separator(f"CANCELANDO REGISTRO DEL MIEMBRO {member_id} PARA LA SESIÓN {session_id}")
    
    url = f"{API_BASE_URL}/schedule/participation/cancel-registration/{session_id}/{member_id}"
    response = requests.post(url, headers=HEADERS)
    
    if response.status_code == 200:
        cancelled = response.json()
        print(f"✅ Registro cancelado exitosamente para la sesión {session_id}")
        print(f"   Estado actual: {cancelled['status']}")
        return cancelled
    else:
        print(f"❌ Error al cancelar registro: {response.status_code}")
        print(response.text)
        return None

def mark_attendance(session_id, member_id):
    """Marca la asistencia de un miembro a una sesión"""
    print_separator(f"MARCANDO ASISTENCIA PARA LA SESIÓN {session_id}")
    
    url = f"{API_BASE_URL}/schedule/participation/attendance/{session_id}/{member_id}"
    response = requests.post(url, headers=HEADERS)
    
    if response.status_code == 200:
        attendance = response.json()
        print(f"✅ Asistencia marcada: {json.dumps(attendance, indent=2, ensure_ascii=False)}")
        return attendance
    else:
        print(f"❌ Error al marcar asistencia: {response.status_code}")
        print(response.text)
        return None

def mark_no_show(session_id, member_id):
    """Marca a un miembro como no presentado (no-show) a una sesión"""
    print_separator(f"MARCANDO NO-SHOW PARA LA SESIÓN {session_id}")
    
    url = f"{API_BASE_URL}/schedule/participation/mark-no-show/{session_id}/{member_id}"
    response = requests.post(url, headers=HEADERS)
    
    if response.status_code == 200:
        no_show = response.json()
        print(f"✅ No-show marcado: {json.dumps(no_show, indent=2, ensure_ascii=False)}")
        return no_show
    else:
        print(f"❌ Error al marcar no-show: {response.status_code}")
        print(response.text)
        return None

# ===== OPERACIONES ADICIONALES DE BÚSQUEDA =====

def get_sessions_by_date_range(start_date, end_date):
    """Obtiene las sesiones dentro de un rango de fechas"""
    print_separator(f"CONSULTANDO SESIONES ENTRE {start_date} Y {end_date}")
    
    # Convertir fechas a formato ISO si son objetos date/datetime
    if isinstance(start_date, (date, datetime)):
        start_date = start_date.isoformat()
    if isinstance(end_date, (date, datetime)):
        end_date = end_date.isoformat()
    
    url = f"{API_BASE_URL}/schedule/sessions/date-range"
    params = {"start_date": start_date, "end_date": end_date}
    response = requests.get(url, headers=HEADERS, params=params)
    
    if response.status_code == 200:
        sessions = response.json()
        print(f"✅ Sesiones obtenidas exitosamente. Cantidad: {len(sessions)}")
        if sessions:
            for session in sessions[:3]:  # Mostrar solo las primeras 3
                start_time = datetime.fromisoformat(session['start_time'].replace('Z', '+00:00'))
                print(f"   ID: {session['id']} - Fecha: {start_time.strftime('%d/%m/%Y %H:%M')}")
            if len(sessions) > 3:
                print(f"   ... y {len(sessions) - 3} más")
        return sessions
    else:
        print(f"❌ Error al obtener sesiones por rango de fechas: {response.status_code}")
        print(response.text)
        return None

def get_trainer_sessions(trainer_id):
    """Obtiene las sesiones asignadas a un entrenador específico"""
    print_separator(f"CONSULTANDO SESIONES DEL ENTRENADOR {trainer_id}")
    
    url = f"{API_BASE_URL}/schedule/sessions/trainer/{trainer_id}"
    response = requests.get(url, headers=HEADERS)
    
    if response.status_code == 200:
        sessions = response.json()
        print(f"✅ Sesiones del entrenador obtenidas exitosamente. Cantidad: {len(sessions)}")
        if sessions:
            for session in sessions[:3]:  # Mostrar solo las primeras 3
                start_time = datetime.fromisoformat(session['start_time'].replace('Z', '+00:00'))
                print(f"   ID: {session['id']} - Fecha: {start_time.strftime('%d/%m/%Y %H:%M')}")
            if len(sessions) > 3:
                print(f"   ... y {len(sessions) - 3} más")
        return sessions
    else:
        print(f"❌ Error al obtener sesiones del entrenador: {response.status_code}")
        print(response.text)
        return None

def get_classes_by_difficulty(difficulty_level):
    """Obtiene clases por nivel de dificultad (beginner, intermediate, advanced)"""
    print_separator(f"CONSULTANDO CLASES CON DIFICULTAD {difficulty_level}")
    
    url = f"{API_BASE_URL}/schedule/classes/classes/difficulty/{difficulty_level}"
    response = requests.get(url, headers=HEADERS)
    
    if response.status_code == 200:
        classes = response.json()
        print(f"✅ Clases obtenidas exitosamente. Cantidad: {len(classes)}")
        if classes:
            for cls in classes[:3]:  # Mostrar solo las primeras 3
                print(f"   ID: {cls['id']} - Nombre: {cls['name']} - Dificultad: {cls['difficulty_level']}")
            if len(classes) > 3:
                print(f"   ... y {len(classes) - 3} más")
        return classes
    else:
        print(f"❌ Error al obtener clases por dificultad: {response.status_code}")
        print(response.text)
        return None

# ===== LIMPIEZA DE RECURSOS =====

def cleanup():
    """Limpia los recursos creados durante la prueba"""
    print_separator("LIMPIEZA DE RECURSOS")
    
    # Cancelar participaciones creadas
    for participation_id in created_participations:
        try:
            # Buscamos primero la sesión asociada a esta participación
            url = f"{API_BASE_URL}/schedule/participation/{participation_id}"
            response = requests.get(url, headers=HEADERS)
            if response.status_code == 200:
                participation = response.json()
                url = f"{API_BASE_URL}/schedule/participation/cancel/{participation_id}"
                cancel_response = requests.post(url, headers=HEADERS)
                if cancel_response.status_code == 200:
                    print(f"✅ Participación {participation_id} cancelada")
                else:
                    print(f"❌ No se pudo cancelar la participación {participation_id}")
        except Exception as e:
            print(f"Error al cancelar participación {participation_id}: {str(e)}")
    
    # Cancelar sesiones creadas
    for session_id in created_sessions:
        try:
            url = f"{API_BASE_URL}/schedule/sessions/sessions/{session_id}/cancel"
            response = requests.post(url, headers=HEADERS)
            if response.status_code == 200:
                print(f"✅ Sesión {session_id} cancelada")
            else:
                print(f"❌ No se pudo cancelar la sesión {session_id}")
        except Exception as e:
            print(f"Error al cancelar sesión {session_id}: {str(e)}")
    
    # Eliminar clases creadas
    for class_id in created_classes:
        try:
            url = f"{API_BASE_URL}/schedule/classes/classes/{class_id}"
            response = requests.delete(url, headers=HEADERS)
            if response.status_code == 200:
                print(f"✅ Clase {class_id} eliminada")
            else:
                print(f"❌ No se pudo eliminar la clase {class_id}")
        except Exception as e:
            print(f"Error al eliminar clase {class_id}: {str(e)}")
    
    # Eliminar categorías creadas
    for category_id in created_categories:
        try:
            url = f"{API_BASE_URL}/schedule/categories/categories/{category_id}"
            response = requests.delete(url, headers=HEADERS)
            if response.status_code == 200:
                print(f"✅ Categoría {category_id} eliminada")
            else:
                print(f"❌ No se pudo eliminar la categoría {category_id}")
        except Exception as e:
            print(f"Error al eliminar categoría {category_id}: {str(e)}")
    
    print("✅ Limpieza completada")

# ===== FLUJO PRINCIPAL DE PRUEBA =====

def run_schedule_flow_test():
    """Ejecuta la prueba completa del flujo de programación de clases"""
    print("\n" + "=" * 80)
    print(" INICIANDO PRUEBA DE FLUJO COMPLETO PARA PROGRAMACIÓN DE CLASES ".center(80, "="))
    print("=" * 80 + "\n")
    
    try:
        # PARTE 1: PRUEBAS DE CLASES
        print("\n" + "=" * 80)
        print(" PARTE 1: PRUEBAS DE CLASES ".center(80, "="))
        print("=" * 80 + "\n")
        
        # Consultar clases por dificultad
        beginner_classes = get_classes_by_difficulty("beginner")
        
        # Consultar clases existentes
        existing_classes = get_classes()
        
        # Crear una clase nueva (sin categoría personalizada)
        class_obj = create_class(None)
        
        if class_obj:
            # Actualizar la clase creada
            update_class(class_obj['id'], class_obj)
            
            # PARTE 2: PRUEBAS DE SESIONES
            print("\n" + "=" * 80)
            print(" PARTE 2: PRUEBAS DE SESIONES ".center(80, "="))
            print("=" * 80 + "\n")
            
            # Consultar sesiones existentes
            existing_sessions = get_sessions()
            
            # Crear una sesión individual
            session_obj = create_session(class_obj['id'])
            
            if session_obj:
                # Actualizar la sesión
                update_session(session_obj['id'])
                
                # Consultar sesiones por rango de fechas (próximos 30 días)
                today = datetime.now().date()
                future_date = today + timedelta(days=30)
                date_range_sessions = get_sessions_by_date_range(today, future_date)
                
                # Consultar sesiones de un entrenador específico
                trainer_id = session_obj.get('trainer_id', 5)  # Usar el trainer_id de la sesión creada o el valor por defecto
                trainer_sessions = get_trainer_sessions(trainer_id)
                
                # PARTE 3: PRUEBAS DE PARTICIPACIÓN
                print("\n" + "=" * 80)
                print(" PARTE 3: PRUEBAS DE PARTICIPACIÓN ".center(80, "="))
                print("=" * 80 + "\n")
                
                # Registrarse para la sesión
                registration = register_for_session(session_obj['id'])
                
                if registration:
                    # Consultar mis clases
                    my_classes = get_my_classes()
                    
                    # Consultar participantes de la sesión
                    session_participants = get_session_participants(session_obj['id'])
                    
                    # Consultar historial de asistencia
                    my_history = get_my_attendance_history()
                    
                    # Cancelar registro
                    cancel_registration(session_obj['id'])
                
                # PARTE 4: PRUEBAS DE ADMINISTRACIÓN DE PARTICIPANTES
                print("\n" + "=" * 80)
                print(" PARTE 4: PRUEBAS DE ADMINISTRACIÓN DE PARTICIPANTES ".center(80, "="))
                print("=" * 80 + "\n")
                
                # Definir un ID de miembro para pruebas administrativas
                test_member_id = 5  # Este debe ser un ID válido en el sistema
                
                # Registrar miembro a la sesión (función administrativa)
                member_registration = register_member_for_session(session_obj['id'], test_member_id)
                
                if member_registration:
                    # Consultar clases del miembro
                    member_classes = get_member_classes(test_member_id)
                    
                    # Consultar historial de asistencia del miembro
                    member_history = get_member_attendance_history(test_member_id)
                    
                    # Marcar asistencia o no-show (alternamos para probar ambas funcionalidades)
                    # En una prueba real, solo marcaríamos una de las dos opciones
                    if random.choice([True, False]):
                        mark_attendance(session_obj['id'], test_member_id)
                    else:
                        mark_no_show(session_obj['id'], test_member_id)
                    
                    # Cancelar registro del miembro
                    cancel_member_registration(session_obj['id'], test_member_id)
                
                # Crear sesiones recurrentes
                recurring_sessions = create_recurring_sessions(class_obj['id'])
                
                if recurring_sessions and len(recurring_sessions) > 0:
                    # Cancelar una de las sesiones recurrentes
                    cancel_session(recurring_sessions[0]['id'])
        
        # PARTE 5: LIMPIEZA
        print("\n" + "=" * 80)
        print(" PARTE 5: LIMPIEZA DE RECURSOS ".center(80, "="))
        print("=" * 80 + "\n")
        
        # Limpiar los recursos creados
        cleanup()
        
    except Exception as e:
        print(f"\n❌ ERROR EN LA PRUEBA: {str(e)}")
        # Intentar limpiar recursos incluso si hay error
        try:
            cleanup()
        except:
            pass
        
        import traceback
        traceback.print_exc()

# Ejecutar la prueba si se ejecuta el script directamente
if __name__ == "__main__":
    run_schedule_flow_test() 