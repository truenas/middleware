"""
Add glusterd to services_services table

Revision ID: c9900d2d11cb
Revises: f8b573192e43
Create Date: 2020-10-20 12:46:04.125860+00:00

"""
from alembic import op


revision = 'c9900d2d11cb'
down_revision = 'f8b573192e43'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("INSERT INTO services_services (srv_service, srv_enable) VALUES ('glusterd', 0)")


def downgrade():
    op.execute("DELETE FROM services_services WHERE srv_service = 'glusterd'")
