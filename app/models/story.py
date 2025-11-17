"""
Modelos de historias para el gimnasio.

Sistema de historias tipo Instagram/WhatsApp para compartir momentos del gym.
Las historias expiran automáticamente después de 24 horas.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Enum as SQLAlchemyEnum, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime, timedelta, timezone
import enum

from app.db.base_class import Base


class StoryType(str, enum.Enum):
    """Tipos de contenido en historias"""
    IMAGE = "image"
    VIDEO = "video"
    TEXT = "text"
    WORKOUT = "workout"  # Historia con datos de entrenamiento
    ACHIEVEMENT = "achievement"  # Logros y metas alcanzadas


class StoryPrivacy(str, enum.Enum):
    """Niveles de privacidad para historias"""
    PUBLIC = "public"  # Todos los miembros del gym
    FOLLOWERS = "followers"  # Solo seguidores
    CLOSE_FRIENDS = "close_friends"  # Solo amigos cercanos
    PRIVATE = "private"  # Solo yo


class Story(Base):
    """
    Modelo principal de historias.
    Las historias expiran después de 24 horas por defecto.
    """
    __tablename__ = "stories"

    id = Column(Integer, primary_key=True, index=True)
    gym_id = Column(Integer, ForeignKey("gyms.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    stream_activity_id = Column(String, unique=True, index=True, nullable=True)

    # Contenido
    story_type = Column(SQLAlchemyEnum(StoryType), nullable=False, default=StoryType.IMAGE)
    media_url = Column(String, nullable=True)  # URL de imagen/video en S3/Cloudinary
    thumbnail_url = Column(String, nullable=True)  # Thumbnail para videos
    caption = Column(Text, nullable=True)  # Texto o caption

    # Metadata específica por tipo
    workout_data = Column(JSON, nullable=True)
    # Para WORKOUT: {exercise: "Bench Press", weight: 100, reps: 10, sets: 3}
    # Para ACHIEVEMENT: {type: "personal_best", title: "Nuevo récord en sentadilla", value: "150kg"}

    # Configuración
    privacy = Column(SQLAlchemyEnum(StoryPrivacy), default=StoryPrivacy.PUBLIC, nullable=False)
    duration_hours = Column(Integer, default=24)  # Duración en horas (default 24)
    is_pinned = Column(Boolean, default=False)  # Historias destacadas no expiran

    # Control de estado
    is_active = Column(Boolean, default=True)
    is_deleted = Column(Boolean, default=False)

    # Estadísticas (cacheadas desde Stream)
    view_count = Column(Integer, default=0)
    reaction_count = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    # Relaciones
    user = relationship("User", back_populates="stories")
    gym = relationship("Gym", back_populates="stories")
    views = relationship("StoryView", back_populates="story", cascade="all, delete-orphan")
    reactions = relationship("StoryReaction", back_populates="story", cascade="all, delete-orphan")
    reports = relationship("StoryReport", back_populates="story", cascade="all, delete-orphan")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Establecer fecha de expiración automáticamente si no está configurada
        if not self.expires_at and not self.is_pinned:
            duration = kwargs.get('duration_hours', 24)
            self.expires_at = datetime.now(timezone.utc) + timedelta(hours=duration)

    @property
    def is_expired(self) -> bool:
        """Verifica si la historia ha expirado"""
        if self.is_pinned:
            return False
        if not self.expires_at:
            return False

        # Asegurar que expires_at tiene timezone para comparación segura
        expires = self.expires_at
        if expires.tzinfo is None:
            # Si es naive, asumimos UTC
            expires = expires.replace(tzinfo=timezone.utc)

        return datetime.now(timezone.utc) > expires

    def __repr__(self):
        return f"<Story(id={self.id}, user_id={self.user_id}, type={self.story_type})>"


class StoryView(Base):
    """
    Registro de visualizaciones de historias.
    Rastrea quién vio cada historia y cuándo.
    """
    __tablename__ = "story_views"
    __table_args__ = (
        UniqueConstraint('story_id', 'viewer_id', name='unique_story_viewer'),
    )

    id = Column(Integer, primary_key=True, index=True)
    story_id = Column(Integer, ForeignKey("stories.id", ondelete="CASCADE"), nullable=False, index=True)
    viewer_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)

    # Tracking
    viewed_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    view_duration_seconds = Column(Integer, nullable=True)  # Tiempo de visualización
    device_info = Column(String, nullable=True)  # iOS, Android, Web

    # Relaciones
    story = relationship("Story", back_populates="views")
    viewer = relationship("User", foreign_keys=[viewer_id])

    def __repr__(self):
        return f"<StoryView(story_id={self.story_id}, viewer_id={self.viewer_id})>"


class StoryReaction(Base):
    """
    Reacciones a historias (emojis, likes, mensajes).
    """
    __tablename__ = "story_reactions"
    __table_args__ = (
        UniqueConstraint('story_id', 'user_id', name='unique_story_reaction_user'),
    )

    id = Column(Integer, primary_key=True, index=True)
    story_id = Column(Integer, ForeignKey("stories.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)

    # Reacción
    emoji = Column(String(10), nullable=False)  # 💪, 🔥, ❤️, etc.
    message = Column(String(500), nullable=True)  # Mensaje opcional con la reacción

    # Timestamp
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)

    # Relaciones
    story = relationship("Story", back_populates="reactions")
    user = relationship("User", foreign_keys=[user_id])

    def __repr__(self):
        return f"<StoryReaction(story_id={self.story_id}, user_id={self.user_id}, emoji={self.emoji})>"


class StoryReport(Base):
    """
    Sistema de reportes para contenido inapropiado.
    """
    __tablename__ = "story_reports"

    id = Column(Integer, primary_key=True, index=True)
    story_id = Column(Integer, ForeignKey("stories.id", ondelete="CASCADE"), nullable=False, index=True)
    reporter_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)

    # Detalles del reporte
    reason = Column(String, nullable=False)  # spam, inappropriate, harassment, etc.
    description = Column(Text, nullable=True)

    # Estado
    is_reviewed = Column(Boolean, default=False)
    reviewed_by = Column(Integer, ForeignKey("user.id"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    action_taken = Column(String, nullable=True)  # deleted, warned, no_action

    # Timestamp
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)

    # Relaciones
    story = relationship("Story", back_populates="reports")
    reporter = relationship("User", foreign_keys=[reporter_id], backref="reported_stories")
    reviewer = relationship("User", foreign_keys=[reviewed_by], backref="reviewed_reports")

    def __repr__(self):
        return f"<StoryReport(story_id={self.story_id}, reporter_id={self.reporter_id})>"


class StoryHighlight(Base):
    """
    Colecciones de historias destacadas (no expiran).
    Similar a los highlights de Instagram.
    """
    __tablename__ = "story_highlights"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    gym_id = Column(Integer, ForeignKey("gyms.id"), nullable=False)

    # Información del highlight
    title = Column(String(50), nullable=False)
    cover_image_url = Column(String, nullable=True)

    # Estado
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    # Relaciones
    user = relationship("User", back_populates="story_highlights")
    gym = relationship("Gym")
    highlight_stories = relationship("StoryHighlightItem", back_populates="highlight", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<StoryHighlight(id={self.id}, user_id={self.user_id}, title={self.title})>"


class StoryHighlightItem(Base):
    """
    Historias individuales dentro de un highlight.
    """
    __tablename__ = "story_highlight_items"

    id = Column(Integer, primary_key=True, index=True)
    highlight_id = Column(Integer, ForeignKey("story_highlights.id", ondelete="CASCADE"), nullable=False)
    story_id = Column(Integer, ForeignKey("stories.id", ondelete="CASCADE"), nullable=False)

    # Orden de visualización
    display_order = Column(Integer, nullable=False, default=0)

    # Timestamp
    added_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)

    # Relaciones
    highlight = relationship("StoryHighlight", back_populates="highlight_stories")
    story = relationship("Story")

    def __repr__(self):
        return f"<StoryHighlightItem(highlight_id={self.highlight_id}, story_id={self.story_id})>"