"""
Configuración de Tests de Integración - Migración Async

Este archivo contiene la configuración para ejecutar tests contra la API real.
Los tokens deben ser proporcionados por el usuario.
"""
import os
from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class TestConfig:
    """Configuración de testing"""

    # API Base URL
    base_url: str = os.getenv("TEST_API_BASE_URL", "https://gymapi-production.up.railway.app")

    # Tokens de autenticación (proporcionados por el usuario)
    admin_token: Optional[str] = os.getenv("TEST_ADMIN_TOKEN")
    trainer_token: Optional[str] = os.getenv("TEST_TRAINER_TOKEN")
    member_token: Optional[str] = os.getenv("TEST_MEMBER_TOKEN")

    # IDs de test
    test_gym_id: int = int(os.getenv("TEST_GYM_ID", "1"))
    test_user_id: int = int(os.getenv("TEST_USER_ID", "1"))
    test_trainer_id: int = int(os.getenv("TEST_TRAINER_ID", "2"))

    # Timeouts
    request_timeout: int = 30  # segundos

    # Configuración de retry
    max_retries: int = 3
    retry_delay: float = 1.0  # segundos

    def get_headers(self, role: str = "admin") -> Dict[str, str]:
        """
        Obtiene headers para requests según el rol.

        Args:
            role: "admin", "trainer", o "member"

        Returns:
            Dict con headers incluyendo Authorization y X-Gym-ID
        """
        token_map = {
            "admin": self.admin_token,
            "trainer": self.trainer_token,
            "member": self.member_token
        }

        token = token_map.get(role)
        if not token:
            raise ValueError(f"Token para rol '{role}' no configurado. "
                           f"Usa TEST_{role.upper()}_TOKEN en env.")

        return {
            "Authorization": f"Bearer {token}",
            "X-Gym-ID": str(self.test_gym_id),
            "Content-Type": "application/json"
        }

    def validate(self) -> None:
        """Valida que la configuración esté completa."""
        errors = []

        if not self.admin_token:
            errors.append("TEST_ADMIN_TOKEN no configurado")
        if not self.trainer_token:
            errors.append("TEST_TRAINER_TOKEN no configurado")
        if not self.member_token:
            errors.append("TEST_MEMBER_TOKEN no configurado")

        if errors:
            raise ValueError(
                "Configuración de tests incompleta:\n" +
                "\n".join(f"  - {e}" for e in errors) +
                "\n\nConfigure las variables de entorno necesarias."
            )


# Instancia global de configuración
config = TestConfig()
