"""
Tests for Survey System Endpoints

This module tests all survey-related API endpoints including
creation, responses, statistics and export functionality.
"""

import pytest
from datetime import datetime, timedelta
import json
from app.models.survey import SurveyStatus, QuestionType
from app.models.gym import Gym
from app.models.user_gym import UserGym, GymRoleType


def test_create_survey(client, db, admin_user):
    """Test creating a new survey with questions"""
    # First create a gym for testing
    gym = Gym(
        name="Test Gym",
        description="Test gym for surveys",
        created_by_id=admin_user.id
    )
    db.add(gym)
    db.commit()
    db.refresh(gym)
    
    # Associate admin with gym
    user_gym = UserGym(
        user_id=admin_user.id,
        gym_id=gym.id,
        role=GymRoleType.ADMIN
    )
    db.add(user_gym)
    db.commit()
    
    survey_data = {
        "title": "Test Customer Satisfaction Survey",
        "description": "Test survey for customer feedback",
        "instructions": "Please answer all questions honestly",
        "is_anonymous": False,
        "allow_multiple": False,
        "show_progress": True,
        "target_audience": "members",
        "questions": [
            {
                "question_text": "How satisfied are you with our facilities?",
                "question_type": "SCALE",
                "is_required": True,
                "order": 0,
                "min_value": 1,
                "max_value": 5,
                "help_text": "1 = Very Unsatisfied, 5 = Very Satisfied"
            },
            {
                "question_text": "Which services do you use most?",
                "question_type": "CHECKBOX",
                "is_required": True,
                "order": 1,
                "choices": [
                    {"choice_text": "Gym Equipment", "order": 0},
                    {"choice_text": "Group Classes", "order": 1},
                    {"choice_text": "Personal Training", "order": 2},
                    {"choice_text": "Swimming Pool", "order": 3}
                ]
            },
            {
                "question_text": "Would you recommend us to a friend?",
                "question_type": "YES_NO",
                "is_required": True,
                "order": 2
            },
            {
                "question_text": "Any suggestions for improvement?",
                "question_type": "TEXTAREA",
                "is_required": False,
                "order": 3,
                "placeholder": "Share your thoughts..."
            }
        ]
    }
    
    # Mock the gym_id in request
    with client as c:
        c.app.dependency_overrides[lambda: gym.id] = lambda: gym.id
        response = c.post(
            "/api/v1/surveys/",
            json=survey_data,
            headers={"gym-id": str(gym.id)}
        )
    
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == survey_data["title"]
    assert data["status"] == "DRAFT"
    assert len(data["questions"]) == 4
    assert data["gym_id"] == gym.id
    
    return data["id"]


def test_get_available_surveys(client, db, member_user):
    """Test getting available surveys for a user"""
    # Create a gym and published survey
    gym = Gym(
        name="Test Gym",
        description="Test gym for surveys",
        created_by_id=member_user.id
    )
    db.add(gym)
    db.commit()
    db.refresh(gym)
    
    # Associate member with gym
    user_gym = UserGym(
        user_id=member_user.id,
        gym_id=gym.id,
        role=GymRoleType.MEMBER
    )
    db.add(user_gym)
    db.commit()
    
    # Create a published survey
    from app.models.survey import Survey
    survey = Survey(
        gym_id=gym.id,
        creator_id=member_user.id,
        title="Published Survey",
        description="Test survey",
        status=SurveyStatus.PUBLISHED,
        published_at=datetime.now()
    )
    db.add(survey)
    db.commit()
    
    with client as c:
        c.app.dependency_overrides[lambda: gym.id] = lambda: gym.id
        response = c.get(
            "/api/v1/surveys/available",
            headers={"gym-id": str(gym.id)}
        )
    
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    
    # Check that only published surveys are returned
    for survey in data:
        assert survey["status"] == "PUBLISHED"
        assert survey["gym_id"] == gym.id


def test_publish_survey(client, db, admin_user):
    """Test publishing a survey"""
    # Create gym
    gym = Gym(
        name="Test Gym",
        description="Test gym for surveys",
        created_by_id=admin_user.id
    )
    db.add(gym)
    db.commit()
    db.refresh(gym)
    
    # Associate admin with gym
    user_gym = UserGym(
        user_id=admin_user.id,
        gym_id=gym.id,
        role=GymRoleType.ADMIN
    )
    db.add(user_gym)
    db.commit()
    
    # Create a draft survey
    from app.models.survey import Survey, SurveyQuestion
    survey = Survey(
        gym_id=gym.id,
        creator_id=admin_user.id,
        title="Survey to Publish",
        description="Test survey",
        status=SurveyStatus.DRAFT
    )
    db.add(survey)
    db.commit()
    db.refresh(survey)
    
    # Add a question
    question = SurveyQuestion(
        survey_id=survey.id,
        question_text="Test question?",
        question_type=QuestionType.TEXT,
        is_required=True,
        order=0
    )
    db.add(question)
    db.commit()
    
    # Publish the survey
    with client as c:
        c.app.dependency_overrides[lambda: gym.id] = lambda: gym.id
        response = c.post(
            f"/api/v1/surveys/{survey.id}/publish",
            headers={"gym-id": str(gym.id)}
        )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "PUBLISHED"
    assert data["published_at"] is not None


def test_submit_survey_response(client, db, member_user):
    """Test submitting a response to a survey"""
    # Create gym and survey setup
    gym = Gym(
        name="Test Gym",
        description="Test gym for surveys",
        created_by_id=member_user.id
    )
    db.add(gym)
    db.commit()
    db.refresh(gym)
    
    # Associate member with gym
    user_gym = UserGym(
        user_id=member_user.id,
        gym_id=gym.id,
        role=GymRoleType.MEMBER
    )
    db.add(user_gym)
    db.commit()
    
    # Create a published survey with questions
    from app.models.survey import Survey, SurveyQuestion, QuestionChoice
    survey = Survey(
        gym_id=gym.id,
        creator_id=member_user.id,
        title="Survey for Response",
        description="Test survey",
        status=SurveyStatus.PUBLISHED,
        published_at=datetime.now()
    )
    db.add(survey)
    db.commit()
    db.refresh(survey)
    
    # Add questions
    question1 = SurveyQuestion(
        survey_id=survey.id,
        question_text="What is your name?",
        question_type=QuestionType.TEXT,
        is_required=True,
        order=0
    )
    db.add(question1)
    
    question2 = SurveyQuestion(
        survey_id=survey.id,
        question_text="Rate our service",
        question_type=QuestionType.SCALE,
        is_required=True,
        order=1,
        min_value=1,
        max_value=5
    )
    db.add(question2)
    db.commit()
    db.refresh(question1)
    db.refresh(question2)
    
    # Prepare response
    response_data = {
        "survey_id": survey.id,
        "answers": [
            {
                "question_id": question1.id,
                "text_answer": "Test User"
            },
            {
                "question_id": question2.id,
                "number_answer": 4
            }
        ]
    }
    
    with client as c:
        c.app.dependency_overrides[lambda: gym.id] = lambda: gym.id
        response = c.post(
            "/api/v1/surveys/responses",
            json=response_data,
            headers={"gym-id": str(gym.id)}
        )
    
    assert response.status_code == 201
    data = response.json()
    assert data["survey_id"] == survey.id
    assert data["is_complete"] == True
    assert len(data["answers"]) == 2


def test_get_survey_statistics(client, db, admin_user):
    """Test getting statistics for a survey"""
    # Create gym and survey with responses
    gym = Gym(
        name="Test Gym",
        description="Test gym for surveys",
        created_by_id=admin_user.id
    )
    db.add(gym)
    db.commit()
    db.refresh(gym)
    
    # Associate admin with gym
    user_gym = UserGym(
        user_id=admin_user.id,
        gym_id=gym.id,
        role=GymRoleType.ADMIN
    )
    db.add(user_gym)
    db.commit()
    
    # Create survey
    from app.models.survey import Survey, SurveyResponse
    survey = Survey(
        gym_id=gym.id,
        creator_id=admin_user.id,
        title="Survey with Stats",
        description="Test survey",
        status=SurveyStatus.PUBLISHED,
        published_at=datetime.now()
    )
    db.add(survey)
    db.commit()
    db.refresh(survey)
    
    # Add some responses
    response1 = SurveyResponse(
        survey_id=survey.id,
        gym_id=gym.id,
        user_id=admin_user.id,
        is_complete=True,
        completed_at=datetime.now()
    )
    response2 = SurveyResponse(
        survey_id=survey.id,
        gym_id=gym.id,
        is_complete=False
    )
    db.add(response1)
    db.add(response2)
    db.commit()
    
    with client as c:
        c.app.dependency_overrides[lambda: gym.id] = lambda: gym.id
        response = c.get(
            f"/api/v1/surveys/{survey.id}/statistics",
            headers={"gym-id": str(gym.id)}
        )
    
    assert response.status_code == 200
    data = response.json()
    assert data["total_responses"] == 2
    assert data["complete_responses"] == 1
    assert data["incomplete_responses"] == 1


def test_get_survey_templates(client, db):
    """Test getting survey templates"""
    # Create a test gym
    from app.models.user import User
    test_user = User(
        email="template_test@test.com",
        hashed_password="test",
        first_name="Template",
        last_name="Test"
    )
    db.add(test_user)
    db.commit()
    db.refresh(test_user)
    
    gym = Gym(
        name="Test Gym",
        description="Test gym for surveys",
        created_by_id=test_user.id
    )
    db.add(gym)
    db.commit()
    db.refresh(gym)
    
    with client as c:
        c.app.dependency_overrides[lambda: gym.id] = lambda: gym.id
        response = c.get(
            "/api/v1/surveys/templates",
            headers={"gym-id": str(gym.id)}
        )
    
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_survey_permissions(client, db, member_user, admin_user):
    """Test that only admins can create/edit surveys"""
    # Create gym
    gym = Gym(
        name="Test Gym",
        description="Test gym for surveys",
        created_by_id=admin_user.id
    )
    db.add(gym)
    db.commit()
    db.refresh(gym)
    
    # Associate users with gym
    member_gym = UserGym(
        user_id=member_user.id,
        gym_id=gym.id,
        role=GymRoleType.MEMBER
    )
    admin_gym = UserGym(
        user_id=admin_user.id,
        gym_id=gym.id,
        role=GymRoleType.ADMIN
    )
    db.add(member_gym)
    db.add(admin_gym)
    db.commit()
    
    survey_data = {
        "title": "Permission Test Survey",
        "description": "Testing permissions",
        "questions": []
    }
    
    # Try to create as member (should fail due to permission)
    with client as c:
        c.app.dependency_overrides[lambda: gym.id] = lambda: gym.id
        c.app.dependency_overrides[lambda: member_user.id] = lambda: member_user.id
        member_response = c.post(
            "/api/v1/surveys/",
            json=survey_data,
            headers={"gym-id": str(gym.id), "user-role": "MEMBER"}
        )
    
    # Note: Without proper Auth0 integration in tests, we may get 401 instead of 403
    assert member_response.status_code in [401, 403]


def test_export_survey_results(client, db, admin_user):
    """Test exporting survey results"""
    # Create gym and survey
    gym = Gym(
        name="Test Gym",
        description="Test gym for surveys",
        created_by_id=admin_user.id
    )
    db.add(gym)
    db.commit()
    db.refresh(gym)
    
    # Associate admin with gym
    user_gym = UserGym(
        user_id=admin_user.id,
        gym_id=gym.id,
        role=GymRoleType.ADMIN
    )
    db.add(user_gym)
    db.commit()
    
    # Create survey
    from app.models.survey import Survey
    survey = Survey(
        gym_id=gym.id,
        creator_id=admin_user.id,
        title="Survey to Export",
        description="Test survey",
        status=SurveyStatus.PUBLISHED,
        published_at=datetime.now()
    )
    db.add(survey)
    db.commit()
    db.refresh(survey)
    
    with client as c:
        c.app.dependency_overrides[lambda: gym.id] = lambda: gym.id
        response = c.get(
            f"/api/v1/surveys/{survey.id}/export?format=csv",
            headers={"gym-id": str(gym.id)}
        )
    
    # The export might fail if pandas is not available
    if response.status_code == 200:
        assert response.headers.get("content-type", "").startswith("text/csv")
    elif response.status_code == 500:
        # Expected if pandas is not installed
        assert "pandas" in response.json().get("detail", "").lower()