#!/usr/bin/env python3
"""
Script para probar el endpoint de historial de clases del usuario.
Obtiene las clases de la última semana para un usuario de prueba.
"""

import os
import sys
import requests
from datetime import datetime, timedelta, date
from typing import Optional, List, Dict, Any
import json

# Añadir el directorio padre al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_last_week_classes(
    base_url: str,
    auth_token: str,
    gym_id: int,
    days_back: int = 7
) -> Optional[List[Dict[str, Any]]]:
    """
    Obtiene el historial de clases de los últimos N días.

    Args:
        base_url: URL base del API (ej: http://localhost:8000)
        auth_token: Token JWT de Auth0
        gym_id: ID del gimnasio
        days_back: Cantidad de días hacia atrás (default: 7)

    Returns:
        Lista de participaciones en clases o None si hay error
    """
    # Calcular fechas
    end_date = date.today()
    start_date = end_date - timedelta(days=days_back)

    # Formatear fechas en formato YYYY-MM-DD
    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')

    # Construir URL
    url = f"{base_url}/api/v1/schedule/participation/my-history"

    # Headers
    headers = {
        'Authorization': f'Bearer {auth_token}',
        'X-Gym-ID': str(gym_id),
        'Content-Type': 'application/json'
    }

    # Parámetros
    params = {
        'start_date': start_date_str,
        'end_date': end_date_str,
        'limit': 100  # Máximo de resultados
    }

    print(f"📅 Obteniendo clases del {start_date_str} al {end_date_str}")
    print(f"🌐 URL: {url}")
    print(f"📊 Parámetros: {params}")

    try:
        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"   Detalle: {response.text}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"❌ Error de conexión: {e}")
        return None


def analyze_class_history(history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analiza el historial de clases y genera estadísticas.

    Args:
        history: Lista de participaciones en clases

    Returns:
        Diccionario con estadísticas
    """
    if not history:
        return {
            'total_classes': 0,
            'attended': 0,
            'registered': 0,
            'cancelled': 0,
            'no_show': 0,
            'total_minutes': 0,
            'by_category': {},
            'by_day': {}
        }

    stats = {
        'total_classes': len(history),
        'attended': 0,
        'registered': 0,
        'cancelled': 0,
        'no_show': 0,
        'total_minutes': 0,
        'by_category': {},
        'by_day': {}
    }

    for item in history:
        participation = item.get('participation', {})
        session = item.get('session', {})
        gym_class = item.get('class', {})

        # Contar por estado
        status = participation.get('status', '')
        if status == 'attended':
            stats['attended'] += 1
            # Sumar tiempo solo si asistió
            stats['total_minutes'] += gym_class.get('duration', 0)
        elif status == 'registered':
            stats['registered'] += 1
        elif status == 'cancelled':
            stats['cancelled'] += 1
        elif status == 'no_show':
            stats['no_show'] += 1

        # Agrupar por categoría
        category = gym_class.get('category_enum', 'other')
        if category not in stats['by_category']:
            stats['by_category'][category] = 0
        stats['by_category'][category] += 1

        # Agrupar por día
        start_time = session.get('start_time_local') or session.get('start_time')
        if start_time:
            try:
                dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                day_name = dt.strftime('%A')
                if day_name not in stats['by_day']:
                    stats['by_day'][day_name] = 0
                stats['by_day'][day_name] += 1
            except:
                pass

    return stats


def print_class_details(history: List[Dict[str, Any]], limit: int = 5):
    """
    Imprime detalles de las últimas clases.

    Args:
        history: Lista de participaciones
        limit: Cantidad máxima de clases a mostrar
    """
    print(f"\n📚 ÚLTIMAS {min(limit, len(history))} CLASES:")
    print("-" * 70)

    for i, item in enumerate(history[:limit]):
        participation = item.get('participation', {})
        session = item.get('session', {})
        gym_class = item.get('class', {})

        # Obtener fecha/hora local
        start_time_local = session.get('start_time_local')
        if start_time_local:
            try:
                dt = datetime.fromisoformat(start_time_local)
                fecha_str = dt.strftime('%d/%m/%Y %H:%M')
            except:
                fecha_str = start_time_local
        else:
            fecha_str = "Fecha no disponible"

        # Estado con emoji
        status = participation.get('status', 'unknown')
        status_emojis = {
            'attended': '✅',
            'registered': '📝',
            'cancelled': '❌',
            'no_show': '⚠️'
        }
        status_emoji = status_emojis.get(status, '❓')

        print(f"\n{i + 1}. {gym_class.get('name', 'Sin nombre')}")
        print(f"   📅 Fecha: {fecha_str}")
        print(f"   ⏱️ Duración: {gym_class.get('duration', 0)} min")
        print(f"   📍 Sala: {session.get('room', 'No especificada')}")
        print(f"   🏃 Categoría: {gym_class.get('category_enum', 'No especificada')}")
        print(f"   🎯 Nivel: {gym_class.get('difficulty_level', 'No especificado')}")
        print(f"   {status_emoji} Estado: {status}")

    if len(history) > limit:
        print(f"\n   ... y {len(history) - limit} clases más")


def main():
    """Función principal del script."""

    # Configuración
    BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
    AUTH_TOKEN = os.getenv("TEST_AUTH_TOKEN", "")
    GYM_ID = int(os.getenv("TEST_GYM_ID", "1"))

    if not AUTH_TOKEN:
        print("❌ Error: TEST_AUTH_TOKEN no configurado en .env")
        print("   Por favor configura un token válido de Auth0")
        return

    print("=" * 70)
    print("🏋️ PRUEBA DE HISTORIAL DE CLASES DEL USUARIO")
    print("=" * 70)
    print(f"🌐 API URL: {BASE_URL}")
    print(f"🏢 Gym ID: {GYM_ID}")
    print()

    # Obtener historial de la última semana
    print("📊 OBTENIENDO HISTORIAL DE LA ÚLTIMA SEMANA...")
    history = get_last_week_classes(BASE_URL, AUTH_TOKEN, GYM_ID, days_back=7)

    if history is None:
        print("❌ No se pudo obtener el historial")
        return

    if len(history) == 0:
        print("ℹ️ No hay clases registradas en los últimos 7 días")

        # Intentar con un rango más amplio
        print("\n🔄 Intentando con los últimos 30 días...")
        history = get_last_week_classes(BASE_URL, AUTH_TOKEN, GYM_ID, days_back=30)

        if history and len(history) > 0:
            print(f"✅ Se encontraron {len(history)} clases en los últimos 30 días")

    if history and len(history) > 0:
        # Analizar estadísticas
        stats = analyze_class_history(history)

        # Mostrar estadísticas
        print("\n" + "=" * 70)
        print("📈 ESTADÍSTICAS")
        print("=" * 70)
        print(f"📊 Total de clases: {stats['total_classes']}")
        print(f"✅ Asistidas: {stats['attended']}")
        print(f"📝 Registradas (pendientes): {stats['registered']}")
        print(f"❌ Canceladas: {stats['cancelled']}")
        print(f"⚠️ No asistió: {stats['no_show']}")
        print(f"⏱️ Tiempo total de entrenamiento: {stats['total_minutes']} minutos")

        if stats['total_minutes'] > 0:
            hours = stats['total_minutes'] // 60
            minutes = stats['total_minutes'] % 60
            print(f"   ({hours} horas y {minutes} minutos)")

        # Mostrar por categoría
        if stats['by_category']:
            print("\n📂 POR CATEGORÍA:")
            for category, count in stats['by_category'].items():
                print(f"   • {category}: {count} clases")

        # Mostrar por día
        if stats['by_day']:
            print("\n📅 POR DÍA DE LA SEMANA:")
            days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            for day in days_order:
                if day in stats['by_day']:
                    print(f"   • {day}: {stats['by_day'][day]} clases")

        # Mostrar detalles de las últimas clases
        print_class_details(history, limit=5)

        # Calcular tasa de asistencia
        if stats['total_classes'] > 0:
            attendance_rate = (stats['attended'] / stats['total_classes']) * 100
            print(f"\n📊 Tasa de asistencia: {attendance_rate:.1f}%")

    print("\n" + "=" * 70)
    print("✅ Prueba completada")
    print("=" * 70)


if __name__ == "__main__":
    main()