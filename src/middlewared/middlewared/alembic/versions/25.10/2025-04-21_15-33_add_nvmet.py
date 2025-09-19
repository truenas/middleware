"""Add nvmet

Revision ID: 08febd74cdf9
Revises: cafccdf50053
Create Date: 2025-04-21 15:33:34.588193+00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = '08febd74cdf9'
down_revision = 'cafccdf50053'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('services_nvmet_global',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('nvmet_global_basenqn', sa.String(length=255), nullable=False),
                    sa.Column('nvmet_global_kernel', sa.Boolean(), nullable=False),
                    sa.Column('nvmet_global_ana', sa.Boolean(), nullable=False),
                    sa.Column('nvmet_global_rdma', sa.Boolean(), nullable=False),
                    sa.Column('nvmet_global_xport_referral', sa.Boolean(), nullable=False),
                    sa.PrimaryKeyConstraint('id', name=op.f('pk_services_nvmet_global')),
                    sqlite_autoincrement=True)
    op.create_table('services_nvmet_host',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('nvmet_host_hostnqn', sa.String(length=255), nullable=False),
                    sa.Column('nvmet_host_dhchap_key', sa.Text(), nullable=True),
                    sa.Column('nvmet_host_dhchap_ctrl_key', sa.Text(), nullable=True),
                    sa.Column('nvmet_host_dhchap_dhgroup', sa.Integer(), nullable=False),
                    sa.Column('nvmet_host_dhchap_hash', sa.Integer(), nullable=False),
                    sa.PrimaryKeyConstraint('id', name=op.f('pk_services_nvmet_host')),
                    sa.UniqueConstraint('nvmet_host_hostnqn', name=op.f('uq_services_nvmet_host_nvmet_host_hostnqn')),
                    sqlite_autoincrement=True)
    op.create_table('services_nvmet_port',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('nvmet_port_index', sa.Integer(), nullable=False),
                    sa.Column('nvmet_port_addr_trtype', sa.Integer(), nullable=False),
                    sa.Column('nvmet_port_addr_trsvcid', sa.String(length=255), nullable=False),
                    sa.Column('nvmet_port_addr_traddr', sa.String(length=255), nullable=False),
                    sa.Column('nvmet_port_addr_adrfam', sa.Integer(), nullable=False),
                    sa.Column('nvmet_port_inline_data_size', sa.Integer(), nullable=True),
                    sa.Column('nvmet_port_max_queue_size', sa.Integer(), nullable=True),
                    sa.Column('nvmet_port_pi_enable', sa.Boolean(), nullable=True),
                    sa.Column('nvmet_port_enabled', sa.Boolean(), nullable=False),
                    sa.PrimaryKeyConstraint('id', name=op.f('pk_services_nvmet_port')),
                    sa.UniqueConstraint('nvmet_port_index', name=op.f('uq_services_nvmet_port_nvmet_port_index')),
                    sqlite_autoincrement=True)
    op.create_table('services_nvmet_subsys',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('nvmet_subsys_name', sa.String(), nullable=False),
                    sa.Column('nvmet_subsys_subnqn', sa.String(length=223), nullable=False),
                    sa.Column('nvmet_subsys_serial', sa.String(), nullable=False),
                    sa.Column('nvmet_subsys_allow_any_host', sa.Boolean(), nullable=False),
                    sa.Column('nvmet_subsys_pi_enable', sa.Boolean(), nullable=True),
                    sa.Column('nvmet_subsys_qid_max', sa.Integer(), nullable=True),
                    sa.Column('nvmet_subsys_ieee_oui', sa.Integer(), nullable=True),
                    sa.Column('nvmet_subsys_ana', sa.Boolean(), nullable=True),
                    sa.PrimaryKeyConstraint('id', name=op.f('pk_services_nvmet_subsys')),
                    sa.UniqueConstraint('nvmet_subsys_name', name=op.f('uq_services_nvmet_subsys_nvmet_subsys_name')),
                    sa.UniqueConstraint('nvmet_subsys_serial', name=op.f('uq_services_nvmet_subsys_nvmet_subsys_serial')),
                    sa.UniqueConstraint('nvmet_subsys_subnqn', name=op.f('uq_services_nvmet_subsys_nvmet_subsys_subnqn')),
                    sqlite_autoincrement=True)
    op.create_table('services_nvmet_host_subsys',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('nvmet_host_subsys_host_id', sa.Integer(), nullable=False),
                    sa.Column('nvmet_host_subsys_subsys_id', sa.Integer(), nullable=False),
                    sa.ForeignKeyConstraint(['nvmet_host_subsys_host_id'], ['services_nvmet_host.id'], name=op.f('fk_services_nvmet_host_subsys_nvmet_host_subsys_host_id_services_nvmet_host')),
                    sa.ForeignKeyConstraint(['nvmet_host_subsys_subsys_id'], ['services_nvmet_subsys.id'], name=op.f('fk_services_nvmet_host_subsys_nvmet_host_subsys_subsys_id_services_nvmet_subsys')),
                    sa.PrimaryKeyConstraint('id', name=op.f('pk_services_nvmet_host_subsys')),
                    sqlite_autoincrement=True)
    with op.batch_alter_table('services_nvmet_host_subsys', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_services_nvmet_host_subsys_nvmet_host_subsys_host_id'), ['nvmet_host_subsys_host_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_services_nvmet_host_subsys_nvmet_host_subsys_subsys_id'), ['nvmet_host_subsys_subsys_id'], unique=False)

    op.create_table('services_nvmet_namespace',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('nvmet_namespace_nsid', sa.Integer(), nullable=False),
                    sa.Column('nvmet_namespace_subsys_id', sa.Integer(), nullable=False),
                    sa.Column('nvmet_namespace_device_type', sa.Integer(), nullable=False),
                    sa.Column('nvmet_namespace_device_path', sa.String(length=255), nullable=False),
                    sa.Column('nvmet_namespace_filesize', sa.Integer(), nullable=True),
                    sa.Column('nvmet_namespace_device_uuid', sa.String(length=40), nullable=False),
                    sa.Column('nvmet_namespace_device_nguid', sa.String(length=40), nullable=False),
                    sa.Column('nvmet_namespace_enabled', sa.Boolean(), nullable=False),
                    sa.ForeignKeyConstraint(['nvmet_namespace_subsys_id'], ['services_nvmet_subsys.id'], name=op.f('fk_services_nvmet_namespace_nvmet_namespace_subsys_id_services_nvmet_subsys')),
                    sa.PrimaryKeyConstraint('id', name=op.f('pk_services_nvmet_namespace')),
                    sa.UniqueConstraint('nvmet_namespace_device_nguid', name=op.f('uq_services_nvmet_namespace_nvmet_namespace_device_nguid')),
                    sa.UniqueConstraint('nvmet_namespace_device_path', name=op.f('uq_services_nvmet_namespace_nvmet_namespace_device_path')),
                    sa.UniqueConstraint('nvmet_namespace_device_uuid', name=op.f('uq_services_nvmet_namespace_nvmet_namespace_device_uuid')))
    with op.batch_alter_table('services_nvmet_namespace', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_services_nvmet_namespace_nvmet_namespace_subsys_id'), ['nvmet_namespace_subsys_id'], unique=False)
        batch_op.create_index('services_nvmet_namespace_nvmet_namespace_subsys_id__nvmet_namespace_nsid_uniq', ['nvmet_namespace_subsys_id', 'nvmet_namespace_nsid'], unique=True)

    op.create_table('services_nvmet_port_subsys',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('nvmet_port_subsys_port_id', sa.Integer(), nullable=False),
                    sa.Column('nvmet_port_subsys_subsys_id', sa.Integer(), nullable=False),
                    sa.ForeignKeyConstraint(['nvmet_port_subsys_port_id'], ['services_nvmet_port.id'], name=op.f('fk_services_nvmet_port_subsys_nvmet_port_subsys_port_id_services_nvmet_port')),
                    sa.ForeignKeyConstraint(['nvmet_port_subsys_subsys_id'], ['services_nvmet_subsys.id'], name=op.f('fk_services_nvmet_port_subsys_nvmet_port_subsys_subsys_id_services_nvmet_subsys')),
                    sa.PrimaryKeyConstraint('id', name=op.f('pk_services_nvmet_port_subsys')),
                    sqlite_autoincrement=True)
    with op.batch_alter_table('services_nvmet_port_subsys', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_services_nvmet_port_subsys_nvmet_port_subsys_port_id'), ['nvmet_port_subsys_port_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_services_nvmet_port_subsys_nvmet_port_subsys_subsys_id'), ['nvmet_port_subsys_subsys_id'], unique=False)

    op.execute(text("INSERT INTO services_services (srv_service, srv_enable) VALUES ('nvmet', 0)"))


def downgrade():
    pass
