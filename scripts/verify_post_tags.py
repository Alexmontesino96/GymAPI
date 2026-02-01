#!/usr/bin/env python3
"""
Script para verificar si los tags de posts se están creando correctamente.
Busca el último post creado y muestra sus tags.
"""

import os
import sys
from datetime import datetime, timedelta
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker

# Añadir el directorio padre al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.post import Post, PostTag, TagType
from app.models.user import User


def verify_post_tags():
    """
    Verifica los tags del post más reciente y muestra estadísticas.
    """
    # Configurar conexión a BD
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        print("❌ DATABASE_URL no configurada")
        return

    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    try:
        print("=" * 70)
        print("🔍 VERIFICACIÓN DE TAGS EN POSTS")
        print("=" * 70)

        # 1. Obtener el post más reciente
        latest_post = db.query(Post).order_by(desc(Post.created_at)).first()

        if not latest_post:
            print("❌ No hay posts en la base de datos")
            return

        # Información del post
        print(f"\n📝 ÚLTIMO POST CREADO:")
        print(f"   ID: {latest_post.id}")
        print(f"   Usuario ID: {latest_post.user_id}")
        print(f"   Gym ID: {latest_post.gym_id}")
        print(f"   Tipo: {latest_post.post_type}")
        print(f"   Caption: {latest_post.caption[:100] if latest_post.caption else '(sin caption)'}...")
        print(f"   Creado: {latest_post.created_at}")

        # 2. Obtener tags del post
        tags = db.query(PostTag).filter(PostTag.post_id == latest_post.id).all()

        if not tags:
            print(f"\n⚠️ El post {latest_post.id} NO tiene tags")
        else:
            print(f"\n✅ El post {latest_post.id} tiene {len(tags)} tags:")
            print("-" * 50)

            # Agrupar por tipo
            mentions = []
            events = []
            sessions = []

            for tag in tags:
                if tag.tag_type == TagType.MENTION:
                    mentions.append(tag)
                elif tag.tag_type == TagType.EVENT:
                    events.append(tag)
                elif tag.tag_type == TagType.SESSION:
                    sessions.append(tag)

            # Mostrar menciones
            if mentions:
                print(f"\n👥 MENCIONES ({len(mentions)}):")
                for tag in mentions:
                    # Buscar nombre del usuario mencionado
                    user = db.query(User).filter(User.id == int(tag.tag_value)).first()
                    user_name = f"{user.first_name} {user.last_name}" if user else "Usuario no encontrado"
                    print(f"   • Usuario ID {tag.tag_value}: {user_name}")

            # Mostrar eventos
            if events:
                print(f"\n🎉 EVENTOS ETIQUETADOS ({len(events)}):")
                for tag in events:
                    print(f"   • Evento ID: {tag.tag_value}")

            # Mostrar sesiones
            if sessions:
                print(f"\n🏋️ SESIONES ETIQUETADAS ({len(sessions)}):")
                for tag in sessions:
                    print(f"   • Sesión ID: {tag.tag_value}")

        # 3. Estadísticas generales
        print("\n" + "=" * 70)
        print("📊 ESTADÍSTICAS GENERALES DE TAGS")
        print("=" * 70)

        # Posts con tags en el último día
        yesterday = datetime.now() - timedelta(days=1)
        recent_posts = db.query(Post).filter(Post.created_at >= yesterday).all()
        posts_with_tags = 0
        total_tags = 0

        for post in recent_posts:
            post_tags = db.query(PostTag).filter(PostTag.post_id == post.id).count()
            if post_tags > 0:
                posts_with_tags += 1
                total_tags += post_tags

        print(f"📅 Últimas 24 horas:")
        print(f"   • Posts creados: {len(recent_posts)}")
        print(f"   • Posts con tags: {posts_with_tags}")
        print(f"   • Total de tags: {total_tags}")

        if len(recent_posts) > 0:
            percentage = (posts_with_tags / len(recent_posts)) * 100
            avg_tags = total_tags / len(recent_posts) if len(recent_posts) > 0 else 0
            print(f"   • % posts con tags: {percentage:.1f}%")
            print(f"   • Promedio tags/post: {avg_tags:.1f}")

        # 4. Distribución de tipos de tags
        all_tags = db.query(PostTag).all()
        tag_counts = {
            TagType.MENTION: 0,
            TagType.EVENT: 0,
            TagType.SESSION: 0
        }

        for tag in all_tags:
            tag_counts[tag.tag_type] = tag_counts.get(tag.tag_type, 0) + 1

        print(f"\n📈 Distribución total de tags:")
        print(f"   • Menciones: {tag_counts[TagType.MENTION]}")
        print(f"   • Eventos: {tag_counts[TagType.EVENT]}")
        print(f"   • Sesiones: {tag_counts[TagType.SESSION]}")
        print(f"   • TOTAL: {sum(tag_counts.values())}")

        # 5. Posts más recientes con tags
        print("\n" + "=" * 70)
        print("📋 ÚLTIMOS 5 POSTS CON TAGS")
        print("=" * 70)

        posts_with_tags_query = (
            db.query(Post)
            .join(PostTag, Post.id == PostTag.post_id)
            .group_by(Post.id)
            .order_by(desc(Post.created_at))
            .limit(5)
            .all()
        )

        for i, post in enumerate(posts_with_tags_query, 1):
            tags = db.query(PostTag).filter(PostTag.post_id == post.id).all()
            print(f"\n{i}. Post ID {post.id} ({post.created_at.strftime('%Y-%m-%d %H:%M')})")
            print(f"   Caption: {post.caption[:50] if post.caption else '(sin caption)'}...")
            print(f"   Tags: ", end="")

            tag_strings = []
            for tag in tags:
                if tag.tag_type == TagType.MENTION:
                    tag_strings.append(f"@user_{tag.tag_value}")
                elif tag.tag_type == TagType.EVENT:
                    tag_strings.append(f"📅event_{tag.tag_value}")
                elif tag.tag_type == TagType.SESSION:
                    tag_strings.append(f"🏋️session_{tag.tag_value}")

            print(", ".join(tag_strings) if tag_strings else "(sin tags)")

        print("\n" + "=" * 70)
        print("✅ Verificación completada")
        print("=" * 70)

    except Exception as e:
        print(f"❌ Error durante la verificación: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    verify_post_tags()