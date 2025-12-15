#!/usr/bin/env python3
"""
Script para arreglar canales sin prefijo 'messaging:' en stream_channel_id

Problema:
- Algunos canales antiguos tienen stream_channel_id sin el prefijo "messaging:"
- Esto causa que la API no los encuentre cuando Stream los reporta con prefijo
- Ejemplo: BD tiene "direct_user_11_user_8" pero Stream reporta "messaging:direct_user_11_user_8"

Solución:
- Agregar prefijo "messaging:" a todos los canales que no lo tienen
- Excluir canales que ya tienen prefijo válido (messaging:, team:, etc.)

Uso:
    # Modo dry-run (ver qué se cambiaría)
    python scripts/fix_channel_id_prefixes.py --dry-run

    # Aplicar cambios
    python scripts/fix_channel_id_prefixes.py --apply

    # Solo un canal específico
    python scripts/fix_channel_id_prefixes.py --room-id 662 --apply
"""

import sys
import os
import argparse
from datetime import datetime

# Agregar path del proyecto
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine, text
from app.core.config import get_settings


def find_channels_without_prefix(engine):
    """Encuentra canales sin prefijo messaging: o team:"""
    with engine.connect() as conn:
        result = conn.execute(text('''
            SELECT
                id,
                name,
                gym_id,
                stream_channel_id,
                stream_channel_type,
                is_direct,
                created_at,
                status
            FROM chat_rooms
            WHERE stream_channel_id NOT LIKE 'messaging:%'
              AND stream_channel_id NOT LIKE 'team:%'
              AND stream_channel_id IS NOT NULL
            ORDER BY created_at DESC
        '''))

        return result.fetchall()


def fix_channel_prefix(engine, room_id, dry_run=True):
    """Agrega prefijo messaging: a un canal específico"""
    with engine.connect() as conn:
        # Obtener canal actual
        result = conn.execute(
            text('SELECT id, stream_channel_id FROM chat_rooms WHERE id = :room_id'),
            {'room_id': room_id}
        )
        room = result.fetchone()

        if not room:
            print(f'❌ Room ID {room_id} no encontrado')
            return False

        old_channel_id = room[1]

        # Verificar si ya tiene prefijo
        if old_channel_id.startswith(('messaging:', 'team:')):
            print(f'✅ Room {room_id} ya tiene prefijo válido: {old_channel_id}')
            return True

        # Crear nuevo ID con prefijo
        new_channel_id = f'messaging:{old_channel_id}'

        if dry_run:
            print(f'🔍 [DRY-RUN] Room {room_id}:')
            print(f'   Antes: {old_channel_id}')
            print(f'   Después: {new_channel_id}')
            return True
        else:
            # Aplicar cambio
            conn.execute(
                text('UPDATE chat_rooms SET stream_channel_id = :new_id WHERE id = :room_id'),
                {'new_id': new_channel_id, 'room_id': room_id}
            )
            conn.commit()
            print(f'✅ Room {room_id} actualizado:')
            print(f'   Antes: {old_channel_id}')
            print(f'   Después: {new_channel_id}')
            return True


def fix_all_channels(engine, dry_run=True):
    """Agrega prefijo a TODOS los canales sin prefijo"""
    with engine.begin() as conn:
        if dry_run:
            print('🔍 [DRY-RUN] Simulando actualización...\n')
        else:
            print('🔧 Aplicando actualización...\n')

        # Actualizar canales
        result = conn.execute(text('''
            UPDATE chat_rooms
            SET stream_channel_id = CONCAT('messaging:', stream_channel_id)
            WHERE stream_channel_id NOT LIKE 'messaging:%'
              AND stream_channel_id NOT LIKE 'team:%'
              AND stream_channel_id IS NOT NULL
            RETURNING id, stream_channel_id
        ''' if not dry_run else '''
            SELECT
                id,
                CONCAT('messaging:', stream_channel_id) as new_channel_id
            FROM chat_rooms
            WHERE stream_channel_id NOT LIKE 'messaging:%'
              AND stream_channel_id NOT LIKE 'team:%'
              AND stream_channel_id IS NOT NULL
        '''))

        updated = result.fetchall()

        if not dry_run:
            conn.commit()

        return updated


def create_backup(engine):
    """Crea backup de la tabla chat_rooms"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = f'backup_chat_rooms_{timestamp}.sql'

    print(f'📦 Creando backup: {backup_file}')

    # Nota: Esto requiere acceso a pg_dump
    # En producción, usar herramientas de backup adecuadas
    print('⚠️  IMPORTANTE: Asegúrate de tener un backup antes de aplicar cambios')
    print('   Comando recomendado:')
    print(f'   pg_dump -t chat_rooms > {backup_file}')

    return backup_file


def main():
    parser = argparse.ArgumentParser(description='Fix channel ID prefixes')
    parser.add_argument('--dry-run', action='store_true',
                        help='Simular cambios sin aplicarlos')
    parser.add_argument('--apply', action='store_true',
                        help='Aplicar cambios realmente')
    parser.add_argument('--room-id', type=int,
                        help='Solo arreglar un room ID específico')

    args = parser.parse_args()

    # Validar argumentos
    if not args.dry_run and not args.apply:
        print('❌ Error: Debes especificar --dry-run o --apply')
        parser.print_help()
        sys.exit(1)

    # Conectar a BD
    settings = get_settings()
    engine = create_engine(settings.SQLALCHEMY_DATABASE_URI)

    print('=' * 60)
    print('🔧 FIX CHANNEL ID PREFIXES')
    print('=' * 60)

    # Modo
    mode = 'DRY-RUN (simulación)' if args.dry_run else 'APPLY (aplicar cambios)'
    print(f'Modo: {mode}\n')

    # Encontrar canales afectados
    print('📊 Buscando canales sin prefijo...\n')
    channels = find_channels_without_prefix(engine)

    if not channels:
        print('✅ No se encontraron canales sin prefijo')
        print('   Todos los canales tienen formato correcto')
        return

    print(f'⚠️  Encontrados {len(channels)} canales sin prefijo:\n')

    # Mostrar tabla
    print(f'{"ID":<6} {"Name":<40} {"Gym":<5} {"Channel ID":<40} {"Created"}')
    print('-' * 120)

    for channel in channels:
        channel_id = channel[0]
        name = (channel[1] or 'Sin nombre')[:38]
        gym_id = channel[2]
        stream_id = (channel[3] or '')[:38]
        created = channel[6].strftime('%Y-%m-%d') if channel[6] else 'N/A'

        print(f'{channel_id:<6} {name:<40} {gym_id:<5} {stream_id:<40} {created}')

    print()

    # Aplicar fix
    if args.room_id:
        # Solo un canal
        print(f'\n🔧 Arreglando Room ID {args.room_id}...\n')
        success = fix_channel_prefix(engine, args.room_id, dry_run=args.dry_run)

        if success and not args.dry_run:
            print('\n✅ Canal actualizado exitosamente')
        elif success and args.dry_run:
            print('\n✅ Simulación completada')
            print('   Para aplicar cambios, ejecuta con --apply')

    else:
        # Todos los canales
        if not args.dry_run:
            print('\n⚠️  ADVERTENCIA: Vas a actualizar TODOS los canales sin prefijo')
            print('   Canales a actualizar: ', len(channels))
            print('')

            # Pedir confirmación
            confirm = input('¿Continuar? (escribe "SI" para confirmar): ')
            if confirm != 'SI':
                print('❌ Operación cancelada')
                sys.exit(0)

            print('\n📦 Recomendación: Crea un backup primero')
            create_backup(engine)
            print()

        print(f'🔧 {"Simulando" if args.dry_run else "Aplicando"} actualización masiva...\n')

        updated = fix_all_channels(engine, dry_run=args.dry_run)

        print(f'\n{"✅ Simulación completada" if args.dry_run else "✅ Actualización completada"}')
        print(f'   Canales {"que se actualizarían" if args.dry_run else "actualizados"}: {len(updated)}')

        if args.dry_run:
            print('\n💡 Para aplicar los cambios, ejecuta:')
            print('   python scripts/fix_channel_id_prefixes.py --apply')
        else:
            print('\n🎉 Migración completada exitosamente')
            print('\n📋 Próximos pasos:')
            print('   1. Verificar que la API ahora encuentra los canales')
            print('   2. Ejecutar auditoría de sincronización')
            print('   3. Verificar que usuarios pueden acceder a sus chats')


if __name__ == '__main__':
    main()
