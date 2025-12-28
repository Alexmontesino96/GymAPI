#!/usr/bin/env python3
"""
Script para migrar automáticamente de get_db (sync) a get_async_db (async)
"""
import re
import sys
from pathlib import Path

def migrate_file(file_path: Path) -> tuple[bool, int]:
    """
    Migra un archivo de sync DB a async DB.

    Returns:
        (was_modified, num_changes)
    """
    content = file_path.read_text()
    original_content = content
    changes = 0

    # 1. Cambiar imports
    if "from sqlalchemy.orm import Session" in content:
        content = content.replace(
            "from sqlalchemy.orm import Session",
            "from sqlalchemy.ext.asyncio import AsyncSession"
        )
        changes += 1

    if "from app.db.session import get_db" in content:
        content = content.replace(
            "from app.db.session import get_db",
            "from app.db.session import get_async_db"
        )
        changes += 1

    # 2. Añadir import de select si no existe y hay queries
    if "from sqlalchemy import" in content and "select" not in content:
        # Buscar líneas de importación de sqlalchemy
        sqlalchemy_import_pattern = r"(from sqlalchemy import [^\n]+)"
        match = re.search(sqlalchemy_import_pattern, content)
        if match:
            old_import = match.group(1)
            if "select" not in old_import:
                new_import = old_import.rstrip(")") + ", select"
                if old_import.endswith(")"):
                    new_import += ")"
                content = content.replace(old_import, new_import)
                changes += 1
    elif "from sqlalchemy import" not in content and ("db.query(" in content or "db.execute(" in content):
        # Añadir import de select al principio si no hay ningún import de sqlalchemy
        import_lines = []
        for line in content.split("\n"):
            if line.startswith("from") or line.startswith("import"):
                import_lines.append(line)
        if import_lines:
            last_import = import_lines[-1]
            content = content.replace(
                last_import,
                last_import + "\nfrom sqlalchemy import select"
            )
            changes += 1

    # 3. Cambiar signatures: Session = Depends(get_db) -> AsyncSession = Depends(get_async_db)
    content = re.sub(
        r"(\w+):\s*Session\s*=\s*Depends\(get_db\)",
        r"\1: AsyncSession = Depends(get_async_db)",
        content
    )

    # 4. Cambiar def a async def para funciones con async db
    # Buscar funciones que NO son async pero tienen AsyncSession
    function_pattern = r"^(def\s+\w+\([^)]*AsyncSession[^)]*\):)"
    content = re.sub(
        function_pattern,
        lambda m: m.group(1).replace("def ", "async def "),
        content,
        flags=re.MULTILINE
    )

    # Contar cuántos cambios se hicieron
    if content != original_content:
        file_path.write_text(content)
        # Contar número de replacements
        changes += content.count("AsyncSession") - original_content.count("AsyncSession")
        return True, changes

    return False, 0

def main():
    # Lista de archivos a migrar
    files_to_migrate = [
        "app/api/v1/endpoints/chat.py",
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

    for file_path_str in files_to_migrate:
        file_path = base_path / file_path_str
        if not file_path.exists():
            print(f"⚠️  Archivo no encontrado: {file_path}")
            continue

        modified, changes = migrate_file(file_path)
        if modified:
            print(f"✅ {file_path_str} - {changes} cambios")
            total_modified += 1
            total_changes += changes
        else:
            print(f"⏭️  {file_path_str} - Sin cambios")

    print(f"\n📊 Resumen:")
    print(f"   Archivos modificados: {total_modified}/{len(files_to_migrate)}")
    print(f"   Total de cambios: {total_changes}")

if __name__ == "__main__":
    main()
