# Plan de Implementación: Historias de Gimnasio con Stream Activity Feed API v3

## 📋 Resumen Ejecutivo

Implementación de sistema de historias estilo Instagram para miembros del gimnasio usando Stream Activity Feed API v3.

### Características Principales
- ✅ Historias efímeras (24 horas)
- ✅ Fotos y videos
- ✅ Reacciones y comentarios
- ✅ Vista de quién vio tu historia
- ✅ Historias destacadas (highlights)
- ✅ Compartir entrenamientos y logros
- ✅ Notificaciones en tiempo real

### Stack Tecnológico
- **Backend**: FastAPI + Stream Feeds API
- **Base de datos**: PostgreSQL (metadata local)
- **Cache**: Redis
- **Media Storage**: AWS S3 / Cloudinary
- **Real-time**: Stream Chat (notificaciones)

## 📊 Análisis de Costos

| Miembros | Plan Stream | Costo Mensual | Actividades Incluidas |
|----------|-------------|---------------|-----------------------|
| 0-500 | Build/Maker | $0 | 5,000 |
| 500-2,000 | Start | $499 | 50,000 |
| 2,000-5,000 | Elevate | $899 | 150,000 |
| 5,000+ | Enterprise | Custom | Ilimitado |

**Nota**: Si tu equipo < 5 personas y < $10k/mes ingresos → **Maker Account GRATIS**

---

## 🚀 FASE 1: Setup Inicial (Días 1-3)

### ✅ Tareas Completadas
- [x] Análisis de Stream Activity Feed API v3
- [x] Evaluación de costos y viabilidad
- [x] Plan de arquitectura

### 📝 Tareas Pendientes

#### 1.1 Configuración de Stream Feeds
```bash
# Instalar SDK
pip install stream-python

# Agregar a requirements.txt
stream-python==5.5.0
```

#### 1.2 Variables de Entorno
```env
# Agregar a .env
STREAM_FEEDS_API_KEY=your_feeds_api_key
STREAM_FEEDS_API_SECRET=your_feeds_api_secret
STREAM_FEEDS_APP_ID=your_app_id
STREAM_FEEDS_LOCATION=us-east  # o eu-west
```

#### 1.3 Cliente de Stream Feeds
```python
# app/core/stream_feeds_client.py
from stream import Stream
from app.core.config import settings

stream_feeds_client = Stream(
    api_key=settings.STREAM_FEEDS_API_KEY,
    api_secret=settings.STREAM_FEEDS_API_SECRET,
    app_id=settings.STREAM_FEEDS_APP_ID,
    location=settings.STREAM_FEEDS_LOCATION
)
```

---

## 📦 FASE 2: Modelos y Estructura de Datos (Días 4-7)

### 2.1 Modelo de Base de Datos Local

```python
# app/models/story.py
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Enum, JSON, Text
from sqlalchemy.orm import relationship
from app.db.base_class import Base
import enum

class StoryType(str, enum.Enum):
    IMAGE = "image"
    VIDEO = "video"
    TEXT = "text"
    WORKOUT = "workout"
    ACHIEVEMENT = "achievement"

class StoryPrivacy(str, enum.Enum):
    PUBLIC = "public"
    FOLLOWERS = "followers"
    CLOSE_FRIENDS = "close_friends"
    PRIVATE = "private"

class Story(Base):
    __tablename__ = "stories"

    id = Column(Integer, primary_key=True, index=True)
    gym_id = Column(Integer, ForeignKey("gyms.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    stream_activity_id = Column(String, unique=True, index=True)

    # Content
    story_type = Column(Enum(StoryType), nullable=False)
    media_url = Column(String, nullable=True)
    thumbnail_url = Column(String, nullable=True)
    caption = Column(Text, nullable=True)

    # Metadata
    workout_data = Column(JSON, nullable=True)  # Para tipo WORKOUT
    privacy = Column(Enum(StoryPrivacy), default=StoryPrivacy.PUBLIC)

    # Stats (cached from Stream)
    view_count = Column(Integer, default=0)
    reaction_count = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=False)

    # Relations
    user = relationship("User", back_populates="stories")
    views = relationship("StoryView", back_populates="story")
    reactions = relationship("StoryReaction", back_populates="story")
```

### 2.2 Schemas/DTOs

```python
# app/schemas/story.py
from pydantic import BaseModel, HttpUrl
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum

class StoryBase(BaseModel):
    caption: Optional[str] = None
    story_type: StoryType
    privacy: StoryPrivacy = StoryPrivacy.PUBLIC
    workout_data: Optional[Dict[str, Any]] = None

class StoryCreate(StoryBase):
    media_url: Optional[HttpUrl] = None
    duration_hours: int = 24

class StoryResponse(StoryBase):
    id: int
    user_id: int
    gym_id: int
    media_url: Optional[str]
    thumbnail_url: Optional[str]
    view_count: int
    reaction_count: int
    created_at: datetime
    expires_at: datetime
    is_expired: bool
    user_info: Dict[str, Any]

    class Config:
        orm_mode = True

class StoryViewCreate(BaseModel):
    story_id: int

class StoryReactionCreate(BaseModel):
    story_id: int
    emoji: str
    message: Optional[str] = None
```

### 2.3 Migración de Base de Datos

```bash
# Crear migración
alembic revision --autogenerate -m "Add stories tables"

# Aplicar migración
alembic upgrade head
```

---

## 🛠️ FASE 3: Servicios y Repositorios (Semana 2)

### 3.1 Repositorio de Stream Feeds

```python
# app/repositories/story_feed_repository.py
from typing import List, Dict, Any, Optional
from stream import Stream
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class StoryFeedRepository:
    def __init__(self, stream_client: Stream):
        self.client = stream_client

    def create_story_activity(
        self,
        user_id: int,
        gym_id: int,
        story_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Crea una actividad de historia en Stream"""

        # Feed del usuario
        user_feed = self.client.feed('user', f'gym_{gym_id}_user_{user_id}')

        # Actividad
        activity = {
            'actor': f'gym_{gym_id}_user_{user_id}',
            'verb': 'post_story',
            'object': f'story:{story_data["id"]}',
            'foreign_id': f'story_{story_data["id"]}',
            'time': datetime.utcnow().isoformat(),
            'expires_at': story_data['expires_at'].isoformat(),

            # Custom fields
            'story_type': story_data['story_type'],
            'media_url': story_data.get('media_url'),
            'caption': story_data.get('caption'),
            'privacy': story_data['privacy'],
            'gym_id': str(gym_id),

            # To targeting
            'to': self._get_target_feeds(story_data['privacy'], gym_id, user_id)
        }

        # Agregar actividad
        result = user_feed.add_activity(activity)
        return result

    def get_stories_feed(
        self,
        user_id: int,
        gym_id: int,
        limit: int = 25,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Obtiene el feed de historias para un usuario"""

        # Timeline feed (historias de usuarios que sigue)
        timeline = self.client.feed('timeline', f'gym_{gym_id}_user_{user_id}')

        # Filtrar solo historias no expiradas
        activities = timeline.get(
            limit=limit,
            offset=offset,
            reactions={'counts': True, 'own': True}
        )

        # Filtrar expiradas client-side
        now = datetime.utcnow()
        active_stories = []

        for activity in activities['results']:
            if 'expires_at' in activity:
                expires_at = datetime.fromisoformat(activity['expires_at'])
                if expires_at > now:
                    active_stories.append(activity)

        return active_stories

    def mark_story_viewed(
        self,
        story_id: str,
        viewer_id: int,
        gym_id: int
    ) -> bool:
        """Marca una historia como vista"""

        viewer_feed = self.client.feed('user', f'gym_{gym_id}_user_{viewer_id}')

        # Agregar reacción de tipo 'view'
        viewer_feed.add_reaction(
            'view',
            story_id,
            data={'viewed_at': datetime.utcnow().isoformat()}
        )

        return True

    def add_story_reaction(
        self,
        story_id: str,
        user_id: int,
        gym_id: int,
        emoji: str,
        message: Optional[str] = None
    ) -> Dict[str, Any]:
        """Agrega una reacción a una historia"""

        user_feed = self.client.feed('user', f'gym_{gym_id}_user_{user_id}')

        reaction_data = {
            'emoji': emoji,
            'user_id': f'gym_{gym_id}_user_{user_id}'
        }

        if message:
            reaction_data['message'] = message

        reaction = user_feed.add_reaction(
            'comment',
            story_id,
            data=reaction_data
        )

        return reaction

    def delete_story(
        self,
        story_id: str,
        user_id: int,
        gym_id: int
    ) -> bool:
        """Elimina una historia"""

        user_feed = self.client.feed('user', f'gym_{gym_id}_user_{user_id}')

        # Eliminar por foreign_id
        user_feed.remove_activity(foreign_id=f'story_{story_id}')

        return True

    def _get_target_feeds(
        self,
        privacy: str,
        gym_id: int,
        user_id: int
    ) -> List[str]:
        """Determina a qué feeds enviar la historia basado en privacidad"""

        targets = []

        if privacy == 'public':
            # Feed público del gimnasio
            targets.append(f'gym:gym_{gym_id}')

        elif privacy == 'followers':
            # Solo timeline de followers (Stream maneja esto automáticamente)
            pass

        elif privacy == 'close_friends':
            # Feed especial de amigos cercanos
            targets.append(f'close_friends:gym_{gym_id}_user_{user_id}')

        return targets
```

### 3.2 Servicio de Historias

```python
# app/services/story_service.py
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import logging

from app.models.story import Story, StoryView, StoryReaction
from app.schemas.story import StoryCreate, StoryResponse
from app.repositories.story_feed_repository import StoryFeedRepository
from app.services.media_service import MediaService
from app.core.stream_feeds_client import stream_feeds_client

logger = logging.getLogger(__name__)

class StoryService:
    def __init__(self):
        self.feed_repo = StoryFeedRepository(stream_feeds_client)
        self.media_service = MediaService()

    async def create_story(
        self,
        db: Session,
        story_data: StoryCreate,
        user_id: int,
        gym_id: int,
        media_file: Optional[Any] = None
    ) -> StoryResponse:
        """Crea una nueva historia"""

        try:
            # 1. Subir media si existe
            media_url = None
            thumbnail_url = None

            if media_file:
                upload_result = await self.media_service.upload_story_media(
                    media_file,
                    user_id,
                    gym_id
                )
                media_url = upload_result['url']

                # Generar thumbnail para videos
                if story_data.story_type == 'video':
                    thumbnail_url = upload_result.get('thumbnail_url')

            # 2. Crear registro local
            expires_at = datetime.utcnow() + timedelta(hours=story_data.duration_hours)

            db_story = Story(
                gym_id=gym_id,
                user_id=user_id,
                story_type=story_data.story_type,
                media_url=media_url,
                thumbnail_url=thumbnail_url,
                caption=story_data.caption,
                privacy=story_data.privacy,
                workout_data=story_data.workout_data,
                expires_at=expires_at
            )

            db.add(db_story)
            db.commit()
            db.refresh(db_story)

            # 3. Crear actividad en Stream
            stream_activity = self.feed_repo.create_story_activity(
                user_id=user_id,
                gym_id=gym_id,
                story_data={
                    'id': db_story.id,
                    'story_type': story_data.story_type,
                    'media_url': media_url,
                    'caption': story_data.caption,
                    'privacy': story_data.privacy,
                    'expires_at': expires_at
                }
            )

            # 4. Guardar ID de Stream
            db_story.stream_activity_id = stream_activity['id']
            db.commit()

            # 5. Notificar a followers (opcional)
            await self._notify_new_story(db, user_id, gym_id, db_story.id)

            return StoryResponse.from_orm(db_story)

        except Exception as e:
            logger.error(f"Error creating story: {str(e)}")
            db.rollback()
            raise

    async def get_stories_feed(
        self,
        db: Session,
        user_id: int,
        gym_id: int,
        limit: int = 25,
        offset: int = 0
    ) -> List[StoryResponse]:
        """Obtiene el feed de historias del usuario"""

        # Obtener de Stream
        stream_stories = self.feed_repo.get_stories_feed(
            user_id, gym_id, limit, offset
        )

        # Enriquecer con data local
        story_ids = []
        for activity in stream_stories:
            # Extraer ID de foreign_id
            if 'foreign_id' in activity:
                story_id = activity['foreign_id'].replace('story_', '')
                story_ids.append(int(story_id))

        # Obtener datos locales
        local_stories = db.query(Story).filter(
            Story.id.in_(story_ids)
        ).all()

        # Mapear y combinar datos
        stories_map = {s.id: s for s in local_stories}
        enriched_stories = []

        for activity in stream_stories:
            story_id = int(activity['foreign_id'].replace('story_', ''))
            if story_id in stories_map:
                story = stories_map[story_id]

                # Actualizar contadores desde Stream
                story.view_count = activity.get('reaction_counts', {}).get('view', 0)
                story.reaction_count = activity.get('reaction_counts', {}).get('comment', 0)

                enriched_stories.append(story)

        return [StoryResponse.from_orm(s) for s in enriched_stories]

    async def view_story(
        self,
        db: Session,
        story_id: int,
        viewer_id: int,
        gym_id: int
    ) -> bool:
        """Marca una historia como vista"""

        # Verificar que no se haya visto antes
        existing_view = db.query(StoryView).filter(
            StoryView.story_id == story_id,
            StoryView.viewer_id == viewer_id
        ).first()

        if existing_view:
            return False

        # Crear registro local
        db_view = StoryView(
            story_id=story_id,
            viewer_id=viewer_id
        )
        db.add(db_view)

        # Marcar en Stream
        story = db.query(Story).filter(Story.id == story_id).first()
        if story and story.stream_activity_id:
            self.feed_repo.mark_story_viewed(
                story.stream_activity_id,
                viewer_id,
                gym_id
            )

        # Actualizar contador
        story.view_count += 1

        db.commit()

        # Notificar al creador (opcional)
        await self._notify_story_view(db, story_id, viewer_id)

        return True

    async def react_to_story(
        self,
        db: Session,
        story_id: int,
        user_id: int,
        gym_id: int,
        emoji: str,
        message: Optional[str] = None
    ) -> Dict[str, Any]:
        """Agrega una reacción a una historia"""

        # Verificar historia existe y no expirada
        story = db.query(Story).filter(Story.id == story_id).first()
        if not story:
            raise ValueError("Historia no encontrada")

        if datetime.utcnow() > story.expires_at:
            raise ValueError("La historia ha expirado")

        # Crear reacción local
        db_reaction = StoryReaction(
            story_id=story_id,
            user_id=user_id,
            emoji=emoji,
            message=message
        )
        db.add(db_reaction)

        # Agregar a Stream
        if story.stream_activity_id:
            stream_reaction = self.feed_repo.add_story_reaction(
                story.stream_activity_id,
                user_id,
                gym_id,
                emoji,
                message
            )

        # Actualizar contador
        story.reaction_count += 1

        db.commit()

        # Notificar al creador
        await self._notify_story_reaction(db, story_id, user_id, emoji)

        return {
            'success': True,
            'reaction_id': db_reaction.id
        }

    async def delete_story(
        self,
        db: Session,
        story_id: int,
        user_id: int,
        gym_id: int
    ) -> bool:
        """Elimina una historia"""

        story = db.query(Story).filter(
            Story.id == story_id,
            Story.user_id == user_id
        ).first()

        if not story:
            raise ValueError("Historia no encontrada o no autorizado")

        # Eliminar de Stream
        if story.stream_activity_id:
            self.feed_repo.delete_story(
                story.stream_activity_id,
                user_id,
                gym_id
            )

        # Eliminar de BD (cascade eliminará views y reactions)
        db.delete(story)
        db.commit()

        # Eliminar media de S3/Cloudinary
        if story.media_url:
            await self.media_service.delete_media(story.media_url)

        return True

    async def cleanup_expired_stories(self, db: Session) -> int:
        """Limpia historias expiradas (job programado)"""

        expired = db.query(Story).filter(
            Story.expires_at < datetime.utcnow(),
            Story.is_pinned == False
        ).all()

        count = 0
        for story in expired:
            try:
                # Stream las elimina automáticamente, solo limpiar local
                if story.media_url:
                    await self.media_service.delete_media(story.media_url)

                db.delete(story)
                count += 1
            except Exception as e:
                logger.error(f"Error cleaning story {story.id}: {e}")

        db.commit()
        logger.info(f"Cleaned {count} expired stories")

        return count

    async def _notify_new_story(
        self,
        db: Session,
        user_id: int,
        gym_id: int,
        story_id: int
    ):
        """Notifica a followers sobre nueva historia"""
        # TODO: Implementar con Stream Chat o OneSignal
        pass

    async def _notify_story_view(
        self,
        db: Session,
        story_id: int,
        viewer_id: int
    ):
        """Notifica al creador que alguien vio su historia"""
        # TODO: Implementar notificación silenciosa
        pass

    async def _notify_story_reaction(
        self,
        db: Session,
        story_id: int,
        user_id: int,
        emoji: str
    ):
        """Notifica al creador sobre nueva reacción"""
        # TODO: Implementar con Stream Chat
        pass

story_service = StoryService()
```

---

## 🔌 FASE 4: Endpoints de API (Semana 2-3)

### 4.1 Endpoints REST

```python
# app/api/v1/endpoints/stories.py
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, get_current_gym_id
from app.models.user import User
from app.schemas.story import (
    StoryCreate,
    StoryResponse,
    StoryViewCreate,
    StoryReactionCreate
)
from app.services.story_service import story_service
from app.core.permissions import require_permission

router = APIRouter(prefix="/stories", tags=["stories"])

@router.post("/", response_model=StoryResponse, status_code=status.HTTP_201_CREATED)
async def create_story(
    *,
    db: Session = Depends(get_db),
    story_in: StoryCreate,
    media: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
    gym_id: int = Depends(get_current_gym_id)
):
    """
    Crear una nueva historia.

    - **story_type**: image, video, text, workout, achievement
    - **privacy**: public, followers, close_friends, private
    - **duration_hours**: Duración antes de expirar (default 24)
    - **media**: Archivo de imagen o video (opcional para tipo text)
    """

    # Validar que si es imagen/video, debe tener media
    if story_in.story_type in ['image', 'video'] and not media:
        raise HTTPException(
            status_code=400,
            detail="Media file required for image/video stories"
        )

    story = await story_service.create_story(
        db=db,
        story_data=story_in,
        user_id=current_user.id,
        gym_id=gym_id,
        media_file=media
    )

    return story

@router.get("/feed", response_model=List[StoryResponse])
async def get_stories_feed(
    *,
    db: Session = Depends(get_db),
    limit: int = Query(25, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    gym_id: int = Depends(get_current_gym_id)
):
    """
    Obtener el feed de historias.

    Retorna historias de:
    - Usuarios que sigo
    - Historias públicas del gimnasio
    - Mis propias historias

    Las historias expiradas se filtran automáticamente.
    """

    stories = await story_service.get_stories_feed(
        db=db,
        user_id=current_user.id,
        gym_id=gym_id,
        limit=limit,
        offset=offset
    )

    return stories

@router.get("/user/{user_id}", response_model=List[StoryResponse])
async def get_user_stories(
    *,
    db: Session = Depends(get_db),
    user_id: int,
    current_user: User = Depends(get_current_user),
    gym_id: int = Depends(get_current_gym_id)
):
    """
    Obtener historias activas de un usuario específico.

    Respeta la configuración de privacidad:
    - Solo muestra historias públicas o si el usuario te sigue
    """

    # TODO: Implementar filtrado por privacidad
    stories = await story_service.get_user_stories(
        db=db,
        target_user_id=user_id,
        viewer_id=current_user.id,
        gym_id=gym_id
    )

    return stories

@router.get("/{story_id}", response_model=StoryResponse)
async def get_story(
    *,
    db: Session = Depends(get_db),
    story_id: int,
    current_user: User = Depends(get_current_user),
    gym_id: int = Depends(get_current_gym_id)
):
    """
    Obtener una historia específica por ID.

    Automáticamente la marca como vista.
    """

    # Marcar como vista
    await story_service.view_story(
        db=db,
        story_id=story_id,
        viewer_id=current_user.id,
        gym_id=gym_id
    )

    # Obtener historia
    story = await story_service.get_story(
        db=db,
        story_id=story_id,
        viewer_id=current_user.id
    )

    if not story:
        raise HTTPException(
            status_code=404,
            detail="Historia no encontrada o no autorizado"
        )

    return story

@router.post("/{story_id}/view", status_code=status.HTTP_204_NO_CONTENT)
async def view_story(
    *,
    db: Session = Depends(get_db),
    story_id: int,
    current_user: User = Depends(get_current_user),
    gym_id: int = Depends(get_current_gym_id)
):
    """
    Marcar una historia como vista.

    Se registra solo la primera vez que se ve.
    """

    success = await story_service.view_story(
        db=db,
        story_id=story_id,
        viewer_id=current_user.id,
        gym_id=gym_id
    )

    if not success:
        raise HTTPException(
            status_code=400,
            detail="Historia ya vista o no encontrada"
        )

    return

@router.post("/{story_id}/reaction", status_code=status.HTTP_201_CREATED)
async def react_to_story(
    *,
    db: Session = Depends(get_db),
    story_id: int,
    reaction_in: StoryReactionCreate,
    current_user: User = Depends(get_current_user),
    gym_id: int = Depends(get_current_gym_id)
):
    """
    Agregar una reacción a una historia.

    - **emoji**: Emoji de reacción (💪, 🔥, ❤️, etc.)
    - **message**: Mensaje opcional con la reacción
    """

    result = await story_service.react_to_story(
        db=db,
        story_id=story_id,
        user_id=current_user.id,
        gym_id=gym_id,
        emoji=reaction_in.emoji,
        message=reaction_in.message
    )

    return result

@router.get("/{story_id}/viewers", response_model=List[Dict])
async def get_story_viewers(
    *,
    db: Session = Depends(get_db),
    story_id: int,
    current_user: User = Depends(get_current_user)
):
    """
    Obtener lista de usuarios que vieron una historia.

    Solo el creador de la historia puede ver esta información.
    """

    viewers = await story_service.get_story_viewers(
        db=db,
        story_id=story_id,
        requester_id=current_user.id
    )

    return viewers

@router.delete("/{story_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_story(
    *,
    db: Session = Depends(get_db),
    story_id: int,
    current_user: User = Depends(get_current_user),
    gym_id: int = Depends(get_current_gym_id)
):
    """
    Eliminar una historia.

    Solo el creador puede eliminar su propia historia.
    """

    success = await story_service.delete_story(
        db=db,
        story_id=story_id,
        user_id=current_user.id,
        gym_id=gym_id
    )

    if not success:
        raise HTTPException(
            status_code=404,
            detail="Historia no encontrada o no autorizado"
        )

    return

@router.get("/highlights/user/{user_id}")
async def get_user_highlights(
    *,
    db: Session = Depends(get_db),
    user_id: int,
    current_user: User = Depends(get_current_user),
    gym_id: int = Depends(get_current_gym_id)
):
    """
    Obtener historias destacadas de un usuario.

    Las historias destacadas no expiran.
    """

    # TODO: Implementar highlights
    return []

# Admin endpoints

@router.delete("/admin/cleanup", response_model=Dict)
@require_permission("admin")
async def cleanup_expired_stories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Limpiar manualmente historias expiradas.

    Normalmente esto se ejecuta automáticamente cada hora.
    """

    count = await story_service.cleanup_expired_stories(db)

    return {
        "message": f"Cleaned {count} expired stories",
        "count": count
    }
```

### 4.2 Integración con Router Principal

```python
# app/api/v1/api.py
from app.api.v1.endpoints import stories  # Agregar import

# Agregar router
api_router.include_router(stories.router)
```

---

## 🧪 FASE 5: Testing y Optimización (Semana 3-4)

### 5.1 Tests Unitarios

```python
# tests/test_stories.py
import pytest
from datetime import datetime, timedelta
from app.services.story_service import story_service

@pytest.fixture
def test_story_data():
    return {
        "story_type": "image",
        "caption": "Test story",
        "privacy": "public",
        "media_url": "https://example.com/image.jpg"
    }

async def test_create_story(db_session, test_user, test_gym, test_story_data):
    """Test creating a new story"""

    story = await story_service.create_story(
        db=db_session,
        story_data=test_story_data,
        user_id=test_user.id,
        gym_id=test_gym.id
    )

    assert story.id is not None
    assert story.user_id == test_user.id
    assert story.expires_at > datetime.utcnow()

async def test_story_expiration(db_session, test_story):
    """Test that expired stories are filtered"""

    # Set expiration to past
    test_story.expires_at = datetime.utcnow() - timedelta(hours=1)
    db_session.commit()

    # Should not appear in feed
    stories = await story_service.get_stories_feed(
        db=db_session,
        user_id=test_story.user_id,
        gym_id=test_story.gym_id
    )

    assert test_story.id not in [s.id for s in stories]

async def test_story_privacy(db_session, test_user, other_user):
    """Test privacy settings work correctly"""

    # Create private story
    private_story = await story_service.create_story(
        db=db_session,
        story_data={"privacy": "private", ...},
        user_id=test_user.id,
        gym_id=1
    )

    # Other user shouldn't see it
    stories = await story_service.get_stories_feed(
        db=db_session,
        user_id=other_user.id,
        gym_id=1
    )

    assert private_story.id not in [s.id for s in stories]
```

### 5.2 Optimizaciones de Performance

#### Cache con Redis
```python
# app/services/story_cache.py
from app.db.redis_client import get_redis_client
import json

class StoryCache:
    def __init__(self):
        self.redis = get_redis_client()
        self.ttl = 300  # 5 minutos

    async def get_feed(self, user_id: int, gym_id: int):
        key = f"stories:feed:gym_{gym_id}:user_{user_id}"
        cached = await self.redis.get(key)
        if cached:
            return json.loads(cached)
        return None

    async def set_feed(self, user_id: int, gym_id: int, stories: List[Dict]):
        key = f"stories:feed:gym_{gym_id}:user_{user_id}"
        await self.redis.setex(
            key,
            self.ttl,
            json.dumps(stories)
        )

    async def invalidate_user_feed(self, user_id: int, gym_id: int):
        # Invalidar cuando el usuario crea nueva historia
        pattern = f"stories:feed:gym_{gym_id}:*"
        keys = await self.redis.keys(pattern)
        if keys:
            await self.redis.delete(*keys)
```

#### Batch Processing
```python
# Procesar vistas en batch cada X segundos
async def batch_process_views():
    """Procesar vistas acumuladas en batch"""

    views_queue = await redis.get("stories:views:queue")
    if not views_queue:
        return

    views = json.loads(views_queue)

    # Agrupar por historia
    grouped = {}
    for view in views:
        story_id = view['story_id']
        if story_id not in grouped:
            grouped[story_id] = []
        grouped[story_id].append(view['viewer_id'])

    # Actualizar contadores en batch
    for story_id, viewer_ids in grouped.items():
        await story_service.batch_mark_viewed(story_id, viewer_ids)

    await redis.delete("stories:views:queue")
```

---

## 🚢 FASE 6: Deployment y Monitoreo (Semana 4)

### 6.1 Variables de Producción

```env
# Production .env
STREAM_FEEDS_API_KEY=pk_prod_xxxxx
STREAM_FEEDS_API_SECRET=sk_prod_xxxxx
STREAM_FEEDS_APP_ID=123456
STREAM_FEEDS_LOCATION=us-east

# Media Storage
AWS_S3_BUCKET=gym-stories-prod
AWS_S3_REGION=us-east-1
CLOUDINARY_URL=cloudinary://api_key:api_secret@cloud_name

# Feature Flags
STORIES_ENABLED=true
STORIES_MAX_DURATION_HOURS=24
STORIES_MAX_FILE_SIZE_MB=100
```

### 6.2 Jobs Programados

```python
# app/core/scheduler.py
from app.services.story_service import story_service

# Agregar job de limpieza
scheduler.add_job(
    story_service.cleanup_expired_stories,
    trigger=CronTrigger(hour='*/1'),  # Cada hora
    id='cleanup_expired_stories',
    replace_existing=True
)
```

### 6.3 Métricas y Monitoreo

```python
# app/api/v1/endpoints/admin/metrics.py

@router.get("/stories/metrics")
async def get_stories_metrics(
    db: Session = Depends(get_db),
    gym_id: int = Query(...)
):
    """Obtener métricas de uso de historias"""

    return {
        "total_stories_today": ...,
        "active_stories": ...,
        "total_views": ...,
        "total_reactions": ...,
        "top_creators": [...],
        "engagement_rate": ...,
    }
```

---

## 📈 Métricas de Éxito

### KPIs a Monitorear
1. **Adopción**: % de usuarios activos que publican historias
2. **Engagement**: Promedio de vistas por historia
3. **Retención**: Usuarios que ven historias diariamente
4. **Viralidad**: Historias compartidas/reaccionadas
5. **Performance**: Tiempo de carga del feed < 200ms

### Objetivos Mes 1
- [ ] 30% de usuarios activos publican al menos 1 historia/semana
- [ ] Promedio 20+ vistas por historia
- [ ] 50% de usuarios ven historias diariamente
- [ ] < 1% de historias reportadas como inapropiadas

---

## 🔧 Troubleshooting Común

### Problema: Historias no expiran
**Solución**: Verificar job de cleanup está corriendo
```bash
python -c "from app.services.story_service import story_service; story_service.cleanup_expired_stories(db)"
```

### Problema: Feed lento
**Solución**: Implementar paginación y cache
```python
# Usar cache Redis
cached = await story_cache.get_feed(user_id, gym_id)
if cached:
    return cached
```

### Problema: Media no se sube
**Solución**: Verificar credenciales S3/Cloudinary
```bash
aws s3 ls s3://gym-stories-prod/
```

---

## 📚 Recursos Adicionales

### Documentación
- [Stream Feeds Docs](https://getstream.io/activity-feeds/docs/)
- [Stream Python SDK](https://github.com/GetStream/stream-python)
- [FastAPI Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/)

### Ejemplos de Código
- [Stream Feeds Examples](https://github.com/GetStream/Stream-Example-Apps)
- [Instagram Clone Tutorial](https://getstream.io/blog/instagram-clone-react/)

### Soporte
- Stream Support: support@getstream.io
- Stream Slack: https://getstream.io/chat/react-native-chat/tutorial/

---

## ✅ Checklist de Implementación

### Fase 1: Setup ✅
- [x] Análisis de viabilidad
- [x] Evaluación de costos
- [ ] Crear cuenta Stream Feeds
- [ ] Configurar API keys
- [ ] Instalar SDK

### Fase 2: Modelos
- [ ] Crear modelos SQLAlchemy
- [ ] Crear schemas Pydantic
- [ ] Generar migraciones
- [ ] Aplicar a BD

### Fase 3: Servicios
- [ ] Implementar repository de feeds
- [ ] Crear servicio de historias
- [ ] Integrar media upload
- [ ] Setup cache Redis

### Fase 4: API
- [ ] Crear endpoints CRUD
- [ ] Implementar autenticación
- [ ] Agregar validaciones
- [ ] Documentar con Swagger

### Fase 5: Testing
- [ ] Unit tests
- [ ] Integration tests
- [ ] Performance tests
- [ ] Security audit

### Fase 6: Deployment
- [ ] Configurar producción
- [ ] Setup monitoring
- [ ] Deploy a staging
- [ ] Launch a producción

---

**Última actualización**: Noviembre 2024
**Versión**: 1.0.0
**Autor**: GymAPI Team