"""Add what the S3 protocol needs to create and delete buckets

Revision ID: b7e3f1a92c48
Revises: e4b8d2f6a1c3
Create Date: 2026-09-09 12:00:00.000000+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7e3f1a92c48'
down_revision = 'e4b8d2f6a1c3'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('services_truenas_s3', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('managed_root_dataset', sa.String(length=255), nullable=False, server_default='')
        )

    with op.batch_alter_table('truenas_s3_accesskey', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_used', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(
            sa.Column('manage_buckets', sa.Boolean(), nullable=False, server_default='0')
        )


def downgrade():
    pass
