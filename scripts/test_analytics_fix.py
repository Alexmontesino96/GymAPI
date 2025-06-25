#!/usr/bin/env python3

"""
Script para probar que las analíticas de chat funcionen correctamente
después de agregar gym_id a ChatRoom.
"""

import requests
import json
import sys
import os

# Configuración
BASE_URL = "http://127.0.0.1:8080/api/v1"
GYM_ID = 4

# Token del usuario (reemplazar con un token válido)
TOKEN = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6InI2YXBIZVNOUEluaXpaeDlYN1NidyJ9.eyJlbWFpbCI6IjFraWNrQGdtYWlsLmNvbSIsImlzcyI6Imh0dHBzOi8vZGV2LWdkNWNyZmU2cWJxbHUyM3AudXMuYXV0aDAuY29tLyIsInN1YiI6ImF1dGgwfDY4MjY5ZWNjNzMxYTc3ZmNmNTU1MjllNyIsImF1ZCI6WyJodHRwczovL2d5bWFwaSIsImh0dHBzOi8vZGV2LWdkNWNyZmU2cWJxbHUyM3AudXMuYXV0aDAuY29tL3VzZXJpbmZvIl0sImlhdCI6MTc1MDgyMDgwOCwiZXhwIjoxNzUwOTA3MjA4LCJzY29wZSI6Im9wZW5pZCBwcm9maWxlIGVtYWlsIiwiYXpwIjoiT3VKNklLRTBsSlNkYU1HNmphVzA0amZwdHNNUmJ5dnAiLCJwZXJtaXNzaW9ucyI6WyJyZXNvdXJjZTphZG1pbiIsInJlc291cmNlOnJlYWQiLCJyZXNvdXJjZTp3cml0ZSIsInRlbmFudDphZG1pbiIsInRlbmFudDpyZWFkIiwidXNlcjpyZWFkIiwidXNlcjp3cml0ZSJdfQ.iFJKIhI3s50tsL2SUv3qAI1p2m6e22dBunTNtwpaF1vEzS67EQipva6P6We45IovXTUs0FiXuQaBeSP-rFhRFLiz9yK8crf8n_als0pf4tTTJHNx07XU0HVNs73OyNx6z3OO_voAg50O3SZRMgMqALibsyG9MvkWxl_0ae8CooDrAT9dpaA9i6WuJZifEITYvXX8yfYx3nG8r23ztKa5YYh_9WXIqG0NpWK8HzBg334JgvA2M-_1WNvdCiOh0D9sPaF9ZWgCBcM-d7_P2XVsXNkMfgl7kjl6vhwmG5Pu5nPEgdLcDyFy8sxk-hIWmHoA-YHrC1iSXckS3qCQ05rchg"

def make_request(method, endpoint, data=None):
    """Hace una petición HTTP con autenticación"""
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "X-Gym-ID": str(GYM_ID),
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    url = f"{BASE_URL}{endpoint}"
    
    try:
        if method.upper() == "GET":
            response = requests.get(url, headers=headers)
        elif method.upper() == "POST":
            response = requests.post(url, headers=headers, json=data)
        else:
            print(f"❌ Método HTTP no soportado: {method}")
            return None
        
        print(f"\n{'='*60}")
        print(f"🔗 {method.upper()} {endpoint}")
        print(f"📊 Status: {response.status_code}")
        
        if response.status_code == 200 or response.status_code == 201:
            result = response.json()
            print(f"✅ Éxito:")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return result
        else:
            print(f"❌ Error: {response.status_code}")
            try:
                error_detail = response.json()
                print(json.dumps(error_detail, indent=2, ensure_ascii=False))
            except:
                print(response.text)
            return None
            
    except Exception as e:
        print(f"❌ Error de conexión: {str(e)}")
        return None

def main():
    print(f"🧪 Probando analíticas de chat para gym_id={GYM_ID}")
    print(f"🌐 Servidor: {BASE_URL}")
    
    # 1. Probar resumen de gimnasio
    print(f"\n{'='*60}")
    print("📈 1. Probando resumen de gimnasio...")
    summary = make_request("GET", "/chat/analytics/gym-summary")
    
    if summary and summary.get("total_rooms", 0) > 0:
        print(f"✅ Encontradas {summary['total_rooms']} salas para gym_id={GYM_ID}")
    else:
        print(f"⚠️  No se encontraron salas para gym_id={GYM_ID}")
    
    # 2. Probar horarios populares
    print(f"\n{'='*60}")
    print("⏰ 2. Probando horarios populares...")
    popular_times = make_request("GET", "/chat/analytics/popular-times")
    
    # 3. Probar métricas de salud
    print(f"\n{'='*60}")
    print("🏥 3. Probando métricas de salud...")
    health = make_request("GET", "/chat/analytics/health-metrics")
    
    # 4. Crear una nueva sala para verificar que se asocie correctamente
    print(f"\n{'='*60}")
    print("🆕 4. Creando nueva sala de prueba...")
    new_room_data = {
        "name": f"Sala Test Analytics {GYM_ID}",
        "is_direct": False,
        "member_ids": [10, 8, 5]
    }
    new_room = make_request("POST", "/chat/rooms", new_room_data)
    
    if new_room:
        room_id = new_room.get("id")
        print(f"✅ Sala creada con ID: {room_id}")
        
        # 5. Volver a probar resumen después de crear la sala
        print(f"\n{'='*60}")
        print("🔄 5. Probando resumen actualizado...")
        updated_summary = make_request("GET", "/chat/analytics/gym-summary")
        
        if updated_summary and updated_summary.get("total_rooms", 0) > (summary.get("total_rooms", 0) if summary else 0):
            print("✅ El resumen se actualizó correctamente después de crear la sala")
        else:
            print("⚠️  El resumen no se actualizó como esperado")
    
    print(f"\n{'='*60}")
    print("🎯 Prueba completada")

if __name__ == "__main__":
    main() 