"""NVMe target does not require trsvcid for FC

Revision ID: dae46dda9606
Revises: c227e49be4d8
Create Date: 2025-05-16 15:58:38.849619+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'dae46dda9606'
down_revision = 'c227e49be4d8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('services_nvmet_port', schema=None) as batch_op:
        batch_op.alter_column('nvmet_port_addr_trsvcid',
               existing_type=sa.VARCHAR(length=255),
               nullable=True)


def downgrade():
    with op.batch_alter_table('services_nvmet_port', schema=None) as batch_op:
        batch_op.alter_column('nvmet_port_addr_trsvcid',
               existing_type=sa.VARCHAR(length=255),
               nullable=False)
