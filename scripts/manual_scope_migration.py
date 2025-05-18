#!/usr/bin/env python3
"""
Script para migrar manualmente los scopes antiguos a los nuevos scopes simplificados.

Este script:
1. Define la tabla de mapeo de scopes antiguos a nuevos
2. Realiza reemplazos directos en los archivos especificados
3. Simplifica comparado con el script anterior, para garantizar efectividad

Uso:
    python scripts/manual_scope_migration.py
"""

import os
import re
import sys

# Mapeo de scopes antiguos a nuevos
SCOPE_MAPPING = {
    # Permisos de usuario
    'scopes=["read:profile"]': 'scopes=["user:read"]',
    'scopes=["read:users"]': 'scopes=["user:read"]',
    'scopes=["read:members"]': 'scopes=["user:read"]',
    'scopes=["admin:users"]': 'scopes=["user:write"]',
    'scopes=["update:users"]': 'scopes=["user:write"]',
    'scopes=["delete:users"]': 'scopes=["user:admin"]',
    
    # Permisos de recursos
    'scopes=["read:events"]': 'scopes=["resource:read"]',
    'scopes=["read_events"]': 'scopes=["resource:read"]',
    'scopes=["read:own_events"]': 'scopes=["resource:read"]',
    'scopes=["read:schedules"]': 'scopes=["resource:read"]',
    'scopes=["read:own_schedules"]': 'scopes=["resource:read"]',
    'scopes=["read:relationships"]': 'scopes=["resource:read"]',
    'scopes=["read:own_relationships"]': 'scopes=["resource:read"]',
    'scopes=["read:participations"]': 'scopes=["resource:read"]',
    'scopes=["read:own_participations"]': 'scopes=["resource:read"]',
    
    'scopes=["create:events"]': 'scopes=["resource:write"]',
    'scopes=["create:participations"]': 'scopes=["resource:write"]',
    'scopes=["create:relationships"]': 'scopes=["resource:write"]',
    'scopes=["create:schedules"]': 'scopes=["resource:write"]',
    'scopes=["update:events"]': 'scopes=["resource:write"]',
    'scopes=["update:participations"]': 'scopes=["resource:write"]',
    'scopes=["update:relationships"]': 'scopes=["resource:write"]',
    'scopes=["update:schedules"]': 'scopes=["resource:write"]',
    
    'scopes=["delete:events"]': 'scopes=["resource:admin"]',
    'scopes=["delete:schedules"]': 'scopes=["resource:admin"]',
    'scopes=["admin:events"]': 'scopes=["resource:admin"]',
    'scopes=["admin:relationships"]': 'scopes=["resource:admin"]',
    'scopes=["delete:relationships"]': 'scopes=["resource:admin"]',
    
    # Permisos de gimnasio (tenant)
    'scopes=["read:gyms"]': 'scopes=["tenant:read"]',
    'scopes=["read:gym_users"]': 'scopes=["tenant:read"]',
    
    'scopes=["admin:gyms"]': 'scopes=["tenant:admin"]',
    
    # Otros permisos específicos
    'scopes=["use:chat"]': 'scopes=["resource:read"]',
    'scopes=["create:chat_rooms"]': 'scopes=["resource:write"]',
    'scopes=["manage:chat_rooms"]': 'scopes=["resource:admin"]',
    'scopes=["register:classes"]': 'scopes=["resource:write"]',
    'scopes=["manage:class_registrations"]': 'scopes=["resource:admin"]',
    'scopes=["delete:own_participations"]': 'scopes=["resource:write"]'
}

# Lista de archivos a procesar
FILES_TO_PROCESS = [
    "app/api/v1/endpoints/users.py",
    "app/api/v1/endpoints/gyms.py",
    "app/api/v1/endpoints/events.py",
    "app/api/v1/endpoints/chat.py",
    "app/api/v1/endpoints/trainer_member.py",
    "app/api/v1/endpoints/schedule/sessions.py",
    "app/api/v1/endpoints/schedule/participation.py",
    "app/api/v1/endpoints/schedule/classes.py",
    "app/api/v1/endpoints/schedule/categories.py",
    "app/api/v1/endpoints/schedule/gym_hours.py",
    "app/api/v1/endpoints/auth/admin.py",
    "app/api/v1/endpoints/auth/user_info.py",
    "app/core/tenant_cache.py"
]

def process_file(file_path):
    """Procesa un archivo y realiza los reemplazos necesarios."""
    if not os.path.exists(file_path):
        print(f"Archivo no encontrado: {file_path}")
        return 0
    
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    changes = 0
    for old_scope, new_scope in SCOPE_MAPPING.items():
        if old_scope in content:
            content = content.replace(old_scope, new_scope)
            changes += content.count(new_scope)
    
    if changes > 0:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Archivo {file_path}: {changes} reemplazos realizados")
    
    return changes

def main():
    """Función principal."""
    print("Iniciando migración de scopes...")
    
    total_changes = 0
    files_with_changes = 0
    
    for file_path in FILES_TO_PROCESS:
        print(f"Procesando {file_path}...")
        changes = process_file(file_path)
        
        if changes > 0:
            files_with_changes += 1
            total_changes += changes
    
    print(f"\nResumen:")
    print(f"  Archivos procesados: {len(FILES_TO_PROCESS)}")
    print(f"  Archivos con cambios: {files_with_changes}")
    print(f"  Total de cambios: {total_changes}")

if __name__ == "__main__":
    main() 