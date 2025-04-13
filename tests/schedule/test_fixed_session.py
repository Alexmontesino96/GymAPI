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

# Variables globales para almacenar IDs de recursos creados
created_class_id = None
created_session_id = None

def print_separator(title):
    """Imprime un separador con un título para mejor legibilidad en la consola"""
    print("\n" + "=" * 80)
    print(f" {title} ".center(80, "="))
    print("=" * 80 + "\n")

def create_class():
    """Crea una clase de prueba"""
    print_separator("CREANDO CLASE")
    
    class_data = {
        "name": "Clase de prueba con fix",
        "description": "Clase para probar la solución del gym_id",
        "duration": 60,
        "category": "YOGA",
        "max_capacity": 10,
        "difficulty_level": "intermediate",
        "equipment_needed": "Ninguno",
        "is_active": True
    }
    
    url = f"{API_BASE_URL}/schedule/classes"
    print(f"REQUEST: POST {url}")
    print(f"HEADERS: {json.dumps(HEADERS, indent=2)}")
    print(f"DATA: {json.dumps(class_data, indent=2)}")
    
    response = requests.post(url, headers=HEADERS, json=class_data)
    
    print(f"RESPONSE STATUS CODE: {response.status_code}")
    if response.status_code == 200:
        created_class = response.json()
        print(f"RESPONSE BODY: {json.dumps(created_class, indent=2)}")
        print(f"✅ Clase creada exitosamente con ID: {created_class['id']}")
        return created_class['id']
    else:
        print(f"❌ Error al crear clase: {response.status_code}")
        print(f"RESPONSE BODY: {response.text}")
        return None

def create_session(class_id):
    """Crea una sesión de prueba"""
    print_separator("CREANDO SESIÓN")
    
    # Crear fechas para la sesión (mañana)
    start_time = (datetime.now() + timedelta(days=1)).replace(hour=10, minute=0, second=0)
    end_time = (datetime.now() + timedelta(days=1)).replace(hour=11, minute=0, second=0)
    
    # Datos mínimos de la sesión
    session_data = {
        "class_id": class_id,
        "trainer_id": 6,  # Usando el ID 6 que es un entrenador válido en la base de datos
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat()
        # Ya no necesitamos incluir el gym_id explícitamente, se obtendrá del tenant
    }
    
    url = f"{API_BASE_URL}/schedule/sessions"
    print(f"REQUEST: POST {url}")
    print(f"HEADERS: {json.dumps(HEADERS, indent=2)}")
    print(f"DATA: {json.dumps(session_data, indent=2)}")
    
    response = requests.post(url, headers=HEADERS, json=session_data)
    
    print(f"RESPONSE STATUS CODE: {response.status_code}")
    if response.status_code == 200:
        created_session = response.json()
        print(f"RESPONSE BODY: {json.dumps(created_session, indent=2)}")
        print(f"✅ Sesión creada exitosamente con ID: {created_session['id']}")
        return created_session['id']
    else:
        print(f"❌ Error al crear sesión: {response.status_code}")
        print(f"RESPONSE BODY: {response.text}")
        return None

def cleanup(class_id, session_id):
    """Limpia los recursos creados durante la prueba"""
    print_separator("LIMPIEZA DE RECURSOS")
    
    if session_id:
        print(f"Eliminando sesión ID: {session_id}")
        url = f"{API_BASE_URL}/schedule/sessions/{session_id}"
        response = requests.delete(url, headers=HEADERS)
        if response.status_code in [200, 204]:
            print(f"✅ Sesión eliminada correctamente")
            try:
                print(f"Detalles de respuesta: {json.dumps(response.json(), indent=2)}")
            except:
                print("No hay cuerpo de respuesta JSON.")
        else:
            print(f"❌ Error al eliminar sesión: {response.status_code}")
            print(response.text)
    
    if class_id:
        print(f"Eliminando clase ID: {class_id}")
        url = f"{API_BASE_URL}/schedule/classes/{class_id}"
        response = requests.delete(url, headers=HEADERS)
        if response.status_code in [200, 204]:
            print(f"✅ Clase eliminada correctamente")
        else:
            print(f"❌ Error al eliminar clase: {response.status_code}")
            print(response.text)

def run_test():
    """Ejecuta la prueba completa"""
    print_separator("INICIANDO PRUEBA DE SOLUCIÓN PARA GYM_ID")
    
    class_id = None
    session_id = None
    
    try:
        # Crear clase
        class_id = create_class()
        if not class_id:
            print("❌ La prueba no puede continuar sin una clase")
            return
        
        # Esperar un momento
        time.sleep(1)
        
        # Crear sesión
        session_id = create_session(class_id)
        
        # Resumen final
        print_separator("RESUMEN DE LA PRUEBA")
        if session_id:
            print("✅ PRUEBA EXITOSA: El problema con gym_id ha sido resuelto.")
            print(f"   Se creó la clase con ID: {class_id}")
            print(f"   Se creó la sesión con ID: {session_id}")
        else:
            print("❌ PRUEBA FALLIDA: Aún hay problemas con la creación de sesiones.")
        
    finally:
        # Limpiar recursos
        cleanup(class_id, session_id)

if __name__ == "__main__":
    run_test() 