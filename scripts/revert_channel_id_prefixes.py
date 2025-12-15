#!/usr/bin/env python3
"""
Script para REVERTIR la migración de prefijos en stream_channel_id

Problema:
- La migración anterior agregó prefijo "messaging:" a todos los canales
- Pero Stream NO acepta ese prefijo en los IDs cuando se consulta un canal
- Stream devuelve "id" sin prefijo, solo "cid" tiene el prefijo completo

Solución:
- QUITAR prefijo "messaging:" y "team:" de todos los stream_channel_id
- Dejar solo el ID limpio: "direct_user_11_user_8"

Uso:
    # Modo dry-run (ver qué se cambiaría)
    python scripts/revert_channel_id_prefixes.py --dry-run

    # Aplicar cambios
    python scripts/revert_channel_id_prefixes.py --apply
"""

import sys
import os
import argparse
from datetime import datetime

# Agregar path del proyecto
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine, text
from app.core.config import get_settings


def find_channels_with_prefix(engine):
    """Encuentra canales CON prefijo messaging: o team:"""
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
            WHERE stream_channel_id LIKE 'messaging:%'
               OR stream_channel_id LIKE 'team:%'
            ORDER BY created_at DESC
        '''))

        return result.fetchall()


def revert_channel_prefix(engine, room_id, dry_run=True):
    """Quita prefijo messaging: o team: de un canal específico"""
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

        # Verificar si tiene prefijo
        if not old_channel_id.startswith(('messaging:', 'team:')):
            print(f'✅ Room {room_id} ya NO tiene prefijo: {old_channel_id}')
            return True

        # Quitar prefijo
        new_channel_id = old_channel_id.replace('messaging:', '').replace('team:', '')

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


def revert_all_channels(engine, dry_run=True):
    """Quita prefijo de TODOS los canales"""
    with engine.begin() as conn:
        if dry_run:
            print('🔍 [DRY-RUN] Simulando reversión...\\n')
        else:
            print('🔧 Aplicando reversión...\\n')

        # Actualizar canales - quitar prefijos
        result = conn.execute(text('''
            UPDATE chat_rooms
            SET stream_channel_id = REPLACE(REPLACE(stream_channel_id, 'messaging:', ''), 'team:', '')
            WHERE stream_channel_id LIKE 'messaging:%'
               OR stream_channel_id LIKE 'team:%'
            RETURNING id, stream_channel_id
        ''' if not dry_run else '''
            SELECT
                id,
                REPLACE(REPLACE(stream_channel_id, 'messaging:', ''), 'team:', '') as new_channel_id
            FROM chat_rooms
            WHERE stream_channel_id LIKE 'messaging:%'
               OR stream_channel_id LIKE 'team:%'
        '''))

        updated = result.fetchall()

        if not dry_run:
            conn.commit()

        return updated


def main():
    parser = argparse.ArgumentParser(description='Revert channel ID prefixes')
    parser.add_argument('--dry-run', action='store_true',
                        help='Simular cambios sin aplicarlos')
    parser.add_argument('--apply', action='store_true',
                        help='Aplicar cambios realmente')
    parser.add_argument('--room-id', type=int,
                        help='Solo revertir un room ID específico')

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
    print('🔄 REVERT CHANNEL ID PREFIXES')
    print('=' * 60)

    # Modo
    mode = 'DRY-RUN (simulación)' if args.dry_run else 'APPLY (aplicar cambios)'
    print(f'Modo: {mode}\\n')

    # Encontrar canales afectados
    print('📊 Buscando canales CON prefijo...\\n')
    channels = find_channels_with_prefix(engine)

    if not channels:
        print('✅ No se encontraron canales con prefijo')
        print('   Todos los canales tienen formato correcto (sin prefijo)')
        return

    print(f'⚠️  Encontrados {len(channels)} canales CON prefijo:\\n')

    # Mostrar tabla
    print(f'{"ID":<6} {"Name":<40} {"Gym":<5} {"Channel ID":<50} {"Created"}')
    print('-' * 130)

    for channel in channels:
        channel_id = channel[0]
        name = (channel[1] or 'Sin nombre')[:38]
        gym_id = channel[2]
        stream_id = (channel[3] or '')[:48]
        created = channel[6].strftime('%Y-%m-%d') if channel[6] else 'N/A'

        print(f'{channel_id:<6} {name:<40} {gym_id:<5} {stream_id:<50} {created}')

    print()

    # Aplicar reversión
    if args.room_id:
        # Solo un canal
        print(f'\\n🔧 Revirtiendo Room ID {args.room_id}...\\n')
        success = revert_channel_prefix(engine, args.room_id, dry_run=args.dry_run)

        if success and not args.dry_run:
            print('\\n✅ Canal revertido exitosamente')
        elif success and args.dry_run:
            print('\\n✅ Simulación completada')
            print('   Para aplicar cambios, ejecuta con --apply')

    else:
        # Todos los canales
        if not args.dry_run:
            print('\\n⚠️  ADVERTENCIA: Vas a REVERTIR TODOS los canales con prefijo')
            print('   Canales a revertir: ', len(channels))
            print('')

            # Pedir confirmación
            confirm = input('¿Continuar? (escribe "SI" para confirmar): ')
            if confirm != 'SI':
                print('❌ Operación cancelada')
                sys.exit(0)

        print(f'\\n🔧 {"Simulando" if args.dry_run else "Aplicando"} reversión masiva...\\n')

        updated = revert_all_channels(engine, dry_run=args.dry_run)

        print(f'\\n{"✅ Simulación completada" if args.dry_run else "✅ Reversión completada"}')
        print(f'   Canales {"que se revertirían" if args.dry_run else "revertidos"}: {len(updated)}')

        if args.dry_run:
            print('\\n💡 Para aplicar los cambios, ejecuta:')
            print('   python scripts/revert_channel_id_prefixes.py --apply')
        else:
            print('\\n🎉 Reversión completada exitosamente')
            print('\\n📋 Próximos pasos:')
            print('   1. Verificar que la API ahora funciona correctamente')
            print('   2. Probar crear/obtener canales desde iOS')
            print('   3. Verificar que no hay errores de Stream')


if __name__ == '__main__':
    main()
