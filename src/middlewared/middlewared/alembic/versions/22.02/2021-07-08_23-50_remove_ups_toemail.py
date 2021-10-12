"""
Remove to_email from UPS service

Revision ID: 27f2004e7e53
Revises: c02971570fb0
Create Date: 2021-07-08 23:50:35.382256+00:00

"""
from alembic import op


revision = '27f2004e7e53'
down_revision = 'c02971570fb0'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('services_ups', schema=None) as batch_op:
        batch_op.drop_column('ups_toemail')
        batch_op.drop_column('ups_emailnotify')
        batch_op.drop_column('ups_subject')


def downgrade():
    pass
