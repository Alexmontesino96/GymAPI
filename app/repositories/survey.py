"""
Survey Repository

This module provides database operations for the survey system.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import and_, or_, func, desc
from fastapi import HTTPException, status

from app.models.survey import (
    Survey, SurveyQuestion, QuestionChoice, SurveyResponse, 
    SurveyAnswer, SurveyTemplate, SurveyStatus, QuestionType
)
from app.schemas.survey import (
    SurveyCreate, SurveyUpdate, SurveyQuestionCreate, SurveyQuestionUpdate,
    ResponseCreate, AnswerCreate, TemplateCreate, TemplateUpdate
)
import logging

logger = logging.getLogger(__name__)


class SurveyRepository:
    """Repository para operaciones de encuestas"""
    
    # ============= Survey CRUD =============
    
    def create_survey(
        self,
        db: Session,
        survey_in: SurveyCreate,
        creator_id: int,
        gym_id: int
    ) -> Survey:
        """Crear una nueva encuesta con preguntas"""
        try:
            # Crear encuesta principal
            survey_data = survey_in.dict(exclude={'questions'})
            survey = Survey(
                **survey_data,
                creator_id=creator_id,
                gym_id=gym_id,
                status=SurveyStatus.DRAFT
            )
            db.add(survey)
            db.flush()  # Para obtener el ID sin hacer commit
            
            # Crear preguntas y opciones
            for idx, question_data in enumerate(survey_in.questions or []):
                question = self._create_question(
                    db=db,
                    survey_id=survey.id,
                    question_data=question_data,
                    order=idx
                )
                survey.questions.append(question)
            
            db.commit()
            db.refresh(survey)
            return survey
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error creando encuesta: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error creando encuesta: {str(e)}"
            )
    
    def _create_question(
        self,
        db: Session,
        survey_id: int,
        question_data: SurveyQuestionCreate,
        order: int
    ) -> SurveyQuestion:
        """Helper para crear una pregunta con opciones"""
        question_dict = question_data.dict(exclude={'choices'})
        question_dict['order'] = order
        question = SurveyQuestion(
            survey_id=survey_id,
            **question_dict
        )
        db.add(question)
        db.flush()
        
        # Crear opciones si es pregunta de selección
        if question_data.choices:
            for idx, choice_data in enumerate(question_data.choices):
                choice_dict = choice_data.dict()
                # Usar el order del choice_data si existe, sino usar idx
                if 'order' not in choice_dict or choice_dict['order'] is None:
                    choice_dict['order'] = idx
                    
                choice = QuestionChoice(
                    question_id=question.id,
                    **choice_dict
                )
                db.add(choice)
        
        return question
    
    def get_survey(
        self,
        db: Session,
        survey_id: int,
        gym_id: Optional[int] = None
    ) -> Optional[Survey]:
        """Obtener una encuesta por ID"""
        query = db.query(Survey).filter(Survey.id == survey_id)
        
        if gym_id:
            query = query.filter(Survey.gym_id == gym_id)
        
        return query.options(
            selectinload(Survey.questions).selectinload(SurveyQuestion.choices)
        ).first()
    
    def get_surveys(
        self,
        db: Session,
        gym_id: int,
        skip: int = 0,
        limit: int = 100,
        status_filter: Optional[SurveyStatus] = None,
        creator_id: Optional[int] = None,
        target_audience: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[Survey]:
        """Obtener lista de encuestas con filtros"""
        query = db.query(Survey).filter(Survey.gym_id == gym_id)
        
        if status_filter:
            query = query.filter(Survey.status == status_filter)
        
        if creator_id:
            query = query.filter(Survey.creator_id == creator_id)
        
        if target_audience:
            query = query.filter(Survey.target_audience == target_audience)
        
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    Survey.title.ilike(search_pattern),
                    Survey.description.ilike(search_pattern)
                )
            )
        
        # Ordenar por fecha de creación descendente
        query = query.order_by(desc(Survey.created_at))
        
        return query.offset(skip).limit(limit).all()
    
    def get_active_surveys(
        self,
        db: Session,
        gym_id: int,
        user_id: Optional[int] = None
    ) -> List[Survey]:
        """Obtener encuestas activas disponibles para un usuario"""
        now = datetime.utcnow()
        
        query = db.query(Survey).filter(
            and_(
                Survey.gym_id == gym_id,
                Survey.status == SurveyStatus.PUBLISHED,
                or_(Survey.start_date.is_(None), Survey.start_date <= now),
                or_(Survey.end_date.is_(None), Survey.end_date >= now)
            )
        )
        
        surveys = query.all()
        
        # Si hay user_id, filtrar las que ya respondió (si no permiten múltiples)
        if user_id:
            result = []
            for survey in surveys:
                if not survey.allow_multiple:
                    # Verificar si ya respondió
                    existing = db.query(SurveyResponse).filter(
                        and_(
                            SurveyResponse.survey_id == survey.id,
                            SurveyResponse.user_id == user_id,
                            SurveyResponse.is_complete == True
                        )
                    ).first()
                    
                    if not existing:
                        result.append(survey)
                else:
                    result.append(survey)
            
            return result
        
        return surveys
    
    def update_survey(
        self,
        db: Session,
        survey_id: int,
        survey_in: SurveyUpdate,
        gym_id: int
    ) -> Optional[Survey]:
        """Actualizar una encuesta"""
        survey = self.get_survey(db, survey_id, gym_id)
        
        if not survey:
            return None
        
        # No permitir editar encuestas publicadas (excepto para cerrarlas)
        if survey.status == SurveyStatus.PUBLISHED and survey_in.status != SurveyStatus.CLOSED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede editar una encuesta publicada"
            )
        
        update_data = survey_in.dict(exclude_unset=True)
        
        # Si se está publicando, guardar fecha
        if survey_in.status == SurveyStatus.PUBLISHED and survey.status == SurveyStatus.DRAFT:
            update_data['published_at'] = datetime.utcnow()
        
        for field, value in update_data.items():
            setattr(survey, field, value)
        
        db.add(survey)
        db.commit()
        db.refresh(survey)
        
        return survey
    
    def delete_survey(
        self,
        db: Session,
        survey_id: int,
        gym_id: int
    ) -> bool:
        """Eliminar una encuesta (solo si está en borrador)"""
        survey = self.get_survey(db, survey_id, gym_id)
        
        if not survey:
            return False
        
        if survey.status != SurveyStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Solo se pueden eliminar encuestas en borrador"
            )
        
        db.delete(survey)
        db.commit()
        
        return True
    
    def publish_survey(
        self,
        db: Session,
        survey_id: int,
        gym_id: int
    ) -> Optional[Survey]:
        """Publicar una encuesta"""
        survey = self.get_survey(db, survey_id, gym_id)
        
        if not survey:
            return None
        
        if survey.status != SurveyStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Solo se pueden publicar encuestas en borrador"
            )
        
        # Verificar que tenga al menos una pregunta
        if not survey.questions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La encuesta debe tener al menos una pregunta"
            )
        
        survey.status = SurveyStatus.PUBLISHED
        survey.published_at = datetime.utcnow()
        
        db.add(survey)
        db.commit()
        db.refresh(survey)
        
        return survey
    
    def close_survey(
        self,
        db: Session,
        survey_id: int,
        gym_id: int
    ) -> Optional[Survey]:
        """Cerrar una encuesta"""
        survey = self.get_survey(db, survey_id, gym_id)
        
        if not survey:
            return None
        
        if survey.status != SurveyStatus.PUBLISHED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Solo se pueden cerrar encuestas publicadas"
            )
        
        survey.status = SurveyStatus.CLOSED
        
        db.add(survey)
        db.commit()
        db.refresh(survey)
        
        return survey
    
    # ============= Response CRUD =============
    
    def create_response(
        self,
        db: Session,
        response_in: ResponseCreate,
        user_id: Optional[int],
        gym_id: int
    ) -> SurveyResponse:
        """Crear una respuesta completa a una encuesta"""
        # Verificar que la encuesta existe y está activa
        survey = self.get_survey(db, response_in.survey_id, gym_id)
        
        if not survey:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Encuesta no encontrada"
            )
        
        if survey.status != SurveyStatus.PUBLISHED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La encuesta no está disponible"
            )
        
        # Verificar fechas
        now = datetime.utcnow()
        if survey.start_date and survey.start_date > now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La encuesta aún no ha comenzado"
            )
        
        if survey.end_date and survey.end_date < now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La encuesta ha finalizado"
            )
        
        # Verificar si puede responder múltiples veces
        if user_id and not survey.allow_multiple:
            existing = db.query(SurveyResponse).filter(
                and_(
                    SurveyResponse.survey_id == survey.id,
                    SurveyResponse.user_id == user_id,
                    SurveyResponse.is_complete == True
                )
            ).first()
            
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Ya has respondido esta encuesta"
                )
        
        # Si es anónima, no guardar user_id
        if survey.is_anonymous:
            user_id = None
        
        try:
            # Crear respuesta
            response = SurveyResponse(
                survey_id=response_in.survey_id,
                user_id=user_id,
                gym_id=gym_id,
                event_id=response_in.event_id,
                started_at=datetime.utcnow()
            )
            db.add(response)
            db.flush()
            
            # Validar y crear answers
            self._validate_and_create_answers(
                db=db,
                response_id=response.id,
                answers=response_in.answers,
                survey=survey
            )
            
            # Marcar como completa
            response.is_complete = True
            response.completed_at = datetime.utcnow()
            
            db.commit()
            db.refresh(response)
            
            return response
            
        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"Error creando respuesta: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error guardando respuesta: {str(e)}"
            )
    
    def _validate_and_create_answers(
        self,
        db: Session,
        response_id: int,
        answers: List[AnswerCreate],
        survey: Survey
    ):
        """Validar y crear respuestas individuales"""
        # Crear diccionario de preguntas para validación rápida
        questions_dict = {q.id: q for q in survey.questions}
        
        # Verificar preguntas requeridas
        required_questions = {q.id for q in survey.questions if q.is_required}
        answered_questions = {a.question_id for a in answers}
        
        missing = required_questions - answered_questions
        if missing:
            missing_texts = [questions_dict[qid].question_text for qid in missing]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Faltan respuestas requeridas: {', '.join(missing_texts)}"
            )
        
        # Crear cada answer
        for answer_data in answers:
            question = questions_dict.get(answer_data.question_id)
            
            if not question:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Pregunta {answer_data.question_id} no encontrada"
                )
            
            # Validar tipo de respuesta
            self._validate_answer_type(answer_data, question)
            
            # Crear answer
            answer = SurveyAnswer(
                response_id=response_id,
                **answer_data.dict()
            )
            db.add(answer)
    
    def _validate_answer_type(self, answer: AnswerCreate, question: SurveyQuestion):
        """Validar que el tipo de respuesta coincida con el tipo de pregunta"""
        qt = question.question_type
        
        # Mapeo de tipos de pregunta a campos de respuesta esperados
        type_field_map = {
            QuestionType.TEXT: 'text_answer',
            QuestionType.TEXTAREA: 'text_answer',
            QuestionType.RADIO: 'choice_id',
            QuestionType.SELECT: 'choice_id',
            QuestionType.CHECKBOX: 'choice_ids',
            QuestionType.NUMBER: 'number_answer',
            QuestionType.SCALE: 'number_answer',
            QuestionType.NPS: 'number_answer',
            QuestionType.DATE: 'date_answer',
            QuestionType.TIME: 'date_answer',
            QuestionType.YES_NO: 'boolean_answer',
            QuestionType.EMAIL: 'text_answer',
            QuestionType.PHONE: 'text_answer'
        }
        
        expected_field = type_field_map.get(qt)
        
        if not expected_field:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tipo de pregunta {qt} no soportado"
            )
        
        # Verificar que el campo correcto tenga valor
        answer_dict = answer.dict()
        if not answer_dict.get(expected_field):
            # Permitir opción "Otro" si está habilitada
            if question.allow_other and answer.other_text:
                return
            
            if not question.is_required:
                return  # Pregunta opcional sin respuesta
            
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Respuesta inválida para pregunta: {question.question_text}"
            )
        
        # Validaciones específicas por tipo
        if qt in [QuestionType.NUMBER, QuestionType.SCALE, QuestionType.NPS]:
            value = answer.number_answer
            if question.min_value is not None and value < question.min_value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Valor mínimo para '{question.question_text}' es {question.min_value}"
                )
            if question.max_value is not None and value > question.max_value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Valor máximo para '{question.question_text}' es {question.max_value}"
                )
        
        elif qt in [QuestionType.TEXT, QuestionType.TEXTAREA, QuestionType.EMAIL, QuestionType.PHONE]:
            value = answer.text_answer
            if question.min_length and len(value) < question.min_length:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Longitud mínima para '{question.question_text}' es {question.min_length}"
                )
            if question.max_length and len(value) > question.max_length:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Longitud máxima para '{question.question_text}' es {question.max_length}"
                )
    
    def get_survey_responses(
        self,
        db: Session,
        survey_id: int,
        gym_id: int,
        skip: int = 0,
        limit: int = 100,
        only_complete: bool = True
    ) -> List[SurveyResponse]:
        """Obtener respuestas de una encuesta"""
        query = db.query(SurveyResponse).filter(
            and_(
                SurveyResponse.survey_id == survey_id,
                SurveyResponse.gym_id == gym_id
            )
        )
        
        if only_complete:
            query = query.filter(SurveyResponse.is_complete == True)
        
        return query.options(
            selectinload(SurveyResponse.answers),
            selectinload(SurveyResponse.user)
        ).order_by(desc(SurveyResponse.created_at)).offset(skip).limit(limit).all()
    
    def get_user_responses(
        self,
        db: Session,
        user_id: int,
        gym_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[SurveyResponse]:
        """Obtener respuestas de un usuario"""
        return db.query(SurveyResponse).filter(
            and_(
                SurveyResponse.user_id == user_id,
                SurveyResponse.gym_id == gym_id
            )
        ).options(
            selectinload(SurveyResponse.survey),
            selectinload(SurveyResponse.answers)
        ).order_by(desc(SurveyResponse.created_at)).offset(skip).limit(limit).all()
    
    # ============= Template CRUD =============
    
    def create_template(
        self,
        db: Session,
        template_in: TemplateCreate,
        gym_id: Optional[int] = None
    ) -> SurveyTemplate:
        """Crear una plantilla de encuesta"""
        template = SurveyTemplate(
            **template_in.dict(),
            gym_id=gym_id
        )
        db.add(template)
        db.commit()
        db.refresh(template)
        
        return template
    
    def get_templates(
        self,
        db: Session,
        gym_id: Optional[int] = None,
        category: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[SurveyTemplate]:
        """Obtener plantillas disponibles"""
        query = db.query(SurveyTemplate)
        
        # Plantillas públicas o del gimnasio específico
        if gym_id:
            query = query.filter(
                or_(
                    SurveyTemplate.is_public == True,
                    SurveyTemplate.gym_id == gym_id
                )
            )
        else:
            query = query.filter(SurveyTemplate.is_public == True)
        
        if category:
            query = query.filter(SurveyTemplate.category == category)
        
        return query.order_by(desc(SurveyTemplate.usage_count)).offset(skip).limit(limit).all()
    
    def create_survey_from_template(
        self,
        db: Session,
        template_id: int,
        title: str,
        description: Optional[str],
        creator_id: int,
        gym_id: int
    ) -> Survey:
        """Crear una encuesta desde una plantilla"""
        template = db.query(SurveyTemplate).filter(
            and_(
                SurveyTemplate.id == template_id,
                or_(
                    SurveyTemplate.is_public == True,
                    SurveyTemplate.gym_id == gym_id
                )
            )
        ).first()
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Plantilla no encontrada"
            )
        
        # Incrementar contador de uso
        template.usage_count += 1
        
        # Crear encuesta desde template_data
        template_data = template.template_data
        survey_data = {
            'title': title,
            'description': description or template_data.get('description', ''),
            'instructions': template_data.get('instructions', ''),
            'is_anonymous': template_data.get('is_anonymous', False),
            'allow_multiple': template_data.get('allow_multiple', False),
            'randomize_questions': template_data.get('randomize_questions', False),
            'show_progress': template_data.get('show_progress', True),
            'thank_you_message': template_data.get('thank_you_message', 'Gracias por completar la encuesta'),
            'tags': template_data.get('tags', []),
            'target_audience': template_data.get('target_audience')
        }
        
        # Crear encuesta
        survey = Survey(
            **survey_data,
            creator_id=creator_id,
            gym_id=gym_id,
            status=SurveyStatus.DRAFT
        )
        db.add(survey)
        db.flush()
        
        # Crear preguntas desde template
        for question_data in template_data.get('questions', []):
            question = SurveyQuestion(
                survey_id=survey.id,
                **{k: v for k, v in question_data.items() if k != 'choices'}
            )
            db.add(question)
            db.flush()
            
            # Crear opciones
            for choice_data in question_data.get('choices', []):
                choice = QuestionChoice(
                    question_id=question.id,
                    **choice_data
                )
                db.add(choice)
        
        db.commit()
        db.refresh(survey)
        
        return survey


# Instancia singleton del repositorio
survey_repository = SurveyRepository()