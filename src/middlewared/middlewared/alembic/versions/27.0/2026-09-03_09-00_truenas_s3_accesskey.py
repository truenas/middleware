"""Add S3 access keys

Revision ID: c7e1a4d9b3f5
Revises: b7d4e91c53aa
Create Date: 2026-09-03 09:00:00.000000+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c7e1a4d9b3f5'
down_revision = 'b7d4e91c53aa'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('truenas_s3_accesskey',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('user_identifier', sa.String(length=200), nullable=False),
    sa.Column('access_key', sa.String(length=128), nullable=False),
    sa.Column('secret', sa.TEXT(), nullable=True),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.Column('expiry', sa.Integer(), nullable=False, server_default='0'),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_truenas_s3_accesskey')),
    sa.UniqueConstraint('access_key', name=op.f('uq_truenas_s3_accesskey_access_key')),
    sqlite_autoincrement=True
    )


def downgrade():
    op.drop_table('truenas_s3_accesskey')
