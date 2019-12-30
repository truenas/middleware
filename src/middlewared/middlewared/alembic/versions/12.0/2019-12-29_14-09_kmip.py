"""KMIP Support

Revision ID: c0f121844b00
Revises: f4e2434ad7f1
Create Date: 2019-12-29 14:09:29.127830+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c0f121844b00'
down_revision = 'f4e2434ad7f1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'system_kmip',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('server', sa.String(length=128), nullable=True),
        sa.Column('port', sa.SmallInteger(), nullable=False),
        sa.Column('certificate_id', sa.Integer(), nullable=True),
        sa.Column('certificate_authority_id', sa.Integer(), nullable=True),
        sa.Column('manage_sed_disks', sa.Boolean(), nullable=False),
        sa.Column('manage_zfs_keys', sa.Boolean(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ['certificate_id'], ['system_certificate.id'],
            name=op.f('fk_system_kmip_certificate_id_system_certificate')
        ),
        sa.ForeignKeyConstraint(
            ['certificate_authority_id'], ['system_certificateauthority.id'],
            name=op.f('fk_system_kmip_certificate_authority_id_system_certificateauthority')
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_system_kmip'))
    )
    with op.batch_alter_table('system_kmip', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_system_kmip_certificate_id'), ['certificate_id'], unique=False)
        batch_op.create_index(
            batch_op.f('ix_system_kmip_certificate_authority_id'), ['certificate_authority_id'], unique=False
        )

    with op.batch_alter_table('storage_disk', schema=None) as batch_op:
        batch_op.add_column(sa.Column('disk_kmip_uid', sa.String(length=255), nullable=True, default=None))
        batch_op.alter_column('disk_passwd', existing_type=sa.CHAR, type_=sa.TEXT)

    with op.batch_alter_table('storage_encrypteddataset', schema=None) as batch_op:
        batch_op.add_column(sa.Column('kmip_uid', sa.String(length=255), nullable=True, default=None))

    with op.batch_alter_table('system_advanced', schema=None) as batch_op:
        batch_op.add_column(sa.Column('adv_kmip_uid', sa.String(length=255), nullable=True, default=None))
        batch_op.alter_column('adv_sed_passwd', existing_type=sa.CHAR, type_=sa.TEXT)


def downgrade():
    pass
