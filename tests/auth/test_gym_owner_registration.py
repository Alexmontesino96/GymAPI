"""
Tests para el endpoint de registro de dueños de gimnasio
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.gym import Gym, GymType
from app.models.user_gym import UserGym, GymRoleType


class TestGymOwnerRegistration:
    """Tests para el registro de dueños de gimnasio"""

    @pytest.fixture
    def valid_registration_data(self):
        """Datos válidos para registro"""
        return {
            "email": "newowner@testgym.com",
            "password": "SecurePass123",
            "first_name": "Carlos",
            "last_name": "González",
            "phone": "+525512345678",
            "gym_name": "Fitness Test Gym",
            "gym_address": "Calle Reforma 123, CDMX",
            "gym_phone": "+525587654321",
            "gym_email": "contacto@testgym.com",
            "timezone": "America/Mexico_City"
        }

    def test_successful_registration(self, client: TestClient, db: Session, valid_registration_data):
        """Test registro exitoso completo"""
        response = client.post("/api/v1/auth/register-gym-owner", json=valid_registration_data)

        assert response.status_code == 201
        data = response.json()

        # Verificar estructura de respuesta
        assert data["success"] is True
        assert "gym" in data
        assert "user" in data
        assert "modules_activated" in data
        assert "next_steps" in data

        # Verificar datos del gym
        assert data["gym"]["name"] == "Fitness Test Gym"
        assert data["gym"]["type"] == "gym"
        assert data["gym"]["timezone"] == "America/Mexico_City"
        assert data["gym"]["is_active"] is True

        # Verificar datos del usuario
        assert data["user"]["email"] == "newowner@testgym.com"
        assert data["user"]["name"] == "Carlos González"
        assert data["user"]["role"] == "ADMIN"

        # Verificar módulos activados
        assert "users" in data["modules_activated"]
        assert "schedule" in data["modules_activated"]
        assert "chat" in data["modules_activated"]
        assert "billing" in data["modules_activated"]

        # Verificar en BD
        user = db.query(User).filter(User.email == "newowner@testgym.com").first()
        assert user is not None
        assert user.first_name == "Carlos"
        assert user.last_name == "González"
        assert user.role.value == "ADMIN"

        gym = db.query(Gym).filter(Gym.id == data["gym"]["id"]).first()
        assert gym is not None
        assert gym.name == "Fitness Test Gym"
        assert gym.type == GymType.gym

        user_gym = db.query(UserGym).filter(
            UserGym.user_id == user.id,
            UserGym.gym_id == gym.id
        ).first()
        assert user_gym is not None
        assert user_gym.role == GymRoleType.OWNER

    def test_duplicate_email_rejected(self, client: TestClient, db: Session, valid_registration_data):
        """Test que email duplicado es rechazado"""
        # Primer registro exitoso
        response1 = client.post("/api/v1/auth/register-gym-owner", json=valid_registration_data)
        assert response1.status_code == 201

        # Segundo intento con mismo email debe fallar
        response2 = client.post("/api/v1/auth/register-gym-owner", json=valid_registration_data)
        assert response2.status_code == 400

        data = response2.json()
        assert "detail" in data
        assert data["detail"]["success"] is False
        assert data["detail"]["error_code"] == "EMAIL_EXISTS"

    def test_weak_password_rejected(self, client: TestClient, valid_registration_data):
        """Test que contraseña débil es rechazada"""
        # Contraseña sin mayúsculas
        data_weak1 = valid_registration_data.copy()
        data_weak1["email"] = "test1@gym.com"
        data_weak1["password"] = "weakpass123"
        response1 = client.post("/api/v1/auth/register-gym-owner", json=data_weak1)
        assert response1.status_code == 422  # Validation error

        # Contraseña sin números
        data_weak2 = valid_registration_data.copy()
        data_weak2["email"] = "test2@gym.com"
        data_weak2["password"] = "WeakPass"
        response2 = client.post("/api/v1/auth/register-gym-owner", json=data_weak2)
        assert response2.status_code == 422

        # Contraseña muy corta
        data_weak3 = valid_registration_data.copy()
        data_weak3["email"] = "test3@gym.com"
        data_weak3["password"] = "Weak1"
        response3 = client.post("/api/v1/auth/register-gym-owner", json=data_weak3)
        assert response3.status_code == 422

    def test_invalid_phone_rejected(self, client: TestClient, valid_registration_data):
        """Test que teléfono inválido es rechazado"""
        data_invalid_phone = valid_registration_data.copy()
        data_invalid_phone["email"] = "testphone@gym.com"
        data_invalid_phone["phone"] = "123456"  # Sin código de país
        response = client.post("/api/v1/auth/register-gym-owner", json=data_invalid_phone)
        assert response.status_code == 422

    def test_invalid_timezone_rejected(self, client: TestClient, valid_registration_data):
        """Test que timezone inválido es rechazado"""
        data_invalid_tz = valid_registration_data.copy()
        data_invalid_tz["email"] = "testtz@gym.com"
        data_invalid_tz["timezone"] = "Invalid/Timezone"
        response = client.post("/api/v1/auth/register-gym-owner", json=data_invalid_tz)
        assert response.status_code == 422

    def test_missing_required_fields(self, client: TestClient):
        """Test que campos requeridos son validados"""
        # Sin email
        data_no_email = {
            "password": "SecurePass123",
            "first_name": "Test",
            "last_name": "User",
            "gym_name": "Test Gym"
        }
        response1 = client.post("/api/v1/auth/register-gym-owner", json=data_no_email)
        assert response1.status_code == 422

        # Sin contraseña
        data_no_password = {
            "email": "test@gym.com",
            "first_name": "Test",
            "last_name": "User",
            "gym_name": "Test Gym"
        }
        response2 = client.post("/api/v1/auth/register-gym-owner", json=data_no_password)
        assert response2.status_code == 422

        # Sin nombre de gym
        data_no_gym = {
            "email": "test@gym.com",
            "password": "SecurePass123",
            "first_name": "Test",
            "last_name": "User"
        }
        response3 = client.post("/api/v1/auth/register-gym-owner", json=data_no_gym)
        assert response3.status_code == 422

    def test_optional_fields_work(self, client: TestClient, db: Session):
        """Test que campos opcionales funcionan correctamente"""
        minimal_data = {
            "email": "minimal@testgym.com",
            "password": "SecurePass123",
            "first_name": "Min",
            "last_name": "Test",
            "gym_name": "Minimal Gym"
            # Sin phone, gym_address, gym_phone, gym_email
            # timezone usa default
        }
        response = client.post("/api/v1/auth/register-gym-owner", json=minimal_data)

        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["gym"]["timezone"] == "America/Mexico_City"  # Default

    def test_subdomain_generated_correctly(self, client: TestClient, db: Session, valid_registration_data):
        """Test que subdomain se genera correctamente"""
        response = client.post("/api/v1/auth/register-gym-owner", json=valid_registration_data)

        assert response.status_code == 201
        data = response.json()

        # Verificar que subdomain existe y es válido
        assert "subdomain" in data["gym"]
        subdomain = data["gym"]["subdomain"]
        assert len(subdomain) > 0
        assert subdomain.islower()  # Debe estar en minúsculas
        assert " " not in subdomain  # No debe tener espacios

    def test_unique_subdomain_handling(self, client: TestClient, db: Session, valid_registration_data):
        """Test que subdomains duplicados se manejan correctamente"""
        # Primer registro
        response1 = client.post("/api/v1/auth/register-gym-owner", json=valid_registration_data)
        assert response1.status_code == 201
        subdomain1 = response1.json()["gym"]["subdomain"]

        # Segundo registro con mismo nombre de gym pero diferente email
        data2 = valid_registration_data.copy()
        data2["email"] = "different@gym.com"
        response2 = client.post("/api/v1/auth/register-gym-owner", json=data2)

        assert response2.status_code == 201
        subdomain2 = response2.json()["gym"]["subdomain"]

        # Los subdomains deben ser diferentes
        assert subdomain1 != subdomain2
