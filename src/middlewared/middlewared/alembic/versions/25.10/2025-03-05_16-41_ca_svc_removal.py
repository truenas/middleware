"""
Remove CA plugin

Revision ID: 9a5b103ec2e4
Revises: 5fda0931889d
Create Date: 2025-03-05 16:41:53.749089+00:00

"""
from alembic import op
import sqlalchemy as sa


revision = '9a5b103ec2e4'
down_revision = '5fda0931889d'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    existing_certs = {
        cert['id']: cert for cert in map(dict, conn.execute("SELECT * FROM system_certificate").fetchall())
    }
    existing_cas = {
        ca['id']: ca for ca in map(dict, conn.execute("SELECT * FROM system_certificateauthority").fetchall())
    }
    kmip_config = next(
        map(dict, conn.execute("SELECT * FROM services_ssh").fetchall()), {'system_certificateauthority': None}
    )
    system_advanced_config = next(
        map(dict, conn.execute("SELECT * FROM system_advanced").fetchall()), {
            'adv_syslog_tls_certificate_authority_id': None,
        }
    )
    # We need to set existing usages to NULL
    conn.execute('UPDATE system_advanced SET adv_syslog_tls_certificate_authority_id = NULL')
    conn.execute('UPDATE system_kmip SET system_certificateauthority = NULL')

    with op.batch_alter_table('system_advanced') as batch_op:
        # Drop old foreign key constraint
        batch_op.drop_constraint(
            'fk_system_advanced_adv_syslog_tls_certificate_authority_id_system_certificateauthority',
            type_='foreignkey')

        # Add new foreign key constraint
        batch_op.create_foreign_key(
            batch_op.f('fk_system_advanced_adv_syslog_tls_certificate_authority_id_system_certificate'),
            'system_certificate',  # New referenced table
            ['adv_syslog_tls_certificate_authority_id'],
            ['id'],
            ondelete='CASCADE'
        )

        # Drop and recreate the index
        batch_op.drop_index(batch_op.f('ix_system_advanced_adv_syslog_tls_certificate_authority_id'))
        batch_op.create_index(
            batch_op.f('ix_system_advanced_adv_syslog_tls_certificate_authority_id'),
            ['adv_syslog_tls_certificate_authority_id'],
            unique=False
        )

    with op.batch_alter_table('system_kmip', schema=None) as batch_op:
        batch_op.drop_constraint(
            'fk_system_kmip_certificate_authority_id_system_certificateauthority',
            type_='foreignkey'
        )
        batch_op.create_foreign_key(
            batch_op.f('fk_system_kmip_certificate_authority_id_system_certificate'),
            'system_certificate',
            ['certificate_authority_id'],
            ['id']
        )
        batch_op.create_index(
            batch_op.f('ix_system_kmip_certificate_authority_id'), ['certificate_authority_id'], unique=False
        )
        batch_op.create_index(
            batch_op.f('ix_system_kmip_certificate_authority_id'), ['certificate_authority_id'], unique=False
        )



def downgrade():
    pass
