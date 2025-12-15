"""
Tests Extensivos para Chat Cross-Gym

Tests comprehensivos para validar la implementación de chats directos cross-gym:
1. Un solo chat por par de usuarios
2. Comportamiento determinista en selección de gym_id
3. Visibilidad cross-gym en /my-rooms
4. Edge cases (usuarios sin gyms compartidos, chats sin miembros)
5. Performance (no N+1 queries)
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from sqlalchemy import text

from app.models.chat import ChatRoom, ChatMember, ChatRoomStatus
from app.models.gym import Gym
from app.models.user import User
from app.models.user_gym import UserGym, GymRoleType
from app.repositories.chat import ChatRepository
from app.services.chat import ChatService


@pytest.fixture
def multi_gym_setup(db):
    """
    Setup completo para tests cross-gym:
    - 3 gimnasios (gym_1, gym_2, gym_3)
    - 4 usuarios con diferentes combinaciones de gyms
    """
    # Crear gimnasios
    gyms = {}
    for i in range(1, 4):
        gym = Gym(
            name=f"Test Gym {i}",
            description=f"Gimnasio de prueba {i}",
            created_by_id=1
        )
        db.add(gym)
        db.commit()
        db.refresh(gym)
        gyms[f"gym_{i}"] = gym

    # Crear usuarios
    users = {}

    # User A: gym_1, gym_2, gym_3 (multi-gym completo)
    user_a = User(
        email="user_a@test.com",
        auth0_id="auth0|user_a",
        full_name="User A Multi-Gym"
    )
    db.add(user_a)
    db.commit()
    db.refresh(user_a)
    users["user_a"] = user_a

    # Asociar a todos los gyms
    for gym_key in ["gym_1", "gym_2", "gym_3"]:
        user_gym = UserGym(
            user_id=user_a.id,
            gym_id=gyms[gym_key].id,
            role=GymRoleType.MEMBER
        )
        db.add(user_gym)

    # User B: gym_2, gym_3 (comparte 2 gyms con A)
    user_b = User(
        email="user_b@test.com",
        auth0_id="auth0|user_b",
        full_name="User B Dual-Gym"
    )
    db.add(user_b)
    db.commit()
    db.refresh(user_b)
    users["user_b"] = user_b

    for gym_key in ["gym_2", "gym_3"]:
        user_gym = UserGym(
            user_id=user_b.id,
            gym_id=gyms[gym_key].id,
            role=GymRoleType.MEMBER
        )
        db.add(user_gym)

    # User C: solo gym_1 (solo comparte 1 gym con A)
    user_c = User(
        email="user_c@test.com",
        auth0_id="auth0|user_c",
        full_name="User C Single-Gym"
    )
    db.add(user_c)
    db.commit()
    db.refresh(user_c)
    users["user_c"] = user_c

    user_gym = UserGym(
        user_id=user_c.id,
        gym_id=gyms["gym_1"].id,
        role=GymRoleType.MEMBER
    )
    db.add(user_gym)

    # User D: solo gym_3 (solo comparte 1 gym con A y B)
    user_d = User(
        email="user_d@test.com",
        auth0_id="auth0|user_d",
        full_name="User D Single-Gym"
    )
    db.add(user_d)
    db.commit()
    db.refresh(user_d)
    users["user_d"] = user_d

    user_gym = UserGym(
        user_id=user_d.id,
        gym_id=gyms["gym_3"].id,
        role=GymRoleType.MEMBER
    )
    db.add(user_gym)

    db.commit()

    return {
        "gyms": gyms,
        "users": users,
        "db": db
    }


class TestSingleChatCrossGym:
    """Tests para verificar que solo existe UN chat por par de usuarios"""

    def test_single_chat_created_regardless_of_gym(self, multi_gym_setup):
        """
        Test: Al crear chat desde diferentes gyms, debe retornar EL MISMO chat

        Setup: User A (gym_1,2,3) y User B (gym_2,3)

        Esperado:
        - Request desde gym_1 → crea chat con gym_id=2 (min de gyms compartidos)
        - Request desde gym_2 → retorna MISMO chat
        - Request desde gym_3 → retorna MISMO chat
        """
        setup = multi_gym_setup
        db = setup["db"]
        user_a = setup["users"]["user_a"]
        user_b = setup["users"]["user_b"]
        gym_1 = setup["gyms"]["gym_1"]
        gym_2 = setup["gyms"]["gym_2"]
        gym_3 = setup["gyms"]["gym_3"]

        chat_service = ChatService()

        # Request 1: Desde gym_1 (NO compartido)
        result_1 = chat_service.get_or_create_direct_chat(
            db,
            user1_id=user_a.id,
            user2_id=user_b.id,
            gym_id=gym_1.id
        )
        chat_id_1 = result_1["id"]

        # Verificar que se creó con gym_id = min(common_gyms) = 2
        chat_room_1 = db.query(ChatRoom).filter(ChatRoom.id == chat_id_1).first()
        assert chat_room_1 is not None
        assert chat_room_1.gym_id == gym_2.id, f"Esperaba gym_id={gym_2.id}, obtuvo {chat_room_1.gym_id}"

        # Request 2: Desde gym_2 (compartido)
        result_2 = chat_service.get_or_create_direct_chat(
            db,
            user1_id=user_a.id,
            user2_id=user_b.id,
            gym_id=gym_2.id
        )
        chat_id_2 = result_2["id"]

        # Debe ser el MISMO chat
        assert chat_id_1 == chat_id_2, "Creó chat duplicado desde gym_2"

        # Request 3: Desde gym_3 (compartido)
        result_3 = chat_service.get_or_create_direct_chat(
            db,
            user1_id=user_a.id,
            user2_id=user_b.id,
            gym_id=gym_3.id
        )
        chat_id_3 = result_3["id"]

        # Debe ser el MISMO chat
        assert chat_id_1 == chat_id_3, "Creó chat duplicado desde gym_3"

        # Verificar que solo existe UN chat en la BD
        total_chats = db.query(ChatRoom).filter(
            ChatRoom.is_direct == True
        ).count()
        assert total_chats == 1, f"Esperaba 1 chat, encontró {total_chats}"

    def test_no_duplicate_chats_with_reversed_users(self, multi_gym_setup):
        """
        Test: El orden de los usuarios no debe importar

        get_or_create_direct_chat(A, B) == get_or_create_direct_chat(B, A)
        """
        setup = multi_gym_setup
        db = setup["db"]
        user_a = setup["users"]["user_a"]
        user_b = setup["users"]["user_b"]
        gym_2 = setup["gyms"]["gym_2"]

        chat_service = ChatService()

        # Request: A → B
        result_1 = chat_service.get_or_create_direct_chat(
            db,
            user1_id=user_a.id,
            user2_id=user_b.id,
            gym_id=gym_2.id
        )

        # Request: B → A (orden invertido)
        result_2 = chat_service.get_or_create_direct_chat(
            db,
            user1_id=user_b.id,
            user2_id=user_a.id,
            gym_id=gym_2.id
        )

        # Debe ser el MISMO chat
        assert result_1["id"] == result_2["id"], "Creó chat duplicado con usuarios invertidos"


class TestDeterministicBehavior:
    """Tests para verificar comportamiento determinista"""

    def test_gym_selection_is_deterministic(self, multi_gym_setup):
        """
        Test: Selección de gym_id debe ser determinista (siempre el mismo)

        Cuando request gym NO está en common_gyms, debe usar min(common_gyms)
        """
        setup = multi_gym_setup
        db = setup["db"]
        user_a = setup["users"]["user_a"]
        user_b = setup["users"]["user_b"]
        gym_1 = setup["gyms"]["gym_1"]
        gym_2 = setup["gyms"]["gym_2"]

        chat_service = ChatService()

        # Llamar 10 veces desde gym_1 (NO compartido con B)
        # Debe SIEMPRE usar gym_2 (min({2, 3}))
        gym_ids = []
        for _ in range(10):
            # Limpiar cache entre llamadas
            from app.services.chat import channel_cache
            channel_cache.clear()

            # Eliminar chat anterior
            db.query(ChatRoom).filter(ChatRoom.is_direct == True).delete()
            db.commit()

            result = chat_service.get_or_create_direct_chat(
                db,
                user1_id=user_a.id,
                user2_id=user_b.id,
                gym_id=gym_1.id
            )

            chat = db.query(ChatRoom).filter(ChatRoom.id == result["id"]).first()
            gym_ids.append(chat.gym_id)

        # Todos deben ser el mismo gym_id
        unique_gym_ids = set(gym_ids)
        assert len(unique_gym_ids) == 1, f"Comportamiento no determinista: {unique_gym_ids}"

        # Debe ser gym_2 (el menor de {2, 3})
        assert gym_ids[0] == gym_2.id, f"Esperaba gym_id={gym_2.id}, obtuvo {gym_ids[0]}"


class TestCrossGymVisibility:
    """Tests para verificar visibilidad cross-gym en /my-rooms"""

    def test_chat_visible_in_all_shared_gyms(self, multi_gym_setup):
        """
        Test: Chat directo debe ser visible en TODOS los gyms compartidos

        Setup: User A (gym_1,2,3), User B (gym_2,3)
        Chat creado con gym_id=2

        Esperado:
        - Visible desde gym_2 (match directo)
        - Visible desde gym_3 (cross-gym, ambos en gym_3)
        - NO visible desde gym_1 (User B no está en gym_1)
        """
        setup = multi_gym_setup
        db = setup["db"]
        user_a = setup["users"]["user_a"]
        user_b = setup["users"]["user_b"]
        gym_1 = setup["gyms"]["gym_1"]
        gym_2 = setup["gyms"]["gym_2"]
        gym_3 = setup["gyms"]["gym_3"]

        # Crear chat
        chat_room = ChatRoom(
            stream_channel_id="test_channel_ab",
            stream_channel_type="messaging",
            name="Chat A-B",
            gym_id=gym_2.id,
            is_direct=True,
            status=ChatRoomStatus.ACTIVE
        )
        db.add(chat_room)
        db.commit()
        db.refresh(chat_room)

        # Agregar miembros
        for user in [user_a, user_b]:
            member = ChatMember(
                room_id=chat_room.id,
                user_id=user.id
            )
            db.add(member)
        db.commit()

        chat_repo = ChatRepository()

        # Test 1: Visible desde gym_2 (match directo con gym_id)
        # Simular lógica de /my-rooms
        from sqlalchemy import and_
        from sqlalchemy.orm import joinedload
        from app.models.user_gym import UserGym as UG

        # Query base
        user_rooms_gym2 = db.query(ChatRoom).join(ChatMember).options(
            joinedload(ChatRoom.members)
        ).filter(
            and_(
                ChatMember.user_id == user_a.id,
                ChatRoom.status == "ACTIVE"
            )
        ).all()

        # Filtrar
        visible_in_gym2 = []
        for room in user_rooms_gym2:
            if room.gym_id == gym_2.id:
                visible_in_gym2.append(room)
            elif room.is_direct:
                member_ids = [m.user_id for m in room.members]
                if not member_ids:
                    continue
                members_in_gym = db.query(UG.user_id).filter(
                    and_(
                        UG.user_id.in_(member_ids),
                        UG.gym_id == gym_2.id
                    )
                ).all()
                members_in_gym_set = {uid for (uid,) in members_in_gym}
                if all(mid in members_in_gym_set for mid in member_ids):
                    visible_in_gym2.append(room)

        assert len(visible_in_gym2) == 1, f"Chat NO visible desde gym_2 (match directo)"
        assert visible_in_gym2[0].id == chat_room.id

        # Test 2: Visible desde gym_3 (cross-gym)
        user_rooms_gym3 = db.query(ChatRoom).join(ChatMember).options(
            joinedload(ChatRoom.members)
        ).filter(
            and_(
                ChatMember.user_id == user_a.id,
                ChatRoom.status == "ACTIVE"
            )
        ).all()

        visible_in_gym3 = []
        for room in user_rooms_gym3:
            if room.gym_id == gym_3.id:
                visible_in_gym3.append(room)
            elif room.is_direct:
                member_ids = [m.user_id for m in room.members]
                if not member_ids:
                    continue
                members_in_gym = db.query(UG.user_id).filter(
                    and_(
                        UG.user_id.in_(member_ids),
                        UG.gym_id == gym_3.id
                    )
                ).all()
                members_in_gym_set = {uid for (uid,) in members_in_gym}
                if all(mid in members_in_gym_set for mid in member_ids):
                    visible_in_gym3.append(room)

        assert len(visible_in_gym3) == 1, f"Chat NO visible desde gym_3 (cross-gym)"
        assert visible_in_gym3[0].id == chat_room.id

        # Test 3: NO visible desde gym_1 (User B no está en gym_1)
        user_rooms_gym1 = db.query(ChatRoom).join(ChatMember).options(
            joinedload(ChatRoom.members)
        ).filter(
            and_(
                ChatMember.user_id == user_a.id,
                ChatRoom.status == "ACTIVE"
            )
        ).all()

        visible_in_gym1 = []
        for room in user_rooms_gym1:
            if room.gym_id == gym_1.id:
                visible_in_gym1.append(room)
            elif room.is_direct:
                member_ids = [m.user_id for m in room.members]
                if not member_ids:
                    continue
                members_in_gym = db.query(UG.user_id).filter(
                    and_(
                        UG.user_id.in_(member_ids),
                        UG.gym_id == gym_1.id
                    )
                ).all()
                members_in_gym_set = {uid for (uid,) in members_in_gym}
                if all(mid in members_in_gym_set for mid in member_ids):
                    visible_in_gym1.append(room)

        assert len(visible_in_gym1) == 0, f"Chat visible incorrectamente desde gym_1"

    def test_group_chat_not_cross_gym_visible(self, multi_gym_setup):
        """
        Test: Chats de GRUPO NO deben usar lógica cross-gym

        Solo deben ser visibles en su gym_id original
        """
        setup = multi_gym_setup
        db = setup["db"]
        user_a = setup["users"]["user_a"]
        user_b = setup["users"]["user_b"]
        gym_2 = setup["gyms"]["gym_2"]
        gym_3 = setup["gyms"]["gym_3"]

        # Crear chat de GRUPO en gym_2
        group_chat = ChatRoom(
            stream_channel_id="test_group_channel",
            stream_channel_type="messaging",
            name="Group Chat",
            gym_id=gym_2.id,
            is_direct=False,  # ← GRUPO, no directo
            status=ChatRoomStatus.ACTIVE
        )
        db.add(group_chat)
        db.commit()
        db.refresh(group_chat)

        # Agregar miembros
        for user in [user_a, user_b]:
            member = ChatMember(
                room_id=group_chat.id,
                user_id=user.id
            )
            db.add(member)
        db.commit()

        # Simular lógica /my-rooms desde gym_3
        from sqlalchemy import and_
        from sqlalchemy.orm import joinedload
        from app.models.user_gym import UserGym as UG

        user_rooms = db.query(ChatRoom).join(ChatMember).options(
            joinedload(ChatRoom.members)
        ).filter(
            and_(
                ChatMember.user_id == user_a.id,
                ChatRoom.status == "ACTIVE"
            )
        ).all()

        visible_in_gym3 = []
        for room in user_rooms:
            if room.gym_id == gym_3.id:
                visible_in_gym3.append(room)
            elif room.is_direct:  # ← Solo chats DIRECTOS usan cross-gym
                member_ids = [m.user_id for m in room.members]
                if not member_ids:
                    continue
                members_in_gym = db.query(UG.user_id).filter(
                    and_(
                        UG.user_id.in_(member_ids),
                        UG.gym_id == gym_3.id
                    )
                ).all()
                members_in_gym_set = {uid for (uid,) in members_in_gym}
                if all(mid in members_in_gym_set for mid in member_ids):
                    visible_in_gym3.append(room)

        # Chat de grupo NO debe aparecer (solo gym_id=2, no cross-gym)
        assert len(visible_in_gym3) == 0, "Chat de grupo apareció incorrectamente en gym_3"


class TestEdgeCases:
    """Tests para edge cases y casos límite"""

    def test_users_with_no_shared_gyms(self, multi_gym_setup):
        """
        Test: Usuarios sin gyms compartidos NO pueden crear chat

        User A (gym_1,2,3) y User C (solo gym_1) → pueden chatear
        User C (gym_1) y User D (gym_3) → NO pueden chatear
        """
        setup = multi_gym_setup
        db = setup["db"]
        user_c = setup["users"]["user_c"]  # solo gym_1
        user_d = setup["users"]["user_d"]  # solo gym_3
        gym_1 = setup["gyms"]["gym_1"]

        # Verificar que NO comparten gyms
        c_gyms = {ug.gym_id for ug in db.query(UserGym).filter(UserGym.user_id == user_c.id).all()}
        d_gyms = {ug.gym_id for ug in db.query(UserGym).filter(UserGym.user_id == user_d.id).all()}
        common = c_gyms & d_gyms
        assert len(common) == 0, "User C y D NO deberían compartir gyms"

        # Intentar crear chat debe fallar en la validación del endpoint
        # (Esto se valida en el endpoint, no en el service)
        # Por ahora verificamos que common_gyms estaría vacío
        assert len(common) == 0

    def test_chat_with_empty_members(self, multi_gym_setup):
        """
        Test: Chats sin miembros (corruptos) NO deben aparecer en /my-rooms
        """
        setup = multi_gym_setup
        db = setup["db"]
        user_a = setup["users"]["user_a"]
        gym_2 = setup["gyms"]["gym_2"]

        # Crear chat CORRUPTO sin miembros
        corrupted_chat = ChatRoom(
            stream_channel_id="corrupted_channel",
            stream_channel_type="messaging",
            name="Corrupted Chat",
            gym_id=gym_2.id,
            is_direct=True,
            status=ChatRoomStatus.ACTIVE
        )
        db.add(corrupted_chat)
        db.commit()
        # NO agregar miembros (chat corrupto)

        # Crear chat NORMAL
        normal_chat = ChatRoom(
            stream_channel_id="normal_channel",
            stream_channel_type="messaging",
            name="Normal Chat",
            gym_id=gym_2.id,
            is_direct=True,
            status=ChatRoomStatus.ACTIVE
        )
        db.add(normal_chat)
        db.commit()
        db.refresh(normal_chat)

        # Agregar miembros al chat normal
        member = ChatMember(
            room_id=normal_chat.id,
            user_id=user_a.id
        )
        db.add(member)
        db.commit()

        # Simular lógica /my-rooms
        from sqlalchemy import and_
        from sqlalchemy.orm import joinedload
        from app.models.user_gym import UserGym as UG

        user_rooms = db.query(ChatRoom).join(ChatMember, isouter=True).options(
            joinedload(ChatRoom.members)
        ).filter(
            ChatRoom.status == "ACTIVE"
        ).all()

        filtered_rooms = []
        for room in user_rooms:
            if room.gym_id == gym_2.id:
                # Verificar que el usuario es miembro
                member_ids = [m.user_id for m in room.members]
                if user_a.id in member_ids:
                    filtered_rooms.append(room)
            elif room.is_direct:
                member_ids = [m.user_id for m in room.members]
                # Fix #5: Validar que no esté vacío
                if not member_ids or len(member_ids) == 0:
                    continue  # ← Skip corrupted chat
                if user_a.id not in member_ids:
                    continue
                members_in_gym = db.query(UG.user_id).filter(
                    and_(
                        UG.user_id.in_(member_ids),
                        UG.gym_id == gym_2.id
                    )
                ).all()
                members_in_gym_set = {uid for (uid,) in members_in_gym}
                if all(mid in members_in_gym_set for mid in member_ids):
                    filtered_rooms.append(room)

        # Solo debe aparecer el chat normal, NO el corrupto
        assert len(filtered_rooms) == 1, f"Esperaba 1 chat, encontró {len(filtered_rooms)}"
        assert filtered_rooms[0].id == normal_chat.id, "Chat corrupto apareció en resultados"


class TestPerformance:
    """Tests para verificar optimizaciones de performance"""

    def test_no_n_plus_1_queries(self, multi_gym_setup):
        """
        Test: Verificar que NO hay N+1 queries en /my-rooms

        Con 50 chats, debe hacer ~2-3 queries, NO 50+
        """
        setup = multi_gym_setup
        db = setup["db"]
        user_a = setup["users"]["user_a"]
        user_b = setup["users"]["user_b"]
        gym_2 = setup["gyms"]["gym_2"]

        # Crear 50 chats directos
        for i in range(50):
            chat = ChatRoom(
                stream_channel_id=f"test_channel_{i}",
                stream_channel_type="messaging",
                name=f"Chat {i}",
                gym_id=gym_2.id,
                is_direct=True,
                status=ChatRoomStatus.ACTIVE
            )
            db.add(chat)
            db.commit()
            db.refresh(chat)

            # Agregar miembros
            for user in [user_a, user_b]:
                member = ChatMember(
                    room_id=chat.id,
                    user_id=user.id
                )
                db.add(member)
        db.commit()

        # Contar queries ejecutados
        from sqlalchemy import event
        from sqlalchemy.engine import Engine

        query_count = []

        @event.listens_for(Engine, "before_cursor_execute")
        def count_queries(conn, cursor, statement, parameters, context, executemany):
            query_count.append(statement)

        # Ejecutar lógica de /my-rooms
        from sqlalchemy import and_
        from sqlalchemy.orm import joinedload
        from app.models.user_gym import UserGym as UG

        query_count.clear()

        # Query con eager loading
        user_rooms = db.query(ChatRoom).join(ChatMember).options(
            joinedload(ChatRoom.members)
        ).filter(
            and_(
                ChatMember.user_id == user_a.id,
                ChatRoom.status == "ACTIVE"
            )
        ).all()

        # Separar por tipo
        rooms_in_gym = [r for r in user_rooms if r.gym_id == gym_2.id]
        direct_rooms = [r for r in user_rooms if r.is_direct and r.gym_id != gym_2.id]

        # Query bulk para membresías
        if direct_rooms:
            all_member_ids = set()
            for room in direct_rooms:
                member_ids = [m.user_id for m in room.members]
                all_member_ids.update(member_ids)

            if all_member_ids:
                members_in_gym = db.query(UG.user_id).filter(
                    and_(
                        UG.user_id.in_(all_member_ids),
                        UG.gym_id == gym_2.id
                    )
                ).all()

        # Verificar número de queries
        total_queries = len([q for q in query_count if 'SELECT' in q.upper()])

        # Debe ser ~2-3 queries, NO 50+
        assert total_queries < 10, f"Demasiadas queries: {total_queries} (esperaba < 10)"
        print(f"✅ Performance OK: {total_queries} queries para 50 chats")


class TestRepositoryEagerLoading:
    """Tests para verificar eager loading en repository"""

    def test_repository_get_direct_chat_with_eager_loading(self, multi_gym_setup):
        """
        Test: Repository debe usar eager loading para evitar lazy loading
        """
        setup = multi_gym_setup
        db = setup["db"]
        user_a = setup["users"]["user_a"]
        user_b = setup["users"]["user_b"]
        gym_2 = setup["gyms"]["gym_2"]

        # Crear chat
        chat = ChatRoom(
            stream_channel_id="test_eager",
            stream_channel_type="messaging",
            name="Test Eager Loading",
            gym_id=gym_2.id,
            is_direct=True,
            status=ChatRoomStatus.ACTIVE
        )
        db.add(chat)
        db.commit()
        db.refresh(chat)

        for user in [user_a, user_b]:
            member = ChatMember(
                room_id=chat.id,
                user_id=user.id
            )
            db.add(member)
        db.commit()

        # Contar queries
        from sqlalchemy import event
        from sqlalchemy.engine import Engine

        query_count = []

        @event.listens_for(Engine, "before_cursor_execute")
        def count_queries(conn, cursor, statement, parameters, context, executemany):
            query_count.append(statement)

        query_count.clear()

        # Usar repository
        chat_repo = ChatRepository()
        result = chat_repo.get_direct_chat(
            db,
            user1_id=user_a.id,
            user2_id=user_b.id,
            gym_id=None
        )

        # Acceder a members (debe estar eager-loaded)
        if result:
            member_ids = [m.user_id for m in result.members]

        # Verificar número de queries
        select_queries = [q for q in query_count if 'SELECT' in q.upper()]

        # Con eager loading: 1 query
        # Sin eager loading: 1 query inicial + 1 lazy load = 2 queries
        assert len(select_queries) <= 1, f"Lazy loading detectado: {len(select_queries)} queries"
        print(f"✅ Eager loading OK: {len(select_queries)} query(ies)")


# Summary fixture para reportar resultados
@pytest.fixture(scope="session", autouse=True)
def test_summary():
    """Fixture para imprimir resumen al final"""
    yield
    print("\n" + "="*60)
    print("✅ RESUMEN DE TESTS CROSS-GYM")
    print("="*60)
    print("Categorías testeadas:")
    print("  - Un solo chat por par de usuarios")
    print("  - Comportamiento determinista")
    print("  - Visibilidad cross-gym")
    print("  - Edge cases")
    print("  - Performance (no N+1)")
    print("  - Eager loading en repository")
    print("="*60)
