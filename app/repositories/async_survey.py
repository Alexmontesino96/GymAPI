"""
AsyncSurveyRepository - Repositorio async para sistema de encuestas.

Este repositorio NO hereda de AsyncBaseRepository porque Survey tiene
una estructura jerárquica compleja con múltiples niveles de relaciones:
Survey -> Questions -> Choices -> Responses -> Answers

Gestiona el ciclo completo de encuestas: creación, publicación, respuestas,
templates y análisis de resultados.

Migrado en FASE 2 de la conversión sync → async.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import and_, or_, func, desc, select
from fastapi import HTTPException, status
import logging

from app.models.survey import (
    Survey, SurveyQuestion, QuestionChoice, SurveyResponse,
    SurveyAnswer, SurveyTemplate, SurveyStatus, QuestionType
)
from app.schemas.survey import (
    SurveyCreate, SurveyUpdate, SurveyQuestionCreate,
    ResponseCreate, AnswerCreate, TemplateCreate
)

logger = logging.getLogger(__name__)


class AsyncSurveyRepository:
    """
    Repositorio async para operaciones de encuestas.

    Este repositorio NO hereda de AsyncBaseRepository porque Survey
    tiene relaciones complejas multinivel y lógica de negocio específica.

    Métodos principales:
    
    **Survey CRUD:**
    - create_survey() - Crear encuesta con preguntas
    - get_survey() - Obtener encuesta con relaciones cargadas
    - get_surveys() - Listar con filtros
    - get_surveys_with_response_count() - Con contadores de respuestas
    - get_active_surveys() - Encuestas activas disponibles
    - update_survey() - Actualizar (con validaciones de estado)
    - delete_survey() - Eliminar (solo borradores)
    - publish_survey() - Publicar encuesta
    - close_survey() - Cerrar encuesta publicada
    
    **Response CRUD:**
    - create_response() - Crear respuesta completa
    - get_survey_responses() - Respuestas de una encuesta
    - get_user_responses() - Respuestas de un usuario
    
    **Template CRUD:**
    - create_template() - Crear plantilla reutilizable
    - get_templates() - Obtener plantillas disponibles
    - create_survey_from_template() - Instanciar desde plantilla
    """

    # ============= Survey CRUD =============

    async def _create_question(
        self,
        db: AsyncSession,
        survey_id: int,
        question_data: SurveyQuestionCreate,
        order: int
    ) -> SurveyQuestion:
        """
        Helper para crear una pregunta con opciones.

        Args:
            db: Sesión async de base de datos
            survey_id: ID de la encuesta padre
            question_data: Datos de la pregunta
            order: Orden de la pregunta en la encuesta

        Returns:
            Pregunta creada con opciones (si aplica)

        Note:
            Si la pregunta es de tipo selección (multiple choice, rating),
            también crea las opciones asociadas.
        """
        question_dict = question_data.dict(exclude={'choices'})
        question_dict['order'] = order
        question = SurveyQuestion(
            survey_id=survey_id,
            **question_dict
        )
        db.add(question)
        await db.flush()

        # Crear opciones si es pregunta de selección
        if question_data.choices:
            for idx, choice_data in enumerate(question_data.choices):
                choice_dict = choice_data.dict()
                if 'order' not in choice_dict or choice_dict['order'] is None:
                    choice_dict['order'] = idx

                choice = QuestionChoice(
                    question_id=question.id,
                    **choice_dict
                )
                db.add(choice)

        return question

    async def create_survey(
        self,
        db: AsyncSession,
        survey_in: SurveyCreate,
        creator_id: int,
        gym_id: int
    ) -> Survey:
        """
        Crear una nueva encuesta con preguntas.

        Args:
            db: Sesión async de base de datos
            survey_in: Datos de la encuesta con preguntas
            creator_id: ID del usuario creador
            gym_id: ID del gimnasio (multi-tenant)

        Returns:
            Encuesta creada con todas sus preguntas y opciones

        Raises:
            HTTPException: Si hay error en la creación

        Note:
            La encuesta se crea en estado DRAFT.
            Incluye transacción completa: encuesta + preguntas + opciones.
        """
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
            await db.flush()

            # Crear preguntas y opciones
            for idx, question_data in enumerate(survey_in.questions or []):
                question = await self._create_question(
                    db=db,
                    survey_id=survey.id,
                    question_data=question_data,
                    order=idx
                )
                survey.questions.append(question)

            await db.flush()
            await db.refresh(survey)
            return survey

        except Exception as e:
            await db.rollback()
            logger.error(f"Error creando encuesta: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error creando encuesta: {str(e)}"
            )

    async def get_survey(
        self,
        db: AsyncSession,
        survey_id: int,
        gym_id: Optional[int] = None
    ) -> Optional[Survey]:
        """
        Obtener una encuesta por ID con relaciones cargadas.

        Args:
            db: Sesión async de base de datos
            survey_id: ID de la encuesta
            gym_id: ID del gimnasio para validación multi-tenant (opcional)

        Returns:
            Encuesta con questions y choices cargados, o None

        Note:
            Usa selectinload para eager loading eficiente.
        """
        stmt = select(Survey).where(Survey.id == survey_id)

        if gym_id:
            stmt = stmt.where(Survey.gym_id == gym_id)

        stmt = stmt.options(
            selectinload(Survey.questions).selectinload(SurveyQuestion.choices)
        )

        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_surveys(
        self,
        db: AsyncSession,
        gym_id: int,
        skip: int = 0,
        limit: int = 100,
        status_filter: Optional[SurveyStatus] = None,
        creator_id: Optional[int] = None,
        target_audience: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[Survey]:
        """
        Obtener lista de encuestas con filtros.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio (multi-tenant)
            skip: Registros a omitir (paginación)
            limit: Máximo de registros
            status_filter: Filtrar por estado (DRAFT, PUBLISHED, CLOSED)
            creator_id: Filtrar por creador
            target_audience: Filtrar por audiencia objetivo
            search: Búsqueda en título y descripción

        Returns:
            Lista de encuestas ordenadas por fecha de creación

        Note:
            La búsqueda es case-insensitive.
        """
        stmt = select(Survey).where(Survey.gym_id == gym_id)

        if status_filter:
            stmt = stmt.where(Survey.status == status_filter)

        if creator_id:
            stmt = stmt.where(Survey.creator_id == creator_id)

        if target_audience:
            stmt = stmt.where(Survey.target_audience == target_audience)

        if search:
            search_pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    Survey.title.ilike(search_pattern),
                    Survey.description.ilike(search_pattern)
                )
            )

        stmt = stmt.order_by(desc(Survey.created_at)).offset(skip).limit(limit)

        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_surveys_with_response_count(
        self,
        db: AsyncSession,
        gym_id: int,
        skip: int = 0,
        limit: int = 100,
        status_filter: Optional[SurveyStatus] = None,
        search: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Obtener encuestas con conteo de respuestas.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio (multi-tenant)
            skip: Registros a omitir
            limit: Máximo de registros
            status_filter: Filtrar por estado
            search: Búsqueda en título/descripción

        Returns:
            Lista de diccionarios con survey + response_count

        Note:
            Usa LEFT JOIN para incluir encuestas sin respuestas.
        """
        stmt = (
            select(
                Survey,
                func.count(SurveyResponse.id).label('response_count')
            )
            .outerjoin(SurveyResponse, Survey.id == SurveyResponse.survey_id)
            .where(Survey.gym_id == gym_id)
            .group_by(Survey.id)
        )

        if status_filter:
            stmt = stmt.where(Survey.status == status_filter)

        if search:
            search_pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    Survey.title.ilike(search_pattern),
                    Survey.description.ilike(search_pattern)
                )
            )

        stmt = stmt.order_by(desc(Survey.created_at)).offset(skip).limit(limit)

        result = await db.execute(stmt)
        results = result.all()

        surveys_with_count = []
        for survey, count in results:
            survey_dict = survey.__dict__.copy()
            survey_dict['response_count'] = count
            surveys_with_count.append(survey_dict)

        return surveys_with_count

    async def get_active_surveys(
        self,
        db: AsyncSession,
        gym_id: int,
        user_id: Optional[int] = None
    ) -> List[Survey]:
        """
        Obtener encuestas activas disponibles para un usuario.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio (multi-tenant)
            user_id: ID del usuario para filtrar ya respondidas (opcional)

        Returns:
            Lista de encuestas publicadas y dentro de fechas válidas

        Note:
            - Solo encuestas PUBLISHED
            - Dentro del rango start_date - end_date
            - Si user_id, excluye encuestas ya respondidas (si allow_multiple=False)
        """
        now = datetime.utcnow()

        stmt = select(Survey).where(
            and_(
                Survey.gym_id == gym_id,
                Survey.status == SurveyStatus.PUBLISHED,
                or_(Survey.start_date.is_(None), Survey.start_date <= now),
                or_(Survey.end_date.is_(None), Survey.end_date >= now)
            )
        )

        result = await db.execute(stmt)
        surveys = list(result.scalars().all())

        # Si hay user_id, filtrar las que ya respondió
        if user_id:
            filtered = []
            for survey in surveys:
                if not survey.allow_multiple:
                    # Verificar si ya respondió
                    check_stmt = select(SurveyResponse).where(
                        and_(
                            SurveyResponse.survey_id == survey.id,
                            SurveyResponse.user_id == user_id,
                            SurveyResponse.is_complete == True
                        )
                    )
                    check_result = await db.execute(check_stmt)
                    existing = check_result.scalar_one_or_none()

                    if not existing:
                        filtered.append(survey)
                else:
                    filtered.append(survey)

            return filtered

        return surveys

    async def update_survey(
        self,
        db: AsyncSession,
        survey_id: int,
        survey_in: SurveyUpdate,
        gym_id: int
    ) -> Optional[Survey]:
        """
        Actualizar una encuesta.

        Args:
            db: Sesión async de base de datos
            survey_id: ID de la encuesta
            survey_in: Datos de actualización
            gym_id: ID del gimnasio (validación multi-tenant)

        Returns:
            Encuesta actualizada o None si no existe

        Raises:
            HTTPException: Si intenta editar encuesta publicada

        Note:
            - No se pueden editar encuestas PUBLISHED (excepto cerrarlas)
            - Al publicar se guarda published_at automáticamente
        """
        survey = await self.get_survey(db, survey_id, gym_id)

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
        await db.flush()
        await db.refresh(survey)

        return survey

    async def delete_survey(
        self,
        db: AsyncSession,
        survey_id: int,
        gym_id: int
    ) -> bool:
        """
        Eliminar una encuesta.

        Args:
            db: Sesión async de base de datos
            survey_id: ID de la encuesta
            gym_id: ID del gimnasio (validación multi-tenant)

        Returns:
            True si se eliminó, False si no existía

        Raises:
            HTTPException: Si intenta eliminar encuesta publicada

        Note:
            Solo se pueden eliminar encuestas en estado DRAFT.
        """
        survey = await self.get_survey(db, survey_id, gym_id)

        if not survey:
            return False

        if survey.status != SurveyStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Solo se pueden eliminar encuestas en borrador"
            )

        db.delete(survey)
        await db.flush()

        return True

    async def publish_survey(
        self,
        db: AsyncSession,
        survey_id: int,
        gym_id: int
    ) -> Optional[Survey]:
        """
        Publicar una encuesta.

        Args:
            db: Sesión async de base de datos
            survey_id: ID de la encuesta
            gym_id: ID del gimnasio (validación multi-tenant)

        Returns:
            Encuesta publicada o None si no existe

        Raises:
            HTTPException: Si no es borrador o no tiene preguntas

        Note:
            - Solo encuestas DRAFT pueden publicarse
            - Debe tener al menos una pregunta
            - Actualiza published_at automáticamente
        """
        survey = await self.get_survey(db, survey_id, gym_id)

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
        await db.flush()
        await db.refresh(survey)

        return survey

    async def close_survey(
        self,
        db: AsyncSession,
        survey_id: int,
        gym_id: int
    ) -> Optional[Survey]:
        """
        Cerrar una encuesta publicada.

        Args:
            db: Sesión async de base de datos
            survey_id: ID de la encuesta
            gym_id: ID del gimnasio (validación multi-tenant)

        Returns:
            Encuesta cerrada o None si no existe

        Raises:
            HTTPException: Si no está publicada

        Note:
            Solo encuestas PUBLISHED pueden cerrarse.
            Una vez cerrada no acepta más respuestas.
        """
        survey = await self.get_survey(db, survey_id, gym_id)

        if not survey:
            return None

        if survey.status != SurveyStatus.PUBLISHED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Solo se pueden cerrar encuestas publicadas"
            )

        survey.status = SurveyStatus.CLOSED

        db.add(survey)
        await db.flush()
        await db.refresh(survey)

        return survey

    # ============= Response CRUD =============

    def _validate_answer_type(self, answer: AnswerCreate, question: SurveyQuestion):
        """
        Validar que el tipo de respuesta coincida con el tipo de pregunta.

        Args:
            answer: Respuesta a validar
            question: Pregunta asociada

        Raises:
            HTTPException: Si el tipo no coincide

        Note:
            Método sync usado internamente por create_response.
        """
        if question.question_type == QuestionType.TEXT:
            if not answer.text_answer:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Pregunta '{question.question_text}' requiere respuesta de texto"
                )
        elif question.question_type in [QuestionType.SINGLE_CHOICE, QuestionType.MULTIPLE_CHOICE]:
            if not answer.choice_ids:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Pregunta '{question.question_text}' requiere seleccionar opciones"
                )
        elif question.question_type == QuestionType.RATING:
            if answer.rating_value is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Pregunta '{question.question_text}' requiere calificación"
                )

    async def _validate_and_create_answers(
        self,
        db: AsyncSession,
        response_id: int,
        answers: List[AnswerCreate],
        survey: Survey
    ):
        """
        Validar y crear respuestas individuales.

        Args:
            db: Sesión async de base de datos
            response_id: ID de la respuesta padre
            answers: Lista de respuestas a crear
            survey: Encuesta con preguntas cargadas

        Raises:
            HTTPException: Si faltan respuestas requeridas o tipo incorrecto

        Note:
            - Valida que todas las preguntas requeridas estén respondidas
            - Valida tipos de respuestas
            - Crea todos los SurveyAnswer asociados
        """
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

    async def create_response(
        self,
        db: AsyncSession,
        response_in: ResponseCreate,
        user_id: Optional[int],
        gym_id: int
    ) -> SurveyResponse:
        """
        Crear una respuesta completa a una encuesta.

        Args:
            db: Sesión async de base de datos
            response_in: Datos de la respuesta con todas las respuestas
            user_id: ID del usuario (None si es anónima)
            gym_id: ID del gimnasio (multi-tenant)

        Returns:
            Respuesta completa creada

        Raises:
            HTTPException: Si encuesta no disponible o respuesta inválida

        Note:
            Validaciones:
            - Encuesta debe estar PUBLISHED
            - Dentro del rango de fechas
            - Usuario no debe haber respondido antes (si allow_multiple=False)
            - Todas las preguntas requeridas respondidas
            - Tipos de respuestas correctos
        """
        # Verificar que la encuesta existe y está activa
        survey = await self.get_survey(db, response_in.survey_id, gym_id)

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
            check_stmt = select(SurveyResponse).where(
                and_(
                    SurveyResponse.survey_id == survey.id,
                    SurveyResponse.user_id == user_id,
                    SurveyResponse.is_complete == True
                )
            )
            check_result = await db.execute(check_stmt)
            existing = check_result.scalar_one_or_none()

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
            await db.flush()

            # Validar y crear answers
            await self._validate_and_create_answers(
                db=db,
                response_id=response.id,
                answers=response_in.answers,
                survey=survey
            )

            # Marcar como completa
            response.is_complete = True
            response.completed_at = datetime.utcnow()

            await db.flush()
            await db.refresh(response)

            return response

        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            logger.error(f"Error creando respuesta: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error guardando respuesta: {str(e)}"
            )

    async def get_survey_responses(
        self,
        db: AsyncSession,
        survey_id: int,
        gym_id: int,
        skip: int = 0,
        limit: int = 100,
        only_complete: bool = True
    ) -> List[SurveyResponse]:
        """
        Obtener respuestas de una encuesta.

        Args:
            db: Sesión async de base de datos
            survey_id: ID de la encuesta
            gym_id: ID del gimnasio (validación multi-tenant)
            skip: Registros a omitir
            limit: Máximo de registros
            only_complete: Solo respuestas completas

        Returns:
            Lista de respuestas con answers y user cargados

        Note:
            Usa selectinload para eager loading eficiente.
        """
        stmt = select(SurveyResponse).where(
            and_(
                SurveyResponse.survey_id == survey_id,
                SurveyResponse.gym_id == gym_id
            )
        )

        if only_complete:
            stmt = stmt.where(SurveyResponse.is_complete == True)

        stmt = stmt.options(
            selectinload(SurveyResponse.answers),
            selectinload(SurveyResponse.user)
        ).order_by(desc(SurveyResponse.created_at)).offset(skip).limit(limit)

        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_user_responses(
        self,
        db: AsyncSession,
        user_id: int,
        gym_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[SurveyResponse]:
        """
        Obtener respuestas de un usuario.

        Args:
            db: Sesión async de base de datos
            user_id: ID del usuario
            gym_id: ID del gimnasio (multi-tenant)
            skip: Registros a omitir
            limit: Máximo de registros

        Returns:
            Lista de respuestas con survey y answers cargados

        Note:
            Útil para ver historial de encuestas del usuario.
        """
        stmt = select(SurveyResponse).where(
            and_(
                SurveyResponse.user_id == user_id,
                SurveyResponse.gym_id == gym_id
            )
        ).options(
            selectinload(SurveyResponse.survey),
            selectinload(SurveyResponse.answers)
        ).order_by(desc(SurveyResponse.created_at)).offset(skip).limit(limit)

        result = await db.execute(stmt)
        return list(result.scalars().all())

    # ============= Template CRUD =============

    async def create_template(
        self,
        db: AsyncSession,
        template_in: TemplateCreate,
        gym_id: Optional[int] = None
    ) -> SurveyTemplate:
        """
        Crear una plantilla de encuesta reutilizable.

        Args:
            db: Sesión async de base de datos
            template_in: Datos de la plantilla
            gym_id: ID del gimnasio (None para plantillas públicas)

        Returns:
            Plantilla creada

        Note:
            - Si gym_id=None, la plantilla es global
            - Si gym_id presente, es privada del gimnasio
        """
        template = SurveyTemplate(
            **template_in.dict(),
            gym_id=gym_id
        )
        db.add(template)
        await db.flush()
        await db.refresh(template)

        return template

    async def get_templates(
        self,
        db: AsyncSession,
        gym_id: Optional[int] = None,
        category: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[SurveyTemplate]:
        """
        Obtener plantillas disponibles.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio (para incluir plantillas privadas)
            category: Filtrar por categoría
            skip: Registros a omitir
            limit: Máximo de registros

        Returns:
            Lista de plantillas ordenadas por uso

        Note:
            - Si gym_id presente: plantillas públicas + privadas del gimnasio
            - Si gym_id=None: solo plantillas públicas
        """
        stmt = select(SurveyTemplate)

        # Plantillas públicas o del gimnasio específico
        if gym_id:
            stmt = stmt.where(
                or_(
                    SurveyTemplate.is_public == True,
                    SurveyTemplate.gym_id == gym_id
                )
            )
        else:
            stmt = stmt.where(SurveyTemplate.is_public == True)

        if category:
            stmt = stmt.where(SurveyTemplate.category == category)

        stmt = stmt.order_by(desc(SurveyTemplate.usage_count)).offset(skip).limit(limit)

        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def create_survey_from_template(
        self,
        db: AsyncSession,
        template_id: int,
        title: str,
        description: Optional[str],
        creator_id: int,
        gym_id: int
    ) -> Survey:
        """
        Crear una encuesta desde una plantilla.

        Args:
            db: Sesión async de base de datos
            template_id: ID de la plantilla
            title: Título de la nueva encuesta
            description: Descripción (opcional, usa de template si no se provee)
            creator_id: ID del usuario creador
            gym_id: ID del gimnasio (multi-tenant)

        Returns:
            Nueva encuesta en estado DRAFT con todas las preguntas

        Raises:
            HTTPException: Si plantilla no encontrada o no accesible

        Note:
            - Incrementa usage_count de la plantilla
            - Copia toda la estructura: preguntas + opciones
            - La encuesta se crea en DRAFT para personalización
        """
        stmt = select(SurveyTemplate).where(
            and_(
                SurveyTemplate.id == template_id,
                or_(
                    SurveyTemplate.is_public == True,
                    SurveyTemplate.gym_id == gym_id
                )
            )
        )
        result = await db.execute(stmt)
        template = result.scalar_one_or_none()

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
        await db.flush()

        # Crear preguntas desde template
        for question_data in template_data.get('questions', []):
            question = SurveyQuestion(
                survey_id=survey.id,
                **{k: v for k, v in question_data.items() if k != 'choices'}
            )
            db.add(question)
            await db.flush()

            # Crear opciones
            for choice_data in question_data.get('choices', []):
                choice = QuestionChoice(
                    question_id=question.id,
                    **choice_data
                )
                db.add(choice)

        await db.flush()
        await db.refresh(survey)

        return survey


# Instancia singleton del repositorio async
async_survey_repository = AsyncSurveyRepository()
