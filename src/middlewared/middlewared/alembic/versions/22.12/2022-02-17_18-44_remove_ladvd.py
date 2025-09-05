"""remove ladvd service

Revision ID: 4c852b54dfa1
Revises: 7a143979d99b
Create Date: 2022-02-17 18:44:19.468377+00:00

"""
from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = '4c852b54dfa1'
down_revision = '7a143979d99b'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table('services_lldp')
    op.execute(text('DELETE FROM services_services where srv_service = "lldp"'))


def downgrade():
    pass
