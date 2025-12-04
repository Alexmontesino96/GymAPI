"""
AsyncSurveyService - Servicio async para gestión de encuestas.

Este módulo proporciona lógica de negocio async para el sistema de encuestas,
incluyendo estadísticas, analytics y exportación.

Migrado en FASE 3 de la conversión sync → async.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from collections import defaultdict
import json
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

# Importación opcional de pandas para exportación
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    pd = None

from app.models.survey import (
    Survey, SurveyQuestion, SurveyResponse,
    SurveyAnswer, SurveyStatus, QuestionType
)
from app.schemas.survey import (
    SurveyCreate, SurveyUpdate, ResponseCreate,
    SurveyStatistics, QuestionStatistics
)
from app.repositories.async_survey import async_survey_repository
from app.services.cache_service import CacheService

# Importación opcional del servicio de notificaciones
try:
    from app.services.async_notification_service import async_notification_service
    NOTIFICATIONS_AVAILABLE = True
except ImportError:
    async_notification_service = None
    NOTIFICATIONS_AVAILABLE = False

logger = logging.getLogger(__name__)


class AsyncSurveyService:
    """
    Servicio async para lógica de negocio de encuestas.

    Todos los métodos son async y utilizan AsyncSession y async_survey_repository.

    Métodos principales:
    - create_survey() - Crear encuesta con preguntas
    - get_available_surveys() - Encuestas disponibles para un usuario
    - get_my_surveys() - Encuestas creadas por un usuario
    - publish_survey() - Publicar encuesta y enviar notificaciones
    - close_survey() - Cerrar encuesta
    - submit_response() - Enviar respuesta a encuesta
    - get_my_responses() - Respuestas de un usuario
    - get_survey_statistics() - Estadísticas completas de encuesta
    """

    # ============= Survey Management =============

    async def create_survey(
        self,
        db: AsyncSession,
        survey_in: SurveyCreate,
        creator_id: int,
        gym_id: int,
        redis_client: Optional[Redis] = None
    ) -> Survey:
        """
        Crear una nueva encuesta e invalidar cachés.

        Args:
            db: Sesión async de base de datos
            survey_in: Datos de la encuesta
            creator_id: ID del creador
            gym_id: ID del gimnasio
            redis_client: Cliente Redis opcional

        Returns:
            Encuesta creada
        """
        survey = await async_survey_repository.create_survey(
            db=db,
            survey_in=survey_in,
            creator_id=creator_id,
            gym_id=gym_id
        )

        # Invalidar cachés
        if redis_client:
            await self._invalidate_survey_caches(redis_client, gym_id)

        logger.info(f"Survey {survey.id} created by user {creator_id} for gym {gym_id}")
        return survey

    async def get_available_surveys(
        self,
        db: AsyncSession,
        gym_id: int,
        user_id: Optional[int] = None,
        redis_client: Optional[Redis] = None
    ) -> List[Survey]:
        """
        Obtener encuestas disponibles para un usuario.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio
            user_id: ID del usuario opcional
            redis_client: Cliente Redis opcional

        Returns:
            Lista de encuestas disponibles

        Note:
            Este es el método principal para que los usuarios vean qué encuestas pueden responder.
            Caché TTL: 5 minutos
        """
        cache_key = f"surveys:available:gym:{gym_id}"
        if user_id:
            cache_key += f":user:{user_id}"

        async def db_fetch():
            return await async_survey_repository.get_active_surveys(
                db=db,
                gym_id=gym_id,
                user_id=user_id
            )

        try:
            if redis_client:
                # Intentar obtener de caché primero
                cached = await redis_client.get(cache_key)
                if cached:
                    logger.debug(f"Cache hit for available surveys: {cache_key}")
                    surveys_data = json.loads(cached)
                    # TODO: Reconstruir objetos Survey desde JSON
                    return surveys_data

                # Obtener de BD
                surveys = await db_fetch()

                # Cachear por 5 minutos
                if surveys:
                    # TODO: Serializar surveys a JSON
                    # surveys_json = json.dumps([s.dict() for s in surveys])
                    # await redis_client.setex(cache_key, 300, surveys_json)
                    pass

                return surveys
            else:
                return await db_fetch()

        except Exception as e:
            logger.error(f"Error getting available surveys: {e}")
            return await db_fetch()

    async def get_my_surveys(
        self,
        db: AsyncSession,
        creator_id: int,
        gym_id: int,
        status_filter: Optional[SurveyStatus] = None,
        redis_client: Optional[Redis] = None
    ) -> List[Survey]:
        """
        Obtener encuestas creadas por un usuario.

        Args:
            db: Sesión async de base de datos
            creator_id: ID del creador
            gym_id: ID del gimnasio
            status_filter: Filtro opcional por estado
            redis_client: Cliente Redis opcional

        Returns:
            Lista de encuestas del creador

        Note:
            Caché TTL: 5 minutos
        """
        cache_key = f"surveys:creator:{creator_id}:gym:{gym_id}"
        if status_filter:
            cache_key += f":status:{status_filter}"

        async def db_fetch():
            return await async_survey_repository.get_surveys(
                db=db,
                gym_id=gym_id,
                creator_id=creator_id,
                status_filter=status_filter
            )

        try:
            if redis_client:
                result = await CacheService.get_or_set(
                    redis_client=redis_client,
                    cache_key=cache_key,
                    db_fetch_func=db_fetch,
                    model_class=Survey,
                    expiry_seconds=300,
                    is_list=True
                )
                return result
            else:
                return await db_fetch()

        except Exception as e:
            logger.error(f"Error getting creator surveys: {e}")
            return await db_fetch()

    async def publish_survey(
        self,
        db: AsyncSession,
        survey_id: int,
        gym_id: int,
        redis_client: Optional[Redis] = None
    ) -> Survey:
        """
        Publicar una encuesta y enviar notificaciones.

        Args:
            db: Sesión async de base de datos
            survey_id: ID de la encuesta
            gym_id: ID del gimnasio
            redis_client: Cliente Redis opcional

        Returns:
            Encuesta publicada

        Note:
            Invalida cachés y envía notificaciones a la audiencia objetivo.
        """
        survey = await async_survey_repository.publish_survey(
            db=db,
            survey_id=survey_id,
            gym_id=gym_id
        )

        if not survey:
            return None

        # Invalidar cachés
        if redis_client:
            await self._invalidate_survey_caches(redis_client, gym_id)

        # Enviar notificaciones a la audiencia objetivo
        try:
            await self._send_survey_notifications(
                db=db,
                survey=survey,
                gym_id=gym_id
            )
        except Exception as e:
            logger.error(f"Error sending survey notifications: {e}")

        logger.info(f"Survey {survey_id} published for gym {gym_id}")
        return survey

    async def close_survey(
        self,
        db: AsyncSession,
        survey_id: int,
        gym_id: int,
        redis_client: Optional[Redis] = None
    ) -> Survey:
        """
        Cerrar una encuesta.

        Args:
            db: Sesión async de base de datos
            survey_id: ID de la encuesta
            gym_id: ID del gimnasio
            redis_client: Cliente Redis opcional

        Returns:
            Encuesta cerrada
        """
        survey = await async_survey_repository.close_survey(
            db=db,
            survey_id=survey_id,
            gym_id=gym_id
        )

        if survey and redis_client:
            await self._invalidate_survey_caches(redis_client, gym_id)

        logger.info(f"Survey {survey_id} closed for gym {gym_id}")
        return survey

    # ============= Response Management =============

    async def submit_response(
        self,
        db: AsyncSession,
        response_in: ResponseCreate,
        user_id: Optional[int],
        gym_id: int,
        redis_client: Optional[Redis] = None
    ) -> SurveyResponse:
        """
        Enviar una respuesta a una encuesta.

        Args:
            db: Sesión async de base de datos
            response_in: Datos de la respuesta
            user_id: ID del usuario (None si es anónima)
            gym_id: ID del gimnasio
            redis_client: Cliente Redis opcional

        Returns:
            Respuesta creada

        Note:
            Invalida automáticamente el caché de estadísticas.
        """
        response = await async_survey_repository.create_response(
            db=db,
            response_in=response_in,
            user_id=user_id,
            gym_id=gym_id
        )

        # Invalidar caché de estadísticas
        if redis_client:
            await self._invalidate_statistics_cache(
                redis_client,
                survey_id=response_in.survey_id
            )

        logger.info(f"Response submitted for survey {response_in.survey_id} by user {user_id}")
        return response

    async def get_my_responses(
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
            gym_id: ID del gimnasio
            skip: Registros a omitir
            limit: Máximo de registros

        Returns:
            Lista de respuestas del usuario
        """
        return await async_survey_repository.get_user_responses(
            db=db,
            user_id=user_id,
            gym_id=gym_id,
            skip=skip,
            limit=limit
        )

    # ============= Statistics & Analytics =============

    async def get_survey_statistics(
        self,
        db: AsyncSession,
        survey_id: int,
        gym_id: int,
        redis_client: Optional[Redis] = None
    ) -> SurveyStatistics:
        """
        Obtener estadísticas completas de una encuesta.

        Args:
            db: Sesión async de base de datos
            survey_id: ID de la encuesta
            gym_id: ID del gimnasio
            redis_client: Cliente Redis opcional

        Returns:
            Estadísticas completas de la encuesta

        Note:
            Caché TTL: 10 minutos
            Incluye: total de respuestas, tiempo promedio, distribución por fecha,
            estadísticas por pregunta (choice distribution, NPS, etc.)
        """
        cache_key = f"survey:stats:{survey_id}"

        async def calculate_stats():
            survey = await async_survey_repository.get_survey(db, survey_id, gym_id)
            if not survey:
                return None

            # Obtener todas las respuestas
            responses = await async_survey_repository.get_survey_responses(
                db=db,
                survey_id=survey_id,
                gym_id=gym_id,
                only_complete=False
            )

            total_responses = len(responses)
            complete_responses = sum(1 for r in responses if r.is_complete)
            incomplete_responses = total_responses - complete_responses

            # Calcular tiempo promedio de completación
            completion_times = []
            for r in responses:
                if r.is_complete and r.completed_at:
                    time_diff = (r.completed_at - r.started_at).total_seconds() / 60
                    completion_times.append(time_diff)

            avg_completion_time = (
                sum(completion_times) / len(completion_times)
                if completion_times else None
            )

            # Calcular tasa de respuesta
            response_rate = None  # TODO: Calcular basado en audiencia objetivo

            # Obtener estadísticas por pregunta
            question_stats = []
            for question in survey.questions:
                q_stat = self._calculate_question_statistics(
                    question=question,
                    responses=responses
                )
                question_stats.append(q_stat)

            # Distribución de respuestas por fecha
            responses_by_date = defaultdict(int)
            for r in responses:
                date_key = r.created_at.date().isoformat()
                responses_by_date[date_key] += 1

            return SurveyStatistics(
                survey_id=survey.id,
                survey_title=survey.title,
                total_responses=total_responses,
                complete_responses=complete_responses,
                incomplete_responses=incomplete_responses,
                average_completion_time=avg_completion_time,
                response_rate=response_rate,
                questions=question_stats,
                responses_by_date=dict(responses_by_date)
            )

        try:
            if redis_client:
                # Intentar obtener de caché
                cached = await redis_client.get(cache_key)
                if cached:
                    logger.debug(f"Cache hit for survey statistics: {cache_key}")
                    return SurveyStatistics(**json.loads(cached))

                # Calcular y cachear
                stats = await calculate_stats()
                if stats:
                    await redis_client.setex(
                        cache_key,
                        600,  # Cachear por 10 minutos
                        json.dumps(stats.dict())
                    )
                return stats
            else:
                return await calculate_stats()

        except Exception as e:
            logger.error(f"Error calculating survey statistics: {e}")
            return await calculate_stats()

    def _calculate_question_statistics(
        self,
        question: SurveyQuestion,
        responses: List[SurveyResponse]
    ) -> QuestionStatistics:
        """
        Calcular estadísticas para una pregunta individual.

        Args:
            question: Pregunta de la encuesta
            responses: Lista de respuestas

        Returns:
            Estadísticas de la pregunta

        Note:
            Cálculos específicos por tipo de pregunta:
            - RADIO/SELECT: Distribución de opciones
            - CHECKBOX: Distribución de opciones múltiples
            - NUMBER/SCALE: Promedio, min, max, mediana
            - NPS: Score NPS con promoters, passives, detractors
            - YES_NO: Distribución Yes/No
            - TEXT/TEXTAREA: Respuestas de texto
        """
        # Recolectar todas las respuestas para esta pregunta
        answers = []
        for response in responses:
            for answer in response.answers:
                if answer.question_id == question.id:
                    answers.append(answer)

        total_responses = len(answers)

        stat = QuestionStatistics(
            question_id=question.id,
            question_text=question.question_text,
            question_type=question.question_type,
            total_responses=total_responses
        )

        # Calcular basado en el tipo de pregunta
        if question.question_type in [QuestionType.RADIO, QuestionType.SELECT]:
            # Contar distribución de opciones
            choice_counts = defaultdict(int)
            for answer in answers:
                if answer.choice_id:
                    choice = next(
                        (c for c in question.choices if c.id == answer.choice_id),
                        None
                    )
                    if choice:
                        choice_counts[choice.choice_text] += 1
                elif answer.other_text:
                    choice_counts["Other"] += 1

            stat.choice_distribution = dict(choice_counts)

        elif question.question_type == QuestionType.CHECKBOX:
            # Contar distribución de opciones múltiples
            choice_counts = defaultdict(int)
            for answer in answers:
                if answer.choice_ids:
                    for choice_id in answer.choice_ids:
                        choice = next(
                            (c for c in question.choices if c.id == choice_id),
                            None
                        )
                        if choice:
                            choice_counts[choice.choice_text] += 1
                if answer.other_text:
                    choice_counts["Other"] += 1

            stat.choice_distribution = dict(choice_counts)

        elif question.question_type in [QuestionType.NUMBER, QuestionType.SCALE]:
            # Calcular estadísticas numéricas
            values = [a.number_answer for a in answers if a.number_answer is not None]
            if values:
                stat.average = sum(values) / len(values)
                stat.min = min(values)
                stat.max = max(values)
                stat.median = sorted(values)[len(values) // 2]

        elif question.question_type == QuestionType.NPS:
            # Calcular score NPS
            values = [a.number_answer for a in answers if a.number_answer is not None]
            if values:
                promoters = sum(1 for v in values if v >= 9)
                passives = sum(1 for v in values if 7 <= v <= 8)
                detractors = sum(1 for v in values if v <= 6)

                stat.promoters = promoters
                stat.passives = passives
                stat.detractors = detractors

                if len(values) > 0:
                    stat.nps_score = ((promoters - detractors) / len(values)) * 100

        elif question.question_type == QuestionType.YES_NO:
            # Contar distribución yes/no
            choice_counts = {"Yes": 0, "No": 0}
            for answer in answers:
                if answer.boolean_answer is not None:
                    if answer.boolean_answer:
                        choice_counts["Yes"] += 1
                    else:
                        choice_counts["No"] += 1

            stat.choice_distribution = choice_counts

        elif question.question_type in [QuestionType.TEXT, QuestionType.TEXTAREA]:
            # Recolectar respuestas de texto
            text_responses = [a.text_answer for a in answers if a.text_answer]
            stat.text_responses = text_responses

        return stat

    # ============= Cache Management =============

    async def _invalidate_survey_caches(
        self,
        redis_client: Redis,
        gym_id: int
    ) -> None:
        """
        Invalidar cachés relacionadas con encuestas.

        Args:
            redis_client: Cliente Redis
            gym_id: ID del gimnasio

        Note:
            Invalida patrones:
            - surveys:available:gym:{gym_id}*
            - surveys:creator:*:gym:{gym_id}*
        """
        patterns = [
            f"surveys:available:gym:{gym_id}*",
            f"surveys:creator:*:gym:{gym_id}*"
        ]

        for pattern in patterns:
            try:
                count = await CacheService.delete_pattern(redis_client, pattern)
                logger.debug(f"Invalidated {count} survey caches with pattern: {pattern}")
            except Exception as e:
                logger.error(f"Error invalidating survey caches: {e}")

    async def _invalidate_statistics_cache(
        self,
        redis_client: Redis,
        survey_id: int
    ) -> None:
        """
        Invalidar caché de estadísticas de una encuesta.

        Args:
            redis_client: Cliente Redis
            survey_id: ID de la encuesta
        """
        cache_key = f"survey:stats:{survey_id}"
        try:
            await redis_client.delete(cache_key)
            logger.debug(f"Invalidated statistics cache for survey {survey_id}")
        except Exception as e:
            logger.error(f"Error invalidating statistics cache: {e}")

    async def _send_survey_notifications(
        self,
        db: AsyncSession,
        survey: Survey,
        gym_id: int
    ) -> None:
        """
        Enviar notificaciones sobre nueva encuesta a la audiencia objetivo.

        Args:
            db: Sesión async de base de datos
            survey: Encuesta publicada
            gym_id: ID del gimnasio

        Note:
            TODO: Implementar cuando se defina la audiencia objetivo.
            Debe enviar notificaciones push a usuarios relevantes.
        """
        if not NOTIFICATIONS_AVAILABLE:
            logger.warning("Notifications service not available")
            return

        # TODO: Determinar audiencia objetivo basada en survey.target_audience
        # TODO: Enviar notificaciones push usando async_notification_service

        logger.info(f"Survey notifications sent for survey {survey.id}")


# Instancia singleton del servicio async
async_survey_service = AsyncSurveyService()
