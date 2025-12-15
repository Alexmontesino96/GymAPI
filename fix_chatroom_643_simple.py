"""
Script simple para corregir ChatRoom 643: Actualizar team de gym_1 a gym_5 en Stream Chat

Actualización DIRECTA sin consultar la base de datos.

Datos conocidos del análisis:
- ChatRoom ID: 643
- stream_channel_id: room_General_4
- gym_id (BD): 5
- team (Stream actual): gym_1 (INCORRECTO)
- team (esperado): gym_5
"""

import os
import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
from app.core.stream_client import stream_client

# Cargar variables de entorno
load_dotenv()

def fix_chatroom_643():
    """Corrige el team del ChatRoom 643 en Stream"""

    # Datos conocidos del análisis
    stream_channel_id = "room_General_4"
    expected_gym_id = 5
    expected_team = f"gym_{expected_gym_id}"

    try:
        print(f"\n📋 Datos del ChatRoom 643 (del análisis):")
        print(f"   - stream_channel_id: {stream_channel_id}")
        print(f"   - gym_id esperado (BD): {expected_gym_id}")

        # 1. Obtener canal de Stream
        channel = stream_client.channel('messaging', stream_channel_id)
        channel_info = channel.query()

        current_team = channel_info['channel'].get('team')
        print(f"   - team actual (Stream): {current_team}")

        # 2. Verificar si necesita corrección
        if current_team == expected_team:
            print(f"\n✅ El team ya es correcto: {current_team}")
            return True

        print(f"\n🔧 Actualizando team de '{current_team}' a '{expected_team}'...")

        # 3. Actualizar team en Stream
        update_response = channel.update({
            "team": expected_team,
            "gym_id": str(expected_gym_id)
        })

        print(f"✅ Team actualizado exitosamente en Stream Chat")

        # 4. Verificar la actualización
        updated_channel = stream_client.channel('messaging', stream_channel_id)
        updated_info = updated_channel.query()
        new_team = updated_info['channel'].get('team')

        print(f"\n🔍 Verificación:")
        print(f"   - Nuevo team en Stream: {new_team}")
        print(f"   - gym_id en BD: {expected_gym_id}")
        print(f"   - ✅ Coinciden: {new_team == expected_team}")

        return new_team == expected_team

    except Exception as e:
        print(f"\n❌ Error al corregir ChatRoom 643: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("🔧 Corrección de ChatRoom 643 - Sincronización team vs gym_id")
    print("=" * 60)

    success = fix_chatroom_643()

    print("\n" + "=" * 60)
    if success:
        print("✅ CORRECCIÓN COMPLETADA EXITOSAMENTE")
    else:
        print("❌ CORRECCIÓN FALLÓ - Revisar errores arriba")
    print("=" * 60)
