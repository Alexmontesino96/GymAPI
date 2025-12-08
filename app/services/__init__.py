"""
Services module for GymAPI app

This module includes all service-related modules, which implement the business logic of the application.
Services interact with models, repositories, and external systems like Auth0 and Redis.
"""

# Inicializador del paquete services 

# servicios disponibles
from app.services.user import user_service
from app.services.trainer_member import trainer_member_service
from app.services.chat import chat_service
from app.services.schedule import (
    gym_hours_service,
    gym_special_hours_service,
    class_service,
    class_session_service,
    class_participation_service
) 
from app.services.gym import gym_service
from app.services.auth0_mgmt import auth0_mgmt_service
from app.services.cache_service import cache_service
from app.services.event import event_service  # Legacy - use async_event_service
from app.services.async_event import async_event_service
from app.services.aws_sqs import sqs_service  # Legacy - use async_sqs_service
from app.services.async_aws_sqs import AsyncSQSService
from app.services.queue_services import queue_service  # Legacy - use async_queue_service
from app.services.async_queue_services import async_queue_service

# Exportar servicios para acceso fácil
__all__ = [
    "user_service",
    "gym_service",
    "trainer_member_service",
    "chat_service",
    "event_service",  # Legacy
    "async_event_service",  # Async version
    "sqs_service",  # Legacy
    "AsyncSQSService",  # Async version
    "queue_service",  # Legacy
    "async_queue_service",  # Async version
] 