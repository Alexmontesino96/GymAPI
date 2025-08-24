"""
Survey System Schemas

This module defines Pydantic schemas for data validation in the survey system.
"""

from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field, validator, EmailStr
from enum import Enum

from app.models.survey import SurveyStatus, QuestionType


# ============= Base Schemas =============

class QuestionChoiceBase(BaseModel):
    """Base schema para opciones de pregunta"""
    choice_text: str = Field(..., min_length=1, max_length=500)
    choice_value: Optional[str] = Field(None, max_length=100)
    order: int = Field(0, ge=0)
    next_question_id: Optional[int] = None


class QuestionChoiceCreate(QuestionChoiceBase):
    """Schema para crear opción de pregunta"""
    pass


class QuestionChoiceUpdate(BaseModel):
    """Schema para actualizar opción de pregunta"""
    choice_text: Optional[str] = Field(None, min_length=1, max_length=500)
    choice_value: Optional[str] = Field(None, max_length=100)
    order: Optional[int] = Field(None, ge=0)
    next_question_id: Optional[int] = None


class QuestionChoice(QuestionChoiceBase):
    """Schema para opción de pregunta con ID"""
    id: int
    question_id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ============= Question Schemas =============

class SurveyQuestionBase(BaseModel):
    """Base schema para preguntas de encuesta"""
    question_text: str = Field(..., min_length=1)
    question_type: QuestionType
    is_required: bool = False
    order: int = Field(0, ge=0)
    help_text: Optional[str] = None
    placeholder: Optional[str] = Field(None, max_length=200)
    
    # Validación
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    min_length: Optional[int] = Field(None, ge=0)
    max_length: Optional[int] = Field(None, ge=1)
    regex_validation: Optional[str] = Field(None, max_length=500)
    
    # Opciones
    allow_other: bool = False
    
    # Lógica condicional
    depends_on_question_id: Optional[int] = None
    depends_on_answer: Optional[Dict[str, Any]] = None
    
    # Metadata
    category: Optional[str] = Field(None, max_length=100)

    @validator('min_value', 'max_value')
    def validate_numeric_bounds(cls, v, values):
        """Validar que min_value < max_value para tipos numéricos"""
        if 'question_type' in values:
            qt = values['question_type']
            if qt in [QuestionType.NUMBER, QuestionType.SCALE, QuestionType.NPS]:
                if v is not None and values.get('min_value') is not None and values.get('max_value') is not None:
                    if values['min_value'] >= values['max_value']:
                        raise ValueError('min_value debe ser menor que max_value')
        return v


class SurveyQuestionCreate(SurveyQuestionBase):
    """Schema para crear pregunta con opciones"""
    choices: Optional[List[QuestionChoiceCreate]] = []

    @validator('choices')
    def validate_choices(cls, v, values):
        """Validar que las preguntas de selección tengan opciones"""
        if 'question_type' in values:
            qt = values['question_type']
            if qt in [QuestionType.RADIO, QuestionType.CHECKBOX, QuestionType.SELECT]:
                if not v or len(v) < 2:
                    raise ValueError(f'Las preguntas de tipo {qt} deben tener al menos 2 opciones')
        return v


class SurveyQuestionUpdate(BaseModel):
    """Schema para actualizar pregunta"""
    question_text: Optional[str] = Field(None, min_length=1)
    question_type: Optional[QuestionType] = None
    is_required: Optional[bool] = None
    order: Optional[int] = Field(None, ge=0)
    help_text: Optional[str] = None
    placeholder: Optional[str] = Field(None, max_length=200)
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    min_length: Optional[int] = Field(None, ge=0)
    max_length: Optional[int] = Field(None, ge=1)
    regex_validation: Optional[str] = Field(None, max_length=500)
    allow_other: Optional[bool] = None
    depends_on_question_id: Optional[int] = None
    depends_on_answer: Optional[Dict[str, Any]] = None
    category: Optional[str] = Field(None, max_length=100)


class SurveyQuestion(SurveyQuestionBase):
    """Schema para pregunta con ID y opciones"""
    id: int
    survey_id: int
    choices: List[QuestionChoice] = []
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# ============= Survey Schemas =============

class SurveyBase(BaseModel):
    """Base schema para encuestas"""
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    instructions: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    is_anonymous: bool = False
    allow_multiple: bool = False
    randomize_questions: bool = False
    show_progress: bool = True
    thank_you_message: str = "Gracias por completar la encuesta"
    tags: Optional[List[str]] = []
    target_audience: Optional[str] = Field(None, max_length=100)

    @validator('end_date')
    def validate_dates(cls, v, values):
        """Validar que end_date > start_date"""
        if v and 'start_date' in values and values['start_date']:
            if v <= values['start_date']:
                raise ValueError('La fecha de fin debe ser posterior a la fecha de inicio')
        return v


class SurveyCreate(SurveyBase):
    """Schema para crear encuesta con preguntas"""
    questions: Optional[List[SurveyQuestionCreate]] = []


class SurveyUpdate(BaseModel):
    """Schema para actualizar encuesta"""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    instructions: Optional[str] = None
    status: Optional[SurveyStatus] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    is_anonymous: Optional[bool] = None
    allow_multiple: Optional[bool] = None
    randomize_questions: Optional[bool] = None
    show_progress: Optional[bool] = None
    thank_you_message: Optional[str] = None
    tags: Optional[List[str]] = None
    target_audience: Optional[str] = Field(None, max_length=100)


class Survey(SurveyBase):
    """Schema para encuesta completa"""
    id: int
    gym_id: int
    creator_id: int
    status: SurveyStatus
    published_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class SurveyWithQuestions(Survey):
    """Schema para encuesta con preguntas"""
    questions: List[SurveyQuestion] = []
    response_count: int = 0
    
    class Config:
        from_attributes = True


class SurveyList(BaseModel):
    """Schema para lista de encuestas"""
    surveys: List[Survey]
    total: int
    skip: int
    limit: int


# ============= Answer Schemas =============

class AnswerBase(BaseModel):
    """Base schema para respuestas"""
    question_id: int
    text_answer: Optional[str] = None
    choice_id: Optional[int] = None
    choice_ids: Optional[List[int]] = None
    number_answer: Optional[float] = None
    date_answer: Optional[datetime] = None
    boolean_answer: Optional[bool] = None
    other_text: Optional[str] = None


class AnswerCreate(AnswerBase):
    """Schema para crear respuesta"""
    
    @validator('text_answer', 'choice_id', 'choice_ids', 'number_answer', 'date_answer', 'boolean_answer')
    def validate_answer_type(cls, v, values, field):
        """Validar que el tipo de respuesta coincida con el tipo de pregunta"""
        # Esta validación se hace en el servicio con acceso a la pregunta
        return v


class Answer(AnswerBase):
    """Schema para respuesta con ID"""
    id: int
    response_id: int
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# ============= Response Schemas =============

class ResponseBase(BaseModel):
    """Base schema para respuestas completas"""
    survey_id: int
    event_id: Optional[int] = None


class ResponseCreate(ResponseBase):
    """Schema para crear respuesta completa con answers"""
    answers: List[AnswerCreate]
    
    @validator('answers')
    def validate_answers(cls, v):
        """Validar que haya al menos una respuesta"""
        if not v:
            raise ValueError('Debe proporcionar al menos una respuesta')
        return v


class ResponseUpdate(BaseModel):
    """Schema para actualizar respuesta"""
    is_complete: bool = True
    completed_at: Optional[datetime] = None


class Response(ResponseBase):
    """Schema para respuesta completa"""
    id: int
    user_id: Optional[int]
    gym_id: int
    started_at: datetime
    completed_at: Optional[datetime]
    is_complete: bool
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class ResponseWithAnswers(Response):
    """Schema para respuesta con answers"""
    answers: List[Answer] = []
    
    class Config:
        from_attributes = True


class ResponseDetail(ResponseWithAnswers):
    """Schema detallado de respuesta con información adicional"""
    survey: Survey
    user_email: Optional[str] = None
    user_name: Optional[str] = None
    
    class Config:
        from_attributes = True


# ============= Statistics Schemas =============

class QuestionStatistics(BaseModel):
    """Estadísticas para una pregunta"""
    question_id: int
    question_text: str
    question_type: QuestionType
    total_responses: int
    
    # Para preguntas de selección
    choice_distribution: Optional[Dict[str, int]] = None
    
    # Para preguntas numéricas
    average: Optional[float] = None
    min: Optional[float] = None
    max: Optional[float] = None
    median: Optional[float] = None
    
    # Para texto
    text_responses: Optional[List[str]] = None
    
    # Para NPS
    nps_score: Optional[float] = None
    promoters: Optional[int] = None
    passives: Optional[int] = None
    detractors: Optional[int] = None


class SurveyStatistics(BaseModel):
    """Estadísticas completas de una encuesta"""
    survey_id: int
    survey_title: str
    total_responses: int
    complete_responses: int
    incomplete_responses: int
    average_completion_time: Optional[float] = None  # en minutos
    response_rate: Optional[float] = None  # porcentaje
    questions: List[QuestionStatistics] = []
    
    # Distribución temporal
    responses_by_date: Optional[Dict[str, int]] = None
    
    # Metadata
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# ============= Template Schemas =============

class TemplateBase(BaseModel):
    """Base schema para plantillas"""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    category: Optional[str] = Field(None, max_length=100)
    is_public: bool = False


class TemplateCreate(TemplateBase):
    """Schema para crear plantilla"""
    template_data: Dict[str, Any]


class TemplateUpdate(BaseModel):
    """Schema para actualizar plantilla"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    category: Optional[str] = Field(None, max_length=100)
    is_public: Optional[bool] = None
    template_data: Optional[Dict[str, Any]] = None


class Template(TemplateBase):
    """Schema para plantilla con ID"""
    id: int
    gym_id: Optional[int]
    template_data: Dict[str, Any]
    usage_count: int
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class CreateFromTemplate(BaseModel):
    """Schema para crear encuesta desde plantilla"""
    template_id: int
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None