#!/usr/bin/env python3
"""
Script para migrar los scopes antiguos a los nuevos scopes simplificados.

Este script:
1. Busca todos los archivos Python en las rutas especificadas
2. Identifica los patrones de scopes antiguos
3. Reemplaza con los nuevos scopes según la tabla de mapeo
4. Guarda los cambios o genera un reporte según las opciones

Uso:
    python scripts/migrate_scopes.py --dry-run  # Solo mostrar cambios sin aplicar
    python scripts/migrate_scopes.py            # Aplicar cambios
"""

import os
import re
import argparse
from typing import Dict, List, Tuple

# Mapeo de scopes antiguos a nuevos
SCOPE_MAPPING = {
    # Permisos de usuario
    "read:profile": "user:read",
    "read:users": "user:read",
    "read:members": "user:read",
    "admin:users": "user:write",
    "update:users": "user:write", 
    "delete:users": "user:admin",
    
    # Permisos de recursos
    "read:events": "resource:read",
    "read_events": "resource:read",
    "read:own_events": "resource:read",
    "read:schedules": "resource:read",
    "read:own_schedules": "resource:read",
    "read:relationships": "resource:read",
    "read:own_relationships": "resource:read",
    "read:participations": "resource:read",
    "read:own_participations": "resource:read",
    
    "create:events": "resource:write",
    "create:participations": "resource:write",
    "create:relationships": "resource:write",
    "create:schedules": "resource:write",
    "update:events": "resource:write",
    "update:participations": "resource:write",
    "update:relationships": "resource:write",
    "update:schedules": "resource:write",
    
    "delete:events": "resource:admin",
    "delete:schedules": "resource:admin",
    "admin:events": "resource:admin",
    "admin:relationships": "resource:admin",
    "delete:relationships": "resource:admin",
    
    # Permisos de gimnasio (tenant)
    "read:gyms": "tenant:read",
    "read:gym_users": "tenant:read",
    
    "admin:gyms": "tenant:admin",
    
    # Otros permisos específicos
    "use:chat": "resource:read",
    "create:chat_rooms": "resource:write",
    "manage:chat_rooms": "resource:admin",
    "register:classes": "resource:write",
    "manage:class_registrations": "resource:admin",
    "delete:own_participations": "resource:write"
}

def find_python_files(base_path: str, exclude_dirs: List[str] = None) -> List[str]:
    """Encuentra todos los archivos Python en la ruta especificada."""
    if exclude_dirs is None:
        exclude_dirs = []
        
    python_files = []
    
    for root, dirs, files in os.walk(base_path):
        # Excluir directorios
        dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith('.')]
        
        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))
                
    return python_files

def find_scope_patterns(file_path: str) -> List[Tuple[str, str, int]]:
    """
    Busca patrones de scopes en un archivo.
    
    Returns:
        List[Tuple[str, str, int]]: Lista de tuplas (línea completa, scope encontrado, número de línea)
    """
    scope_pattern = re.compile(r'scopes=\["([^"]+)"\]')
    multi_scope_pattern = re.compile(r'scopes=\["([^"]+)"(?:,\s*"([^"]+)")*\]')
    
    results = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f, 1):
            # Buscar patrones de un solo scope
            match = scope_pattern.search(line)
            if match:
                scope = match.group(1)
                if scope in SCOPE_MAPPING:
                    results.append((line, scope, i))
                    continue
                    
            # Buscar patrones de múltiples scopes
            match = multi_scope_pattern.search(line)
            if match:
                for group_idx in range(1, match.lastindex + 1 if match.lastindex else 1):
                    scope = match.group(group_idx)
                    if scope and scope in SCOPE_MAPPING:
                        results.append((line, scope, i))
    
    return results

def replace_scope(line: str, old_scope: str, new_scope: str) -> str:
    """Reemplaza un scope antiguo por el nuevo en una línea."""
    return line.replace(f'"{old_scope}"', f'"{new_scope}"')

def process_file(file_path: str, dry_run: bool = True) -> List[Tuple[str, str, str, int]]:
    """
    Procesa un archivo para encontrar y posiblemente reemplazar scopes.
    
    Args:
        file_path: Ruta al archivo a procesar
        dry_run: Si es True, solo reporta cambios sin aplicarlos
        
    Returns:
        List[Tuple[str, str, str, int]]: Lista de tuplas (línea original, línea nueva, scope reemplazado, número de línea)
    """
    changes = []
    scope_matches = find_scope_patterns(file_path)
    
    if not scope_matches:
        return changes
    
    if dry_run:
        for line, old_scope, line_num in scope_matches:
            new_scope = SCOPE_MAPPING[old_scope]
            new_line = replace_scope(line, old_scope, new_scope)
            changes.append((line.strip(), new_line.strip(), old_scope, line_num))
    else:
        # Leer todo el archivo
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.readlines()
        
        # Hacer reemplazos
        for line, old_scope, line_num in scope_matches:
            new_scope = SCOPE_MAPPING[old_scope]
            new_line = replace_scope(line, old_scope, new_scope)
            
            # Registrar el cambio
            changes.append((line.strip(), new_line.strip(), old_scope, line_num))
            
            # Actualizar la línea en el contenido
            content[line_num - 1] = new_line
        
        # Escribir el archivo actualizado
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(content)
    
    return changes

def main():
    parser = argparse.ArgumentParser(description='Migra los scopes antiguos a los nuevos scopes simplificados.')
    parser.add_argument('--dry-run', action='store_true', help='Solo mostrar cambios sin aplicarlos')
    parser.add_argument('--path', default='app', help='Ruta base para buscar archivos (default: app)')
    args = parser.parse_args()
    
    # Carpetas a excluir
    exclude_dirs = ['__pycache__', 'venv', 'env', '.git', 'node_modules', 'migrations']
    
    # Encontrar todos los archivos Python
    print(f"Buscando archivos Python en {args.path}...")
    python_files = find_python_files(args.path, exclude_dirs)
    print(f"Encontrados {len(python_files)} archivos Python.")
    
    # Procesar cada archivo
    total_changes = 0
    files_with_changes = 0
    
    for file_path in python_files:
        changes = process_file(file_path, args.dry_run)
        
        if changes:
            files_with_changes += 1
            total_changes += len(changes)
            
            print(f"\nCambios en {file_path}:")
            for i, (old_line, new_line, old_scope, line_num) in enumerate(changes, 1):
                print(f"  Línea {line_num}: {old_scope} → {SCOPE_MAPPING[old_scope]}")
                if args.dry_run:
                    print(f"    - {old_line}")
                    print(f"    + {new_line}")
    
    # Resumen
    print(f"\nResumen:")
    print(f"  Archivos procesados: {len(python_files)}")
    print(f"  Archivos con cambios: {files_with_changes}")
    print(f"  Total de cambios: {total_changes}")
    
    if args.dry_run:
        print("\nEste fue un dry-run. No se aplicaron cambios.")
        print("Para aplicar los cambios, ejecute sin --dry-run")

if __name__ == "__main__":
    main() 