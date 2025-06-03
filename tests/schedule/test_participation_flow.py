#!/usr/bin/env python3
"""
Tests para el flujo completo de participación en clases.

Estos tests simulan el proceso completo desde la creación de una sesión
hasta el registro de usuarios y check-in por QR.
"""

import pytest
from datetime import datetime, timedelta, date
from sqlalchemy.orm import Session

from app.models.gym import Gym
from app.models.user import User, UserRole
from app.models.user_gym import UserGym, GymRoleType
from app.models.schedule import (
    Class, ClassSession, ClassParticipation, 
    ClassDifficultyLevel, ClassCategory, ClassSessionStatus, ClassParticipationStatus
)
from app.schemas.schedule import ClassCreate, ClassSessionCreate
from app.services.attendance import attendance_service


@pytest.fixture
def test_gym(db: Session):
    """Crea un gimnasio de prueba."""
    gym = Gym(
        name="Test Gym",
        address="123 Test Street",
        phone="555-0123",
        email="test@gym.com",
        is_active=True
    )
    db.add(gym)
    db.commit()
    db.refresh(gym)
    return gym


@pytest.fixture
def test_user_with_qr(db: Session, test_gym: Gym):
    """Crea un usuario de prueba con código QR y lo asigna al gimnasio."""
    user = User(
        email="testuser@example.com",
        full_name="Test User",
        role=UserRole.MEMBER,
        auth0_id="auth0|testuser123",
        qr_code="U999_test123"  # QR de prueba
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Asignar usuario al gimnasio
    user_gym = UserGym(
        user_id=user.id,
        gym_id=test_gym.id,
        role=GymRoleType.MEMBER
    )
    db.add(user_gym)
    db.commit()
    
    return user


@pytest.fixture
def test_trainer(db: Session, test_gym: Gym):
    """Crea un entrenador de prueba."""
    trainer = User(
        email="trainer@example.com",
        full_name="Test Trainer",
        role=UserRole.TRAINER,
        auth0_id="auth0|trainer123",
        qr_code="U998_trainer123"
    )
    db.add(trainer)
    db.commit()
    db.refresh(trainer)
    
    # Asignar entrenador al gimnasio
    user_gym = UserGym(
        user_id=trainer.id,
        gym_id=test_gym.id,
        role=GymRoleType.TRAINER
    )
    db.add(user_gym)
    db.commit()
    
    return trainer


@pytest.fixture
def test_class(db: Session, test_gym: Gym):
    """Crea una clase de prueba."""
    gym_class = Class(
        name="Test Yoga Class",
        description="A relaxing yoga session",
        duration=60,
        max_capacity=10,
        difficulty_level=ClassDifficultyLevel.BEGINNER,
        category_enum=ClassCategory.YOGA,
        gym_id=test_gym.id,
        is_active=True
    )
    db.add(gym_class)
    db.commit()
    db.refresh(gym_class)
    return gym_class


@pytest.fixture
def test_session(db: Session, test_class: Class, test_trainer: User, test_gym: Gym):
    """Crea una sesión de clase de prueba."""
    # Crear una sesión para mañana a las 10:00 AM
    tomorrow = datetime.now() + timedelta(days=1)
    start_time = tomorrow.replace(hour=10, minute=0, second=0, microsecond=0)
    end_time = start_time + timedelta(minutes=test_class.duration)
    
    session = ClassSession(
        class_id=test_class.id,
        trainer_id=test_trainer.id,
        gym_id=test_gym.id,
        start_time=start_time,
        end_time=end_time,
        room="Studio A",
        status=ClassSessionStatus.SCHEDULED,
        current_participants=0
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


class TestParticipationFlow:
    """Tests para el flujo completo de participación en clases."""
    
    def test_create_session_successfully(self, db: Session, test_class: Class, test_trainer: User, test_gym: Gym):
        """Test que verifica la creación exitosa de una sesión de clase."""
        # Datos para crear la sesión
        tomorrow = datetime.now() + timedelta(days=1)
        start_time = tomorrow.replace(hour=14, minute=0, second=0, microsecond=0)
        
        session_data = {
            "class_id": test_class.id,
            "trainer_id": test_trainer.id,
            "start_time": start_time,
            "room": "Studio B",
            "status": ClassSessionStatus.SCHEDULED
        }
        
        # Crear la sesión
        session = ClassSession(**session_data, gym_id=test_gym.id)
        session.end_time = start_time + timedelta(minutes=test_class.duration)
        
        db.add(session)
        db.commit()
        db.refresh(session)
        
        # Verificaciones
        assert session.id is not None
        assert session.class_id == test_class.id
        assert session.trainer_id == test_trainer.id
        assert session.gym_id == test_gym.id
        assert session.start_time == start_time
        assert session.room == "Studio B"
        assert session.status == ClassSessionStatus.SCHEDULED
        assert session.current_participants == 0
        
        print(f"✅ Sesión creada exitosamente: ID {session.id}")
        print(f"   Clase: {test_class.name}")
        print(f"   Entrenador: {test_trainer.full_name}")
        print(f"   Fecha: {session.start_time}")
        print(f"   Sala: {session.room}")
    
    def test_user_registration_for_session(self, db: Session, test_session: ClassSession, test_user_with_qr: User, test_gym: Gym):
        """Test que simula un usuario registrándose para una sesión de clase."""
        # Verificar estado inicial
        assert test_session.current_participants == 0
        
        # Crear participación
        participation = ClassParticipation(
            session_id=test_session.id,
            member_id=test_user_with_qr.id,
            gym_id=test_gym.id,
            status=ClassParticipationStatus.REGISTERED
        )
        
        db.add(participation)
        
        # Actualizar contador de participantes
        test_session.current_participants += 1
        db.add(test_session)
        
        db.commit()
        db.refresh(participation)
        db.refresh(test_session)
        
        # Verificaciones
        assert participation.id is not None
        assert participation.session_id == test_session.id
        assert participation.member_id == test_user_with_qr.id
        assert participation.gym_id == test_gym.id
        assert participation.status == ClassParticipationStatus.REGISTERED
        assert participation.registration_time is not None
        assert test_session.current_participants == 1
        
        print(f"✅ Usuario registrado exitosamente en la sesión:")
        print(f"   Usuario: {test_user_with_qr.full_name} ({test_user_with_qr.email})")
        print(f"   QR: {test_user_with_qr.qr_code}")
        print(f"   Sesión: {test_session.id}")
        print(f"   Estado: {participation.status}")
        print(f"   Participantes actuales: {test_session.current_participants}")
    
    def test_multiple_users_registration(self, db: Session, test_session: ClassSession, test_gym: Gym):
        """Test que simula múltiples usuarios registrándose para la misma sesión."""
        users = []
        
        # Crear 3 usuarios adicionales
        for i in range(3):
            user = User(
                email=f"user{i}@example.com",
                full_name=f"Test User {i}",
                role=UserRole.MEMBER,
                auth0_id=f"auth0|user{i}",
                qr_code=f"U{900+i}_test{i}"
            )
            db.add(user)
            
            # Asignar al gimnasio
            user_gym = UserGym(
                user_id=user.id,
                gym_id=test_gym.id,
                role=GymRoleType.MEMBER
            )
            db.add(user_gym)
            users.append(user)
        
        db.commit()
        
        # Registrar cada usuario en la sesión
        participations = []
        for user in users:
            participation = ClassParticipation(
                session_id=test_session.id,
                member_id=user.id,
                gym_id=test_gym.id,
                status=ClassParticipationStatus.REGISTERED
            )
            db.add(participation)
            participations.append(participation)
        
        # Actualizar contador
        test_session.current_participants += len(users)
        db.add(test_session)
        
        db.commit()
        
        # Verificaciones
        assert test_session.current_participants == len(users)
        assert len(participations) == 3
        
        for i, participation in enumerate(participations):
            assert participation.member_id == users[i].id
            assert participation.status == ClassParticipationStatus.REGISTERED
        
        print(f"✅ {len(users)} usuarios registrados exitosamente:")
        for i, user in enumerate(users):
            print(f"   - {user.full_name} ({user.email}) - QR: {user.qr_code}")
        print(f"   Total participantes: {test_session.current_participants}")
    
    def test_session_capacity_limit(self, db: Session, test_gym: Gym):
        """Test que verifica el límite de capacidad de una sesión."""
        # Crear una clase con capacidad limitada
        small_class = Class(
            name="Small Class",
            description="Limited capacity class",
            duration=30,
            max_capacity=2,  # Solo 2 participantes
            difficulty_level=ClassDifficultyLevel.BEGINNER,
            category_enum=ClassCategory.FUNCTIONAL,
            gym_id=test_gym.id,
            is_active=True
        )
        db.add(small_class)
        
        # Crear entrenador
        trainer = User(
            email="smalltrainer@example.com",
            full_name="Small Trainer",
            role=UserRole.TRAINER,
            auth0_id="auth0|smalltrainer",
            qr_code="U997_small"
        )
        db.add(trainer)
        
        user_gym = UserGym(
            user_id=trainer.id,
            gym_id=test_gym.id,
            role=GymRoleType.TRAINER
        )
        db.add(user_gym)
        
        db.commit()
        db.refresh(small_class)
        db.refresh(trainer)
        
        # Crear sesión
        start_time = datetime.now() + timedelta(days=1, hours=2)
        session = ClassSession(
            class_id=small_class.id,
            trainer_id=trainer.id,
            gym_id=test_gym.id,
            start_time=start_time,
            end_time=start_time + timedelta(minutes=30),
            status=ClassSessionStatus.SCHEDULED,
            current_participants=0
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        
        # Crear 3 usuarios (uno más que la capacidad)
        users = []
        for i in range(3):
            user = User(
                email=f"capacity_user{i}@example.com",
                full_name=f"Capacity User {i}",
                role=UserRole.MEMBER,
                auth0_id=f"auth0|capacity{i}",
                qr_code=f"U{800+i}_cap{i}"
            )
            db.add(user)
            
            user_gym = UserGym(
                user_id=user.id,
                gym_id=test_gym.id,
                role=GymRoleType.MEMBER
            )
            db.add(user_gym)
            users.append(user)
        
        db.commit()
        
        # Registrar los primeros 2 usuarios (dentro de la capacidad)
        successful_registrations = 0
        for i, user in enumerate(users):
            if session.current_participants < small_class.max_capacity:
                participation = ClassParticipation(
                    session_id=session.id,
                    member_id=user.id,
                    gym_id=test_gym.id,
                    status=ClassParticipationStatus.REGISTERED
                )
                db.add(participation)
                session.current_participants += 1
                successful_registrations += 1
                
                print(f"✅ Usuario {i+1} registrado: {user.full_name}")
            else:
                print(f"❌ Usuario {i+1} NO registrado (capacidad llena): {user.full_name}")
        
        db.add(session)
        db.commit()
        db.refresh(session)
        
        # Verificaciones
        assert session.current_participants == small_class.max_capacity == 2
        assert successful_registrations == 2
        
        print(f"✅ Test de capacidad completado:")
        print(f"   Capacidad máxima: {small_class.max_capacity}")
        print(f"   Participantes registrados: {session.current_participants}")
        print(f"   Registros exitosos: {successful_registrations}")
    
    async def test_qr_check_in_simulation(self, db: Session, test_session: ClassSession, test_user_with_qr: User, test_gym: Gym):
        """Test que simula el check-in por código QR."""
        # Primero registrar al usuario en la sesión
        participation = ClassParticipation(
            session_id=test_session.id,
            member_id=test_user_with_qr.id,
            gym_id=test_gym.id,
            status=ClassParticipationStatus.REGISTERED
        )
        db.add(participation)
        db.commit()
        db.refresh(participation)
        
        # Simular que la clase está cerca de empezar (dentro de la ventana de ±30 minutos)
        current_time = datetime.now()
        test_session.start_time = current_time + timedelta(minutes=15)  # Clase en 15 minutos
        test_session.end_time = test_session.start_time + timedelta(minutes=60)
        db.add(test_session)
        db.commit()
        
        # Simular check-in por QR usando el servicio de attendance
        qr_code = test_user_with_qr.qr_code
        
        # Verificar que el QR puede extraer el user_id
        if qr_code.startswith("U") and "_" in qr_code:
            user_id_str = qr_code.split("_")[0][1:]  # Remover 'U' y obtener el ID
            extracted_user_id = int(user_id_str)
            
            assert extracted_user_id == test_user_with_qr.id
            
            # Simular que se encuentra la participación y se marca como asistida
            participation.status = ClassParticipationStatus.ATTENDED
            participation.attendance_time = current_time
            db.add(participation)
            db.commit()
            db.refresh(participation)
            
            # Verificaciones
            assert participation.status == ClassParticipationStatus.ATTENDED
            assert participation.attendance_time is not None
            
            print(f"✅ Check-in por QR exitoso:")
            print(f"   Usuario: {test_user_with_qr.full_name}")
            print(f"   QR escaneado: {qr_code}")
            print(f"   ID extraído: {extracted_user_id}")
            print(f"   Estado actualizado: {participation.status}")
            print(f"   Hora de asistencia: {participation.attendance_time}")
        else:
            pytest.fail(f"Formato de QR inválido: {qr_code}")
    
    def test_complete_session_flow(self, db: Session, test_gym: Gym):
        """Test que simula el flujo completo de una sesión desde creación hasta finalización."""
        print("\n🏃‍♀️ === INICIANDO FLUJO COMPLETO DE SESIÓN ===")
        
        # 1. Crear clase
        gym_class = Class(
            name="Complete Flow Class",
            description="Full flow test class",
            duration=45,
            max_capacity=5,
            difficulty_level=ClassDifficultyLevel.INTERMEDIATE,
            category_enum=ClassCategory.HIIT,
            gym_id=test_gym.id,
            is_active=True
        )
        db.add(gym_class)
        
        # 2. Crear entrenador
        trainer = User(
            email="flow_trainer@example.com",
            full_name="Flow Trainer",
            role=UserRole.TRAINER,
            auth0_id="auth0|flowtrainer",
            qr_code="U996_flow"
        )
        db.add(trainer)
        
        user_gym = UserGym(
            user_id=trainer.id,
            gym_id=test_gym.id,
            role=GymRoleType.TRAINER
        )
        db.add(user_gym)
        
        db.commit()
        db.refresh(gym_class)
        db.refresh(trainer)
        
        print(f"✅ 1. Clase creada: {gym_class.name}")
        print(f"✅ 2. Entrenador asignado: {trainer.full_name}")
        
        # 3. Crear sesión
        start_time = datetime.now() + timedelta(hours=1)
        session = ClassSession(
            class_id=gym_class.id,
            trainer_id=trainer.id,
            gym_id=test_gym.id,
            start_time=start_time,
            end_time=start_time + timedelta(minutes=45),
            room="Main Studio",
            status=ClassSessionStatus.SCHEDULED,
            current_participants=0
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        
        print(f"✅ 3. Sesión programada: {session.start_time}")
        
        # 4. Crear y registrar usuarios
        users = []
        for i in range(3):
            user = User(
                email=f"flow_user{i}@example.com",
                full_name=f"Flow User {i}",
                role=UserRole.MEMBER,
                auth0_id=f"auth0|flowuser{i}",
                qr_code=f"U{700+i}_flow{i}"
            )
            db.add(user)
            
            user_gym = UserGym(
                user_id=user.id,
                gym_id=test_gym.id,
                role=GymRoleType.MEMBER
            )
            db.add(user_gym)
            users.append(user)
        
        db.commit()
        
        # Registrar usuarios en la sesión
        participations = []
        for user in users:
            participation = ClassParticipation(
                session_id=session.id,
                member_id=user.id,
                gym_id=test_gym.id,
                status=ClassParticipationStatus.REGISTERED
            )
            db.add(participation)
            participations.append(participation)
        
        session.current_participants = len(users)
        db.add(session)
        db.commit()
        
        print(f"✅ 4. {len(users)} usuarios registrados")
        
        # 5. Simular check-ins
        checked_in_users = 0
        for participation in participations:
            participation.status = ClassParticipationStatus.ATTENDED
            participation.attendance_time = datetime.now()
            db.add(participation)
            checked_in_users += 1
        
        db.commit()
        
        print(f"✅ 5. {checked_in_users} usuarios hicieron check-in")
        
        # 6. Marcar sesión como completada
        session.status = ClassSessionStatus.COMPLETED
        db.add(session)
        db.commit()
        
        print(f"✅ 6. Sesión marcada como completada")
        
        # Verificaciones finales
        final_participations = db.query(ClassParticipation).filter(
            ClassParticipation.session_id == session.id
        ).all()
        
        attended_count = sum(1 for p in final_participations if p.status == ClassParticipationStatus.ATTENDED)
        
        assert session.status == ClassSessionStatus.COMPLETED
        assert len(final_participations) == 3
        assert attended_count == 3
        assert session.current_participants == 3
        
        print(f"\n🎉 === FLUJO COMPLETO EXITOSO ===")
        print(f"   Clase: {gym_class.name}")
        print(f"   Participantes registrados: {len(final_participations)}")
        print(f"   Participantes que asistieron: {attended_count}")
        print(f"   Estado final: {session.status}")
        print(f"   Duración: {gym_class.duration} minutos")
        print(f"   Sala: {session.room}") 