"""
Docker ipv6 support

Revision ID: bb352e66987f
Revises: 2b59607575b8
Create Date: 2024-11-15 12:14:35.553785+00:00

"""
import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = 'bb352e66987f'
down_revision = '2b59607575b8'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    with op.batch_alter_table('services_docker', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cidr_v6', sa.String(), nullable=False, server_default='fdd0::/64'))

    if docker_config := list(map(
        dict, conn.execute(text('SELECT * FROM services_docker')).fetchall()
    )):
        docker_config = docker_config[0]
        address_pool_config = json.loads(docker_config['address_pools'])
        address_pool_config.append({'base': 'fdd0::/48', 'size': 64})

        conn.execute("UPDATE services_docker SET address_pools = ? WHERE id = ?", [
            json.dumps(address_pool_config),
            docker_config['id']]
        )


def downgrade():
    pass
