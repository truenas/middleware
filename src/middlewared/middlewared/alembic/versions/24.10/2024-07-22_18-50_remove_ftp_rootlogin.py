""" Remove FTP rootlogin

Revision ID: 81b8bae8fb11
Revises: 1307a8e6a8b6
Create Date: 2024-07-22 18:50:09.235185+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = '81b8bae8fb11'
down_revision = '1307a8e6a8b6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('services_ftp', schema=None) as batch_op:
        batch_op.drop_column('ftp_rootlogin')

    # ### end Alembic commands ###
