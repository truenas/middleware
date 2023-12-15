""" remove gluster service

Revision ID: 69789458866a
Revises: e2e0b53cb627
Create Date: 2023-12-23 18:12:00.848725+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '69789458866a'
down_revision = 'e2e0b53cb627'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("DELETE FROM services_services WHERE srv_service = 'glusterd'")

def downgrade():
    pass
