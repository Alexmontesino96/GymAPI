"""
Survey Service

This module provides business logic for the survey system, including
statistics, analytics, and export functionality.
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
import json
from io import BytesIO
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from redis.asyncio import Redis
import logging

# Importación opcional de pandas para exportación
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    pd = None

from app.models.survey import (
    Survey, SurveyQuestion, QuestionChoice, SurveyResponse, 
    SurveyAnswer, SurveyTemplate, SurveyStatus, QuestionType
)
from app.models.user import User
from app.schemas.survey import (
    SurveyCreate, SurveyUpdate, ResponseCreate,
    SurveyStatistics, QuestionStatistics
)
from app.repositories.survey import survey_repository
from app.services.cache_service import CacheService

# Importación opcional del servicio de notificaciones
try:
    from app.services.notification_service import notification_service
    NOTIFICATIONS_AVAILABLE = True
except ImportError:
    notification_service = None
    NOTIFICATIONS_AVAILABLE = False

logger = logging.getLogger(__name__)


class SurveyService:
    """Service for survey business logic"""
    
    # ============= Survey Management =============
    
    async def create_survey(
        self,
        db: Session,
        survey_in: SurveyCreate,
        creator_id: int,
        gym_id: int,
        redis_client: Optional[Redis] = None
    ) -> Survey:
        """Create a new survey and invalidate caches"""
        survey = survey_repository.create_survey(
            db=db,
            survey_in=survey_in,
            creator_id=creator_id,
            gym_id=gym_id
        )
        
        # Invalidate caches
        if redis_client:
            await self._invalidate_survey_caches(redis_client, gym_id)
        
        logger.info(f"Survey {survey.id} created by user {creator_id} for gym {gym_id}")
        return survey
    
    async def get_available_surveys(
        self,
        db: Session,
        gym_id: int,
        user_id: Optional[int] = None,
        redis_client: Optional[Redis] = None
    ) -> List[Survey]:
        """
        Get available surveys for a user.
        This is the main method for users to see what surveys they can answer.
        """
        cache_key = f"surveys:available:gym:{gym_id}"
        if user_id:
            cache_key += f":user:{user_id}"
        
        async def db_fetch():
            return survey_repository.get_active_surveys(
                db=db,
                gym_id=gym_id,
                user_id=user_id
            )
        
        try:
            if redis_client:
                # Try cache first
                cached = await redis_client.get(cache_key)
                if cached:
                    logger.debug(f"Cache hit for available surveys: {cache_key}")
                    surveys_data = json.loads(cached)
                    return [Survey(**s) for s in surveys_data]
                
                # Get from DB
                surveys = await db_fetch()
                
                # Cache for 5 minutes
                if surveys:
                    surveys_json = json.dumps([s.dict() for s in surveys])
                    await redis_client.setex(cache_key, 300, surveys_json)
                
                return surveys
            else:
                return await db_fetch()
                
        except Exception as e:
            logger.error(f"Error getting available surveys: {e}")
            return await db_fetch()
    
    async def get_my_surveys(
        self,
        db: Session,
        creator_id: int,
        gym_id: int,
        status_filter: Optional[SurveyStatus] = None,
        redis_client: Optional[Redis] = None
    ) -> List[Survey]:
        """Get surveys created by a user"""
        cache_key = f"surveys:creator:{creator_id}:gym:{gym_id}"
        if status_filter:
            cache_key += f":status:{status_filter}"
        
        async def db_fetch():
            return survey_repository.get_surveys(
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
        db: Session,
        survey_id: int,
        gym_id: int,
        redis_client: Optional[Redis] = None
    ) -> Survey:
        """Publish a survey and send notifications"""
        survey = survey_repository.publish_survey(
            db=db,
            survey_id=survey_id,
            gym_id=gym_id
        )
        
        if not survey:
            return None
        
        # Invalidate caches
        if redis_client:
            await self._invalidate_survey_caches(redis_client, gym_id)
        
        # Send notifications to target audience
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
        db: Session,
        survey_id: int,
        gym_id: int,
        redis_client: Optional[Redis] = None
    ) -> Survey:
        """Close a survey"""
        survey = survey_repository.close_survey(
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
        db: Session,
        response_in: ResponseCreate,
        user_id: Optional[int],
        gym_id: int,
        redis_client: Optional[Redis] = None
    ) -> SurveyResponse:
        """Submit a survey response"""
        response = survey_repository.create_response(
            db=db,
            response_in=response_in,
            user_id=user_id,
            gym_id=gym_id
        )
        
        # Invalidate statistics cache
        if redis_client:
            await self._invalidate_statistics_cache(
                redis_client,
                survey_id=response_in.survey_id
            )
        
        logger.info(f"Response submitted for survey {response_in.survey_id} by user {user_id}")
        return response
    
    async def get_my_responses(
        self,
        db: Session,
        user_id: int,
        gym_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[SurveyResponse]:
        """Get user's survey responses"""
        return survey_repository.get_user_responses(
            db=db,
            user_id=user_id,
            gym_id=gym_id,
            skip=skip,
            limit=limit
        )
    
    # ============= Statistics & Analytics =============
    
    async def get_survey_statistics(
        self,
        db: Session,
        survey_id: int,
        gym_id: int,
        redis_client: Optional[Redis] = None
    ) -> SurveyStatistics:
        """Get comprehensive statistics for a survey"""
        cache_key = f"survey:stats:{survey_id}"
        
        async def calculate_stats():
            survey = survey_repository.get_survey(db, survey_id, gym_id)
            if not survey:
                return None
            
            # Get all responses
            responses = survey_repository.get_survey_responses(
                db=db,
                survey_id=survey_id,
                gym_id=gym_id,
                only_complete=False
            )
            
            total_responses = len(responses)
            complete_responses = sum(1 for r in responses if r.is_complete)
            incomplete_responses = total_responses - complete_responses
            
            # Calculate average completion time
            completion_times = []
            for r in responses:
                if r.is_complete and r.completed_at:
                    time_diff = (r.completed_at - r.started_at).total_seconds() / 60
                    completion_times.append(time_diff)
            
            avg_completion_time = (
                sum(completion_times) / len(completion_times) 
                if completion_times else None
            )
            
            # Calculate response rate (if we know target audience size)
            response_rate = None  # TODO: Calculate based on target audience
            
            # Get question statistics
            question_stats = []
            for question in survey.questions:
                q_stat = self._calculate_question_statistics(
                    question=question,
                    responses=responses
                )
                question_stats.append(q_stat)
            
            # Response distribution by date
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
                # Try cache first
                cached = await redis_client.get(cache_key)
                if cached:
                    logger.debug(f"Cache hit for survey statistics: {cache_key}")
                    return SurveyStatistics(**json.loads(cached))
                
                # Calculate and cache
                stats = await calculate_stats()
                if stats:
                    await redis_client.setex(
                        cache_key,
                        600,  # Cache for 10 minutes
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
        """Calculate statistics for a single question"""
        # Collect all answers for this question
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
        
        # Calculate based on question type
        if question.question_type in [QuestionType.RADIO, QuestionType.SELECT]:
            # Count choice distribution
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
            # Count multiple choice distribution
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
            # Calculate numeric statistics
            values = [a.number_answer for a in answers if a.number_answer is not None]
            if values:
                stat.average = sum(values) / len(values)
                stat.min = min(values)
                stat.max = max(values)
                stat.median = sorted(values)[len(values) // 2]
        
        elif question.question_type == QuestionType.NPS:
            # Calculate NPS score
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
            # Count yes/no distribution
            choice_counts = {"Yes": 0, "No": 0}
            for answer in answers:
                if answer.boolean_answer is not None:
                    if answer.boolean_answer:
                        choice_counts["Yes"] += 1
                    else:
                        choice_counts["No"] += 1
            
            stat.choice_distribution = choice_counts
        
        elif question.question_type in [QuestionType.TEXT, QuestionType.TEXTAREA]:
            # Collect text responses (limit to 100 for performance)
            text_responses = [
                a.text_answer for a in answers[:100] 
                if a.text_answer
            ]
            stat.text_responses = text_responses
        
        return stat
    
    # ============= Export Functionality =============
    
    async def export_survey_results(
        self,
        db: Session,
        survey_id: int,
        gym_id: int,
        format: str = "csv"
    ) -> BytesIO:
        """Export survey results to CSV or Excel"""
        if not PANDAS_AVAILABLE:
            raise ImportError(
                "La exportación de datos requiere pandas. "
                "Por favor instale pandas con: pip install pandas openpyxl"
            )
        
        survey = survey_repository.get_survey(db, survey_id, gym_id)
        if not survey:
            return None
        
        responses = survey_repository.get_survey_responses(
            db=db,
            survey_id=survey_id,
            gym_id=gym_id,
            only_complete=True
        )
        
        # Prepare data for export
        data = []
        for response in responses:
            row = {
                "Response ID": response.id,
                "User ID": response.user_id,
                "Started At": response.started_at,
                "Completed At": response.completed_at,
                "Is Complete": response.is_complete
            }
            
            # Add user info if not anonymous
            if response.user_id and response.user:
                row["User Email"] = response.user.email
                row["User Name"] = f"{response.user.first_name} {response.user.last_name}"
            
            # Add answers
            for question in survey.questions:
                answer = next(
                    (a for a in response.answers if a.question_id == question.id),
                    None
                )
                
                if answer:
                    value = self._get_answer_value(answer, question)
                    row[f"Q{question.order + 1}: {question.question_text}"] = value
                else:
                    row[f"Q{question.order + 1}: {question.question_text}"] = ""
            
            data.append(row)
        
        # Create DataFrame
        df = pd.DataFrame(data)
        
        # Export to BytesIO
        output = BytesIO()
        if format == "excel":
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Survey Results')
                
                # Add statistics sheet
                stats = await self.get_survey_statistics(db, survey_id, gym_id)
                if stats:
                    stats_df = self._create_statistics_dataframe(stats)
                    stats_df.to_excel(writer, index=False, sheet_name='Statistics')
        else:
            df.to_csv(output, index=False)
        
        output.seek(0)
        return output
    
    def _get_answer_value(self, answer: SurveyAnswer, question: SurveyQuestion) -> str:
        """Get the display value for an answer"""
        if answer.text_answer:
            return answer.text_answer
        elif answer.choice_id:
            choice = next(
                (c for c in question.choices if c.id == answer.choice_id),
                None
            )
            return choice.choice_text if choice else ""
        elif answer.choice_ids:
            choices = [
                c.choice_text for c in question.choices 
                if c.id in answer.choice_ids
            ]
            return ", ".join(choices)
        elif answer.number_answer is not None:
            return str(answer.number_answer)
        elif answer.date_answer:
            return answer.date_answer.isoformat()
        elif answer.boolean_answer is not None:
            return "Yes" if answer.boolean_answer else "No"
        elif answer.other_text:
            return f"Other: {answer.other_text}"
        else:
            return ""
    
    def _create_statistics_dataframe(self, stats: SurveyStatistics):
        """Create a DataFrame with survey statistics"""
        if not PANDAS_AVAILABLE:
            return None
        data = []
        
        # Summary row
        data.append({
            "Metric": "Total Responses",
            "Value": stats.total_responses
        })
        data.append({
            "Metric": "Complete Responses",
            "Value": stats.complete_responses
        })
        data.append({
            "Metric": "Incomplete Responses",
            "Value": stats.incomplete_responses
        })
        
        if stats.average_completion_time:
            data.append({
                "Metric": "Average Completion Time (minutes)",
                "Value": round(stats.average_completion_time, 2)
            })
        
        # Add question statistics
        for q_stat in stats.questions:
            data.append({
                "Metric": f"Q: {q_stat.question_text}",
                "Value": f"Total responses: {q_stat.total_responses}"
            })
            
            if q_stat.choice_distribution:
                for choice, count in q_stat.choice_distribution.items():
                    data.append({
                        "Metric": f"  - {choice}",
                        "Value": count
                    })
            
            if q_stat.average is not None:
                data.append({
                    "Metric": f"  - Average",
                    "Value": round(q_stat.average, 2)
                })
            
            if q_stat.nps_score is not None:
                data.append({
                    "Metric": f"  - NPS Score",
                    "Value": round(q_stat.nps_score, 1)
                })
        
        return pd.DataFrame(data)
    
    # ============= Cache Management =============
    
    async def _invalidate_survey_caches(
        self,
        redis_client: Redis,
        gym_id: int,
        survey_id: Optional[int] = None
    ):
        """Invalidate survey-related caches"""
        patterns = [
            f"surveys:available:gym:{gym_id}*",
            f"surveys:list:gym:{gym_id}*",
            f"surveys:creator:*:gym:{gym_id}*"
        ]
        
        if survey_id:
            patterns.extend([
                f"survey:detail:{survey_id}",
                f"survey:stats:{survey_id}"
            ])
        
        for pattern in patterns:
            try:
                await CacheService.delete_pattern(redis_client, pattern)
                logger.debug(f"Invalidated cache pattern: {pattern}")
            except Exception as e:
                logger.error(f"Error invalidating cache pattern {pattern}: {e}")
    
    async def _invalidate_statistics_cache(
        self,
        redis_client: Redis,
        survey_id: int
    ):
        """Invalidate statistics cache for a survey"""
        cache_key = f"survey:stats:{survey_id}"
        try:
            await redis_client.delete(cache_key)
            logger.debug(f"Invalidated statistics cache: {cache_key}")
        except Exception as e:
            logger.error(f"Error invalidating statistics cache: {e}")
    
    # ============= Notifications =============
    
    async def _send_survey_notifications(
        self,
        db: Session,
        survey: Survey,
        gym_id: int
    ):
        """Send notifications about new survey"""
        # Get target users based on audience
        from app.models.user_gym import UserGym, GymRoleType
        
        query = db.query(UserGym).filter(UserGym.gym_id == gym_id)
        
        if survey.target_audience == "trainers":
            query = query.filter(UserGym.role == GymRoleType.TRAINER)
        elif survey.target_audience == "members":
            query = query.filter(UserGym.role == GymRoleType.MEMBER)
        
        user_gyms = query.all()
        
        # Send notifications if service is available
        if NOTIFICATIONS_AVAILABLE and notification_service:
            for user_gym in user_gyms:
                try:
                    await notification_service.send_notification(
                        user_id=user_gym.user_id,
                        title="Nueva encuesta disponible",
                        body=f"{survey.title} - Tu opinión es importante",
                        data={
                            "type": "new_survey",
                            "survey_id": survey.id,
                            "gym_id": gym_id
                        }
                    )
                except Exception as e:
                    logger.error(f"Error sending notification to user {user_gym.user_id}: {e}")
        else:
            logger.debug("Notification service not available, skipping notifications")


# Singleton instance
survey_service = SurveyService()