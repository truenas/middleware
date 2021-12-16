"""
Add CA to system's trusted store

Revision ID: 29abd3dce632
Revises: 410b83305c45
Create Date: 2021-09-08 09:30:42.818433+00:00
"""
from alembic import op
import sqlalchemy as sa


revision = '29abd3dce632'
down_revision = '410b83305c45'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('system_certificateauthority', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cert_add_to_trusted_store', sa.Boolean(), server_default=False, nullable=False))


def downgrade():
    pass
