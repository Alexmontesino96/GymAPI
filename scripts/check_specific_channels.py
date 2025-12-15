#!/usr/bin/env python3
"""
Verificar canales específicos reportados en logs
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine, text
from app.core.config import get_settings


def check_channels(engine):
    """Verificar canales específicos de los logs"""

    # Canales reportados como "NO EN API"
    channels_to_check = [
        'messaging:direct_user_10_user_8',
        'messaging:room_General_10',
        'messaging:direct_user_11_user_8',
        'messaging:event_644_d3d94468'
    ]

    print('=' * 100)
    print('🔍 VERIFICACIÓN DE CANALES ESPECÍFICOS')
    print('=' * 100)
    print(f'\nBuscando {len(channels_to_check)} canales reportados como "NO EN API"...\n')

    with engine.connect() as conn:
        for stream_id in channels_to_check:
            print(f'\n🔎 Buscando: {stream_id}')
            print('-' * 100)

            # Buscar canal exacto
            result = conn.execute(text('''
                SELECT
                    id,
                    name,
                    gym_id,
                    stream_channel_id,
                    is_direct,
                    event_id,
                    status,
                    created_at
                FROM chat_rooms
                WHERE stream_channel_id = :stream_id
            '''), {'stream_id': stream_id})

            room = result.fetchone()

            if room:
                print(f'✅ ENCONTRADO en BD:')
                print(f'   Room ID: {room[0]}')
                print(f'   Name: {room[1] or "Sin nombre"}')
                print(f'   Gym ID: {room[2]}')
                print(f'   Stream Channel ID (BD): {room[3]}')
                print(f'   Is Direct: {room[4]}')
                print(f'   Event ID: {room[5]}')
                print(f'   Status: {room[6]}')
                print(f'   Created: {room[7]}')
            else:
                print(f'❌ NO ENCONTRADO en BD con ID: {stream_id}')

                # Intentar buscar sin prefijo (por si no se migró)
                channel_without_prefix = stream_id.replace('messaging:', '').replace('team:', '')
                result2 = conn.execute(text('''
                    SELECT
                        id,
                        name,
                        stream_channel_id,
                        created_at
                    FROM chat_rooms
                    WHERE stream_channel_id = :stream_id
                '''), {'stream_id': channel_without_prefix})

                room_no_prefix = result2.fetchone()

                if room_no_prefix:
                    print(f'⚠️  ENCONTRADO SIN PREFIJO:')
                    print(f'   Room ID: {room_no_prefix[0]}')
                    print(f'   Stream Channel ID (BD): {room_no_prefix[2]}')
                    print(f'   ❌ Migración NO aplicada a este canal')
                else:
                    print(f'❌ Canal NO existe en BD (ni con ni sin prefijo)')
                    print(f'   Este es un canal HUÉRFANO en Stream')

    print('\n' + '=' * 100)
    print('📊 RESUMEN')
    print('=' * 100)

    # Resumen general
    with engine.connect() as conn:
        # Total de canales en BD
        result = conn.execute(text('SELECT COUNT(*) FROM chat_rooms'))
        total = result.scalar()

        # Canales con prefijo
        result = conn.execute(text('''
            SELECT COUNT(*)
            FROM chat_rooms
            WHERE stream_channel_id LIKE 'messaging:%'
               OR stream_channel_id LIKE 'team:%'
        '''))
        with_prefix = result.scalar()

        # Canales sin prefijo
        result = conn.execute(text('''
            SELECT COUNT(*)
            FROM chat_rooms
            WHERE stream_channel_id NOT LIKE 'messaging:%'
              AND stream_channel_id NOT LIKE 'team:%'
              AND stream_channel_id IS NOT NULL
        '''))
        without_prefix = result.scalar()

        print(f'\nTotal canales en BD: {total}')
        print(f'✅ Con prefijo: {with_prefix}')
        print(f'❌ Sin prefijo: {without_prefix}')

        if without_prefix > 0:
            print(f'\n⚠️  ATENCIÓN: {without_prefix} canales SIN prefijo detectados')
            print('   La migración NO se aplicó correctamente o hay canales nuevos sin prefijo')
        else:
            print('\n✅ Todos los canales tienen prefijo correcto')


def main():
    settings = get_settings()
    engine = create_engine(settings.SQLALCHEMY_DATABASE_URI)

    check_channels(engine)


if __name__ == '__main__':
    main()
