"""
Remove redundant/unused k8s table fields

Revision ID: f1ca9deb82b9
Revises: 19900774fe2c
Create Date: 2024-10-30 15:15:24.171303+00:00

"""
from alembic import op


revision = 'f1ca9deb82b9'
down_revision = '19900774fe2c'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table('services_container')
    with op.batch_alter_table('services_kubernetes', schema=None) as batch_op:
        batch_op.drop_column('node_ip')
        batch_op.drop_column('cluster_dns_ip')
        batch_op.drop_column('route_v4_interface')
        batch_op.drop_column('cni_config')
        batch_op.drop_column('servicelb')
        batch_op.drop_column('route_v6_gateway')
        batch_op.drop_column('passthrough_mode')
        batch_op.drop_column('route_v6_interface')
        batch_op.drop_column('cluster_cidr')
        batch_op.drop_column('service_cidr')
        batch_op.drop_column('configure_gpus')
        batch_op.drop_column('route_v4_gateway')
        batch_op.drop_column('metrics_server')


def downgrade():
    pass
