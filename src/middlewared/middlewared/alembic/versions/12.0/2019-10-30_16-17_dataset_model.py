"""Encrypted dataset model

Revision ID: 7e8f7f07153e
Revises: 7f8be1364037
Create Date: 2019-10-30 16:17:53.964201+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7e8f7f07153e'
down_revision = '7f8be1364037'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'storage_encrypteddataset',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('encryption_key', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('storage_encrypteddataset')
