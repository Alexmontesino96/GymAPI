"""
Script para verificar la consistencia de IDs entre Story y Post Feed Repositories.
"""

from app.repositories.story_feed_repository import StoryFeedRepository
from app.repositories.post_feed_repository import PostFeedRepository

def test_id_consistency():
    """Verifica que ambos repositorios generen IDs consistentes."""

    story_repo = StoryFeedRepository()
    post_repo = PostFeedRepository()

    # Test cases
    test_cases = [
        (1, 123),    # gym_id=1, user_id=123
        (2, 456),    # gym_id=2, user_id=456
        (1, 1000),   # gym_id=1, user_id=1000
        (5, 42),     # gym_id=5, user_id=42
    ]

    print("🔍 Verificando consistencia de IDs entre Stories y Posts\n")
    print("=" * 70)

    all_consistent = True

    for gym_id, user_id in test_cases:
        # Generar IDs con ambos repositorios
        story_safe_id = story_repo._sanitize_user_id(user_id)
        post_safe_id = post_repo._sanitize_user_id(user_id)

        # Construir IDs completos
        story_feed_id = f"gym_{gym_id}_user_{story_safe_id}"
        post_feed_id = f"gym_{gym_id}_user_{post_safe_id}"

        # Verificar consistencia
        consistent = story_feed_id == post_feed_id
        all_consistent = all_consistent and consistent

        status = "✅" if consistent else "❌"

        print(f"\n{status} Gym ID: {gym_id}, User ID: {user_id}")
        print(f"   Story Feed ID: {story_feed_id}")
        print(f"   Post Feed ID:  {post_feed_id}")
        print(f"   Sanitized IDs: story={story_safe_id}, post={post_safe_id}")

        if not consistent:
            print(f"   ⚠️  INCONSISTENCIA DETECTADA!")

    print("\n" + "=" * 70)

    if all_consistent:
        print("\n✅ TODOS LOS IDS SON CONSISTENTES")
        print("   Patrón unificado: gym_{gym_id}_user_{user_id}")
    else:
        print("\n❌ SE ENCONTRARON INCONSISTENCIAS")
        print("   Revisar la implementación de _sanitize_user_id()")

    return all_consistent


if __name__ == "__main__":
    try:
        success = test_id_consistency()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Error durante el test: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
