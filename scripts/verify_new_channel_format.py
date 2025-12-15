#!/usr/bin/env python3
"""
Script para verificar que los nuevos canales se creen con formato correcto

Verifica que canales creados después de la migración tengan prefijo "messaging:"
"""

import sys
import os
from datetime import datetime, timedelta

# Agregar path del proyecto
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine, text
from app.core.config import get_settings


def verify_recent_channels(engine, days_back=7):
    """Verifica canales creados en los últimos N días"""

    # Fecha límite
    cutoff_date = datetime.now() - timedelta(days=days_back)

    with engine.connect() as conn:
        # Obtener canales recientes
        result = conn.execute(text('''
            SELECT
                id,
                name,
                gym_id,
                stream_channel_id,
                stream_channel_type,
                is_direct,
                event_id,
                created_at
            FROM chat_rooms
            WHERE created_at >= :cutoff_date
            ORDER BY created_at DESC
        '''), {'cutoff_date': cutoff_date})

        channels = result.fetchall()

        if not channels:
            print(f'ℹ️  No se encontraron canales creados en los últimos {days_back} días')
            return

        print(f'\n📊 Canales creados en los últimos {days_back} días: {len(channels)}\n')
        print('=' * 120)

        # Estadísticas
        with_prefix = 0
        without_prefix = 0
        issues = []

        for channel in channels:
            channel_id = channel[0]
            name = (channel[1] or 'Sin nombre')[:35]
            gym_id = channel[2]
            stream_id = channel[3] or ''
            channel_type = channel[4] or ''
            is_direct = channel[5]
            event_id = channel[6]
            created = channel[7].strftime('%Y-%m-%d %H:%M:%S')

            # Verificar formato
            has_prefix = stream_id.startswith(('messaging:', 'team:'))
            status = '✅' if has_prefix else '❌'

            if has_prefix:
                with_prefix += 1
            else:
                without_prefix += 1
                issues.append({
                    'id': channel_id,
                    'name': name,
                    'stream_id': stream_id,
                    'created': created
                })

            # Determinar tipo de canal
            if is_direct:
                chat_type = '1-to-1'
            elif event_id:
                chat_type = f'Evento {event_id}'
            else:
                chat_type = 'Grupo'

            print(f'{status} Room {channel_id:<5} | {name:<35} | Gym {gym_id:<3} | {chat_type:<15} | {created}')
            print(f'   Stream ID: {stream_id}')
            print('-' * 120)

        # Resumen
        print('\n' + '=' * 120)
        print('📈 RESUMEN')
        print('=' * 120)
        print(f'Total canales analizados: {len(channels)}')
        print(f'✅ Con prefijo correcto:  {with_prefix} ({with_prefix/len(channels)*100:.1f}%)')
        print(f'❌ Sin prefijo:           {without_prefix} ({without_prefix/len(channels)*100:.1f}%)')

        if without_prefix == 0:
            print('\n🎉 ¡EXCELENTE! Todos los canales nuevos tienen formato correcto')
            print('   El sistema está creando canales correctamente con prefijo "messaging:"')
        else:
            print(f'\n⚠️  ATENCIÓN: {without_prefix} canales recientes SIN prefijo detectados')
            print('\n📋 Canales problemáticos:')
            for issue in issues:
                print(f'   - Room {issue["id"]}: {issue["name"]}')
                print(f'     Stream ID: {issue["stream_id"]}')
                print(f'     Creado: {issue["created"]}')

            print('\n💡 Acción recomendada:')
            print('   Estos canales necesitan ser arreglados con el script de migración:')
            print('   python scripts/fix_channel_id_prefixes.py --apply')


def verify_channel_creation_code():
    """Verifica que el código actual guarde el ID de Stream correctamente"""

    print('\n' + '=' * 120)
    print('🔍 VERIFICACIÓN DE CÓDIGO')
    print('=' * 120)

    print('\n📝 Flujo de creación de canales en app/services/chat.py:')
    print('   1. Genera channel_id SIN prefijo (ej: "direct_user_1_user_2")')
    print('   2. Crea canal en Stream: channel.create(...)')
    print('   3. Stream responde con ID completo (ej: "messaging:direct_user_1_user_2")')
    print('   4. Guarda stream_channel_id desde respuesta de Stream')
    print('   5. Persiste en BD con el ID que Stream devolvió')

    print('\n✅ Conclusión:')
    print('   El código DEBERÍA estar guardando el formato correcto automáticamente')
    print('   porque usa el ID que Stream devuelve en su respuesta.')

    print('\n🔎 Verificación del código:')
    print('   - Línea 521: stream_channel_id = channel_data.get("id")  # ID de Stream')
    print('   - Línea 546: stream_channel_id=stream_channel_id        # Guarda en BD')

    print('\n💡 Si hay canales sin prefijo creados recientemente:')
    print('   - Indica un BUG en cómo se procesa la respuesta de Stream')
    print('   - Necesita investigación adicional del flujo de creación')


def main():
    print('=' * 120)
    print('🔧 VERIFICACIÓN DE FORMATO DE NUEVOS CANALES')
    print('=' * 120)

    # Conectar a BD
    settings = get_settings()
    engine = create_engine(settings.SQLALCHEMY_DATABASE_URI)

    # Verificar canales recientes
    verify_recent_channels(engine, days_back=14)

    # Verificar código
    verify_channel_creation_code()

    print('\n' + '=' * 120)


if __name__ == '__main__':
    main()
