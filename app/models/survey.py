"""
Survey System Models

This module defines the database models for the survey/questionnaire system.
Supports multiple question types, conditional logic, and multi-tenant architecture.
"""

from enum import Enum
from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, DateTime, JSON, Float, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


class SurveyStatus(str, Enum):
    """Estados posibles de una encuesta"""
    DRAFT = "DRAFT"  # En borrador, no visible para usuarios
    PUBLISHED = "PUBLISHED"  # Publicada y activa
    CLOSED = "CLOSED"  # Cerrada, no acepta más respuestas
    ARCHIVED = "ARCHIVED"  # Archivada


class QuestionType(str, Enum):
    """Tipos de preguntas soportadas"""
    TEXT = "TEXT"  # Respuesta de texto libre
    TEXTAREA = "TEXTAREA"  # Texto largo
    RADIO = "RADIO"  # Opción única
    CHECKBOX = "CHECKBOX"  # Múltiples opciones
    SELECT = "SELECT"  # Dropdown
    SCALE = "SCALE"  # Escala numérica (1-5, 1-10, etc)
    DATE = "DATE"  # Selector de fecha
    TIME = "TIME"  # Selector de hora
    NUMBER = "NUMBER"  # Número
    EMAIL = "EMAIL"  # Email con validación
    PHONE = "PHONE"  # Teléfono
    YES_NO = "YES_NO"  # Sí/No
    NPS = "NPS"  # Net Promoter Score (0-10)


class Survey(Base):
    """
    Modelo para encuestas/cuestionarios
    """
    __tablename__ = "surveys"

    id = Column(Integer, primary_key=True, index=True)
    gym_id = Column(Integer, ForeignKey("gyms.id"), nullable=False, index=True)
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    title = Column(String(200), nullable=False)
    description = Column(Text)
    instructions = Column(Text)  # Instrucciones para completar la encuesta
    
    status = Column(SQLEnum(SurveyStatus), default=SurveyStatus.DRAFT, nullable=False, index=True)
    
    # Control de tiempo
    start_date = Column(DateTime(timezone=True))  # Fecha de inicio (opcional)
    end_date = Column(DateTime(timezone=True))  # Fecha de fin (opcional)
    
    # Configuración
    is_anonymous = Column(Boolean, default=False)  # Si las respuestas son anónimas
    allow_multiple = Column(Boolean, default=False)  # Si un usuario puede responder múltiples veces
    randomize_questions = Column(Boolean, default=False)  # Aleatorizar orden de preguntas
    show_progress = Column(Boolean, default=True)  # Mostrar barra de progreso
    
    # Mensaje de confirmación personalizado
    thank_you_message = Column(Text, default="Gracias por completar la encuesta")
    
    # Metadata para análisis
    tags = Column(JSON)  # Tags para categorización
    target_audience = Column(String(100))  # Audiencia objetivo (members, trainers, all)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    published_at = Column(DateTime(timezone=True))  # Cuándo se publicó
    
    # Relationships
    gym = relationship("Gym", back_populates="surveys")
    creator = relationship("User", back_populates="created_surveys")
    questions = relationship("SurveyQuestion", back_populates="survey", order_by="SurveyQuestion.order", cascade="all, delete-orphan")
    responses = relationship("SurveyResponse", back_populates="survey", cascade="all, delete-orphan")


class SurveyQuestion(Base):
    """
    Modelo para preguntas de encuesta
    """
    __tablename__ = "survey_questions"

    id = Column(Integer, primary_key=True, index=True)
    survey_id = Column(Integer, ForeignKey("surveys.id"), nullable=False, index=True)
    
    question_text = Column(Text, nullable=False)
    question_type = Column(SQLEnum(QuestionType), nullable=False)
    
    # Configuración de la pregunta
    is_required = Column(Boolean, default=False)
    order = Column(Integer, default=0)  # Orden de aparición
    
    # Ayuda y validación
    help_text = Column(Text)  # Texto de ayuda
    placeholder = Column(String(200))  # Placeholder para campos de texto
    
    # Validación para diferentes tipos
    min_value = Column(Float)  # Para números y escalas
    max_value = Column(Float)  # Para números y escalas
    min_length = Column(Integer)  # Para texto
    max_length = Column(Integer)  # Para texto
    regex_validation = Column(String(500))  # Expresión regular para validación
    
    # Para preguntas con opciones
    allow_other = Column(Boolean, default=False)  # Permitir opción "Otro"
    
    # Lógica condicional
    depends_on_question_id = Column(Integer, ForeignKey("survey_questions.id"))
    depends_on_answer = Column(JSON)  # Condición para mostrar esta pregunta
    
    # Metadata
    category = Column(String(100))  # Categoría de la pregunta
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    survey = relationship("Survey", back_populates="questions")
    choices = relationship("QuestionChoice", back_populates="question", order_by="QuestionChoice.order", cascade="all, delete-orphan")
    answers = relationship("SurveyAnswer", back_populates="question", cascade="all, delete-orphan")
    depends_on = relationship("SurveyQuestion", remote_side=[id])


class QuestionChoice(Base):
    """
    Modelo para opciones de respuesta en preguntas de selección
    """
    __tablename__ = "question_choices"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("survey_questions.id"), nullable=False, index=True)
    
    choice_text = Column(String(500), nullable=False)
    choice_value = Column(String(100))  # Valor interno (opcional)
    order = Column(Integer, default=0)
    
    # Para lógica condicional avanzada
    next_question_id = Column(Integer, ForeignKey("survey_questions.id"))  # Saltar a pregunta específica
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    question = relationship("SurveyQuestion", back_populates="choices", foreign_keys=[question_id])
    next_question = relationship("SurveyQuestion", foreign_keys=[next_question_id])


class SurveyResponse(Base):
    """
    Modelo para respuestas completas a encuestas
    """
    __tablename__ = "survey_responses"

    id = Column(Integer, primary_key=True, index=True)
    survey_id = Column(Integer, ForeignKey("surveys.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)  # Nullable para respuestas anónimas
    gym_id = Column(Integer, ForeignKey("gyms.id"), nullable=False, index=True)
    
    # Metadata de la respuesta
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
    is_complete = Column(Boolean, default=False)
    
    # Información adicional
    ip_address = Column(String(45))  # Para tracking (si no es anónimo)
    user_agent = Column(String(500))  # Browser/device info
    
    # Para encuestas relacionadas con eventos
    event_id = Column(Integer, ForeignKey("events.id"))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    survey = relationship("Survey", back_populates="responses")
    user = relationship("User", back_populates="survey_responses")
    gym = relationship("Gym", back_populates="survey_responses")
    event = relationship("Event", back_populates="survey_responses")
    answers = relationship("SurveyAnswer", back_populates="response", cascade="all, delete-orphan")


class SurveyAnswer(Base):
    """
    Modelo para respuestas individuales a preguntas
    """
    __tablename__ = "survey_answers"

    id = Column(Integer, primary_key=True, index=True)
    response_id = Column(Integer, ForeignKey("survey_responses.id"), nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("survey_questions.id"), nullable=False, index=True)
    
    # Diferentes tipos de respuesta
    text_answer = Column(Text)  # Para TEXT, TEXTAREA
    choice_id = Column(Integer, ForeignKey("question_choices.id"))  # Para RADIO, SELECT
    choice_ids = Column(JSON)  # Para CHECKBOX (array de IDs)
    number_answer = Column(Float)  # Para NUMBER, SCALE, NPS
    date_answer = Column(DateTime(timezone=True))  # Para DATE, TIME
    boolean_answer = Column(Boolean)  # Para YES_NO
    
    # Para opción "Otro"
    other_text = Column(Text)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    response = relationship("SurveyResponse", back_populates="answers")
    question = relationship("SurveyQuestion", back_populates="answers")
    choice = relationship("QuestionChoice")


class SurveyTemplate(Base):
    """
    Modelo para plantillas de encuestas predefinidas
    """
    __tablename__ = "survey_templates"

    id = Column(Integer, primary_key=True, index=True)
    gym_id = Column(Integer, ForeignKey("gyms.id"), index=True)  # Null para templates globales
    
    name = Column(String(200), nullable=False)
    description = Column(Text)
    category = Column(String(100))  # satisfaction, feedback, evaluation, etc.
    
    # Estructura de la plantilla
    template_data = Column(JSON, nullable=False)  # JSON con preguntas y configuración
    
    is_public = Column(Boolean, default=False)  # Si está disponible para todos los gimnasios
    usage_count = Column(Integer, default=0)  # Contador de uso
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    gym = relationship("Gym", back_populates="survey_templates")