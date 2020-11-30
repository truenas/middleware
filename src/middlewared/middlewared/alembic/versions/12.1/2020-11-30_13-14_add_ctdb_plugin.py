"""
add ctdb plugin

Revision ID: f7746f911a45
Revises: 3d611f8cc676
Create Date: 2020-11-30 13:14:28.215714+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f7746f911a45'
down_revision = '3d611f8cc676'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'ctdb_private_ips',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ip', sa.String(length=45), nullable=True),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_ctdb_private_ips'))
    )
    op.create_table(
        'ctdb_public_ips',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ip', sa.String(length=45), nullable=True),
        sa.Column('netmask', sa.String(length=3), nullable=True),
        sa.Column('interface', sa.String(length=256), nullable=True),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_ctdb_public_ips'))
    )

    op.execute("INSERT INTO services_services (srv_service, srv_enable) VALUES ('ctdb', 0)")

def downgrade():
    op.drop_table('ctdb_public_ips')
    op.drop_table('ctdb_private_ips')

    op.execute("DELETE FROM services_services WHERE srv_service = 'ctdb'")
