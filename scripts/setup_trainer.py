#!/usr/bin/env python
"""
Script de Onboarding para Entrenadores Personales
Crea automáticamente un workspace completo para un entrenador personal
"""

import asyncio
import sys
import json
from typing import Optional, List, Dict, Any
from datetime import datetime
import stripe
import os

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal
from app.models.gym import Gym, GymType
from app.models.user import User, UserRole
from app.models.user_gym import UserGym, GymRoleType
from app.models.gym_module import GymModule
from app.models.membership import MembershipPlan
from app.core.config import Settings

# Configuración
settings = Settings()
stripe.api_key = settings.STRIPE_API_KEY if hasattr(settings, 'STRIPE_API_KEY') else None

class TrainerSetup:
    """Configuración automatizada para entrenadores personales"""

    def __init__(self):
        self.db = SessionLocal()

    def __del__(self):
        """Cerrar sesión de BD al destruir el objeto"""
        if hasattr(self, 'db'):
            self.db.close()

    async def create_trainer_workspace(
        self,
        email: str,
        first_name: str,
        last_name: str,
        phone: Optional[str] = None,
        specialties: Optional[List[str]] = None,
        certifications: Optional[List[Dict]] = None,
        timezone: str = "America/Mexico_City"
    ) -> Dict:
        """
        Crear workspace completo para un entrenador personal

        Args:
            email: Email del entrenador
            first_name: Nombre del entrenador
            last_name: Apellido del entrenador
            phone: Teléfono opcional
            specialties: Lista de especialidades ["CrossFit", "Nutrición"]
            certifications: Lista de certificaciones [{"name": "NASM-CPT", "year": 2020}]
            timezone: Zona horaria del workspace

        Returns:
            Dict con información del resultado
        """
        try:
            print(f"🚀 Iniciando setup para entrenador: {first_name} {last_name}")

            # 1. Verificar si el usuario ya existe
            existing_user = self.db.query(User).filter(
                User.email == email
            ).first()

            if existing_user:
                # Verificar si ya tiene un gym
                existing_gym = self.db.query(UserGym).filter(
                    UserGym.user_id == existing_user.id,
                    UserGym.role == GymRoleType.OWNER
                ).first()

                if existing_gym:
                    print(f"⚠️  El usuario ya tiene un espacio de trabajo (ID: {existing_gym.gym_id})")
                    return {
                        "success": False,
                        "message": "El usuario ya tiene un espacio de trabajo",
                        "gym_id": existing_gym.gym_id
                    }

                user = existing_user
                print(f"✅ Usuario existente encontrado (ID: {user.id})")
            else:
                # 2. Crear usuario nuevo
                user = User(
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    phone=phone,
                    role=UserRole.TRAINER,  # Rol global
                    is_active=True,
                    created_at=datetime.utcnow()
                )
                self.db.add(user)
                self.db.flush()  # Obtener ID sin commit
                print(f"✅ Usuario creado (ID: {user.id})")

            # 3. Crear "gimnasio" personal
            gym_name = f"Entrenamiento Personal {first_name} {last_name}"

            # Generar subdomain único
            subdomain = f"{first_name.lower()}-{last_name.lower()}".replace(" ", "-")
            subdomain = subdomain[:50]  # Limitar longitud

            # Verificar si el subdomain ya existe
            counter = 1
            original_subdomain = subdomain
            while self.db.query(Gym).filter(Gym.subdomain == subdomain).first():
                subdomain = f"{original_subdomain}-{counter}"
                counter += 1

            gym = Gym(
                name=gym_name,
                type=GymType.personal_trainer,
                subdomain=subdomain,
                email=email,
                phone=phone,
                timezone=timezone,
                is_active=True,
                trainer_specialties=specialties or ["Fitness General"],
                trainer_certifications=certifications,
                max_clients=30,  # Límite default
                description=f"Espacio de entrenamiento personalizado de {first_name} {last_name}"
            )
            self.db.add(gym)
            self.db.flush()
            print(f"✅ Workspace creado (ID: {gym.id}, Subdomain: {subdomain})")

            # 4. Crear relación UserGym como OWNER
            user_gym = UserGym(
                user_id=user.id,
                gym_id=gym.id,
                role=GymRoleType.OWNER,
                is_active=True,
                membership_type="owner",
                created_at=datetime.utcnow()
            )
            self.db.add(user_gym)
            print(f"✅ Entrenador asignado como OWNER del workspace")

            # 5. Configurar Stripe Connect (si está disponible)
            stripe_onboarding_url = None
            if stripe.api_key:
                try:
                    stripe_data = await self._setup_stripe_connect(gym, user)
                    if stripe_data:
                        stripe_onboarding_url = stripe_data.get('onboarding_url')
                        print(f"✅ Stripe Connect configurado")
                except Exception as e:
                    print(f"⚠️  No se pudo configurar Stripe: {e}")

            # 6. Activar módulos esenciales
            essential_modules = [
                ("users", "Gestión de Clientes", True),
                ("chat", "Mensajería", True),
                ("health", "Tracking de Salud", True),
                ("nutrition", "Planes Nutricionales", True),
                ("billing", "Pagos y Facturación", True),
                ("appointments", "Agenda de Citas", True),
                ("progress", "Progreso de Clientes", True),
                ("surveys", "Encuestas y Feedback", True),
                # Módulos desactivados para entrenadores
                ("equipment", "Gestión de Equipos", False),
                ("classes", "Clases Grupales", False),
                ("schedule", "Horarios del Gimnasio", False)
            ]

            modules_created = []
            for module_code, description, is_active in essential_modules:
                module = GymModule(
                    gym_id=gym.id,
                    module_code=module_code,
                    is_active=is_active,
                    description=description,
                    config={},  # Configuración default
                    created_at=datetime.utcnow()
                )
                self.db.add(module)
                if is_active:
                    modules_created.append(module_code)

            print(f"✅ Módulos activados: {', '.join(modules_created)}")

            # 7. Crear planes de pago default (DESACTIVADO)
            # plans_created = await self._create_default_payment_plans(gym.id)
            # print(f"✅ Planes de pago creados: {len(plans_created)}")
            plans_created = []
            print(f"ℹ️  Los planes de pago se crearán manualmente")

            # Commit final
            self.db.commit()
            print(f"✅ Todos los cambios guardados en la base de datos")

            # 8. Preparar respuesta
            result = {
                "success": True,
                "message": "Espacio de trabajo creado exitosamente",
                "gym": {
                    "id": gym.id,
                    "name": gym.name,
                    "subdomain": subdomain,
                    "type": gym.type.value,
                    "email": gym.email,
                    "timezone": gym.timezone
                },
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "name": f"{user.first_name} {user.last_name}",
                    "role": user.role.value
                },
                "modules_activated": modules_created,
                "payment_plans": plans_created,
                "next_steps": [
                    "1. Completar configuración de perfil",
                    "2. Agregar primeros clientes",
                    "3. Configurar horario de disponibilidad",
                    "4. Personalizar planes de pago"
                ]
            }

            if stripe_onboarding_url:
                result["stripe_onboarding_url"] = stripe_onboarding_url
                result["next_steps"].insert(0, "0. Completar onboarding de Stripe para recibir pagos")

            print("\n" + "="*50)
            print("🎉 SETUP COMPLETADO EXITOSAMENTE!")
            print("="*50)

            return result

        except Exception as e:
            self.db.rollback()
            print(f"❌ Error al crear workspace: {str(e)}")
            return {
                "success": False,
                "message": f"Error al crear workspace: {str(e)}"
            }

    async def _setup_stripe_connect(self, gym: Gym, user: User) -> Optional[Dict]:
        """Configurar cuenta Stripe Connect para el entrenador"""
        try:
            if not stripe.api_key:
                print("⚠️  Stripe API key no configurada")
                return None

            # Crear cuenta Connect Standard
            account = stripe.Account.create(
                type="standard",
                country="MX",
                email=user.email,
                capabilities={
                    "transfers": {"requested": True},
                    "card_payments": {"requested": True}
                },
                business_profile={
                    "name": gym.name,
                    "product_description": "Servicios de entrenamiento personal",
                    "support_email": gym.email
                },
                metadata={
                    "gym_id": str(gym.id),
                    "user_id": str(user.id),
                    "type": "personal_trainer"
                }
            )

            # Generar link de onboarding
            account_link = stripe.AccountLink.create(
                account=account.id,
                refresh_url=f"{settings.FRONTEND_URL}/stripe/refresh" if hasattr(settings, 'FRONTEND_URL') else "https://app.example.com/stripe/refresh",
                return_url=f"{settings.FRONTEND_URL}/stripe/success" if hasattr(settings, 'FRONTEND_URL') else "https://app.example.com/stripe/success",
                type="account_onboarding"
            )

            # Guardar en BD (si existe la tabla)
            try:
                from app.models.gym_stripe import GymStripeAccount
                gym_stripe = GymStripeAccount(
                    gym_id=gym.id,
                    stripe_account_id=account.id,
                    is_connected=False,  # Se activa después del onboarding
                    created_at=datetime.utcnow()
                )
                self.db.add(gym_stripe)
            except ImportError:
                print("⚠️  Tabla GymStripeAccount no encontrada, omitiendo...")

            return {
                "account_id": account.id,
                "onboarding_url": account_link.url
            }

        except Exception as e:
            print(f"Error configurando Stripe: {e}")
            return None

    async def _create_default_payment_plans(self, gym_id: int) -> List[str]:
        """Crear planes de pago predeterminados para el entrenador"""
        plans_created = []

        default_plans = [
            {
                "name": "Sesión Individual",
                "type": "one_time",
                "price": 50000,  # $500 MXN en centavos
                "currency": "mxn",
                "interval": None,
                "sessions": 1
            },
            {
                "name": "Paquete 5 Sesiones",
                "type": "package",
                "price": 225000,  # $2,250 MXN (10% descuento)
                "currency": "mxn",
                "sessions": 5
            },
            {
                "name": "Paquete 10 Sesiones",
                "type": "package",
                "price": 400000,  # $4,000 MXN (20% descuento)
                "currency": "mxn",
                "sessions": 10
            },
            {
                "name": "Mensualidad Ilimitada",
                "type": "subscription",
                "price": 300000,  # $3,000 MXN/mes
                "currency": "mxn",
                "interval": "month",
                "sessions": None
            }
        ]

        for plan_data in default_plans:
            try:
                # Crear en Stripe si está configurado
                stripe_price_id = None
                if stripe.api_key:
                    if plan_data["type"] == "subscription":
                        stripe_price = stripe.Price.create(
                            unit_amount=plan_data["price"],
                            currency=plan_data["currency"],
                            recurring={"interval": plan_data.get("interval", "month")},
                            product_data={"name": plan_data["name"]},
                            metadata={"gym_id": str(gym_id)}
                        )
                    else:
                        stripe_price = stripe.Price.create(
                            unit_amount=plan_data["price"],
                            currency=plan_data["currency"],
                            product_data={"name": plan_data["name"]},
                            metadata={
                                "gym_id": str(gym_id),
                                "sessions": str(plan_data.get("sessions", 1))
                            }
                        )
                    stripe_price_id = stripe_price.id

                # Guardar en BD
                membership_plan = MembershipPlan(
                    gym_id=gym_id,
                    name=plan_data["name"],
                    stripe_price_id=stripe_price_id,
                    price=plan_data["price"],
                    currency=plan_data["currency"],
                    billing_interval=plan_data.get("interval", "one_time"),
                    is_active=True,
                    features=f"{plan_data.get('sessions', '')} sesiones" if plan_data.get('sessions') else "Sesiones ilimitadas",
                    created_at=datetime.utcnow()
                )
                self.db.add(membership_plan)
                plans_created.append(plan_data["name"])

            except Exception as e:
                print(f"Error creando plan {plan_data['name']}: {e}")
                continue

        return plans_created


# CLI para ejecutar el script
async def main():
    """Función principal del script CLI"""

    print("="*50)
    print("🏋️  SETUP DE ENTRENADOR PERSONAL")
    print("="*50)

    # Parsear argumentos de línea de comandos
    if len(sys.argv) < 4:
        print("\n📋 Uso del script:")
        print("python setup_trainer.py <email> <first_name> <last_name> [phone] [timezone]")
        print("\n📌 Ejemplos:")
        print("python setup_trainer.py juan@trainer.com Juan Pérez")
        print("python setup_trainer.py maria@fitness.com Maria González +525512345678")
        print("python setup_trainer.py carlos@gym.com Carlos López +525587654321 America/Mexico_City")
        sys.exit(1)

    email = sys.argv[1]
    first_name = sys.argv[2]
    last_name = sys.argv[3]
    phone = sys.argv[4] if len(sys.argv) > 4 else None
    timezone = sys.argv[5] if len(sys.argv) > 5 else "America/Mexico_City"

    # Datos de ejemplo para especialidades y certificaciones
    specialties = ["Fitness", "Nutrición", "Entrenamiento Funcional"]
    certifications = [
        {"name": "NASM-CPT", "year": 2020},
        {"name": "Precision Nutrition L1", "year": 2021}
    ]

    print(f"\n📝 Configuración:")
    print(f"  • Email: {email}")
    print(f"  • Nombre: {first_name} {last_name}")
    print(f"  • Teléfono: {phone or 'No especificado'}")
    print(f"  • Zona horaria: {timezone}")
    print(f"  • Especialidades: {', '.join(specialties)}")
    print(f"  • Certificaciones: {len(certifications)}")
    print()

    # Confirmar antes de proceder
    confirm = input("¿Desea continuar con la creación del workspace? (s/n): ")
    if confirm.lower() != 's':
        print("❌ Operación cancelada")
        sys.exit(0)

    print()
    setup = TrainerSetup()
    result = await setup.create_trainer_workspace(
        email=email,
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        specialties=specialties,
        certifications=certifications,
        timezone=timezone
    )

    # Mostrar resultado
    if result["success"]:
        print("\n" + "="*50)
        print("📊 RESUMEN DEL WORKSPACE CREADO:")
        print("="*50)
        print(f"✅ Workspace ID: {result['gym']['id']}")
        print(f"✅ Subdomain: {result['gym']['subdomain']}")
        print(f"✅ Usuario ID: {result['user']['id']}")
        print(f"✅ Email: {result['user']['email']}")
        print(f"✅ Módulos activos: {len(result['modules_activated'])}")

        if result.get('stripe_onboarding_url'):
            print(f"\n🔗 URL de Stripe Onboarding:")
            print(f"   {result['stripe_onboarding_url']}")

        print(f"\n📋 Próximos pasos:")
        for step in result['next_steps']:
            print(f"   • {step}")

        # Guardar resultado en archivo JSON
        output_file = f"trainer_{result['gym']['id']}_setup.json"
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2, default=str)
        print(f"\n💾 Detalles guardados en: {output_file}")
    else:
        print(f"\n❌ Error: {result['message']}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())