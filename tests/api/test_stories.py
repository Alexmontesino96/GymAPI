"""
Tests for Stories System Endpoints

This module tests the stories API endpoints including
feed retrieval, story creation, and story interactions.
"""

import pytest
from datetime import datetime, timedelta
from app.models.gym import Gym
from app.models.user import User
from app.models.user_gym import UserGym, GymRoleType
from app.models.story import Story, StoryType, StoryPrivacy
from app.models.module import Module
from app.models.gym_module import GymModule


@pytest.fixture
def test_gym(db, admin_user):
    """Create a test gym with stories module enabled"""
    gym = Gym(
        name="Test Gym for Stories",
        description="Test gym",
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

    # Enable stories module
    stories_module = db.query(Module).filter(Module.code == "stories").first()
    if not stories_module:
        stories_module = Module(
            code="stories",
            name="Historias",
            description="Sistema de historias estilo Instagram",
            is_premium=False
        )
        db.add(stories_module)
        db.commit()
        db.refresh(stories_module)

    gym_module = GymModule(
        gym_id=gym.id,
        module_id=stories_module.id,
        active=True
    )
    db.add(gym_module)
    db.commit()

    return gym


@pytest.fixture
def test_user(db, test_gym):
    """Create a test user in the gym"""
    user = User(
        email="storyuser@test.com",
        first_name="Story",
        last_name="User",
        auth0_id="auth0|storyuser123",
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Associate user with gym
    user_gym = UserGym(
        user_id=user.id,
        gym_id=test_gym.id,
        role=GymRoleType.MEMBER
    )
    db.add(user_gym)
    db.commit()

    return user


@pytest.fixture
def test_story(db, test_gym, test_user):
    """Create a test story"""
    story = Story(
        gym_id=test_gym.id,
        user_id=test_user.id,
        story_type=StoryType.TEXT,
        privacy=StoryPrivacy.PUBLIC,
        caption="Test story for testing",
        expires_at=datetime.utcnow() + timedelta(hours=24),
        is_pinned=False,
        is_active=True,
        is_deleted=False,
        view_count=0,
        reaction_count=0
    )
    db.add(story)
    db.commit()
    db.refresh(story)
    return story


def test_get_stories_feed_empty(client, db, test_gym, test_user, auth_headers):
    """Test getting stories feed when no stories exist"""
    # Mock dependency overrides for auth
    from app.core.tenant import get_tenant_id
    from app.core.auth0_fastapi import get_current_user

    def override_tenant_id():
        return test_gym.id

    def override_current_user():
        return test_user

    # Import app from client
    from main import app
    app.dependency_overrides[get_tenant_id] = override_tenant_id
    app.dependency_overrides[get_current_user] = override_current_user

    try:
        response = client.get(
            "/api/v1/stories/feed?filter_type=all&limit=25",
            headers=auth_headers
        )

        # Should return 200 even with empty feed
        assert response.status_code == 200
        data = response.json()

        # Check response structure
        assert "user_stories" in data
        assert "total_users" in data
        assert "has_more" in data

        # Should be empty
        assert data["total_users"] == 0
        assert len(data["user_stories"]) == 0
        assert data["has_more"] is False

    finally:
        app.dependency_overrides.clear()


def test_get_stories_feed_with_stories(client, db, test_gym, test_user, test_story, auth_headers):
    """Test getting stories feed with existing stories"""
    from app.core.tenant import get_tenant_id
    from app.core.auth0_fastapi import get_current_user

    def override_tenant_id():
        return test_gym.id

    def override_current_user():
        return test_user

    from main import app
    app.dependency_overrides[get_tenant_id] = override_tenant_id
    app.dependency_overrides[get_current_user] = override_current_user

    try:
        response = client.get(
            "/api/v1/stories/feed?filter_type=all&limit=25",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Should have stories
        assert data["total_users"] >= 1
        assert len(data["user_stories"]) >= 1

        # Check story structure
        user_story = data["user_stories"][0]
        assert "user_id" in user_story
        assert "user_name" in user_story
        assert "stories" in user_story
        assert len(user_story["stories"]) >= 1

        # Check individual story
        story = user_story["stories"][0]
        assert "id" in story
        assert "story_type" in story
        assert "caption" in story
        assert story["caption"] == "Test story for testing"

    finally:
        app.dependency_overrides.clear()


def test_get_user_stories(client, db, test_gym, test_user, test_story, auth_headers):
    """Test getting stories from a specific user"""
    from app.core.tenant import get_tenant_id
    from app.core.auth0_fastapi import get_current_user

    def override_tenant_id():
        return test_gym.id

    def override_current_user():
        return test_user

    from main import app
    app.dependency_overrides[get_tenant_id] = override_tenant_id
    app.dependency_overrides[get_current_user] = override_current_user

    try:
        response = client.get(
            f"/api/v1/stories/user/{test_user.id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        assert "stories" in data
        assert "total" in data
        assert data["total"] >= 1
        assert len(data["stories"]) >= 1

        # Verify story belongs to user
        story = data["stories"][0]
        assert "user_info" in story
        assert story["user_info"]["id"] == test_user.id

    finally:
        app.dependency_overrides.clear()


def test_stories_module_not_enabled(client, db, admin_user, auth_headers):
    """Test that stories endpoint returns 404 when module is not enabled"""
    # Create gym WITHOUT stories module
    gym = Gym(
        name="No Stories Gym",
        description="Gym without stories",
        created_by_id=admin_user.id
    )
    db.add(gym)
    db.commit()
    db.refresh(gym)

    user_gym = UserGym(
        user_id=admin_user.id,
        gym_id=gym.id,
        role=GymRoleType.ADMIN
    )
    db.add(user_gym)
    db.commit()

    from app.core.tenant import get_tenant_id
    from app.core.auth0_fastapi import get_current_user

    def override_tenant_id():
        return gym.id

    def override_current_user():
        return admin_user

    from main import app
    app.dependency_overrides[get_tenant_id] = override_tenant_id
    app.dependency_overrides[get_current_user] = override_current_user

    try:
        response = client.get(
            "/api/v1/stories/feed?filter_type=all&limit=25",
            headers=auth_headers
        )

        # Should return 404 because module is not enabled
        assert response.status_code == 404

    finally:
        app.dependency_overrides.clear()


def test_get_story_by_id(client, db, test_gym, test_user, test_story, auth_headers):
    """Test getting a specific story by ID"""
    from app.core.tenant import get_tenant_id
    from app.core.auth0_fastapi import get_current_user

    def override_tenant_id():
        return test_gym.id

    def override_current_user():
        return test_user

    from main import app
    app.dependency_overrides[get_tenant_id] = override_tenant_id
    app.dependency_overrides[get_current_user] = override_current_user

    try:
        response = client.get(
            f"/api/v1/stories/{test_story.id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        assert data["id"] == test_story.id
        assert data["caption"] == test_story.caption
        assert data["story_type"] == test_story.story_type.value
        assert "is_expired" in data
        assert "is_own_story" in data

    finally:
        app.dependency_overrides.clear()


def test_stories_pagination(client, db, test_gym, test_user, auth_headers):
    """Test pagination in stories feed"""
    # Create multiple stories
    for i in range(30):
        story = Story(
            gym_id=test_gym.id,
            user_id=test_user.id,
            story_type=StoryType.TEXT,
            privacy=StoryPrivacy.PUBLIC,
            caption=f"Test story {i}",
            expires_at=datetime.utcnow() + timedelta(hours=24),
            is_active=True,
            is_deleted=False
        )
        db.add(story)
    db.commit()

    from app.core.tenant import get_tenant_id
    from app.core.auth0_fastapi import get_current_user

    def override_tenant_id():
        return test_gym.id

    def override_current_user():
        return test_user

    from main import app
    app.dependency_overrides[get_tenant_id] = override_tenant_id
    app.dependency_overrides[get_current_user] = override_current_user

    try:
        # First page
        response = client.get(
            "/api/v1/stories/feed?filter_type=all&limit=10&offset=0",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        assert data["has_more"] is True
        assert "next_offset" in data

        # Second page
        response2 = client.get(
            f"/api/v1/stories/feed?filter_type=all&limit=10&offset={data['next_offset']}",
            headers=auth_headers
        )

        assert response2.status_code == 200

    finally:
        app.dependency_overrides.clear()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
