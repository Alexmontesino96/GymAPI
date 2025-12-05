#!/usr/bin/env python3
"""
Script temporal para convertir schedule.py a async_schedule.py
Procesa las clases ClassService, ClassSessionService y ClassParticipationService
"""

import re

def convert_to_async(content: str) -> str:
    """Convierte código de sync a async"""

    # Cambiar imports
    content = re.sub(r'from sqlalchemy\.orm import Session', 'from sqlalchemy.ext.asyncio import AsyncSession', content)
    content = re.sub(r'from app\.repositories\.schedule import', 'from app.repositories.async_schedule import async_', content)

    # Cambiar nombres de clases
    content = re.sub(r'\bClassService\b', 'AsyncClassService', content)
    content = re.sub(r'\bClassSessionService\b', 'AsyncClassSessionService', content)
    content = re.sub(r'\bClassParticipationService\b', 'AsyncClassParticipationService', content)

    # Cambiar parámetros de función
    content = re.sub(r'\bdb: Session\b', 'db: AsyncSession', content)

    # Cambiar repositorios a async
    content = re.sub(r'\bclass_repository\.', 'async_class_repository.', content)
    content = re.sub(r'\bclass_session_repository\.', 'async_class_session_repository.', content)
    content = re.sub(r'\bclass_participation_repository\.', 'async_class_participation_repository.', content)
    content = re.sub(r'\bclass_category_repository\.', 'async_class_category_repository.', content)
    content = re.sub(r'\bgym_hours_repository\.', 'async_gym_hours_repository.', content)
    content = re.sub(r'\bgym_special_hours_repository\.', 'async_gym_special_hours_repository.', content)

    # Cambiar métodos del repositorio a async
    content = re.sub(r'\.get\(', '.get_async(', content)
    content = re.sub(r'\.create\(', '.create_async(', content)
    content = re.sub(r'\.update\(', '.update_async(', content)
    content = re.sub(r'\.remove\(', '.remove_async(', content)
    content = re.sub(r'\.get_by_', '.get_by_', content)  # Los get_by ya tienen versión async

    # Agregar await antes de llamadas a repositorio
    lines = content.split('\n')
    new_lines = []
    for line in lines:
        # Buscar líneas que tengan llamadas a repositorios async sin await
        if 'async_' in line and '=' in line and 'await' not in line and 'def ' not in line and 'class ' not in line:
            # Insertar await si no está
            if 'async_' in line and '(' in line:
                line = line.replace('= async_', '= await async_', 1)
                line = line.replace('return async_', 'return await async_', 1)

        # Agregar await en db.execute, db.commit, db.refresh
        line = re.sub(r'(\s+)db\.execute\(', r'\1await db.execute(', line)
        line = re.sub(r'(\s+)db\.commit\(\)', r'\1await db.commit()', line)
        line = re.sub(r'(\s+)db\.refresh\(', r'\1await db.refresh(', line)
        line = re.sub(r'(\s+)db\.rollback\(\)', r'\1await db.rollback()', line)

        new_lines.append(line)

    content = '\n'.join(new_lines)

    # Convertir db.query() a select() con await
    # Este es más complejo y requiere análisis manual para cada caso

    return content

# Leer el archivo original
print("Leyendo archivo original...")
with open('/Users/alexmontesino/GymApi/app/services/schedule.py', 'r') as f:
    original = f.read()

# Extraer solo las clases que necesitamos (líneas 1698-3290)
lines = original.split('\n')
service_lines = lines[1697:3290]  # Desde ClassService hasta el final
service_content = '\n'.join(service_lines)

# Convertir a async
print("Convirtiendo a async...")
async_content = convert_to_async(service_content)

# Guardar resultado
print("Guardando resultado...")
with open('/Users/alexmontesino/GymApi/async_schedule_part2.txt', 'w') as f:
    f.write(async_content)

print("¡Conversión completa! Revisar async_schedule_part2.txt")
print(f"Total de líneas convertidas: {len(async_content.split(chr(10)))}")
