"""Migrate directory services to new schema

Revision ID: f8b0ab7c2275
Revises: dae46dda9606
Create Date: 2025-05-07 12:57:43.575785+00:00

"""
from alembic import op
from json import dumps, loads
from middlewared.utils.pwenc import encrypt, decrypt
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = 'f8b0ab7c2275'
down_revision = 'dae46dda9606'
branch_labels = None
depends_on = None


def ds_migrate_ldap(conn, ldap):
    """ Convert LDAP table into the directory services table. """
    service_type = 'LDAP'
    cache_enabled = not ldap['ldap_disable_freenas_cache']
    kerberos_realm_id = ldap.pop('ldap_kerberos_realm_id')
    cert_id = ldap.pop('ldap_certificate_id')
    krb_princ = ldap.pop('ldap_kerberos_principal')
    ssl = ldap.pop('ldap_ssl')
    ldap_starttls = ssl == 'START_TLS'
    prefix = 'ldaps://' if ssl == 'ON' else 'ldap://'
    anon = ldap.pop('ldap_anonbind')
    ldap_server_urls = dumps([f'{prefix}{uri}' for uri in ldap.pop('ldap_hostname').split()])
    cred_type = None
    cred_krb5 = None
    cred_plain = None

    # initialize our directoryservices row
    conn.execute(text("INSERT INTO directoryservices (enable, service_type, enable_dns_updates) VALUES (1, 'LDAP', 0)"))

    # generate the cred information
    if anon:
        cred_type = 'LDAP_ANONYMOUS'
    elif cert_id:
        cred_type = 'LDAP_MTLS'
    elif krb_princ:
        cred_type = 'KERBEROS_PRINCIPAL'
        cred_krb5 = encrypt(dumps({
            'credential_type': 'KERBEROS_PRINCIPAL',
            'principal': krb_princ
        }))
    elif kerberos_realm_id:
        cred_type = 'KERBEROS_USER'
        cred_krb5 = encrypt(dumps({
            'credential_type': 'KERBEROS_USER',
            'username': ldap['ldap_binddn'],
            'password': decrypt(ldap['ldap_bindpw'])
        }))
    else:
        cred_type = 'LDAP_PLAIN'
        cred_plain = encrypt(dumps({
            'credential_type': 'LDAP_PLAIN',
            'binddn': ldap['ldap_binddn'],
            'bindpw': decrypt(ldap['ldap_bindpw']),
        }))

    stmt = (
        # Basic LDAP fields
        'UPDATE directoryservices SET '
        'service_type = :stype, '
        'cred_type = :cred_type,'
        'cred_krb5 = :cred_krb5,'
        'cred_ldap_mtls_cert_id = :mtls_cert_id,'
        'cred_ldap_plain = :cred_plain,'
        'enable = :enable,'
        'enable_account_cache = :enable_cache,'
        'timeout = :timeout,'
        'kerberos_realm_id = :realm_id,'
        'ldap_server_urls = :server_urls,'
        'ldap_starttls = :starttls,'
        'ldap_basedn = :basedn,'
        'ldap_validate_certificates = :validate_certs,'
        'ldap_schema = :schema,'
        'ldap_auxiliary_parameters = :aux,'
        # Search bases. These are modified if IPA domain that didn't go through a proper join process
        'ldap_base_user = :baseuser,'
        'ldap_base_group = :basegroup,'
        'ldap_base_netgroup = :basenetgroup,'
        # Attribute maps. Generally these wouldn't have been touched by users
        # passwd
        'ldap_user_object_class = :userobj,'
        'ldap_user_name = :username,'
        'ldap_user_uid = :useruid,'
        'ldap_user_gid = :usergid,'
        'ldap_user_gecos = :usergecos,'
        'ldap_user_home_directory = :userpath,'
        'ldap_user_shell = :usershell,'
        # shadow
        # We're dropping the shadow_object_class. It existed in nslcd but not sssd
        # 'ldap_shadow_object_class = :shadowobj'
        'ldap_shadow_last_change = :shadowchg,'
        'ldap_shadow_min = :shadowmin,'
        'ldap_shadow_max = :shadowmax,'
        'ldap_shadow_warning = :shadowwarn,'
        'ldap_shadow_inactive = :shadowinact,'
        'ldap_shadow_expire = :shadowexp,'
        # group
        'ldap_group_object_class = :groupobj,'
        'ldap_group_gid = :groupgid,'
        'ldap_group_member = :groupmem,'
        # netgroup
        'ldap_netgroup_object_class = :ngobj,'
        'ldap_netgroup_member = :ngmem,'
        'ldap_netgroup_triple = :ngtrip '
    )

    conn.execute(
        text(stmt), {
            'enable': ldap['ldap_enable'],
            'stype': service_type,
            'enable_cache': cache_enabled,
            'cred_type': cred_type,
            'cred_krb5': cred_krb5,
            'mtls_cert_id': cert_id,
            'cred_plain': cred_plain,
            'timeout': ldap['ldap_timeout'],
            'realm_id': kerberos_realm_id,
            'server_urls': ldap_server_urls,
            'starttls': ldap_starttls,
            'basedn': ldap['ldap_basedn'],
            'validate_certs': ldap['ldap_validate_certificates'],
            'schema': ldap['ldap_schema'],
            'aux': ldap['ldap_auxiliary_parameters'],
            'baseuser': ldap['ldap_base_user'],
            'basegroup': ldap['ldap_base_group'],
            'basenetgroup': ldap['ldap_base_netgroup'],
            'userobj': ldap['ldap_user_object_class'],
            'username': ldap['ldap_user_name'],
            'useruid': ldap['ldap_user_uid'],
            'usergid': ldap['ldap_user_gid'],
            'usergecos': ldap['ldap_user_gecos'],
            'userpath': ldap['ldap_user_home_directory'],
            'usershell': ldap['ldap_user_shell'],
            'shadowchg': ldap['ldap_shadow_last_change'],
            'shadowmin': ldap['ldap_shadow_min'],
            'shadowmax': ldap['ldap_shadow_max'],
            'shadowwarn': ldap['ldap_shadow_warning'],
            'shadowinact': ldap['ldap_shadow_inactive'],
            'shadowexp': ldap['ldap_shadow_expire'],
            'groupobj': ldap['ldap_group_object_class'],
            'groupgid': ldap['ldap_group_gid'],
            'groupmem': ldap['ldap_group_member'],
            'ngobj': ldap['ldap_netgroup_object_class'],
            'ngmem': ldap['ldap_netgroup_member'],
            'ngtrip': ldap['ldap_netgroup_triple']
        }

    )


def ds_migrate_ipa(conn, ldap):
    keytabs = [row for row in conn.execute(text('SELECT * FROM directoryservice_kerberoskeytab')).mappings().all()]
    realms = [row for row in conn.execute(text('SELECT * FROM directoryservice_kerberosrealm')).mappings().all()]

    if not keytabs or not realms:
        # Kerberos configuration is required to properly join IPA and so this is a legacy setup
        return ds_migrate_ldap(conn, ldap)

    if not any([k['keytab_name'] == 'IPA_MACHINE_ACCOUNT' for k in keytabs]):
        # IPA keytab doesn't exist so also not joined to IPA domain
        return ds_migrate_ldap(conn, ldap)

    cache_enabled = not ldap['ldap_disable_freenas_cache']
    kerberos_realm_id = ldap.pop('ldap_kerberos_realm_id')
    krb_princ = ldap.pop('ldap_kerberos_principal')

    if not kerberos_realm_id or not krb_princ:
        # LDAP service isn't configured to use IPA principal or kerberos config. Still not joined.
        return ds_migrate_ldap(conn, ldap)

    if not krb_princ.startswith('host/'):
        # User isn't using an IPA-related kerberos principal. This means hand-rolled configuration
        # and so we'll throw it into the generic LDAP config as well
        return ds_migrate_ldap(conn, ldap)

    # Our host keytab encodes our hostname in it
    # example: host/test39iollzjz7.tn.ixsystems.net@TN.IXSYSTEMS.NET
    hostname = krb_princ.split('.')[0][len('host/'):]

    realm_name = None
    for realm in realms:
        if realm['id'] == kerberos_realm_id:
            realm_name = realm['krb_realm']
            break

    if not realm_name:
        # This shouldn't happen, but since we have a kerberos principal we can extract from it
        try:
            realm_name = krb_princ.split('@')[1]
        except Exception:
            # Some very broken config, fallback to plain LDAP
            return ds_migrate_ldap(conn, ldap)

    cred_krb5 = encrypt(dumps({'credential_type': 'KERBEROS_PRINCIPAL', 'principal': krb_princ}))
    target_server = ldap['ldap_hostname'].split()[0]

    # initialize our directoryservices row
    conn.execute(text("INSERT INTO directoryservices (enable, service_type) VALUES (1, 'IPA')"))

    # Unfortunately, we can't set the IPA_SMB_DOMAIN during migration because it's not known until runtime
    stmt = (
        'UPDATE directoryservices SET '
        'service_type = :stype, '
        'cred_type = :cred_type,'
        'cred_krb5 = :cred_krb5,'
        'enable = :enable,'
        'enable_account_cache = :enable_cache,'
        'timeout = :timeout,'
        'kerberos_realm_id = :realm_id,'
        'ipa_domain = :dom,'
        'ipa_basedn = :basedn,'
        'ipa_hostname = :hostname,'
        'ipa_target_server =  :server,'
        'ipa_validate_certificates = :validate_certs '
    )

    conn.execute(
        text(stmt), {
            'enable': ldap['ldap_enable'],
            'stype': 'IPA',
            'enable_cache': cache_enabled,
            'cred_type': 'KERBEROS_PRINCIPAL',
            'cred_krb5': cred_krb5,
            'timeout': ldap['ldap_timeout'],
            'realm_id': kerberos_realm_id,
            'basedn': ldap['ldap_basedn'],
            'validate_certs': ldap['ldap_validate_certificates'],
            'dom': realm_name,
            'server': target_server,
            'hostname': hostname
        }
    )


def migrate_idmap_domain(dom, netbios_domain_name) -> dict | None:
    """ returning None means that we need to exclude idmap from configuration because it's invalid """
    out = {
        'name': netbios_domain_name,
        'idmap_backend': dom['idmap_domain_idmap_backend'].upper(),
        'range_low': dom['idmap_domain_range_low'],
        'range_high': dom['idmap_domain_range_high']
    }

    # idmap_domain_options may be something like "{"sssd_compat": false}" or empty string ""
    # the original field had a NOT NULL constraint.
    orig_opts = loads(dom.get('idmap_domain_options') or '{}')

    match out['idmap_backend']:
        case 'AUTORID' | 'RID' | 'AD':
            # no transformation needed
            out.update(orig_opts)
        case 'LDAP':
            url = orig_opts.pop('ldap_url', None)
            if not url:
                # LDAP url was not populated. This never worked
                return None

            prefix = 'ldaps://' if orig_opts.get('ssl', 'ON') == 'ON' else 'ldap://'
            ldap_url = f'{prefix}{url}' if not url.startswith(('ldap://', 'ldaps://')) else url
            out.update(orig_opts)
            out['ldap_url'] = ldap_url
        case 'RFC2307':
            if orig_opts.pop('ldap_server', '') != 'STANDALONE':
                # The AD variant although technically existing was never really used by
                # customers as AD was the proper option for this
                return None

            for key in ('cn_realm', 'ldap_domain'):
                orig_opts.pop(key, None)

            prefix = 'ldaps://' if orig_opts.pop('ssl', 'ON') == 'ON' else 'ldap://'
            url = orig_opts.pop('ldap_url', None)
            if not url:
                # LDAP url was not populated. This never worked
                return None

            ldap_url = f'{prefix}{url}' if not url.startswith(('ldap://', 'ldaps://')) else url
            out.update(orig_opts)
            out['ldap_url'] = ldap_url
        case _:
            # unsupported backend drop it
            return None

    return out


def ds_migrate_ad(conn, ad):
    smb = conn.execute(text('SELECT * FROM services_cifs')).mappings().first()
    idmaps = conn.execute(text('SELECT * FROM directoryservice_idmap_domain')).mappings().all()
    primary_idmap = None
    default_domain = None
    cache_enabled = not ad['ad_disable_freenas_cache']

    # Exclude variations of broken configurations
    if not ad['ad_domainname'] or not ad['ad_kerberos_principal'] or not ad['ad_kerberos_realm_id']:
        # If we're properly joined to AD then these will be present. Rather than migrate
        # a broken configuration, just bail here
        return

    for idmap in idmaps:
        if idmap['idmap_domain_name'] == 'DS_TYPE_ACTIVEDIRECTORY':
            primary_idmap = idmap
        elif idmap['idmap_domain_name'] == 'DS_TYPE_DEFAULT_DOMAIN':
            default_domain = idmap

    if not primary_idmap or not default_domain:
        # The idmap configuration is totally busted. User deleted the AD entry via sqlite3 command?
        # There's no way this would work in previous version and so bail here as well
        return

    cred_krb5 = encrypt(dumps({'credential_type': 'KERBEROS_PRINCIPAL', 'principal': ad['ad_kerberos_principal']}))

    # autorid covers the default domain in idmap configuration for winbindd and so its
    # directory services configuration is slightly different
    if primary_idmap['idmap_domain_idmap_backend'] == 'AUTORID':
        idmap_config = encrypt(dumps({'idmap_domain': migrate_idmap_domain(primary_idmap, smb['cifs_srv_workgroup'])}))
    else:
        idmap_domain = migrate_idmap_domain(primary_idmap, smb['cifs_srv_workgroup'])
        if not idmap_domain:
            # AD won't work without a valid idmap domain, bail out
            return

        idmap_config = encrypt(dumps({
            'builtin': {
                'range_low': default_domain['idmap_domain_range_low'],
                'range_high': default_domain['idmap_domain_range_high']
            },
            'idmap_domain': idmap_domain
        }))

    trusted_doms = []
    if ad['ad_allow_trusted_doms']:
        for idmap in idmaps:
            if idmap['idmap_domain_name'] in ('DS_TYPE_LDAP', 'DS_TYPE_ACTIVEDIRECTORY', 'DS_TYPE_DEFAULT_DOMAIN'):
                continue

            converted = migrate_idmap_domain(idmap, idmap['idmap_domain_name'])
            if not converted:
                # invalid configuration, remove from trusted domains
                continue

            trusted_doms.append(converted)

    has_trusted_doms = len(trusted_doms) > 0
    trusted_doms = encrypt(dumps(trusted_doms))

    # initialize our directoryservices row
    conn.execute(text("INSERT INTO directoryservices (enable, service_type) VALUES (1, 'ACTIVEDIRECTORY')"))

    stmt = (
        'UPDATE directoryservices SET '
        'enable_dns_updates = :dnsup,'
        'cred_type = :cred_type,'
        'cred_krb5 = :cred_krb5,'
        'enable_account_cache = :enable_cache,'
        'timeout = :timeout,'
        'kerberos_realm_id = :realm_id,'
        'ad_domain = :dom,'
        'ad_hostname = :hostname,'
        'ad_idmap = :idmap,'
        'ad_site = :site,'
        'ad_computer_account_ou = :caou,'
        'ad_use_default_domain = :defdom,'
        'ad_enable_trusted_domains = :enable_trusted_doms,'
        'ad_trusted_domains = :trusted_doms'
    )

    conn.execute(
        text(stmt), {
            'enable_cache': cache_enabled,
            'cred_type': 'KERBEROS_PRINCIPAL',
            'cred_krb5': cred_krb5,
            'timeout': ad['ad_timeout'],
            'dom': ad['ad_domainname'],
            'hostname': smb['cifs_srv_netbiosname'],
            'idmap': idmap_config,
            'site': ad['ad_site'] or None,
            'caou': ad['ad_createcomputer'] or None,
            'defdom': ad['ad_use_default_domain'],
            'enable_trusted_doms': has_trusted_doms,
            'trusted_doms': trusted_doms,
            'dnsup': ad['ad_allow_dns_updates'],
            'realm_id': ad['ad_kerberos_realm_id']
        }
    )


def ds_migrate():
    conn = op.get_bind()
    ad = conn.execute(text('SELECT * FROM directoryservice_activedirectory')).mappings().first()
    ldap = conn.execute(text('SELECT * FROM directoryservice_ldap')).mappings().first()

    if ldap['ldap_enable']:
        if ldap['ldap_server_type'] == 'FREEIPA':
            return ds_migrate_ipa(conn, ldap)
        else:
            return ds_migrate_ldap(conn, ldap)

    elif ad['ad_enable']:
        return ds_migrate_ad(conn, ad)


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
    sa.Column('ldap_basedn', sa.String(length=120), nullable=True),
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

    with op.batch_alter_table('directoryservices', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_directoryservices_cred_ldap_mtls_cert_id'), ['cred_ldap_mtls_cert_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_directoryservices_kerberos_realm_id'), ['kerberos_realm_id'], unique=False)

    # Migrate from old to new
    ds_migrate()

    # Drop old tables
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
