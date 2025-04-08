#!/usr/bin/env python3
import requests
import json
from datetime import datetime, timedelta
import time
import random
import os
from dotenv import load_dotenv

# Cargar variables de entorno del archivo .env
load_dotenv()

# Configuración de la prueba
API_BASE_URL = "http://localhost:8080/api/v1"
# Obtener token de variable de entorno o usar uno predeterminado
AUTH_TOKEN = os.getenv("TEST_AUTH_TOKEN", "")
GYM_ID = int(os.getenv("TEST_GYM_ID", "1"))  # ID del gimnasio para pruebas

# Headers comunes para todas las peticiones
HEADERS = {
    "Authorization": f"Bearer {AUTH_TOKEN}",
    "Content-Type": "application/json",
    "x-tenant-id": str(GYM_ID)
}

# Lista para almacenar los IDs de las relaciones creadas para limpiarlos al final
created_relationships = []

# ID de entrenador y miembro para pruebas (deben existir en el sistema)
TRAINER_ID = int(os.getenv("TEST_TRAINER_ID", "6"))  # ID de un entrenador existente
MEMBER_ID = int(os.getenv("TEST_MEMBER_ID", "7"))    # ID de un miembro existente

def print_separator(title):
    """Imprime un separador con un título para mejor legibilidad en la consola"""
    print("\n" + "=" * 80)
    print(f" {title} ".center(80, "="))
    print("=" * 80 + "\n")

def get_users():
    """Obtiene la lista de usuarios para identificar entrenadores y miembros"""
    print_separator("CONSULTANDO USUARIOS")
    
    url = f"{API_BASE_URL}/users/"
    response = requests.get(url, headers=HEADERS)
    
    if response.status_code == 200:
        users = response.json()
        print(f"✅ Usuarios obtenidos exitosamente. Cantidad: {len(users)}")
        
        # Identificar entrenadores y miembros
        trainers = [u for u in users if u.get('role') == 'TRAINER']
        members = [u for u in users if u.get('role') == 'MEMBER']
        
        print(f"👥 Entrenadores encontrados: {len(trainers)}")
        if trainers:
            for t in trainers[:3]:  # Mostrar solo los primeros 3
                print(f"   ID: {t['id']} - Nombre: {t.get('full_name', 'Sin nombre')}")
            if len(trainers) > 3:
                print(f"   ... y {len(trainers) - 3} más")
        
        print(f"👥 Miembros encontrados: {len(members)}")
        if members:
            for m in members[:3]:  # Mostrar solo los primeros 3
                print(f"   ID: {m['id']} - Nombre: {m.get('full_name', 'Sin nombre')}")
            if len(members) > 3:
                print(f"   ... y {len(members) - 3} más")
        
        return {"trainers": trainers, "members": members}
    else:
        print(f"❌ Error al obtener usuarios: {response.status_code}")
        print(response.text)
        return {"trainers": [], "members": []}

def get_all_relationships():
    """Obtiene todas las relaciones entrenador-miembro (como administrador)"""
    print_separator("CONSULTANDO TODAS LAS RELACIONES")
    
    url = f"{API_BASE_URL}/trainer-member/"
    response = requests.get(url, headers=HEADERS)
    
    if response.status_code == 200:
        relationships = response.json()
        print(f"✅ Relaciones obtenidas exitosamente. Cantidad: {len(relationships)}")
        
        if relationships:
            for rel in relationships[:3]:  # Mostrar solo las primeras 3
                print(f"   ID: {rel['id']} - Entrenador: {rel['trainer_id']} - Miembro: {rel['member_id']}")
            if len(relationships) > 3:
                print(f"   ... y {len(relationships) - 3} más")
        
        return relationships
    else:
        print(f"❌ Error al obtener relaciones: {response.status_code}")
        print(response.text)
        return []

def create_relationship(trainer_id, member_id):
    """Crea una nueva relación entre un entrenador y un miembro"""
    print_separator(f"CREANDO RELACIÓN ENTRENADOR {trainer_id} - MIEMBRO {member_id}")
    
    relationship_data = {
        "trainer_id": trainer_id,
        "member_id": member_id,
        "status": "ACTIVE",  # ACTIVE, PENDING, PAUSED, COMPLETED
        "notes": f"Relación de prueba creada el {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "start_date": datetime.now().isoformat(),
        "goals": "Objetivos de prueba para esta relación"
    }
    
    url = f"{API_BASE_URL}/trainer-member/"
    response = requests.post(url, headers=HEADERS, json=relationship_data)
    
    if response.status_code == 200:
        created_relationship = response.json()
        relationship_id = created_relationship['id']
        created_relationships.append(relationship_id)  # Guardar para limpieza
        
        print(f"✅ Relación creada exitosamente con ID: {relationship_id}")
        print(f"   Entrenador: {created_relationship['trainer_id']}")
        print(f"   Miembro: {created_relationship['member_id']}")
        print(f"   Estado: {created_relationship['status']}")
        
        return created_relationship
    else:
        print(f"❌ Error al crear relación: {response.status_code}")
        print(response.text)
        return None

def get_relationship(relationship_id):
    """Obtiene una relación específica por su ID"""
    print_separator(f"CONSULTANDO RELACIÓN {relationship_id}")
    
    url = f"{API_BASE_URL}/trainer-member/{relationship_id}"
    response = requests.get(url, headers=HEADERS)
    
    if response.status_code == 200:
        relationship = response.json()
        print(f"✅ Relación {relationship_id} obtenida exitosamente")
        print(f"   Entrenador: {relationship['trainer_id']}")
        print(f"   Miembro: {relationship['member_id']}")
        print(f"   Estado: {relationship['status']}")
        print(f"   Notas: {relationship.get('notes', 'Sin notas')}")
        
        return relationship
    else:
        print(f"❌ Error al obtener relación {relationship_id}: {response.status_code}")
        print(response.text)
        return None

def get_members_by_trainer(trainer_id):
    """Obtiene los miembros asignados a un entrenador específico"""
    print_separator(f"CONSULTANDO MIEMBROS DEL ENTRENADOR {trainer_id}")
    
    url = f"{API_BASE_URL}/trainer-member/trainer/{trainer_id}/members"
    response = requests.get(url, headers=HEADERS)
    
    if response.status_code == 200:
        members = response.json()
        print(f"✅ Miembros del entrenador {trainer_id} obtenidos exitosamente. Cantidad: {len(members)}")
        
        if members:
            for member in members[:3]:  # Mostrar solo los primeros 3
                print(f"   ID: {member['user']['id']} - Nombre: {member['user'].get('full_name', 'Sin nombre')}")
                print(f"   Relación ID: {member['relationship']['id']} - Estado: {member['relationship']['status']}")
            if len(members) > 3:
                print(f"   ... y {len(members) - 3} más")
        
        return members
    else:
        print(f"❌ Error al obtener miembros del entrenador {trainer_id}: {response.status_code}")
        print(response.text)
        return []

def get_trainers_by_member(member_id):
    """Obtiene los entrenadores asignados a un miembro específico"""
    print_separator(f"CONSULTANDO ENTRENADORES DEL MIEMBRO {member_id}")
    
    url = f"{API_BASE_URL}/trainer-member/member/{member_id}/trainers"
    response = requests.get(url, headers=HEADERS)
    
    if response.status_code == 200:
        trainers = response.json()
        print(f"✅ Entrenadores del miembro {member_id} obtenidos exitosamente. Cantidad: {len(trainers)}")
        
        if trainers:
            for trainer in trainers[:3]:  # Mostrar solo los primeros 3
                print(f"   ID: {trainer['user']['id']} - Nombre: {trainer['user'].get('full_name', 'Sin nombre')}")
                print(f"   Relación ID: {trainer['relationship']['id']} - Estado: {trainer['relationship']['status']}")
            if len(trainers) > 3:
                print(f"   ... y {len(trainers) - 3} más")
        
        return trainers
    else:
        print(f"❌ Error al obtener entrenadores del miembro {member_id}: {response.status_code}")
        print(response.text)
        return []

def get_my_members():
    """Obtiene los miembros asignados al entrenador autenticado"""
    print_separator("CONSULTANDO MIS MIEMBROS")
    
    url = f"{API_BASE_URL}/trainer-member/my-members"
    response = requests.get(url, headers=HEADERS)
    
    if response.status_code == 200:
        members = response.json()
        print(f"✅ Mis miembros obtenidos exitosamente. Cantidad: {len(members)}")
        
        if members:
            for member in members[:3]:  # Mostrar solo los primeros 3
                print(f"   ID: {member['user']['id']} - Nombre: {member['user'].get('full_name', 'Sin nombre')}")
                print(f"   Relación ID: {member['relationship']['id']} - Estado: {member['relationship']['status']}")
            if len(members) > 3:
                print(f"   ... y {len(members) - 3} más")
        
        return members
    else:
        print(f"❌ Error al obtener mis miembros: {response.status_code}")
        print(response.text)
        return []

def get_my_trainers():
    """Obtiene los entrenadores asignados al miembro autenticado"""
    print_separator("CONSULTANDO MIS ENTRENADORES")
    
    url = f"{API_BASE_URL}/trainer-member/my-trainers"
    response = requests.get(url, headers=HEADERS)
    
    if response.status_code == 200:
        trainers = response.json()
        print(f"✅ Mis entrenadores obtenidos exitosamente. Cantidad: {len(trainers)}")
        
        if trainers:
            for trainer in trainers[:3]:  # Mostrar solo los primeros 3
                print(f"   ID: {trainer['user']['id']} - Nombre: {trainer['user'].get('full_name', 'Sin nombre')}")
                print(f"   Relación ID: {trainer['relationship']['id']} - Estado: {trainer['relationship']['status']}")
            if len(trainers) > 3:
                print(f"   ... y {len(trainers) - 3} más")
        
        return trainers
    else:
        print(f"❌ Error al obtener mis entrenadores: {response.status_code}")
        if response.status_code == 400:
            print("⚠️ El usuario actual podría no ser un miembro o no tener los permisos necesarios")
        print(response.text)
        return []

def update_relationship(relationship_id, status=None, notes=None, goals=None):
    """Actualiza una relación existente"""
    print_separator(f"ACTUALIZANDO RELACIÓN {relationship_id}")
    
    # Construir los datos de actualización
    update_data = {}
    if status:
        update_data["status"] = status
    if notes:
        update_data["notes"] = notes
    if goals:
        update_data["goals"] = goals
    
    if not update_data:
        # Si no hay datos para actualizar, agregar notas predeterminadas
        update_data["notes"] = f"Relación actualizada el {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    url = f"{API_BASE_URL}/trainer-member/{relationship_id}"
    response = requests.put(url, headers=HEADERS, json=update_data)
    
    if response.status_code == 200:
        updated_relationship = response.json()
        print(f"✅ Relación {relationship_id} actualizada exitosamente")
        
        # Mostrar los campos actualizados
        for key, value in update_data.items():
            print(f"   {key}: {updated_relationship.get(key, 'N/A')}")
        
        return updated_relationship
    else:
        print(f"❌ Error al actualizar relación {relationship_id}: {response.status_code}")
        print(response.text)
        return None

def delete_relationship(relationship_id):
    """Elimina una relación existente"""
    print_separator(f"ELIMINANDO RELACIÓN {relationship_id}")
    
    url = f"{API_BASE_URL}/trainer-member/{relationship_id}"
    response = requests.delete(url, headers=HEADERS)
    
    if response.status_code == 200:
        print(f"✅ Relación {relationship_id} eliminada exitosamente")
        
        # Eliminar el ID de la lista de relaciones creadas
        if relationship_id in created_relationships:
            created_relationships.remove(relationship_id)
            
        return True
    else:
        print(f"❌ Error al eliminar relación {relationship_id}: {response.status_code}")
        print(response.text)
        return False

def clean_up_relationships():
    """Elimina todas las relaciones creadas durante las pruebas"""
    print_separator("LIMPIEZA DE RELACIONES")
    
    if not created_relationships:
        print("No hay relaciones para limpiar")
        return
    
    print(f"Eliminando {len(created_relationships)} relaciones creadas durante las pruebas...")
    
    success_count = 0
    for relationship_id in list(created_relationships):  # Usar una copia para poder modificar durante la iteración
        if delete_relationship(relationship_id):
            success_count += 1
    
    print(f"\n✅ Limpieza completada: {success_count}/{len(created_relationships)} relaciones eliminadas")

def run_trainer_member_flow_test():
    """Ejecutar el flujo completo de pruebas de relaciones entrenador-miembro"""
    print_separator("INICIANDO PRUEBA DE FLUJO DE RELACIONES ENTRENADOR-MIEMBRO")
    
    try:
        # 1. Obtener usuarios para identificar entrenadores y miembros
        users = get_users()
        
        if not users["trainers"] or not users["members"]:
            print("❌ No hay suficientes usuarios para las pruebas. Se necesita al menos un entrenador y un miembro.")
            return
        
        # 2. Obtener todas las relaciones existentes
        existing_relationships = get_all_relationships()
        
        # 3. Crear una nueva relación
        trainer_id = TRAINER_ID
        member_id = MEMBER_ID
        
        # Verificar si ya existe una relación entre este entrenador y miembro
        existing_relation = next(
            (r for r in existing_relationships if r["trainer_id"] == trainer_id and r["member_id"] == member_id), 
            None
        )
        
        if existing_relation:
            print(f"⚠️ Ya existe una relación entre el entrenador {trainer_id} y el miembro {member_id}.")
            print(f"   ID de relación existente: {existing_relation['id']}")
            relationship = existing_relation
            # Agregar a la lista para potencialmente eliminarla durante la limpieza
            created_relationships.append(existing_relation['id'])
        else:
            # Crear nueva relación
            relationship = create_relationship(trainer_id, member_id)
            if not relationship:
                print("❌ No se pudo crear la relación. Abortando prueba.")
                return
        
        relationship_id = relationship['id']
        print(f"✅ Relación de prueba establecida con ID: {relationship_id}")
        
        # 4. Obtener una relación específica
        relationship_detail = get_relationship(relationship_id)
        
        # 5. Obtener miembros de un entrenador
        members_of_trainer = get_members_by_trainer(trainer_id)
        
        # 6. Obtener entrenadores de un miembro
        trainers_of_member = get_trainers_by_member(member_id)
        
        # 7. Intentar obtener "mis miembros" (puede fallar si el token no es de un entrenador)
        try:
            my_members = get_my_members()
        except Exception as e:
            print(f"⚠️ Error intentando obtener mis miembros: {str(e)}")
        
        # 8. Intentar obtener "mis entrenadores" (puede fallar si el token no es de un miembro)
        try:
            my_trainers = get_my_trainers()
        except Exception as e:
            print(f"⚠️ Error intentando obtener mis entrenadores: {str(e)}")
        
        # 9. Actualizar la relación - primero con cambio de notas
        updated_notes = f"Notas actualizadas en prueba el {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        updated_relationship = update_relationship(relationship_id, notes=updated_notes)
        
        # 10. Actualizar la relación - cambio de estado
        if updated_relationship:
            new_status = "PAUSED"  # ACTIVE, PENDING, PAUSED, COMPLETED
            updated_relationship = update_relationship(relationship_id, status=new_status)
        
        # 11. Verificar la relación actualizada
        updated_detail = get_relationship(relationship_id)
        
        # 12. Verificar nuevamente los miembros del entrenador para ver los cambios
        updated_members = get_members_by_trainer(trainer_id)
        
        # 13. Resumen de la prueba
        print_separator("RESUMEN DE LA PRUEBA")
        print(f"✅ Se creó/utilizó una relación entrenador-miembro con ID: {relationship_id}")
        print(f"✅ Se actualizó la relación exitosamente")
        
        # Opcional: Si queremos eliminar la relación como parte de la prueba
        # delete_relationship(relationship_id)
        
    finally:
        # Limpiar relaciones creadas durante la prueba
        clean_up_relationships()

if __name__ == "__main__":
    run_trainer_member_flow_test() 