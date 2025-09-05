from sqlalchemy import text

"""
Docker address pool default updated

Revision ID: 92b98613c498
Revises: c31881e67797
Create Date: 2024-10-03 20:46:17.935672+00:00
"""
import json

from alembic import op


revision = '92b98613c498'
down_revision = 'c31881e67797'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    if docker_config := list(map(
        dict, conn.execute(text('SELECT * FROM services_docker')).fetchall()
    )):
        docker_config = docker_config[0]
        address_pool_config = json.loads(docker_config['address_pools'])

        if address_pool_config == [{'base': '172.30.0.0/16', 'size': 27}, {'base': '172.31.0.0/16', 'size': 27}]:
            conn.execute("UPDATE services_docker SET address_pools = ? WHERE id = ?", [json.dumps(
                [{"base": "172.17.0.0/12", "size": 24}]
            ), docker_config['id']])


def downgrade():
    pass
