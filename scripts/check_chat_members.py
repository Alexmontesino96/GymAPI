#!/usr/bin/env python3
"""
Verificar si los canales sincronizados tienen ChatMember entries
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine, text
from app.core.config import get_settings


def check_chat_members(engine):
    """Verificar ChatMember para canales sincronizados"""

    # Canales que sabemos que están sincronizados
    channels_to_check = [
        ('messaging:direct_user_10_user_8', 638),
        ('messaging:room_General_10', 639),
        ('messaging:direct_user_11_user_8', 662),
        ('messaging:direct_user_10_user_17', 664),
        ('messaging:direct_user_10_user_11', 663)
    ]

    print('=' * 100)
    print('🔍 VERIFICACIÓN DE CHAT_MEMBERS')
    print('=' * 100)
    print(f'\nVerificando {len(channels_to_check)} canales sincronizados...\n')

    with engine.connect() as conn:
        for stream_id, room_id in channels_to_check:
            print(f'\n📋 Canal: {stream_id}')
            print(f'   Room ID: {room_id}')
            print('-' * 100)

            # Verificar ChatRoom
            result = conn.execute(text('''
                SELECT
                    id,
                    name,
                    gym_id,
                    stream_channel_id,
                    is_direct,
                    status
                FROM chat_rooms
                WHERE id = :room_id
            '''), {'room_id': room_id})

            room = result.fetchone()

            if not room:
                print(f'   ❌ ChatRoom NO existe')
                continue

            print(f'   ✅ ChatRoom existe:')
            print(f'      - Name: {room[1] or "Sin nombre"}')
            print(f'      - Gym ID: {room[2]}')
            print(f'      - Is Direct: {room[4]}')
            print(f'      - Status: {room[5]}')

            # Verificar ChatMembers
            result = conn.execute(text('''
                SELECT
                    cm.id,
                    cm.user_id,
                    cm.room_id,
                    cm.joined_at,
                    u.first_name,
                    u.last_name
                FROM chat_members cm
                LEFT JOIN "user" u ON u.id = cm.user_id
                WHERE cm.room_id = :room_id
                ORDER BY cm.joined_at
            '''), {'room_id': room_id})

            members = result.fetchall()

            if not members:
                print(f'   ❌ NO hay ChatMembers en la BD')
                print(f'   ⚠️  PROBLEMA: Canal existe pero no tiene miembros')
                print(f'   → El endpoint /my-rooms NO regresará este chat')
            else:
                print(f'   ✅ ChatMembers: {len(members)}')
                for member in members:
                    user_name = f"{member[4] or ''} {member[5] or ''}".strip() or "Usuario sin nombre"
                    print(f'      - User {member[1]}: {user_name} (Joined: {member[3]})')

            # Verificar si está oculto para algún usuario
            result = conn.execute(text('''
                SELECT
                    user_id,
                    hidden_at
                FROM chat_member_hidden
                WHERE room_id = :room_id
            '''), {'room_id': room_id})

            hidden = result.fetchall()

            if hidden:
                print(f'   ⚠️  Oculto para {len(hidden)} usuarios:')
                for h in hidden:
                    print(f'      - User {h[0]} (oculto desde: {h[1]})')

    print('\n' + '=' * 100)
    print('📊 ANÁLISIS DEL ENDPOINT /my-rooms')
    print('=' * 100)
    print('\n🔍 Lógica del endpoint:')
    print('   1. WHERE ChatMember.user_id = current_user.id')
    print('   2. AND ChatRoom.status = "ACTIVE"')
    print('   3. AND (room.gym_id = current_gym.id OR room.is_direct)')
    print('   4. AND room NOT IN chat_member_hidden (si include_hidden=false)')
    print('\n💡 Un canal NO aparecerá si:')
    print('   ❌ No tiene ChatMember para el usuario')
    print('   ❌ Status != "ACTIVE"')
    print('   ❌ Está en chat_member_hidden y include_hidden=false')
    print('   ❌ No es directo y gym_id != current_gym.id')


def main():
    settings = get_settings()
    engine = create_engine(settings.SQLALCHEMY_DATABASE_URI)

    check_chat_members(engine)


if __name__ == '__main__':
    main()
