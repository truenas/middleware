"""
Add KMIP ssl version field

Revision ID: 8b6d0edc6a38
Revises: 19eb67dcdee2
Create Date: 2022-05-23 18:22:38.186590+00:00

"""
from alembic import op
import sqlalchemy as sa


revision = '8b6d0edc6a38'
down_revision = '19eb67dcdee2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('system_kmip', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('ssl_version', sa.String(length=128), server_default='PROTOCOL_TLSv1_2')
        )


def downgrade():
    pass
