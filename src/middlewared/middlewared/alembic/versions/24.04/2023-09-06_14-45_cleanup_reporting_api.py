"""
Cleanup Reporting API

Revision ID: e915a3b8fff6
Revises: 3f39fe7d911d
Create Date: 2023-09-06 14:45:13.261715+00:00

"""
from alembic import op
from sqlalchemy.engine.reflection import Inspector


revision = 'e915a3b8fff6'
down_revision = '3f39fe7d911d'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    if 'system_reporting' not in inspector.get_table_names():
        return  # Skip as backported cobia migration already removed system_reporting table

    with op.batch_alter_table('system_reporting', schema=None) as batch_op:
        batch_op.drop_column('graph_age')
        batch_op.drop_column('graph_points')


def downgrade():
    pass
