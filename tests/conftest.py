import os
import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, TypeDecorator, CHAR
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_db
from main import app


# TypeDecorator para UUID compatible con SQLite
class GUID(TypeDecorator):
    """Platform-independent GUID type.
    Uses PostgreSQL's UUID type, otherwise uses CHAR(32), storing as stringified hex values.
    """
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(UUID())
        else:
            return dialect.type_descriptor(CHAR(32))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return str(value)
        else:
            if not isinstance(value, uuid.UUID):
                return "%.32x" % uuid.UUID(value).int
            else:
                return "%.32x" % value.int

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, uuid.UUID):
                value = uuid.UUID(value)
            return value


# Monkey patch para UUID en tests con SQLite
import sqlalchemy.dialects.postgresql as postgresql_dialect
original_uuid = postgresql_dialect.UUID

class SQLiteCompatibleUUID(original_uuid):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def load_dialect_impl(self, dialect):
        if dialect.name == 'sqlite':
            return CHAR(32)
        return super().load_dialect_impl(dialect)

postgresql_dialect.UUID = SQLiteCompatibleUUID


# Usar una base de datos en memoria para pruebas
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Crear las tablas en la base de datos de prueba
@pytest.fixture(scope="session")
def db_engine():
    # Excluir tablas que usan UUID (no compatibles con SQLite en tests)
    tables_to_create = [table for table in Base.metadata.sorted_tables
                        if table.name not in ['device_tokens']]

    for table in tables_to_create:
        table.create(bind=engine, checkfirst=True)

    yield engine

    # Limpiar
    for table in reversed(tables_to_create):
        table.drop(bind=engine, checkfirst=True)


@pytest.fixture(scope="function")
def db(db_engine):
    """
    Crea una sesión de base de datos fresca para cada test y la cierra al finalizar.
    """
    connection = db_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def client(db):
    """
    Crea un cliente de prueba usando una sesión de base de datos de prueba.
    """
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# Mock para el token de autenticación
@pytest.fixture(scope="function")
def auth_headers():
    """
    Proporciona headers de autenticación mock para pruebas.
    En un entorno real, esto vendría de Auth0.
    """
    # Este es un mock simple para pruebas
    return {"Authorization": "Bearer test_token"}


# Fixture para crear un usuario administrador de prueba
@pytest.fixture(scope="function")
def admin_user(db):
    """
    Crea un usuario administrador para pruebas.
    """
    from app.repositories.user import user_repository
    from app.models.user import UserRole
    
    admin = user_repository.get_by_email(db, email="admin@test.com")
    if not admin:
        from app.schemas.user import UserCreate
        admin_data = UserCreate(
            email="admin@test.com",
            password="admin_password",
            full_name="Admin Test",
            is_superuser=True,
            role=UserRole.ADMIN
        )
        admin = user_repository.create(db, obj_in=admin_data)
    
    return admin


# Fixture para crear un entrenador de prueba
@pytest.fixture(scope="function")
def trainer_user(db):
    """
    Crea un usuario entrenador para pruebas.
    """
    from app.repositories.user import user_repository
    from app.models.user import UserRole
    
    trainer = user_repository.get_by_email(db, email="trainer@test.com")
    if not trainer:
        from app.schemas.user import UserCreate
        trainer_data = UserCreate(
            email="trainer@test.com",
            password="trainer_password",
            full_name="Trainer Test",
            is_superuser=False,
            role=UserRole.TRAINER
        )
        trainer = user_repository.create(db, obj_in=trainer_data)
    
    return trainer


# Fixture para crear un miembro de prueba
@pytest.fixture(scope="function")
def member_user(db):
    """
    Crea un usuario miembro para pruebas.
    """
    from app.repositories.user import user_repository
    from app.models.user import UserRole
    
    member = user_repository.get_by_email(db, email="member@test.com")
    if not member:
        from app.schemas.user import UserCreate
        member_data = UserCreate(
            email="member@test.com",
            password="member_password",
            full_name="Member Test",
            is_superuser=False,
            role=UserRole.MEMBER
        )
        member = user_repository.create(db, obj_in=member_data)
    
    return member


# Fixture para crear una relación entrenador-miembro
@pytest.fixture(scope="function")
def trainer_member_relationship(db, trainer_user, member_user):
    """
    Crea una relación entrenador-miembro para pruebas.
    """
    from app.repositories.trainer_member import trainer_member_repository
    from app.models.trainer_member import RelationshipStatus
    
    # Verificar si ya existe la relación
    relationship = trainer_member_repository.get_by_trainer_and_member(
        db, trainer_id=trainer_user.id, member_id=member_user.id
    )
    
    if not relationship:
        from app.schemas.trainer_member import TrainerMemberRelationshipCreate
        relationship_data = TrainerMemberRelationshipCreate(
            trainer_id=trainer_user.id,
            member_id=member_user.id,
            status=RelationshipStatus.ACTIVE,
        )
        relationship = trainer_member_repository.create(db, obj_in=relationship_data)
    
    return relationship


# Mock para Auth0 response
@pytest.fixture(scope="function")
def mock_auth0_user():
    """
    Proporciona datos de usuario de Auth0 simulados para pruebas.
    """
    return {
        "sub": "auth0|test123456",
        "email": "auth0user@test.com",
        "name": "Auth0 Test User",
        "picture": "https://example.com/picture.jpg",
        "email_verified": True
    } 