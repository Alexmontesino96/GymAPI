"""
Modelos de publicaciones para el gimnasio.

Sistema de posts permanentes tipo Instagram para compartir contenido del gym.
Los posts son permanentes (no expiran como las stories).
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Enum as SQLAlchemyEnum, JSON, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum

from app.db.base_class import Base


class PostType(str, enum.Enum):
    """Tipos de contenido en posts"""
    SINGLE_IMAGE = "single_image"  # Un post con una sola imagen
    GALLERY = "gallery"  # Múltiples imágenes (carousel)
    VIDEO = "video"  # Post de video
    WORKOUT = "workout"  # Post con datos de entrenamiento


class PostPrivacy(str, enum.Enum):
    """Niveles de privacidad para posts"""
    PUBLIC = "public"  # Todos los miembros del gym
    PRIVATE = "private"  # Solo yo


class TagType(str, enum.Enum):
    """Tipos de tags en posts"""
    MENTION = "mention"  # @usuario mencionado
    EVENT = "event"  # Etiqueta a evento del gym
    SESSION = "session"  # Etiqueta a sesión/clase


class Post(Base):
    """
    Modelo principal de posts.
    Los posts son permanentes (a diferencia de stories).
    """
    __tablename__ = "posts"
    __table_args__ = (
        Index('ix_posts_gym_created', 'gym_id', 'created_at'),
        Index('ix_posts_gym_engagement', 'gym_id', 'like_count', 'comment_count'),
        Index('ix_posts_location', 'gym_id', 'location'),
    )

    id = Column(Integer, primary_key=True, index=True)
    gym_id = Column(Integer, ForeignKey("gyms.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    stream_activity_id = Column(String, unique=True, index=True, nullable=True)

    # Contenido
    post_type = Column(SQLAlchemyEnum(PostType), nullable=False, default=PostType.SINGLE_IMAGE)
    caption = Column(Text, nullable=True)  # Texto del post
    location = Column(String(100), nullable=True)  # Ubicación del gym/lugar

    # Metadata específica por tipo
    workout_data = Column(JSON, nullable=True)
    # Para WORKOUT: {exercise: "Bench Press", weight: 100, reps: 10, sets: 3, duration_minutes: 60}

    # Configuración
    privacy = Column(SQLAlchemyEnum(PostPrivacy), default=PostPrivacy.PUBLIC, nullable=False)

    # Edición
    is_edited = Column(Boolean, default=False)
    edited_at = Column(DateTime, nullable=True)

    # Control de estado
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime, nullable=True)

    # Estadísticas
    like_count = Column(Integer, default=0, nullable=False)
    comment_count = Column(Integer, default=0, nullable=False)
    view_count = Column(Integer, default=0, nullable=False)  # Contador implícito

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relaciones
    user = relationship("User", back_populates="posts")
    gym = relationship("Gym", back_populates="posts")
    media = relationship("PostMedia", back_populates="post", cascade="all, delete-orphan", order_by="PostMedia.display_order")
    tags = relationship("PostTag", back_populates="post", cascade="all, delete-orphan")
    likes = relationship("PostLike", back_populates="post", cascade="all, delete-orphan")
    comments = relationship("PostComment", back_populates="post", cascade="all, delete-orphan")
    reports = relationship("PostReport", back_populates="post", cascade="all, delete-orphan")
    views = relationship("PostView", back_populates="post", cascade="all, delete-orphan")

    @property
    def engagement_score(self) -> float:
        """
        Calcula el score de engagement para algoritmo de feed.
        Formula: likes + (comentarios * 2) - (horas desde creación * 0.1)
        """
        age_hours = (datetime.utcnow() - self.created_at).total_seconds() / 3600
        return (self.like_count * 1.0) + (self.comment_count * 2.0) - (age_hours * 0.1)

    def __repr__(self):
        return f"<Post(id={self.id}, user_id={self.user_id}, type={self.post_type})>"


class PostMedia(Base):
    """
    Archivos de media asociados a un post (imágenes/videos).
    Soporta múltiples archivos para posts tipo GALLERY.
    """
    __tablename__ = "post_media"
    __table_args__ = (
        Index('ix_post_media_post_order', 'post_id', 'display_order'),
    )

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)

    # URLs
    media_url = Column(String, nullable=False)  # URL completa del archivo
    thumbnail_url = Column(String, nullable=True)  # Thumbnail para videos o imágenes grandes

    # Tipo de media
    media_type = Column(String(20), nullable=False)  # 'image' o 'video'

    # Orden de visualización (para galerías)
    display_order = Column(Integer, default=0, nullable=False)

    # Dimensiones opcionales
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)

    # Relaciones
    post = relationship("Post", back_populates="media")

    def __repr__(self):
        return f"<PostMedia(id={self.id}, post_id={self.post_id}, type={self.media_type})>"


class PostTag(Base):
    """
    Tags/etiquetas en posts: menciones a usuarios, eventos o sesiones.
    """
    __tablename__ = "post_tags"
    __table_args__ = (
        UniqueConstraint('post_id', 'tag_type', 'tag_value', name='unique_post_tag'),
        Index('ix_post_tags_type_value', 'tag_type', 'tag_value'),
    )

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)

    # Tipo de tag
    tag_type = Column(SQLAlchemyEnum(TagType), nullable=False)

    # Valor del tag
    # - Para MENTION: user_id (string)
    # - Para EVENT: event_id (string)
    # - Para SESSION: session_id (string)
    tag_value = Column(String(100), nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)

    # Relaciones
    post = relationship("Post", back_populates="tags")

    def __repr__(self):
        return f"<PostTag(id={self.id}, type={self.tag_type}, value={self.tag_value})>"
