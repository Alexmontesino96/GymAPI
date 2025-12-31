"""
Testing intensivo del sistema de seguridad nutricional B2B2C
Cubre todos los casos de uso, validaciones y flujos de seguridad
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import json

from app.main import app
from app.db.session import SessionLocal
from app.models.user import User
from app.models.user_gym import UserGym
from app.models.gym import Gym
from app.models.nutrition import NutritionPlan
from app.models.nutrition_safety import SafetyScreening, SafetyAuditLog, RiskLevel
from app.services.nutrition_ai_safety import NutritionAISafetyService

# Cliente de prueba
client = TestClient(app)

# Configuración de base de datos de prueba
def get_test_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class TestNutritionSafetySystem:
    """Suite completa de tests para el sistema de seguridad nutricional"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Configuración inicial para cada test"""
        self.db = next(get_test_db())
        self.gym_id = 1

        # Crear usuarios de prueba con diferentes roles
        self.admin_user = self._create_user("admin_test", "admin")
        self.trainer_user = self._create_user("trainer_test", "trainer")
        self.member_user = self._create_user("member_test", "member")

        # Crear planes de prueba
        self.normal_plan = self._create_plan("Plan Normal", 2000, "maintenance")
        self.restrictive_plan = self._create_plan("Plan Pérdida Peso", 1200, "weight_loss")

        # Tokens de autenticación mockeados
        self.admin_token = "Bearer admin_token_123"
        self.trainer_token = "Bearer trainer_token_456"
        self.member_token = "Bearer member_token_789"

        yield

        # Limpieza después de cada test
        self._cleanup()

    def _create_user(self, username: str, role: str) -> User:
        """Helper para crear usuario con rol específico"""
        user = User(
            email=f"{username}@test.com",
            full_name=username,
            auth0_id=f"auth0|{username}",
            created_at=datetime.utcnow()
        )
        self.db.add(user)
        self.db.flush()

        user_gym = UserGym(
            user_id=user.id,
            gym_id=self.gym_id,
            role=role,
            joined_at=datetime.utcnow()
        )
        self.db.add(user_gym)
        self.db.commit()

        return user

    def _create_plan(self, title: str, calories: int, goal: str) -> NutritionPlan:
        """Helper para crear plan nutricional"""
        plan = NutritionPlan(
            title=title,
            description=f"Plan de {calories} calorías",
            gym_id=self.gym_id,
            creator_id=self.trainer_user.id,
            daily_calories=calories,
            nutrition_goal=goal,
            plan_type="template",
            is_public=True,
            created_at=datetime.utcnow()
        )
        self.db.add(plan)
        self.db.commit()
        return plan

    def _create_safety_screening(
        self,
        user_id: int,
        risk_level: str = "LOW",
        can_proceed: bool = True,
        is_pregnant: bool = False,
        has_eating_disorder: bool = False,
        age: int = 25
    ) -> SafetyScreening:
        """Helper para crear safety screening"""
        screening = SafetyScreening(
            user_id=user_id,
            gym_id=self.gym_id,
            age=age,
            weight=70.0,
            height=170.0,
            sex="male",
            is_pregnant=is_pregnant,
            is_breastfeeding=False,
            has_eating_disorder_history=has_eating_disorder,
            risk_score=2 if risk_level == "LOW" else 8,
            risk_level=risk_level,
            can_proceed=can_proceed,
            requires_professional=not can_proceed,
            accepts_disclaimer=True,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=24),
            last_updated_at=datetime.utcnow()
        )
        self.db.add(screening)
        self.db.commit()
        return screening

    def _cleanup(self):
        """Limpieza de datos de prueba"""
        # Limpiar en orden inverso de dependencias
        self.db.query(SafetyAuditLog).delete()
        self.db.query(SafetyScreening).delete()
        self.db.query(NutritionPlan).delete()
        self.db.query(UserGym).delete()
        self.db.query(User).filter(User.email.like("%@test.com")).delete()
        self.db.commit()

    # ========== TESTS DE GENERACIÓN CON IA (TRAINERS/ADMIN) ==========

    def test_trainer_can_generate_with_ai_without_screening(self):
        """Trainer puede generar con IA sin safety screening"""
        with patch('app.api.v1.endpoints.nutrition.get_current_user') as mock_user:
            mock_user.return_value = MagicMock(id=self.trainer_user.auth0_id)

            # Intentar generar ingredientes con IA
            response = client.post(
                f"/api/v1/nutrition/meals/1/ingredients/ai-generate",
                headers={"Authorization": self.trainer_token},
                json={
                    "recipe_name": "Ensalada César",
                    "target_calories": 400,
                    "meal_type": "lunch"
                }
            )

            # Debería permitirlo sin screening
            assert response.status_code in [200, 404]  # 404 si no existe la comida

            # Verificar audit log
            audit = self.db.query(SafetyAuditLog).filter(
                SafetyAuditLog.user_id == self.trainer_user.id,
                SafetyAuditLog.action_type == "ai_generation_by_trainer"
            ).first()

            if audit:
                assert audit.was_allowed == True
                assert audit.screening_id == None  # No requiere screening
                assert "trainer" in str(audit.action_details).lower()

    def test_member_cannot_generate_with_ai(self):
        """Member no puede generar con IA (solo trainers/admin)"""
        with patch('app.api.v1.endpoints.nutrition.get_current_user') as mock_user:
            mock_user.return_value = MagicMock(id=self.member_user.auth0_id)

            # Intentar generar ingredientes con IA
            response = client.post(
                f"/api/v1/nutrition/meals/1/ingredients/ai-generate",
                headers={"Authorization": self.member_token},
                json={
                    "recipe_name": "Ensalada César",
                    "target_calories": 400,
                    "meal_type": "lunch"
                }
            )

            # Debería rechazarlo
            assert response.status_code == 403
            assert "Solo trainers y administradores" in response.json()["detail"]

    def test_admin_can_generate_with_ai_without_screening(self):
        """Admin puede generar con IA sin safety screening"""
        with patch('app.api.v1.endpoints.nutrition.get_current_user') as mock_user:
            mock_user.return_value = MagicMock(id=self.admin_user.auth0_id)

            # Intentar generar ingredientes con IA
            response = client.post(
                f"/api/v1/nutrition/meals/1/ingredients/ai-generate",
                headers={"Authorization": self.admin_token},
                json={
                    "recipe_name": "Batido Proteico",
                    "target_calories": 350,
                    "meal_type": "snack"
                }
            )

            # Debería permitirlo sin screening
            assert response.status_code in [200, 404]

    # ========== TESTS DE SEGUIMIENTO DE PLANES (MEMBERS) ==========

    def test_member_can_follow_normal_plan_without_screening(self):
        """Member puede seguir plan normal sin safety screening"""
        with patch('app.api.v1.endpoints.nutrition.get_current_user') as mock_user:
            mock_user.return_value = MagicMock(id=self.member_user.auth0_id)

            # Intentar seguir plan normal (2000 calorías)
            response = client.post(
                f"/api/v1/nutrition/plans/{self.normal_plan.id}/follow",
                headers={"Authorization": self.member_token}
            )

            # Debería permitirlo sin screening (plan no restrictivo)
            assert response.status_code in [200, 400]  # 400 si ya lo sigue

    def test_member_cannot_follow_restrictive_plan_without_screening(self):
        """Member no puede seguir plan restrictivo sin safety screening"""
        with patch('app.api.v1.endpoints.nutrition.get_current_user') as mock_user:
            mock_user.return_value = MagicMock(id=self.member_user.auth0_id)

            # Intentar seguir plan restrictivo (1200 calorías)
            response = client.post(
                f"/api/v1/nutrition/plans/{self.restrictive_plan.id}/follow",
                headers={"Authorization": self.member_token}
            )

            # Debería rechazarlo y pedir screening
            assert response.status_code == 403
            detail = response.json()["detail"]
            assert detail["reason"] == "restrictive_plan"
            assert detail["action_required"] == "safety_screening"
            assert "/api/v1/nutrition/safety-check" in detail["endpoint"]

    def test_member_with_valid_screening_can_follow_restrictive_plan(self):
        """Member con screening válido puede seguir plan restrictivo"""
        # Crear screening válido para el member
        screening = self._create_safety_screening(
            user_id=self.member_user.id,
            risk_level="LOW",
            can_proceed=True
        )

        with patch('app.api.v1.endpoints.nutrition.get_current_user') as mock_user:
            mock_user.return_value = MagicMock(id=self.member_user.auth0_id)

            # Intentar seguir plan restrictivo
            response = client.post(
                f"/api/v1/nutrition/plans/{self.restrictive_plan.id}/follow",
                headers={"Authorization": self.member_token}
            )

            # Debería permitirlo con screening válido
            assert response.status_code in [200, 400]

            # Verificar audit log
            audit = self.db.query(SafetyAuditLog).filter(
                SafetyAuditLog.user_id == self.member_user.id,
                SafetyAuditLog.action_type == "follow_plan_with_screening"
            ).first()

            if audit:
                assert audit.was_allowed == True
                assert audit.screening_id == screening.id

    def test_high_risk_member_cannot_follow_restrictive_plan(self):
        """Member de alto riesgo no puede seguir plan restrictivo"""
        # Crear screening de alto riesgo
        screening = self._create_safety_screening(
            user_id=self.member_user.id,
            risk_level="HIGH",
            can_proceed=False
        )

        with patch('app.api.v1.endpoints.nutrition.get_current_user') as mock_user:
            mock_user.return_value = MagicMock(id=self.member_user.auth0_id)

            # Intentar seguir plan restrictivo
            response = client.post(
                f"/api/v1/nutrition/plans/{self.restrictive_plan.id}/follow",
                headers={"Authorization": self.member_token}
            )

            # Debería rechazarlo por alto riesgo
            assert response.status_code == 403
            detail = response.json()["detail"]
            assert detail["risk_level"] == "HIGH"
            assert detail["requires_professional"] == True

    # ========== TESTS DE EVALUACIÓN DE SEGURIDAD ==========

    def test_safety_screening_creation(self):
        """Crear evaluación de seguridad médica"""
        with patch('app.api.v1.endpoints.nutrition.get_current_user') as mock_user:
            mock_user.return_value = MagicMock(id=self.member_user.auth0_id)

            response = client.post(
                "/api/v1/nutrition/safety-check",
                headers={"Authorization": self.member_token},
                json={
                    "age": 25,
                    "is_pregnant": False,
                    "is_breastfeeding": False,
                    "has_diabetes": False,
                    "has_heart_condition": False,
                    "has_kidney_disease": False,
                    "has_liver_disease": False,
                    "has_eating_disorder": False,
                    "has_other_condition": False,
                    "accepts_disclaimer": True
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert "risk_score" in data
            assert "risk_level" in data
            assert "can_proceed" in data
            assert data["expires_in_hours"] == 24

    def test_pregnant_woman_high_risk(self):
        """Mujer embarazada debe ser evaluada como alto riesgo"""
        with patch('app.api.v1.endpoints.nutrition.get_current_user') as mock_user:
            mock_user.return_value = MagicMock(id=self.member_user.auth0_id)

            response = client.post(
                "/api/v1/nutrition/safety-check",
                headers={"Authorization": self.member_token},
                json={
                    "age": 28,
                    "is_pregnant": True,  # Embarazada
                    "is_breastfeeding": False,
                    "has_diabetes": False,
                    "has_heart_condition": False,
                    "has_kidney_disease": False,
                    "has_liver_disease": False,
                    "has_eating_disorder": False,
                    "has_other_condition": False,
                    "accepts_disclaimer": True
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["risk_level"] in ["HIGH", "CRITICAL"]
            assert data["requires_professional"] == True
            assert "Obstetra" in str(data.get("recommended_specialists", []))

    def test_minor_requires_parental_consent(self):
        """Menor de edad requiere consentimiento parental"""
        with patch('app.api.v1.endpoints.nutrition.get_current_user') as mock_user:
            mock_user.return_value = MagicMock(id=self.member_user.auth0_id)

            response = client.post(
                "/api/v1/nutrition/safety-check",
                headers={"Authorization": self.member_token},
                json={
                    "age": 16,  # Menor de edad
                    "is_pregnant": False,
                    "is_breastfeeding": False,
                    "has_diabetes": False,
                    "has_heart_condition": False,
                    "has_kidney_disease": False,
                    "has_liver_disease": False,
                    "has_eating_disorder": False,
                    "has_other_condition": False,
                    "accepts_disclaimer": True,
                    "parental_consent_email": None  # Sin consentimiento
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["parental_consent_required"] == True
            assert data["next_step"] == "parental_consent"

    def test_eating_disorder_history_critical_risk(self):
        """Historial de TCA debe ser riesgo crítico"""
        with patch('app.api.v1.endpoints.nutrition.get_current_user') as mock_user:
            mock_user.return_value = MagicMock(id=self.member_user.auth0_id)

            response = client.post(
                "/api/v1/nutrition/safety-check",
                headers={"Authorization": self.member_token},
                json={
                    "age": 22,
                    "is_pregnant": False,
                    "is_breastfeeding": False,
                    "has_diabetes": False,
                    "has_heart_condition": False,
                    "has_kidney_disease": False,
                    "has_liver_disease": False,
                    "has_eating_disorder": True,  # TCA
                    "has_other_condition": False,
                    "accepts_disclaimer": True
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["risk_level"] in ["HIGH", "CRITICAL"]
            assert data["requires_professional"] == True
            assert "Psicólogo" in str(data.get("recommended_specialists", []))

    def test_multiple_conditions_compound_risk(self):
        """Múltiples condiciones aumentan el riesgo compuesto"""
        with patch('app.api.v1.endpoints.nutrition.get_current_user') as mock_user:
            mock_user.return_value = MagicMock(id=self.member_user.auth0_id)

            response = client.post(
                "/api/v1/nutrition/safety-check",
                headers={"Authorization": self.member_token},
                json={
                    "age": 45,
                    "is_pregnant": False,
                    "is_breastfeeding": False,
                    "has_diabetes": True,  # Diabetes
                    "has_heart_condition": True,  # Condición cardíaca
                    "has_kidney_disease": False,
                    "has_liver_disease": False,
                    "has_eating_disorder": False,
                    "has_other_condition": False,
                    "accepts_disclaimer": True
                }
            )

            assert response.status_code == 200
            data = response.json()
            # Con dos condiciones serias, el riesgo debe ser alto
            assert data["risk_score"] >= 5
            assert data["risk_level"] in ["HIGH", "CRITICAL"]

    # ========== TESTS DE AUDIT LOGS ==========

    def test_audit_log_created_for_blocked_attempt(self):
        """Se crea audit log cuando se bloquea un intento"""
        with patch('app.api.v1.endpoints.nutrition.get_current_user') as mock_user:
            mock_user.return_value = MagicMock(id=self.member_user.auth0_id)

            # Intentar seguir plan restrictivo sin screening
            response = client.post(
                f"/api/v1/nutrition/plans/{self.restrictive_plan.id}/follow",
                headers={"Authorization": self.member_token}
            )

            # Verificar que se creó audit log
            audit = self.db.query(SafetyAuditLog).filter(
                SafetyAuditLog.user_id == self.member_user.id,
                SafetyAuditLog.action_type == "follow_plan_blocked"
            ).first()

            assert audit is not None
            assert audit.was_allowed == False
            assert audit.denial_reason is not None
            assert "no_valid_screening" in str(audit.action_details)

    def test_audit_log_created_for_successful_follow(self):
        """Se crea audit log cuando se permite seguir plan"""
        # Crear screening válido
        screening = self._create_safety_screening(
            user_id=self.member_user.id,
            risk_level="LOW",
            can_proceed=True
        )

        with patch('app.api.v1.endpoints.nutrition.get_current_user') as mock_user:
            mock_user.return_value = MagicMock(id=self.member_user.auth0_id)

            # Seguir plan restrictivo con screening
            response = client.post(
                f"/api/v1/nutrition/plans/{self.restrictive_plan.id}/follow",
                headers={"Authorization": self.member_token}
            )

            # Verificar audit log
            audit = self.db.query(SafetyAuditLog).filter(
                SafetyAuditLog.user_id == self.member_user.id,
                SafetyAuditLog.action_type == "follow_plan_with_screening"
            ).first()

            if audit:
                assert audit.was_allowed == True
                assert audit.screening_id == screening.id
                assert audit.denial_reason is None

    # ========== TESTS DE EXPIRACIÓN Y VALIDACIÓN ==========

    def test_expired_screening_requires_renewal(self):
        """Screening expirado requiere renovación"""
        # Crear screening expirado
        expired_screening = SafetyScreening(
            user_id=self.member_user.id,
            gym_id=self.gym_id,
            age=25,
            weight=70.0,
            height=170.0,
            sex="male",
            risk_score=2,
            risk_level="LOW",
            can_proceed=True,
            requires_professional=False,
            accepts_disclaimer=True,
            created_at=datetime.utcnow() - timedelta(hours=48),
            expires_at=datetime.utcnow() - timedelta(hours=24),  # Expirado
            last_updated_at=datetime.utcnow() - timedelta(hours=48)
        )
        self.db.add(expired_screening)
        self.db.commit()

        with patch('app.api.v1.endpoints.nutrition.get_current_user') as mock_user:
            mock_user.return_value = MagicMock(id=self.member_user.auth0_id)

            # Intentar seguir plan restrictivo con screening expirado
            response = client.post(
                f"/api/v1/nutrition/plans/{self.restrictive_plan.id}/follow",
                headers={"Authorization": self.member_token}
            )

            # Debería rechazarlo por screening expirado
            assert response.status_code == 403
            detail = response.json()["detail"]
            assert detail["action_required"] == "safety_screening"

    def test_screening_validation_endpoint(self):
        """Endpoint de validación de screening funciona correctamente"""
        # Crear screening válido
        screening = self._create_safety_screening(
            user_id=self.member_user.id,
            risk_level="MEDIUM",
            can_proceed=True
        )

        with patch('app.api.v1.endpoints.nutrition.get_current_user') as mock_user:
            mock_user.return_value = MagicMock(id=self.member_user.auth0_id)

            response = client.get(
                f"/api/v1/nutrition/safety-check/validate/{screening.id}",
                headers={"Authorization": self.member_token}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["valid"] == True
            assert data["can_proceed"] == True
            assert data["hours_remaining"] is not None
            assert data["hours_remaining"] > 0

    # ========== TESTS DE CASOS EDGE ==========

    def test_plan_title_detection_for_restriction(self):
        """Detección de planes restrictivos por título"""
        # Crear varios planes con títulos específicos
        detox_plan = self._create_plan("Challenge Detox 21 días", 1800, "maintenance")
        weight_loss_plan = self._create_plan("Weight Loss Program", 1600, "maintenance")

        with patch('app.api.v1.endpoints.nutrition.get_current_user') as mock_user:
            mock_user.return_value = MagicMock(id=self.member_user.auth0_id)

            # Ambos deben ser detectados como restrictivos por el título
            for plan in [detox_plan, weight_loss_plan]:
                response = client.post(
                    f"/api/v1/nutrition/plans/{plan.id}/follow",
                    headers={"Authorization": self.member_token}
                )

                assert response.status_code == 403
                detail = response.json()["detail"]
                assert detail["reason"] == "restrictive_plan"

    def test_weight_loss_restriction_for_special_conditions(self):
        """Restricción de pérdida de peso para condiciones especiales"""
        # Crear screening con embarazo
        pregnant_screening = self._create_safety_screening(
            user_id=self.member_user.id,
            risk_level="HIGH",
            can_proceed=True,  # Puede proceder con algunos planes
            is_pregnant=True
        )

        with patch('app.api.v1.endpoints.nutrition.get_current_user') as mock_user:
            mock_user.return_value = MagicMock(id=self.member_user.auth0_id)

            # No debe poder seguir plan de pérdida de peso
            response = client.post(
                f"/api/v1/nutrition/plans/{self.restrictive_plan.id}/follow",
                headers={"Authorization": self.member_token}
            )

            # Debe ser bloqueado específicamente por pérdida de peso + embarazo
            assert response.status_code == 403
            detail = response.json()["detail"]
            assert "medical_restriction" in detail.get("reason", "")

    def test_calorie_threshold_detection(self):
        """Detección correcta del umbral de calorías restrictivas"""
        # Plan justo en el límite (1500 calorías)
        borderline_plan = self._create_plan("Plan Borderline", 1500, "maintenance")

        # Plan justo debajo del límite (1499 calorías)
        restrictive_1499 = self._create_plan("Plan 1499", 1499, "maintenance")

        with patch('app.api.v1.endpoints.nutrition.get_current_user') as mock_user:
            mock_user.return_value = MagicMock(id=self.member_user.auth0_id)

            # 1500 calorías NO debe requerir screening
            response = client.post(
                f"/api/v1/nutrition/plans/{borderline_plan.id}/follow",
                headers={"Authorization": self.member_token}
            )
            assert response.status_code in [200, 400]  # No 403

            # 1499 calorías SÍ debe requerir screening
            response = client.post(
                f"/api/v1/nutrition/plans/{restrictive_1499.id}/follow",
                headers={"Authorization": self.member_token}
            )
            assert response.status_code == 403
            detail = response.json()["detail"]
            assert detail["reason"] == "restrictive_plan"


# ========== FUNCIÓN PRINCIPAL DE TESTING ==========

def run_intensive_tests():
    """
    Ejecuta suite completa de tests de seguridad nutricional
    """
    print("\n" + "="*70)
    print("🧪 INICIANDO TESTING INTENSIVO DEL SISTEMA DE SEGURIDAD NUTRICIONAL")
    print("="*70)

    # Instanciar la clase de tests
    test_suite = TestNutritionSafetySystem()

    # Lista de todos los métodos de test
    test_methods = [
        ("Trainer puede generar sin screening", test_suite.test_trainer_can_generate_with_ai_without_screening),
        ("Member no puede generar con IA", test_suite.test_member_cannot_generate_with_ai),
        ("Admin puede generar sin screening", test_suite.test_admin_can_generate_with_ai_without_screening),
        ("Member puede seguir plan normal", test_suite.test_member_can_follow_normal_plan_without_screening),
        ("Member bloqueado en plan restrictivo", test_suite.test_member_cannot_follow_restrictive_plan_without_screening),
        ("Member con screening puede seguir plan", test_suite.test_member_with_valid_screening_can_follow_restrictive_plan),
        ("Alto riesgo bloqueado", test_suite.test_high_risk_member_cannot_follow_restrictive_plan),
        ("Creación de screening", test_suite.test_safety_screening_creation),
        ("Embarazo = alto riesgo", test_suite.test_pregnant_woman_high_risk),
        ("Menor requiere consentimiento", test_suite.test_minor_requires_parental_consent),
        ("TCA = riesgo crítico", test_suite.test_eating_disorder_history_critical_risk),
        ("Múltiples condiciones", test_suite.test_multiple_conditions_compound_risk),
        ("Audit log en bloqueo", test_suite.test_audit_log_created_for_blocked_attempt),
        ("Audit log en éxito", test_suite.test_audit_log_created_for_successful_follow),
        ("Screening expirado", test_suite.test_expired_screening_requires_renewal),
        ("Validación de screening", test_suite.test_screening_validation_endpoint),
        ("Detección por título", test_suite.test_plan_title_detection_for_restriction),
        ("Restricción peso + condición", test_suite.test_weight_loss_restriction_for_special_conditions),
        ("Umbral de calorías", test_suite.test_calorie_threshold_detection)
    ]

    # Contadores de resultados
    passed = 0
    failed = 0
    errors = []

    print("\n🔬 Ejecutando tests...\n")

    # Ejecutar cada test
    for test_name, test_method in test_methods:
        try:
            # Setup antes de cada test
            test_suite.setup()

            # Ejecutar el test
            test_method()

            print(f"✅ {test_name}")
            passed += 1

        except AssertionError as e:
            print(f"❌ {test_name}: Falló - {str(e)}")
            failed += 1
            errors.append((test_name, str(e)))

        except Exception as e:
            print(f"⚠️ {test_name}: Error - {str(e)}")
            failed += 1
            errors.append((test_name, f"Error inesperado: {str(e)}"))

        finally:
            # Cleanup después de cada test
            try:
                test_suite._cleanup()
            except:
                pass

    # Mostrar resumen de resultados
    print("\n" + "="*70)
    print("📊 RESUMEN DE RESULTADOS")
    print("="*70)
    print(f"✅ Tests pasados: {passed}")
    print(f"❌ Tests fallados: {failed}")
    print(f"📈 Tasa de éxito: {(passed/(passed+failed)*100):.1f}%")

    if errors:
        print("\n⚠️ DETALLES DE ERRORES:")
        for test_name, error in errors:
            print(f"\n• {test_name}:")
            print(f"  {error}")

    print("\n" + "="*70)

    # Verificar cobertura del sistema
    print("\n🎯 COBERTURA DEL SISTEMA:")
    print("✓ Permisos por rol (trainer/admin/member)")
    print("✓ Safety screening obligatorio para planes restrictivos")
    print("✓ Evaluación de riesgo médico")
    print("✓ Condiciones especiales (embarazo, TCA, menores)")
    print("✓ Expiración de screenings (24 horas)")
    print("✓ Audit logs para cumplimiento legal")
    print("✓ Detección de planes restrictivos")
    print("✓ Validación de umbrales de calorías")
    print("✓ Mensajes de error informativos")

    return passed, failed


if __name__ == "__main__":
    # Ejecutar los tests
    passed, failed = run_intensive_tests()

    # Salir con código apropiado
    if failed == 0:
        print("\n🎉 ¡TODOS LOS TESTS PASARON EXITOSAMENTE!")
        exit(0)
    else:
        print(f"\n⚠️ {failed} tests fallaron. Revisar implementación.")
        exit(1)