#!/usr/bin/env python3
import requests
import json
from datetime import datetime, timedelta
import time
import os

# Configuración de la prueba
API_BASE_URL = "http://localhost:8080/api/v1"
# Token con permisos correctos - usar variable de entorno o un token reciente
AUTH_TOKEN = os.environ.get("TEST_AUTH_TOKEN", "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6InI2YXBIZVNOUEluaXpaeDlYN1NidyJ9.eyJlbWFpbCI6ImFsZXhtb250ZXNpbm85NkBpY2xvdWQuY29tIiwiaXNzIjoiaHR0cHM6Ly9kZXYtZ2Q1Y3JmZTZxYnFsdTIzcC51cy5hdXRoMC5jb20vIiwic3ViIjoiYXV0aDB8NjdkNWQ2NGQ2NGNjZjFjNTIyYTY5NTBiIiwiYXVkIjpbImh0dHBzOi8vZ3ltYXBpIiwiaHR0cHM6Ly9kZXYtZ2Q1Y3JmZTZxYnFsdTIzcC51cy5hdXRoMC5jb20vdXNlcmluZm8iXSwiaWF0IjoxNzQ0MTcyODg3LCJleHAiOjE3NDQyNTkyODcsInNjb3BlIjoib3BlbmlkIHByb2ZpbGUgZW1haWwiLCJhenAiOiJPdUo2SUtFMGxKU2RhTUc2amFXMDRqZnB0c01SYnl2cCIsInBlcm1pc3Npb25zIjpbImFkbWluOmV2ZW50cyIsImFkbWluOmd5bXMiLCJhZG1pbjpyZWxhdGlvbnNoaXBzIiwiYWRtaW46dXNlcnMiLCJjcmVhdGU6Y2hhdF9yb29tcyIsImNyZWF0ZTpldmVudHMiLCJjcmVhdGU6cGFydGljaXBhdGlvbnMiLCJjcmVhdGU6cmVsYXRpb25zaGlwcyIsImNyZWF0ZTpzY2hlZHVsZXMiLCJkZWxldGU6ZXZlbnRzIiwiZGVsZXRlOm93bl9wYXJ0aWNpcGF0aW9ucyIsImRlbGV0ZTpyZWxhdGlvbnNoaXBzIiwiZGVsZXRlOnNjaGVkdWxlcyIsImRlbGV0ZTp1c2VycyIsIm1hbmFnZTpjaGF0X3Jvb21zIiwibWFuYWdlOmNsYXNzX3JlZ2lzdHJhdGlvbnMiLCJyZWFkX2V2ZW50cyIsInJlYWQ6Z3ltcyIsInJlYWQ6bWVtYmVycyIsInJlYWQ6b3duX2V2ZW50cyIsInJlYWQ6b3duX3BhcnRpY2lwYXRpb25zIiwicmVhZDpvd25fcmVsYXRpb25zaGlwcyIsInJlYWQ6b3duX3NjaGVkdWxlcyIsInJlYWQ6cGFydGljaXBhdGlvbnMiLCJyZWFkOnByb2ZpbGUiLCJyZWFkOnNjaGVkdWxlcyIsInJlYWQ6dXNlcnMiLCJyZWRhOmd5bV91c2VycyIsInJlZ2lzdGVyOmNsYXNzZXMiLCJ1cGRhdGU6cGFydGljaXBhdGlvbnMiLCJ1cGRhdGU6cmVsYXRpb25zaGlwcyIsInVwZGF0ZTpzY2hlZHVsZXMiLCJ1cGRhdGU6dXNlcnMiLCJ1c2U6Y2hhdCJdfQ.HI0BQ4H01txsoOmubk5klsO80nNWh5AQSoxHG15AcOkQcGS8pEnMuf_DdIfcUpBYw5TXkfZkFAg007xa7lTUcYkFrUkJczwpS8xRSGIu_qBAzfaPltvERUFlOEIRJQIIOnMWLjTPQssBHBobqfPFVmh-zEeecwq5Nz881wEG87pclxh7od-ifWxemu5fTqGgzFJ7U_2bpXOjuT179Cfz_E-AL_L--PF-n__DGGCHguc87MSCISOjUSSCWGJVrje-cOYQWjkEApwkUGo-4LIM1ynMIERFujTwlrOOIkMWZTT3hRvFuRi3cWO_L6yevH-XG8GLPilDag0W7twiuMmwNw")
GYM_ID = 1

# Headers comunes para todas las peticiones
HEADERS = {
    "Authorization": f"Bearer {AUTH_TOKEN}",
    "Content-Type": "application/json",
    "x-tenant-id": str(GYM_ID)
}

# Variables para almacenar recursos creados
created_class_id = None
created_session_id = None

def print_separator(title):
    """Imprime un separador con un título para mejor legibilidad"""
    print("\n" + "=" * 80)
    print(" " + title.center(78, " "))
    print("=" * 80 + "\n")

def print_request_info(method, url, headers, data=None):
    """Imprime información de una solicitud HTTP"""
    print(f"REQUEST: {method} {url}")
    print(f"HEADERS: {json.dumps(headers, indent=2)}")
    if data:
        print(f"DATA: {json.dumps(data, indent=2)}")

def print_response_info(response):
    """Imprime información de una respuesta HTTP"""
    print(f"RESPONSE STATUS CODE: {response.status_code}")
    try:
        # Intentar formatear como JSON si es posible
        response_json = response.json()
        print(f"RESPONSE BODY: {json.dumps(response_json, indent=2)}")
    except:
        # Si no es JSON, mostrar el texto plano
        print(f"RESPONSE BODY: {response.text}")

def create_class():
    """Crea una clase de prueba"""
    print_separator("CREANDO CLASE")
    
    class_data = {
        "name": "Clase de prueba sesiones",
        "description": "Clase para probar la creación de sesiones",
        "duration": 60,
        "category": "YOGA",
        "max_capacity": 10,
        "difficulty_level": "intermediate",
        "equipment_needed": "Ninguno",
        "is_active": True
    }
    
    print_request_info("POST", f"{API_BASE_URL}/schedule/classes", HEADERS, class_data)
    response = requests.post(f"{API_BASE_URL}/schedule/classes", headers=HEADERS, json=class_data)
    print_response_info(response)
    
    if response.status_code == 200:
        class_data = response.json()
        print(f"✅ Clase creada exitosamente con ID: {class_data['id']}")
        return class_data['id']
    else:
        print(f"❌ Error al crear clase: {response.status_code}")
        return None

def create_session(class_id):
    """Crea una sesión para la clase dada"""
    print_separator("CREANDO SESIÓN")
    
    # Datos fijos para facilitar la depuración
    start_time = datetime.now() + timedelta(days=1)
    start_time = start_time.replace(hour=10, minute=0, second=0)
    end_time = start_time + timedelta(hours=1)
    
    session_data = {
        "class_id": class_id,
        "trainer_id": 6,  # Actualizado para usar un ID de trainer válido
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "gym_id": GYM_ID
    }
    
    print_request_info("POST", f"{API_BASE_URL}/schedule/sessions", HEADERS, session_data)
    response = requests.post(f"{API_BASE_URL}/schedule/sessions", headers=HEADERS, json=session_data)
    print_response_info(response)
    
    if response.status_code == 200:
        session = response.json()
        print(f"✅ Sesión creada exitosamente con ID: {session['id']}")
        return session['id']
    else:
        print(f"❌ Error al crear sesión: {response.status_code}")
        return None

def create_session_simplified(class_id):
    """Intenta crear una sesión con menos campos"""
    print_separator("CREANDO SESIÓN SIN GYM_ID")
    
    # Datos mínimos necesarios para crear una sesión
    start_time = datetime.now() + timedelta(days=1)
    start_time = start_time.replace(hour=14, minute=0, second=0)
    end_time = start_time + timedelta(hours=1)
    
    # Datos mínimos para la sesión
    session_data = {
        "class_id": class_id,
        "trainer_id": 6,  # Actualizado para usar un ID de trainer válido
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat()
    }
    
    print_request_info("POST", f"{API_BASE_URL}/schedule/sessions", HEADERS, session_data)
    response = requests.post(f"{API_BASE_URL}/schedule/sessions", headers=HEADERS, json=session_data)
    print_response_info(response)
    
    if response.status_code == 200:
        session = response.json()
        print(f"✅ Sesión simplificada creada exitosamente con ID: {session['id']}")
        return session['id']
    else:
        print(f"❌ Error al crear sesión simplificada: {response.status_code}")
        return None

def delete_class(class_id):
    """Elimina una clase creada durante la prueba"""
    print(f"Eliminando clase ID: {class_id}")
    response = requests.delete(f"{API_BASE_URL}/schedule/classes/{class_id}", headers=HEADERS)
    
    if response.status_code == 200:
        print("✅ Clase eliminada correctamente")
        return True
    else:
        print(f"❌ Error al eliminar clase: {response.status_code}")
        return False

def cleanup():
    """Limpia los recursos creados durante la prueba"""
    print_separator("LIMPIEZA DE RECURSOS")
    
    if created_class_id:
        delete_class(created_class_id)

def run_test():
    """Ejecuta la prueba completa de sesiones"""
    global created_class_id, created_session_id
    
    print_separator("INICIANDO PRUEBA SIMPLE DE SESIONES")
    
    try:
        # Paso 1: Crear una clase
        class_id = create_class()
        if not class_id:
            print("❌ La prueba no puede continuar sin una clase")
            return
        
        created_class_id = class_id
        
        # Paso 2: Crear una sesión con campo gym_id
        session_id = create_session(class_id)
        
        # Paso 3: Crear sesión sin gym_id
        session_id_2 = create_session_simplified(class_id)
        
        # Resumen final
        print_separator("RESUMEN DE LA PRUEBA")
        print(f"✅ Clase creada con ID: {class_id}")
        print(f"{'✅' if session_id else '❌'} Primera sesión {'creada con ID: '+str(session_id) if session_id else 'no pudo ser creada'}")
        print(f"{'✅' if session_id_2 else '❌'} Segunda sesión {'creada con ID: '+str(session_id_2) if session_id_2 else 'no pudo ser creada'}")
        
    finally:
        # Limpiar recursos creados
        cleanup()

if __name__ == "__main__":
    run_test() 