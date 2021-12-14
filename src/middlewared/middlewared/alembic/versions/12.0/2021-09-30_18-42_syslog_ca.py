"""
Allow configuring CA for remote syslog tls connection

Revision ID: 45d6f6f07b0f
Revises: 26de83f45a9d
Create Date: 2021-09-30 18:42:42.818433+00:00
"""
from alembic import op
import sqlalchemy as sa


revision = '45d6f6f07b0f'
down_revision = '26de83f45a9d'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('system_advanced', schema=None) as batch_op:
        batch_op.add_column(sa.Column('adv_syslog_tls_certificate_authority_id', sa.Integer(), nullable=True))
        batch_op.create_index(
            batch_op.f('ix_system_advanced_adv_syslog_tls_certificate_authority_id'),
            ['adv_syslog_tls_certificate_authority_id'], unique=False
        )
        batch_op.create_foreign_key(
            batch_op.f('fk_system_advanced_adv_syslog_tls_certificate_authority_id_system_certificateauthority'),
            'system_certificateauthority', ['adv_syslog_tls_certificate_authority_id'], ['id']
        )


def downgrade():
    pass
