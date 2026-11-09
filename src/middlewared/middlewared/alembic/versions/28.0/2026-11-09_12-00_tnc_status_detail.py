"""Store the reason for a failed TrueNAS Connect status

Revision ID: 3c7e91ad5b20
Revises: 84556ccb6184
Create Date: 2026-11-09 12:00:00.000000+00:00

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "3c7e91ad5b20"
down_revision = "84556ccb6184"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("truenas_connect", schema=None) as batch_op:
        batch_op.add_column(sa.Column("status_detail", sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table("truenas_connect", schema=None) as batch_op:
        batch_op.drop_column("status_detail")
