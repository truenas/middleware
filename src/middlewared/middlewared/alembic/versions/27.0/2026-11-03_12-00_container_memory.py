"""Container memory

Revision ID: b37fe56131ac
Revises: 36eb34176424
Create Date: 2026-11-03 12:00:00.000000+00:00

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b37fe56131ac"
down_revision = "36eb34176424"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("container_container", schema=None) as batch_op:
        batch_op.add_column(sa.Column("memory", sa.Integer(), nullable=True))


def downgrade():
    pass
