"""Remove `F_IS_DEBUG` syslog level

Revision ID: 5e4a6dbd7bd2
Revises: 2c92fe98fc9d
Create Date: 2021-10-29 19:34:05.030458+00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = '5e4a6dbd7bd2'
down_revision = '2c92fe98fc9d'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(text("UPDATE system_advanced SET adv_sysloglevel = UPPER(adv_sysloglevel)"))
    op.execute(text("UPDATE system_advanced SET adv_sysloglevel = 'F_DEBUG' WHERE adv_sysloglevel = 'F_IS_DEBUG'"))


def downgrade():
    pass
