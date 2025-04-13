#!/usr/bin/env python3
import requests
import json
from datetime import datetime, timedelta
import time
import random
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

# Lista para almacenar los IDs de los recursos creados durante la prueba
created_classes = []

def print_separator(title):
    """Imprime un separador con un título para mejor legibilidad en la consola"""
    print("\n" + "=" * 80)
    print(f" {title} ".center(80, "="))
    print("=" * 80 + "\n")

def get_classes():
    """Obtiene la lista de clases"""
    print_separator("CONSULTANDO CLASES")
    
    url = f"{API_BASE_URL}/schedule/classes"
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

def create_class():
    """Crea una nueva clase"""
    print_separator("CREANDO CLASE")
    
    # Datos de la clase
    class_data = {
        "name": f"Clase de Prueba {int(time.time())}",
        "description": "Esta es una clase creada automáticamente para pruebas de integración",
        "duration": 60,  # Duración en minutos
        "category": "YOGA",  # Categoría predefinida
        "max_capacity": 20,
        "difficulty_level": "intermediate",
        "equipment_needed": "Esterilla, toalla",
        "is_active": True
    }
    
    url = f"{API_BASE_URL}/schedule/classes"
    response = requests.post(url, headers=HEADERS, json=class_data)
    
    if response.status_code == 200:
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

def get_class_by_id(class_id):
    """Obtiene detalles de una clase específica por ID"""
    print_separator(f"CONSULTANDO DETALLES DE CLASE {class_id}")
    
    url = f"{API_BASE_URL}/schedule/classes/{class_id}"
    response = requests.get(url, headers=HEADERS)
    
    if response.status_code == 200:
        class_obj = response.json()
        print(f"✅ Clase {class_id} obtenida exitosamente")
        print(f"   Nombre: {class_obj['name']}")
        print(f"   Descripción: {class_obj['description']}")
        print(f"   Duración: {class_obj['duration']} minutos")
        return class_obj
    else:
        print(f"❌ Error al obtener detalles de clase {class_id}: {response.status_code}")
        print(response.text)
        return None

def update_class(class_id, original_class):
    """Actualiza una clase existente"""
    print_separator(f"ACTUALIZANDO CLASE {class_id}")
    
    # Datos para actualizar
    update_data = {
        "name": f"{original_class['name']} (Actualizada)",
        "description": f"{original_class['description']} - Esta descripción fue actualizada",
        "max_capacity": 25,
        "equipment_needed": "Esterilla, toalla, bloque de yoga"
    }
    
    url = f"{API_BASE_URL}/schedule/classes/{class_id}"
    response = requests.put(url, headers=HEADERS, json=update_data)
    
    if response.status_code == 200:
        updated_class = response.json()
        print(f"✅ Clase {class_id} actualizada exitosamente")
        print(f"   Nombre nuevo: {updated_class['name']}")
        print(f"   Descripción nueva: {updated_class['description']}")
        print(f"   Capacidad máxima nueva: {updated_class['max_capacity']} personas")
        return updated_class
    else:
        print(f"❌ Error al actualizar clase {class_id}: {response.status_code}")
        print(response.text)
        return None

def delete_class(class_id):
    """Elimina una clase existente"""
    print_separator(f"ELIMINANDO CLASE {class_id}")
    
    url = f"{API_BASE_URL}/schedule/classes/{class_id}"
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

def verify_class_deleted(class_id):
    """Verifica que una clase haya sido eliminada correctamente"""
    print_separator(f"VERIFICANDO ELIMINACIÓN DE CLASE {class_id}")
    
    url = f"{API_BASE_URL}/schedule/classes/{class_id}"
    response = requests.get(url, headers=HEADERS)
    
    if response.status_code == 404:
        print(f"✅ Clase {class_id} no se encuentra, confirmando eliminación exitosa")
        return True
    else:
        print(f"❌ La clase {class_id} todavía existe o hay otro error: {response.status_code}")
        print(response.text)
        return False

def cleanup():
    """Limpia los recursos creados durante las pruebas"""
    print_separator("LIMPIEZA DE RECURSOS")
    
    # Eliminar clases creadas
    for class_id in list(created_classes):
        print(f"Eliminando clase {class_id}...")
        delete_class(class_id)
    
    print("✅ Limpieza completada")

def run_classes_crud_test():
    """Ejecuta la prueba CRUD completa para clases"""
    print_separator("INICIANDO PRUEBA CRUD PARA CLASES")
    
    try:
        # Paso 1: Listar clases existentes
        get_classes()
        
        # Paso 2: Crear una nueva clase
        new_class = create_class()
        if not new_class:
            print("❌ No se pudo crear la clase, abortando prueba")
            return
            
        class_id = new_class["id"]
        
        # Paso 3: Obtener la clase por ID
        get_class_by_id(class_id)
        
        # Paso 4: Actualizar la clase
        updated_class = update_class(class_id, new_class)
        if not updated_class:
            print("❌ No se pudo actualizar la clase, continuando con la prueba")
        
        # Paso 5: Eliminar la clase
        delete_result = delete_class(class_id)
        if not delete_result:
            print("❌ No se pudo eliminar la clase")
            return
            
        # Paso 6: Verificar que la clase se eliminó correctamente
        verify_class_deleted(class_id)
        
        # Resumen final
        print_separator("RESUMEN DE LA PRUEBA")
        print("✅ Prueba CRUD para clases completada exitosamente")
    
    finally:
        # Limpiar recursos creados durante la prueba
        cleanup()

if __name__ == "__main__":
    run_classes_crud_test() 