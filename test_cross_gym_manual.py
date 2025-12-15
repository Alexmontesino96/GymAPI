"""
Test Manual Extensivo - Implementación Cross-Gym

Este script valida manualmente la implementación cross-gym usando PostgreSQL real.
NO usa pytest debido a incompatibilidades UUID/SQLite.
"""

import sys
import os
from pathlib import Path

# Agregar directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
from sqlalchemy import select, and_, func
from sqlalchemy.orm import joinedload

from app.db.session import SessionLocal
from app.models.chat import ChatRoom, ChatMember
from app.models.gym import Gym
from app.models.user import User
from app.models.user_gym import UserGym, GymRoleType
from app.repositories.chat import ChatRepository
from app.services.chat import ChatService

# Cargar variables de entorno
load_dotenv()


class CrossGymTester:
    """Tester para validación de implementación cross-gym"""

    def __init__(self):
        self.db = SessionLocal()
        self.chat_service = ChatService()
        self.chat_repo = ChatRepository()
        self.test_results = []
        self.gyms = {}
        self.users = {}

    def cleanup(self):
        """Limpia datos de test anteriores"""
        print("🧹 Limpiando datos de tests anteriores...")

        # Eliminar chats de test
        self.db.query(ChatMember).filter(
            ChatMember.room_id.in_(
                self.db.query(ChatRoom.id).filter(
                    ChatRoom.name.like("%Test Cross-Gym%")
                )
            )
        ).delete(synchronize_session=False)

        self.db.query(ChatRoom).filter(
            ChatRoom.name.like("%Test Cross-Gym%")
        ).delete(synchronize_session=False)

        # Eliminar asociaciones de usuarios de test
        self.db.query(UserGym).filter(
            UserGym.user_id.in_(
                self.db.query(User.id).filter(
                    User.email.like("%crossgym_test%")
                )
            )
        ).delete(synchronize_session=False)

        # Eliminar usuarios de test
        self.db.query(User).filter(
            User.email.like("%crossgym_test%")
        ).delete(synchronize_session=False)

        # Eliminar gyms de test
        self.db.query(Gym).filter(
            Gym.name.like("%Test Cross-Gym%")
        ).delete(synchronize_session=False)

        self.db.commit()
        print("✅ Limpieza completada")

    def setup_test_data(self):
        """Crea datos de test: 3 gyms y 4 usuarios"""
        print("\n📦 Creando datos de test...")

        # Crear 3 gimnasios
        for i in range(1, 4):
            gym = Gym(
                name=f"Test Cross-Gym {i}",
                description=f"Gimnasio de prueba {i}",
                created_by_id=1
            )
            self.db.add(gym)
            self.db.commit()
            self.db.refresh(gym)
            self.gyms[f"gym_{i}"] = gym
            print(f"  ✅ Gym {i} creado (ID: {gym.id})")

        # User A: gym_1, gym_2, gym_3 (multi-gym completo)
        user_a = User(
            email="crossgym_test_user_a@test.com",
            auth0_id="auth0|crossgym_test_user_a",
            full_name="Test User A (Multi-Gym)"
        )
        self.db.add(user_a)
        self.db.commit()
        self.db.refresh(user_a)
        self.users["user_a"] = user_a

        for gym_key in ["gym_1", "gym_2", "gym_3"]:
            ug = UserGym(
                user_id=user_a.id,
                gym_id=self.gyms[gym_key].id,
                role=GymRoleType.MEMBER
            )
            self.db.add(ug)
        self.db.commit()
        print(f"  ✅ User A creado (ID: {user_a.id}) - gyms: 1,2,3")

        # User B: gym_2, gym_3 (comparte 2 gyms con A)
        user_b = User(
            email="crossgym_test_user_b@test.com",
            auth0_id="auth0|crossgym_test_user_b",
            full_name="Test User B (Dual-Gym)"
        )
        self.db.add(user_b)
        self.db.commit()
        self.db.refresh(user_b)
        self.users["user_b"] = user_b

        for gym_key in ["gym_2", "gym_3"]:
            ug = UserGym(
                user_id=user_b.id,
                gym_id=self.gyms[gym_key].id,
                role=GymRoleType.MEMBER
            )
            self.db.add(ug)
        self.db.commit()
        print(f"  ✅ User B creado (ID: {user_b.id}) - gyms: 2,3")

        # User C: solo gym_1
        user_c = User(
            email="crossgym_test_user_c@test.com",
            auth0_id="auth0|crossgym_test_user_c",
            full_name="Test User C (Single-Gym)"
        )
        self.db.add(user_c)
        self.db.commit()
        self.db.refresh(user_c)
        self.users["user_c"] = user_c

        ug = UserGym(
            user_id=user_c.id,
            gym_id=self.gyms["gym_1"].id,
            role=GymRoleType.MEMBER
        )
        self.db.add(ug)
        self.db.commit()
        print(f"  ✅ User C creado (ID: {user_c.id}) - gym: 1")

        print("\n✅ Setup completado")

    def test_single_chat_cross_gym(self):
        """Test 1: Un solo chat por par de usuarios, independiente del gym"""
        print("\n" + "="*60)
        print("TEST 1: Un Solo Chat Cross-Gym")
        print("="*60)

        user_a = self.users["user_a"]
        user_b = self.users["user_b"]
        gym_1 = self.gyms["gym_1"]
        gym_2 = self.gyms["gym_2"]
        gym_3 = self.gyms["gym_3"]

        print(f"Setup: User A (gyms: 1,2,3), User B (gyms: 2,3)")
        print(f"Common gyms: {{2, 3}}")

        # Request 1: Desde gym_1 (NO compartido)
        print(f"\n📍 Request 1: Crear chat desde gym_1 (NO compartido)")
        result_1 = self.chat_service.get_or_create_direct_chat(
            self.db,
            user1_id=user_a.id,
            user2_id=user_b.id,
            gym_id=gym_1.id
        )
        chat_id_1 = result_1["id"]
        chat_1 = self.db.query(ChatRoom).filter(ChatRoom.id == chat_id_1).first()

        print(f"  Chat creado: ID={chat_id_1}, gym_id={chat_1.gym_id}")
        expected_gym_id = gym_2.id  # min({2, 3})
        if chat_1.gym_id == expected_gym_id:
            print(f"  ✅ gym_id correcto: {expected_gym_id} (min de common_gyms)")
            self.test_results.append(("1.1 - gym_id determinista", "PASS"))
        else:
            print(f"  ❌ gym_id incorrecto: esperaba {expected_gym_id}, obtuvo {chat_1.gym_id}")
            self.test_results.append(("1.1 - gym_id determinista", "FAIL"))

        # Request 2: Desde gym_2 (compartido)
        print(f"\n📍 Request 2: Obtener chat desde gym_2 (compartido)")
        result_2 = self.chat_service.get_or_create_direct_chat(
            self.db,
            user1_id=user_a.id,
            user2_id=user_b.id,
            gym_id=gym_2.id
        )
        chat_id_2 = result_2["id"]

        if chat_id_1 == chat_id_2:
            print(f"  ✅ Mismo chat (ID={chat_id_2}), NO creó duplicado")
            self.test_results.append(("1.2 - No duplicado desde gym_2", "PASS"))
        else:
            print(f"  ❌ Chat duplicado: ID1={chat_id_1}, ID2={chat_id_2}")
            self.test_results.append(("1.2 - No duplicado desde gym_2", "FAIL"))

        # Request 3: Desde gym_3 (compartido)
        print(f"\n📍 Request 3: Obtener chat desde gym_3 (compartido)")
        result_3 = self.chat_service.get_or_create_direct_chat(
            self.db,
            user1_id=user_a.id,
            user2_id=user_b.id,
            gym_id=gym_3.id
        )
        chat_id_3 = result_3["id"]

        if chat_id_1 == chat_id_3:
            print(f"  ✅ Mismo chat (ID={chat_id_3}), NO creó duplicado")
            self.test_results.append(("1.3 - No duplicado desde gym_3", "PASS"))
        else:
            print(f"  ❌ Chat duplicado: ID1={chat_id_1}, ID3={chat_id_3}")
            self.test_results.append(("1.3 - No duplicado desde gym_3", "FAIL"))

        # Verificar total de chats
        total_chats = self.db.query(ChatRoom).filter(
            ChatRoom.is_direct == True,
            ChatRoom.name.like("%Test Cross-Gym%")
        ).count()

        if total_chats == 1:
            print(f"\n  ✅ Total chats directos: {total_chats} (correcto)")
            self.test_results.append(("1.4 - Total chats = 1", "PASS"))
        else:
            print(f"\n  ❌ Total chats directos: {total_chats} (esperaba 1)")
            self.test_results.append(("1.4 - Total chats = 1", "FAIL"))

    def test_cross_gym_visibility(self):
        """Test 2: Visibilidad cross-gym en /my-rooms"""
        print("\n" + "="*60)
        print("TEST 2: Visibilidad Cross-Gym en /my-rooms")
        print("="*60)

        user_a = self.users["user_a"]
        user_b = self.users["user_b"]
        gym_1 = self.gyms["gym_1"]
        gym_2 = self.gyms["gym_2"]
        gym_3 = self.gyms["gym_3"]

        # Buscar el chat existente (creado en test anterior)
        chat = self.db.query(ChatRoom).filter(
            ChatRoom.is_direct == True,
            ChatRoom.name.like("%Test Cross-Gym%")
        ).first()

        if not chat:
            print("  ❌ No se encontró chat de test anterior")
            self.test_results.append(("2.x - Chat existente", "FAIL"))
            return

        print(f"Chat encontrado: ID={chat.id}, gym_id={chat.gym_id}")

        # Simular lógica de /my-rooms para cada gym
        for gym_key, gym in [("gym_2", gym_2), ("gym_3", gym_3), ("gym_1", gym_1)]:
            print(f"\n📍 Verificando visibilidad desde {gym_key} (ID={gym.id})")

            # Query base con eager loading
            user_rooms = self.db.query(ChatRoom).join(ChatMember).options(
                joinedload(ChatRoom.members)
            ).filter(
                and_(
                    ChatMember.user_id == user_a.id,
                    ChatRoom.status == "ACTIVE",
                    ChatRoom.name.like("%Test Cross-Gym%")
                )
            ).all()

            # Filtrar
            filtered_rooms = []
            for room in user_rooms:
                # Match directo
                if room.gym_id == gym.id:
                    filtered_rooms.append(room)
                # Cross-gym para directos
                elif room.is_direct:
                    member_ids = [m.user_id for m in room.members]
                    if not member_ids:
                        continue

                    # Verificar que TODOS estén en el gym
                    members_in_gym = self.db.query(UserGym.user_id).filter(
                        and_(
                            UserGym.user_id.in_(member_ids),
                            UserGym.gym_id == gym.id
                        )
                    ).all()
                    members_in_gym_set = {uid for (uid,) in members_in_gym}

                    if all(mid in members_in_gym_set for mid in member_ids):
                        filtered_rooms.append(room)

            # Verificar resultado esperado
            visible = len(filtered_rooms) > 0
            expected = gym_key in ["gym_2", "gym_3"]  # Debe ser visible en 2 y 3, NO en 1

            if visible == expected:
                status = "visible" if visible else "NO visible"
                print(f"  ✅ {status} (correcto)")
                self.test_results.append((f"2.{gym_key} - Visibilidad", "PASS"))
            else:
                status = "visible" if visible else "NO visible"
                expected_status = "visible" if expected else "NO visible"
                print(f"  ❌ {status} (esperaba {expected_status})")
                self.test_results.append((f"2.{gym_key} - Visibilidad", "FAIL"))

    def test_deterministic_behavior(self):
        """Test 3: Comportamiento determinista"""
        print("\n" + "="*60)
        print("TEST 3: Comportamiento Determinista")
        print("="*60)

        user_a = self.users["user_a"]
        user_c = self.users["user_c"]  # solo gym_1
        gym_1 = self.gyms["gym_1"]

        print(f"Setup: User A (gyms: 1,2,3), User C (gym: 1)")
        print(f"Common gyms: {{1}}")
        print(f"Request desde gym_2 (NO compartido con C)")

        # Llamar 5 veces y verificar que siempre usa el mismo gym_id
        gym_ids = []
        for i in range(5):
            # Limpiar cache
            from app.services.chat import channel_cache
            channel_cache.clear()

            # Eliminar chat anterior
            self.db.query(ChatMember).filter(
                ChatMember.room_id.in_(
                    self.db.query(ChatRoom.id).filter(
                        ChatRoom.name.like("%User A - User C%")
                    )
                )
            ).delete(synchronize_session=False)
            self.db.query(ChatRoom).filter(
                ChatRoom.name.like("%User A - User C%")
            ).delete(synchronize_session=False)
            self.db.commit()

            # Crear chat
            result = self.chat_service.get_or_create_direct_chat(
                self.db,
                user1_id=user_a.id,
                user2_id=user_c.id,
                gym_id=self.gyms["gym_2"].id  # Request desde gym_2
            )

            chat = self.db.query(ChatRoom).filter(ChatRoom.id == result["id"]).first()
            gym_ids.append(chat.gym_id)
            print(f"  Iteración {i+1}: gym_id={chat.gym_id}")

        # Verificar que todos sean iguales
        unique = set(gym_ids)
        if len(unique) == 1:
            print(f"\n  ✅ Comportamiento determinista: siempre gym_id={gym_ids[0]}")
            self.test_results.append(("3.1 - Determinista", "PASS"))

            # Verificar que sea el correcto (gym_1, único compartido)
            if gym_ids[0] == gym_1.id:
                print(f"  ✅ gym_id correcto: {gym_1.id} (único compartido)")
                self.test_results.append(("3.2 - gym_id correcto", "PASS"))
            else:
                print(f"  ❌ gym_id incorrecto: esperaba {gym_1.id}, obtuvo {gym_ids[0]}")
                self.test_results.append(("3.2 - gym_id correcto", "FAIL"))
        else:
            print(f"\n  ❌ Comportamiento NO determinista: {unique}")
            self.test_results.append(("3.1 - Determinista", "FAIL"))

    def print_summary(self):
        """Imprime resumen de resultados"""
        print("\n" + "="*60)
        print("📊 RESUMEN DE TESTS")
        print("="*60)

        passed = sum(1 for _, result in self.test_results if result == "PASS")
        failed = sum(1 for _, result in self.test_results if result == "FAIL")
        total = len(self.test_results)

        for test_name, result in self.test_results:
            icon = "✅" if result == "PASS" else "❌"
            print(f"{icon} {test_name}: {result}")

        print("\n" + "-"*60)
        print(f"Total: {total} tests")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"Success Rate: {(passed/total*100):.1f}%")
        print("="*60)

        return failed == 0

    def run_all_tests(self):
        """Ejecuta todos los tests"""
        try:
            print("\n🚀 Iniciando Tests Extensivos Cross-Gym")
            print("="*60)

            self.cleanup()
            self.setup_test_data()

            self.test_single_chat_cross_gym()
            self.test_cross_gym_visibility()
            self.test_deterministic_behavior()

            success = self.print_summary()

            # Cleanup final
            print("\n🧹 Limpieza final...")
            self.cleanup()

            return success

        except Exception as e:
            print(f"\n❌ Error durante tests: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            self.db.close()


if __name__ == "__main__":
    tester = CrossGymTester()
    success = tester.run_all_tests()

    if success:
        print("\n✅ TODOS LOS TESTS PASARON")
        sys.exit(0)
    else:
        print("\n❌ ALGUNOS TESTS FALLARON")
        sys.exit(1)
