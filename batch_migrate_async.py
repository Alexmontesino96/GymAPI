#!/usr/bin/env python3
"""
Script para migrar en batch todos los archivos de sync DB a async DB
"""
import re
from pathlib import Path
from typing import List, Tuple

def migrate_file(file_path: Path) -> Tuple[bool, int]:
    """Migra un archivo completo"""
    content = file_path.read_text()
    original_content = content
    changes_count = 0

    # 1. Cambiar imports
    if "from sqlalchemy.orm import Session" in content:
        content = content.replace(
            "from sqlalchemy.orm import Session",
            "from sqlalchemy.ext.asyncio import AsyncSession"
        )
        changes_count += 1

    if "from app.db.session import get_db" in content:
        content = content.replace(
            "from app.db.session import get_db",
            "from app.db.session import get_async_db"
        )
        changes_count += 1

    # 2. Añadir select a imports de sqlalchemy
    if "from sqlalchemy import" in content and ", select" not in content and "db.query(" in content:
        # Buscar la línea de import de sqlalchemy
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if line.startswith("from sqlalchemy import") and "select" not in line:
                # Añadir select al import
                if line.endswith(')'):
                    lines[i] = line[:-1] + ', select)'
                else:
                    lines[i] = line + ', select'
                changes_count += 1
                break
        content = '\n'.join(lines)

    # 3. Cambiar signatures: Session = Depends(get_db) -> AsyncSession = Depends(get_async_db)
    original_count = content.count('Session = Depends(get_db)')
    content = re.sub(
        r'(\w+):\s*Session\s*=\s*Depends\(get_db\)',
        r'\1: AsyncSession = Depends(get_async_db)',
        content
    )
    changes_count += original_count

    # 4. Convertir queries comunes
    query_patterns = [
        # .first() queries - patrón genérico
        (
            r'(\w+) = db\.query\((\w+)\)\.filter\(([^)]+)\)\.first\(\)',
            r'result = await db.execute(select(\2).where(\3))\n    \1 = result.scalar_one_or_none()'
        ),
        # .all() queries - patrón genérico
        (
            r'(\w+) = db\.query\((\w+)\)\.filter\(([^)]+)\)\.all\(\)',
            r'result = await db.execute(select(\2).where(\3))\n    \1 = result.scalars().all()'
        ),
        # .join().filter().all()
        (
            r'(\w+) = db\.query\((\w+)\)\.join\(([^)]+)\)\.filter\(([^)]+)\)\.all\(\)',
            r'result = await db.execute(select(\2).join(\3).where(\4))\n    \1 = result.scalars().all()'
        ),
        # .join().filter().first()
        (
            r'(\w+) = db\.query\((\w+)\)\.join\(([^)]+)\)\.filter\(([^)]+)\)\.first\(\)',
            r'result = await db.execute(select(\2).join(\3).where(\4))\n    \1 = result.scalar_one_or_none()'
        ),
        # db operations
        (r'db\.commit\(\)', r'await db.commit()'),
        (r'db\.refresh\(([^)]+)\)', r'await db.refresh(\1)'),
        (r'db\.rollback\(\)', r'await db.rollback()'),
    ]

    for pattern, replacement in query_patterns:
        before = content
        content = re.sub(pattern, replacement, content)
        if content != before:
            changes_count += 1

    # Guardar solo si hubo cambios
    if content != original_content:
        file_path.write_text(content)
        return True, changes_count

    return False, 0


def main():
    files_to_migrate = [
        # Ya migrado: "app/api/v1/endpoints/chat.py",
        "app/api/v1/endpoints/users.py",
        "app/api/v1/endpoints/memberships.py",
        "app/api/v1/endpoints/schedule/sessions.py",
        "app/api/v1/endpoints/schedule/participation.py",
        "app/api/v1/endpoints/posts.py",
        "app/api/v1/endpoints/events.py",
        "app/api/v1/endpoints/schedule/classes.py",
        "app/api/v1/endpoints/surveys.py",
        "app/api/v1/endpoints/gyms.py",
        "app/api/v1/endpoints/schedule/special_days.py",
        "app/api/v1/endpoints/schedule/gym_hours.py",
        "app/api/v1/endpoints/stories.py",
        "app/api/v1/endpoints/schedule/categories.py",
        "app/api/v1/endpoints/trainer_member.py",
        "app/api/v1/endpoints/user_dashboard.py",
        "app/api/v1/endpoints/modules.py",
        "app/api/v1/endpoints/stripe_connect.py",
        "app/api/v1/endpoints/notification.py",
        "app/api/v1/endpoints/worker.py",
        "app/api/v1/endpoints/auth/admin.py",
        "app/api/v1/endpoints/webhooks/stream_webhooks.py",
        "app/api/v1/endpoints/auth/trainer_registration.py",
        "app/api/v1/endpoints/context.py",
        "app/api/v1/endpoints/admin_diagnostics.py",
        "app/api/v1/endpoints/payment_pages.py",
        "app/api/v1/endpoints/attendance.py",
    ]

    base_path = Path("/Users/alexmontesino/GymApi")
    total_modified = 0
    total_changes = 0

    print("🚀 Iniciando migración en batch de sync DB a async DB\n")

    for file_path_str in files_to_migrate:
        file_path = base_path / file_path_str
        if not file_path.exists():
            print(f"⚠️  {file_path_str} - No encontrado")
            continue

        modified, changes = migrate_file(file_path)
        if modified:
            print(f"✅ {file_path_str} - {changes} cambios")
            total_modified += 1
            total_changes += changes
        else:
            print(f"⏭️  {file_path_str} - Sin cambios necesarios")

    print(f"\n📊 Resumen Final:")
    print(f"   Archivos modificados: {total_modified}/{len(files_to_migrate)}")
    print(f"   Total de cambios: {total_changes}")
    print(f"\n⚠️  IMPORTANTE: Revisar manualmente queries complejos que no pudieron ser auto-convertidos")


if __name__ == "__main__":
    main()
