"""migrate_chat_members_to_user_ids

Revision ID: 844027f63a7c
Revises: fc6eb1818724
Create Date: 2025-04-10 23:13:16.657802

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = '844027f63a7c'
down_revision = 'fc6eb1818724'
branch_labels = None
depends_on = None


def upgrade():
    # Renombrar la columna user_id a auth0_user_id
    op.alter_column('chat_members', 'user_id', new_column_name='auth0_user_id', nullable=True)
    
    # Añadir nueva columna user_id (referencia a user.id)
    op.add_column('chat_members', sa.Column('user_id', sa.Integer(), nullable=True))
    
    # Añadir foreign key para user_id
    op.create_foreign_key(
        'fk_chat_members_user_id_user', 
        'chat_members', 'user', 
        ['user_id'], ['id']
    )
    
    # Crear índices
    op.create_index('ix_chat_members_user_id_room_id', 'chat_members', ['user_id', 'room_id'])
    op.create_index('ix_chat_members_auth0_user_id', 'chat_members', ['auth0_user_id'])
    
    # Ejecutar SQL para actualizar las filas existentes
    # Esto mapea los auth0_user_id a sus correspondientes user_id en la tabla user
    connection = op.get_bind()
    connection.execute(
        text("""
        UPDATE chat_members
        SET user_id = "user".id
        FROM "user" 
        WHERE chat_members.auth0_user_id = "user".auth0_id
        """)
    )


def downgrade():
    # Eliminar índices
    op.drop_index('ix_chat_members_user_id_room_id')
    op.drop_index('ix_chat_members_auth0_user_id')
    
    # Eliminar foreign key
    op.drop_constraint('fk_chat_members_user_id_user', 'chat_members', type_='foreignkey')
    
    # Eliminar columna user_id
    op.drop_column('chat_members', 'user_id')
    
    # Renombrar auth0_user_id de vuelta a user_id
    op.alter_column('chat_members', 'auth0_user_id', new_column_name='user_id', nullable=False) 