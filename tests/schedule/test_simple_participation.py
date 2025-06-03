#!/usr/bin/env python3
"""
Test simple de participación en clases sin dependencias complejas.
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.sql import func

# Crear una base temporal para los tests
TestBase = declarative_base()

# Enums simplificados para el test
from app.models.schedule import ClassDifficultyLevel, ClassCategory, ClassSessionStatus, ClassParticipationStatus
from app.models.user import UserRole
from app.models.user_gym import GymRoleType

# Modelos simplificados para tests
class TestGym(TestBase):
    __tablename__ = "test_gyms"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    address = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class TestUser(TestBase):
    __tablename__ = "test_users"
    
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    full_name = Column(String)
    role = Column(Enum(UserRole), default=UserRole.MEMBER)
    auth0_id = Column(String, unique=True)
    qr_code = Column(String, unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class TestUserGym(TestBase):
    __tablename__ = "test_user_gym"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("test_users.id"), nullable=False)
    gym_id = Column(Integer, ForeignKey("test_gyms.id"), nullable=False)
    role = Column(Enum(GymRoleType), default=GymRoleType.MEMBER)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class TestClass(TestBase):
    __tablename__ = "test_classes"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    duration = Column(Integer, nullable=False)
    max_capacity = Column(Integer, nullable=False)
    difficulty_level = Column(Enum(ClassDifficultyLevel), nullable=False)
    category_enum = Column(Enum(ClassCategory))
    gym_id = Column(Integer, ForeignKey("test_gyms.id"), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class TestClassSession(TestBase):
    __tablename__ = "test_class_sessions"
    
    id = Column(Integer, primary_key=True)
    class_id = Column(Integer, ForeignKey("test_classes.id"), nullable=False)
    trainer_id = Column(Integer, ForeignKey("test_users.id"), nullable=False)
    gym_id = Column(Integer, ForeignKey("test_gyms.id"), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    room = Column(String)
    status = Column(Enum(ClassSessionStatus), default=ClassSessionStatus.SCHEDULED)
    current_participants = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class TestClassParticipation(TestBase):
    __tablename__ = "test_class_participations"
    
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("test_class_sessions.id"), nullable=False)
    member_id = Column(Integer, ForeignKey("test_users.id"), nullable=False)
    gym_id = Column(Integer, ForeignKey("test_gyms.id"), nullable=False)
    status = Column(Enum(ClassParticipationStatus), default=ClassParticipationStatus.REGISTERED)
    registration_time = Column(DateTime(timezone=True), server_default=func.now())
    attendance_time = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# Configuración de test independiente
@pytest.fixture(scope="function")
def test_db():
    """Crear una base de datos de test independiente."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    TestBase.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()

class TestSimpleParticipation:
    """Tests simples de participación sin dependencias externas."""
    
    def test_create_gym_and_user(self, test_db: Session):
        """Test básico: crear gimnasio y usuario."""
        # Crear gimnasio
        gym = TestGym(
            name="Test Gym",
            address="123 Test Street",
            is_active=True
        )
        test_db.add(gym)
        test_db.commit()
        test_db.refresh(gym)
        
        # Crear usuario
        user = TestUser(
            email="test@example.com",
            full_name="Test User",
            role=UserRole.MEMBER,
            auth0_id="auth0|test123",
            qr_code="U1_test123"
        )
        test_db.add(user)
        test_db.commit()
        test_db.refresh(user)
        
        # Asignar usuario al gimnasio
        user_gym = TestUserGym(
            user_id=user.id,
            gym_id=gym.id,
            role=GymRoleType.MEMBER
        )
        test_db.add(user_gym)
        test_db.commit()
        
        # Verificaciones
        assert gym.id is not None
        assert gym.name == "Test Gym"
        assert user.id is not None
        assert user.email == "test@example.com"
        assert user.qr_code == "U1_test123"
        assert user_gym.user_id == user.id
        assert user_gym.gym_id == gym.id
        
        print(f"✅ Gimnasio creado: {gym.name} (ID: {gym.id})")
        print(f"✅ Usuario creado: {user.full_name} ({user.email})")
        print(f"✅ QR del usuario: {user.qr_code}")
        print(f"✅ Usuario asignado al gimnasio")
    
    def test_create_session_and_register_user(self, test_db: Session):
        """Test completo: crear sesión y registrar usuario."""
        # 1. Crear gimnasio
        gym = TestGym(name="Test Gym", address="123 Test Street")
        test_db.add(gym)
        test_db.commit()
        test_db.refresh(gym)
        
        # 2. Crear entrenador
        trainer = TestUser(
            email="trainer@example.com",
            full_name="Test Trainer",
            role=UserRole.TRAINER,
            auth0_id="auth0|trainer123",
            qr_code="U2_trainer"
        )
        test_db.add(trainer)
        
        # 3. Crear miembro
        member = TestUser(
            email="member@example.com",
            full_name="Test Member",
            role=UserRole.MEMBER,
            auth0_id="auth0|member123",
            qr_code="U3_member"
        )
        test_db.add(member)
        test_db.commit()
        test_db.refresh(trainer)
        test_db.refresh(member)
        
        # 4. Asignar ambos al gimnasio
        trainer_gym = TestUserGym(user_id=trainer.id, gym_id=gym.id, role=GymRoleType.TRAINER)
        member_gym = TestUserGym(user_id=member.id, gym_id=gym.id, role=GymRoleType.MEMBER)
        test_db.add(trainer_gym)
        test_db.add(member_gym)
        test_db.commit()
        
        # 5. Crear clase
        gym_class = TestClass(
            name="Test Yoga",
            description="Relaxing yoga session",
            duration=60,
            max_capacity=10,
            difficulty_level=ClassDifficultyLevel.BEGINNER,
            category_enum=ClassCategory.YOGA,
            gym_id=gym.id
        )
        test_db.add(gym_class)
        test_db.commit()
        test_db.refresh(gym_class)
        
        # 6. Crear sesión de clase
        start_time = datetime.now() + timedelta(hours=1)
        end_time = start_time + timedelta(minutes=60)
        
        session = TestClassSession(
            class_id=gym_class.id,
            trainer_id=trainer.id,
            gym_id=gym.id,
            start_time=start_time,
            end_time=end_time,
            room="Studio A",
            status=ClassSessionStatus.SCHEDULED,
            current_participants=0
        )
        test_db.add(session)
        test_db.commit()
        test_db.refresh(session)
        
        # 7. Registrar miembro en la sesión
        participation = TestClassParticipation(
            session_id=session.id,
            member_id=member.id,
            gym_id=gym.id,
            status=ClassParticipationStatus.REGISTERED
        )
        test_db.add(participation)
        
        # 8. Actualizar contador de participantes
        session.current_participants += 1
        test_db.add(session)
        test_db.commit()
        test_db.refresh(participation)
        test_db.refresh(session)
        
        # Verificaciones
        assert gym.id is not None
        assert trainer.id is not None
        assert member.id is not None
        assert gym_class.id is not None
        assert session.id is not None
        assert participation.id is not None
        
        assert session.class_id == gym_class.id
        assert session.trainer_id == trainer.id
        assert session.gym_id == gym.id
        assert session.current_participants == 1
        
        assert participation.session_id == session.id
        assert participation.member_id == member.id
        assert participation.gym_id == gym.id
        assert participation.status == ClassParticipationStatus.REGISTERED
        
        print(f"\n🏃‍♀️ === FLUJO DE PARTICIPACIÓN EXITOSO ===")
        print(f"✅ Gimnasio: {gym.name}")
        print(f"✅ Entrenador: {trainer.full_name} ({trainer.email})")
        print(f"✅ Miembro: {member.full_name} ({member.email}) - QR: {member.qr_code}")
        print(f"✅ Clase: {gym_class.name} ({gym_class.duration} min)")
        print(f"✅ Sesión: {session.start_time} en {session.room}")
        print(f"✅ Participantes registrados: {session.current_participants}")
        print(f"✅ Estado de participación: {participation.status}")
    
    def test_qr_check_in_simulation(self, test_db: Session):
        """Test de simulación de check-in por QR."""
        # Configuración inicial (reutilizando código del test anterior)
        gym = TestGym(name="QR Test Gym")
        test_db.add(gym)
        
        member = TestUser(
            email="qr_member@example.com",
            full_name="QR Member",
            role=UserRole.MEMBER
            # QR se generará después de obtener el ID
        )
        test_db.add(member)
        
        trainer = TestUser(
            email="qr_trainer@example.com",
            full_name="QR Trainer", 
            role=UserRole.TRAINER
        )
        test_db.add(trainer)
        
        test_db.commit()
        test_db.refresh(gym)
        test_db.refresh(member)
        test_db.refresh(trainer)
        
        # Generar QR con el ID real del usuario
        member.qr_code = f"U{member.id}_qrmember"
        test_db.add(member)
        test_db.commit()
        
        # Asignar al gimnasio
        member_gym = TestUserGym(user_id=member.id, gym_id=gym.id, role=GymRoleType.MEMBER)
        trainer_gym = TestUserGym(user_id=trainer.id, gym_id=gym.id, role=GymRoleType.TRAINER)
        test_db.add(member_gym)
        test_db.add(trainer_gym)
        
        # Crear clase y sesión
        gym_class = TestClass(
            name="QR Test Class",
            duration=45,
            max_capacity=5,
            difficulty_level=ClassDifficultyLevel.INTERMEDIATE,
            category_enum=ClassCategory.HIIT,
            gym_id=gym.id
        )
        test_db.add(gym_class)
        test_db.commit()
        test_db.refresh(gym_class)
        
        # Crear sesión próxima (dentro de ventana de check-in)
        current_time = datetime.now()
        start_time = current_time + timedelta(minutes=15)  # Clase en 15 minutos
        
        session = TestClassSession(
            class_id=gym_class.id,
            trainer_id=trainer.id,
            gym_id=gym.id,
            start_time=start_time,
            end_time=start_time + timedelta(minutes=45)
        )
        test_db.add(session)
        test_db.commit()
        test_db.refresh(session)
        
        # Registrar usuario en la sesión
        participation = TestClassParticipation(
            session_id=session.id,
            member_id=member.id,
            gym_id=gym.id,
            status=ClassParticipationStatus.REGISTERED
        )
        test_db.add(participation)
        test_db.commit()
        test_db.refresh(participation)
        
        # Simular check-in por QR
        qr_code = member.qr_code
        
        # Extraer user_id del QR
        assert qr_code.startswith("U") and "_" in qr_code
        user_id_str = qr_code.split("_")[0][1:]  # Remover 'U'
        extracted_user_id = int(user_id_str)
        
        # Verificar que el ID extraído coincide
        assert extracted_user_id == member.id
        
        # Simular check-in (marcar como asistido)
        participation.status = ClassParticipationStatus.ATTENDED
        participation.attendance_time = current_time
        test_db.add(participation)
        test_db.commit()
        test_db.refresh(participation)
        
        # Verificaciones finales
        assert participation.status == ClassParticipationStatus.ATTENDED
        assert participation.attendance_time is not None
        
        print(f"\n📱 === CHECK-IN POR QR EXITOSO ===")
        print(f"✅ Miembro: {member.full_name}")
        print(f"✅ QR escaneado: {qr_code}")
        print(f"✅ User ID extraído: {extracted_user_id}")
        print(f"✅ Estado actualizado: {participation.status}")
        print(f"✅ Hora de asistencia: {participation.attendance_time}")
        print(f"✅ Clase: {gym_class.name}")
        print(f"✅ Sesión: {session.start_time}")
    
    def test_multiple_users_capacity_limit(self, test_db: Session):
        """Test de múltiples usuarios y límite de capacidad."""
        # Crear gimnasio
        gym = TestGym(name="Capacity Test Gym")
        test_db.add(gym)
        test_db.commit()
        test_db.refresh(gym)
        
        # Crear entrenador
        trainer = TestUser(
            email="capacity_trainer@example.com",
            full_name="Capacity Trainer",
            role=UserRole.TRAINER
        )
        test_db.add(trainer)
        test_db.commit()
        test_db.refresh(trainer)
        
        trainer_gym = TestUserGym(user_id=trainer.id, gym_id=gym.id, role=GymRoleType.TRAINER)
        test_db.add(trainer_gym)
        
        # Crear clase con capacidad limitada
        small_class = TestClass(
            name="Small Capacity Class",
            duration=30,
            max_capacity=2,  # Solo 2 participantes
            difficulty_level=ClassDifficultyLevel.BEGINNER,
            category_enum=ClassCategory.FUNCTIONAL,
            gym_id=gym.id
        )
        test_db.add(small_class)
        test_db.commit()
        test_db.refresh(small_class)
        
        # Crear sesión
        start_time = datetime.now() + timedelta(hours=2)
        session = TestClassSession(
            class_id=small_class.id,
            trainer_id=trainer.id,
            gym_id=gym.id,
            start_time=start_time,
            end_time=start_time + timedelta(minutes=30),
            current_participants=0
        )
        test_db.add(session)
        test_db.commit()
        test_db.refresh(session)
        
        # Crear 4 usuarios (más que la capacidad)
        users = []
        for i in range(4):
            user = TestUser(
                email=f"capacity_user{i}@example.com",
                full_name=f"Capacity User {i}",
                role=UserRole.MEMBER,
                qr_code=f"U{20+i}_cap{i}"
            )
            test_db.add(user)
            users.append(user)
        
        test_db.commit()
        
        # Asignar usuarios al gimnasio
        for user in users:
            user_gym = TestUserGym(user_id=user.id, gym_id=gym.id, role=GymRoleType.MEMBER)
            test_db.add(user_gym)
        test_db.commit()
        
        # Intentar registrar usuarios (solo hasta la capacidad)
        successful_registrations = 0
        rejected_users = []
        
        for i, user in enumerate(users):
            if session.current_participants < small_class.max_capacity:
                # Registrar usuario
                participation = TestClassParticipation(
                    session_id=session.id,
                    member_id=user.id,
                    gym_id=gym.id,
                    status=ClassParticipationStatus.REGISTERED
                )
                test_db.add(participation)
                session.current_participants += 1
                successful_registrations += 1
                print(f"✅ Usuario {i+1} registrado: {user.full_name}")
            else:
                # Usuario rechazado por capacidad
                rejected_users.append(user)
                print(f"❌ Usuario {i+1} RECHAZADO (capacidad llena): {user.full_name}")
        
        test_db.add(session)
        test_db.commit()
        test_db.refresh(session)
        
        # Verificaciones
        assert session.current_participants == small_class.max_capacity == 2
        assert successful_registrations == 2
        assert len(rejected_users) == 2
        
        print(f"\n📊 === CONTROL DE CAPACIDAD EXITOSO ===")
        print(f"✅ Capacidad máxima: {small_class.max_capacity}")
        print(f"✅ Participantes registrados: {session.current_participants}")
        print(f"✅ Registros exitosos: {successful_registrations}")
        print(f"✅ Usuarios rechazados: {len(rejected_users)}")
        print(f"✅ Clase: {small_class.name}") 