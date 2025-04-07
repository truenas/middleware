"""empty message

Revision ID: f8b0ab7c2275
Revises: 08febd74cdf9
Create Date: 2025-05-07 12:57:43.575785+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f8b0ab7c2275'
down_revision = '08febd74cdf9'
branch_labels = None
depends_on = None


def upgrade():
    # Create new common directoryservices table
    op.create_table('directoryservices',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('service_type', sa.String(length=120), nullable=True),
    sa.Column('cred_type', sa.String(length=120), nullable=True),
    sa.Column('cred_krb5', sa.TEXT(), nullable=True),
    sa.Column('cred_ldap_plain', sa.TEXT(), nullable=True),
    sa.Column('cred_ldap_mtls_cert_id', sa.Integer(), nullable=True),
    sa.Column('enable', sa.Boolean(), nullable=False, server_default='0'),
    sa.Column('enable_account_cache', sa.Boolean(), nullable=False, server_default='1'),
    sa.Column('enable_dns_updates', sa.Boolean(), nullable=False, server_default='1'),
    sa.Column('timeout', sa.Integer(), nullable=False, server_default='10'),
    sa.Column('kerberos_realm_id', sa.Integer(), nullable=True),
    sa.Column('ad_hostname', sa.String(length=120), nullable=True),
    sa.Column('ad_domain', sa.String(length=120), nullable=True),
    sa.Column('ad_idmap', sa.TEXT(), nullable=True),
    sa.Column('ad_site', sa.String(length=120), nullable=True),
    sa.Column('ad_computer_account_ou', sa.String(length=120), nullable=True),
    sa.Column('ad_use_default_domain', sa.Boolean(), nullable=False, server_default='0'),
    sa.Column('ad_enable_trusted_domains', sa.Boolean(), nullable=False, server_default='0'),
    sa.Column('ad_trusted_domains', sa.TEXT(), nullable=True),
    sa.Column('ipa_hostname', sa.String(length=120), nullable=True),
    sa.Column('ipa_domain', sa.String(length=120), nullable=True),
    sa.Column('ipa_target_server', sa.String(length=120), nullable=True),
    sa.Column('ipa_basedn', sa.String(length=120), nullable=True),
    sa.Column('ipa_smb_domain', sa.TEXT(), nullable=True),
    sa.Column('ipa_validate_certificates', sa.Boolean(), nullable=False, server_default='1'),
    sa.Column('ldap_server_urls', sa.TEXT(), nullable=True),
    sa.Column('ldap_starttls', sa.Boolean(), nullable=False, server_default='0'),
    sa.Column('ldap_server_basedn', sa.String(length=120), nullable=True),
    sa.Column('ldap_validate_certificates', sa.Boolean(), nullable=False, server_default='1'),
    sa.Column('ldap_schema', sa.String(length=120), nullable=True),
    sa.Column('ldap_base_user', sa.String(length=256), nullable=True),
    sa.Column('ldap_base_group', sa.String(length=256), nullable=True),
    sa.Column('ldap_base_netgroup', sa.String(length=256), nullable=True),
    sa.Column('ldap_user_object_class', sa.String(length=256), nullable=True),
    sa.Column('ldap_user_name', sa.String(length=256), nullable=True),
    sa.Column('ldap_user_uid', sa.String(length=256), nullable=True),
    sa.Column('ldap_user_gid', sa.String(length=256), nullable=True),
    sa.Column('ldap_user_gecos', sa.String(length=256), nullable=True),
    sa.Column('ldap_user_home_directory', sa.String(length=256), nullable=True),
    sa.Column('ldap_user_shell', sa.String(length=256), nullable=True),
    sa.Column('ldap_shadow_object_class', sa.String(length=256), nullable=True),
    sa.Column('ldap_shadow_last_change', sa.String(length=256), nullable=True),
    sa.Column('ldap_shadow_min', sa.String(length=256), nullable=True),
    sa.Column('ldap_shadow_max', sa.String(length=256), nullable=True),
    sa.Column('ldap_shadow_warning', sa.String(length=256), nullable=True),
    sa.Column('ldap_shadow_inactive', sa.String(length=256), nullable=True),
    sa.Column('ldap_shadow_expire', sa.String(length=256), nullable=True),
    sa.Column('ldap_group_object_class', sa.String(length=256), nullable=True),
    sa.Column('ldap_group_gid', sa.String(length=256), nullable=True),
    sa.Column('ldap_group_member', sa.String(length=256), nullable=True),
    sa.Column('ldap_netgroup_object_class', sa.String(length=256), nullable=True),
    sa.Column('ldap_netgroup_member', sa.String(length=256), nullable=True),
    sa.Column('ldap_netgroup_triple', sa.String(length=256), nullable=True),
    sa.Column('ldap_auxiliary_parameters', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['cred_ldap_mtls_cert_id'], ['system_certificate.id'], name=op.f('fk_directoryservices_cred_ldap_mtls_cert_id_system_certificate')),
    sa.ForeignKeyConstraint(['kerberos_realm_id'], ['directoryservice_kerberosrealm.id'], name=op.f('fk_directoryservices_kerberos_realm_id_directoryservice_kerberosrealm'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_directoryservices')),
    sqlite_autoincrement=True
    )

    # Migrate from old to new

    # Drop old tables
    with op.batch_alter_table('directoryservices', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_directoryservices_cred_ldap_mtls_cert_id'), ['cred_ldap_mtls_cert_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_directoryservices_kerberos_realm_id'), ['kerberos_realm_id'], unique=False)

    with op.batch_alter_table('directoryservice_ldap', schema=None) as batch_op:
        batch_op.drop_index('ix_directoryservice_ldap_ldap_certificate_id')
        batch_op.drop_index('ix_directoryservice_ldap_ldap_kerberos_realm_id')

    op.drop_table('directoryservice_ldap')
    with op.batch_alter_table('directoryservice_idmap_domain', schema=None) as batch_op:
        batch_op.drop_index('ix_directoryservice_idmap_domain_idmap_domain_certificate_id')

    op.drop_table('directoryservice_idmap_domain')
    with op.batch_alter_table('directoryservice_activedirectory', schema=None) as batch_op:
        batch_op.drop_index('ix_directoryservice_activedirectory_ad_kerberos_realm_id')

    op.drop_table('directoryservice_activedirectory')
