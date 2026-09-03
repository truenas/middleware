"""Add the S3 service and its buckets

Revision ID: e4b8d2f6a1c3
Revises: c7e1a4d9b3f5
Create Date: 2026-09-03 15:00:00.000000+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e4b8d2f6a1c3'
down_revision = 'c7e1a4d9b3f5'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('services_truenas_s3',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('bindip', sa.TEXT(), nullable=False, server_default='[]'),
    sa.Column('port', sa.Integer(), nullable=False, server_default='9000'),
    sa.Column('servers', sa.Integer(), nullable=False, server_default='1'),
    sa.Column('certificate_id', sa.Integer(), nullable=True),
    sa.Column('region', sa.String(length=120), nullable=False, server_default=''),
    sa.Column('log_level', sa.String(length=16), nullable=False, server_default='NOTICE'),
    sa.Column('default_audit', sa.TEXT(), nullable=False, server_default='[]'),
    sa.Column('default_audit_overflow', sa.String(length=16), nullable=False, server_default='DROP'),
    sa.Column('global_grants', sa.TEXT(), nullable=False, server_default='[]'),
    sa.Column('host_id', sa.String(length=64), nullable=False, server_default=''),
    sa.Column('owner_id_seed', sa.String(length=64), nullable=False, server_default=''),
    sa.ForeignKeyConstraint(['certificate_id'], ['system_certificate.id'], name=op.f('fk_services_truenas_s3_certificate_id_system_certificate')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_services_truenas_s3')),
    sqlite_autoincrement=True
    )
    with op.batch_alter_table('services_truenas_s3', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_services_truenas_s3_certificate_id'), ['certificate_id'], unique=False)

    op.create_table('truenas_s3_bucket',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=63), nullable=False),
    sa.Column('dataset', sa.String(length=255), nullable=False),
    sa.Column('path', sa.String(length=255), nullable=False),
    sa.Column('relative_path', sa.String(length=255), nullable=True),
    sa.Column('enabled', sa.Boolean(), nullable=False, server_default='1'),
    sa.Column('owner_uid', sa.Integer(), nullable=False),
    sa.Column('grants', sa.TEXT(), nullable=False, server_default='[]'),
    sa.Column('permissions_model', sa.String(length=16), nullable=False, server_default='S3'),
    sa.Column('versioning', sa.String(length=16), nullable=False, server_default='OFF'),
    sa.Column('object_lock', sa.Boolean(), nullable=False, server_default='0'),
    sa.Column('object_lock_default_mode', sa.String(length=16), nullable=True),
    sa.Column('object_lock_default_days', sa.Integer(), nullable=True),
    sa.Column('object_lock_default_years', sa.Integer(), nullable=True),
    sa.Column('sosapi_block_size', sa.Integer(), nullable=True),
    sa.Column('audit', sa.TEXT(), nullable=True),
    sa.Column('audit_overflow', sa.String(length=16), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_truenas_s3_bucket')),
    sa.UniqueConstraint('dataset', name=op.f('uq_truenas_s3_bucket_dataset')),
    sa.UniqueConstraint('name', name=op.f('uq_truenas_s3_bucket_name')),
    sqlite_autoincrement=True
    )

    op.execute(sa.text("INSERT INTO services_services (srv_service, srv_enable) VALUES ('truenas_s3', 0)"))


def downgrade():
    op.execute(sa.text("DELETE FROM services_services WHERE srv_service = 'truenas_s3'"))
    op.drop_table('truenas_s3_bucket')
    with op.batch_alter_table('services_truenas_s3', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_services_truenas_s3_certificate_id'))
    op.drop_table('services_truenas_s3')
