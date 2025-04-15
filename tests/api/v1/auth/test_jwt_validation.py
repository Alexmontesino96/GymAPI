import pytest
import jwt
from datetime import datetime, timedelta
from jose import jwt as jose_jwt
from fastapi.testclient import TestClient
from app.core.auth0_fastapi import auth, Auth0UnauthenticatedException
from app.core.config import get_settings
from main import app
from unittest.mock import patch, MagicMock

client = TestClient(app)

@pytest.fixture
def mock_jwks():
    """Mock para el endpoint JWKS de Auth0"""
    return {
        "keys": [
            {
                "kid": "test-key-id",
                "kty": "RSA",
                "use": "sig",
                "n": "test-modulus",
                "e": "AQAB",
                "alg": "RS256"
            }
        ]
    }

@pytest.fixture
def valid_token_payload():
    """Genera un payload válido para un token JWT"""
    settings = get_settings()
    return {
        "iss": f"https://{settings.AUTH0_DOMAIN}/",
        "sub": "auth0|12345678",
        "aud": [settings.AUTH0_API_AUDIENCE],
        "iat": datetime.utcnow().timestamp(),
        "exp": (datetime.utcnow() + timedelta(hours=1)).timestamp(),
        "azp": settings.AUTH0_CLIENT_ID,
        "scope": "openid profile email",
        "permissions": ["read:profile"]
    }

@pytest.fixture
def generate_token(valid_token_payload):
    """Genera un token JWT firmado mock"""
    # En producción usamos RS256, pero para tests usamos HS256 que es más simple
    secret = "test-secret"
    headers = {"kid": "test-key-id", "alg": "HS256"}
    return jose_jwt.encode(valid_token_payload, secret, algorithm="HS256", headers=headers)

# TESTS

def test_valid_token_passes_validation(generate_token):
    """Un token bien formado y con permisos debe pasar la validación"""
    with patch('app.core.auth0_fastapi.jwt.decode') as mock_decode:
        mock_decode.return_value = valid_token_payload
        
        # Llamar al endpoint protegido
        response = client.get(
            "/api/v1/auth/me", 
            headers={"Authorization": f"Bearer {generate_token}"}
        )
        assert response.status_code == 200

def test_expired_token_fails_validation(valid_token_payload, generate_token):
    """Un token expirado debe fallar la validación"""
    # Modificar el payload para que esté expirado
    expired_payload = valid_token_payload.copy()
    expired_payload["exp"] = (datetime.utcnow() - timedelta(hours=1)).timestamp()
    
    with patch('app.core.auth0_fastapi.jwt.decode') as mock_decode:
        mock_decode.side_effect = jwt.ExpiredSignatureError()
        
        # Llamar al endpoint protegido
        response = client.get(
            "/api/v1/auth/me", 
            headers={"Authorization": f"Bearer {generate_token}"}
        )
        assert response.status_code == 401
        assert "Token expirado" in response.json()["detail"].lower()

def test_invalid_issuer_fails_validation(valid_token_payload, generate_token):
    """Un token con issuer inválido debe fallar"""
    # Modificar el payload con un issuer incorrecto
    invalid_payload = valid_token_payload.copy()
    invalid_payload["iss"] = "https://wrong-domain.auth0.com/"
    
    with patch('app.core.auth0_fastapi.jwt.decode') as mock_decode:
        mock_decode.side_effect = jwt.InvalidIssuerError()
        
        # Llamar al endpoint protegido
        response = client.get(
            "/api/v1/auth/me", 
            headers={"Authorization": f"Bearer {generate_token}"}
        )
        assert response.status_code == 401
        assert "issuer inválido" in response.json()["detail"].lower()

def test_missing_token_fails_validation():
    """Sin token, la autenticación debe fallar"""
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert "no se proporcionó el token" in response.json()["detail"].lower() 