"""Replace a stored line break in a value that has to stay on one line

Revision ID: ede75214c588
Revises: 89df7b088012
Create Date: 2026-11-12 12:00:00.000000+00:00

"""
import json
import logging

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ede75214c588'
down_revision = '89df7b088012'
branch_labels = None
depends_on = None


logger = logging.getLogger('alembic.runtime.migration')

COLUMNS = {
    'account_api_key': ('name', 'revoked_reason', 'user_identifier'),
    'account_bsdgroups': ('bsdgrp_group',),
    'account_bsdusers': ('bsdusr_email', 'bsdusr_full_name', 'bsdusr_home', 'bsdusr_shell', 'bsdusr_username'),
    'account_privilege': ('builtin_name', 'name'),
    'account_twofactor_user_auth': ('user_sid',),
    'app_registry': ('name', 'uri'),
    'container_config': ('bridge', 'preferred_pool', 'v4_network', 'v6_network'),
    'container_container': (
        'capabilities_policy', 'cpuset', 'dataset', 'init', 'initdir', 'initgroup', 'inituser', 'name', 'time',
        'uuid'
    ),
    'directoryservice_kerberoskeytab': ('keytab_name',),
    'directoryservice_kerberosrealm': (
        'krb_admin_server', 'krb_kdc', 'krb_kpasswd_server', 'krb_primary_kdc', 'krb_realm'
    ),
    'directoryservices': (
        'ad_computer_account_ou', 'ad_domain', 'ad_hostname', 'ad_site', 'cred_type', 'ipa_basedn', 'ipa_domain',
        'ipa_hostname', 'ipa_target_server', 'ldap_base_group', 'ldap_base_netgroup', 'ldap_base_user',
        'ldap_basedn', 'ldap_group_gid', 'ldap_group_member', 'ldap_group_object_class', 'ldap_netgroup_member',
        'ldap_netgroup_object_class', 'ldap_netgroup_triple', 'ldap_schema', 'ldap_shadow_expire',
        'ldap_shadow_inactive', 'ldap_shadow_last_change', 'ldap_shadow_max', 'ldap_shadow_min',
        'ldap_shadow_warning', 'ldap_user_gecos', 'ldap_user_gid', 'ldap_user_home_directory', 'ldap_user_name',
        'ldap_user_object_class', 'ldap_user_shell', 'ldap_user_uid', 'service_type'
    ),
    'enclosure_label': ('encid',),
    'filesystem_acltemplate': ('acltemplate_acltype', 'acltemplate_name'),
    'network_alias': ('alias_address', 'alias_address_b', 'alias_vip'),
    'network_globalconfiguration': (
        'gc_domain', 'gc_domains', 'gc_hostname', 'gc_hostname_b', 'gc_hostname_virtual', 'gc_httpproxy',
        'gc_ipv4gateway', 'gc_ipv6gateway', 'gc_nameserver1', 'gc_nameserver2', 'gc_nameserver3'
    ),
    'network_interface_link_address': ('interface', 'link_address', 'link_address_b'),
    'network_interfaces': ('int_address', 'int_address_b', 'int_fec_mode', 'int_interface', 'int_name', 'int_vip'),
    'network_lagginterface': ('lagg_lacpdu_rate', 'lagg_protocol', 'lagg_xmit_hash_policy'),
    'network_lagginterfacemembers': ('lagg_physnic',),
    'network_staticroute': ('sr_destination', 'sr_gateway'),
    'network_vlan': ('vlan_pint', 'vlan_vint'),
    'rdma_interface': ('rdmaif_address', 'rdmaif_ifname', 'rdmaif_node'),
    'reporting_exporters': ('name',),
    'services_cifs': (
        'cifs_SID', 'cifs_srv_admin_group', 'cifs_srv_description', 'cifs_srv_dirmask', 'cifs_srv_encryption',
        'cifs_srv_filemask', 'cifs_srv_guest', 'cifs_srv_minimum_protocol', 'cifs_srv_netbiosalias',
        'cifs_srv_netbiosname', 'cifs_srv_unixcharset', 'cifs_srv_workgroup'
    ),
    'services_docker': ('cidr_v6', 'pool'),
    'services_fc_host': ('fc_host_alias', 'fc_host_wwpn', 'fc_host_wwpn_b'),
    'services_fibrechanneltotarget': ('fc_port',),
    'services_ftp': ('ftp_anonpath', 'ftp_dirmask', 'ftp_filemask', 'ftp_masqaddress', 'ftp_tls_policy'),
    'services_iscsitarget': ('iscsi_target_alias', 'iscsi_target_mode', 'iscsi_target_name'),
    'services_iscsitargetauthcredential': (
        'iscsi_target_auth_discovery_auth', 'iscsi_target_auth_peeruser', 'iscsi_target_auth_user'
    ),
    'services_iscsitargetauthorizedinitiator': ('iscsi_target_initiator_initiators',),
    'services_iscsitargetextent': (
        'iscsi_target_extent_dataset', 'iscsi_target_extent_filesize', 'iscsi_target_extent_naa',
        'iscsi_target_extent_name', 'iscsi_target_extent_path', 'iscsi_target_extent_product_id',
        'iscsi_target_extent_relative_path', 'iscsi_target_extent_rpm', 'iscsi_target_extent_serial',
        'iscsi_target_extent_type', 'iscsi_target_extent_vendor'
    ),
    'services_iscsitargetglobalconfiguration': ('iscsi_basename', 'iscsi_isns_servers'),
    'services_iscsitargetgroups': ('iscsi_target_authtype', 'iscsi_target_initialdigest'),
    'services_iscsitargetportalip': ('iscsi_target_portalip_ip',),
    'services_nfs': ('nfs_srv_v4_domain',),
    'services_nvmet_global': ('nvmet_global_basenqn',),
    'services_nvmet_host': ('nvmet_host_hostnqn',),
    'services_nvmet_namespace': (
        'nvmet_namespace_dataset', 'nvmet_namespace_device_nguid', 'nvmet_namespace_device_path',
        'nvmet_namespace_device_uuid', 'nvmet_namespace_relative_path'
    ),
    'services_nvmet_port': ('nvmet_port_addr_traddr', 'nvmet_port_addr_trsvcid'),
    'services_nvmet_subsys': ('nvmet_subsys_name', 'nvmet_subsys_serial', 'nvmet_subsys_subnqn'),
    'services_services': ('srv_service',),
    'services_snmp': (
        'snmp_community', 'snmp_contact', 'snmp_location', 'snmp_v3_authtype', 'snmp_v3_privproto',
        'snmp_v3_username'
    ),
    'services_ssh': ('ssh_sftp_log_facility', 'ssh_sftp_log_level'),
    'services_truenas_s3': (
        'default_audit_overflow', 'host_id', 'log_level', 'managed_root_dataset', 'owner_id_seed', 'region'
    ),
    'services_ups': (
        'ups_description', 'ups_driver', 'ups_identifier', 'ups_mode', 'ups_monuser', 'ups_port', 'ups_remotehost',
        'ups_shutdown', 'ups_shutdowncmd'
    ),
    'services_webshare': ('passkey',),
    'sharing_cifs_share': (
        'cifs_comment', 'cifs_dataset', 'cifs_hostsallow', 'cifs_hostsdeny', 'cifs_name', 'cifs_path',
        'cifs_path_suffix', 'cifs_purpose', 'cifs_relative_path', 'cifs_share_acl', 'cifs_vuid'
    ),
    'sharing_nfs_share': (
        'nfs_dataset', 'nfs_hosts', 'nfs_mapall_group', 'nfs_mapall_user', 'nfs_maproot_group', 'nfs_maproot_user',
        'nfs_network', 'nfs_path', 'nfs_relative_path'
    ),
    'sharing_webshare_share': ('dataset', 'name', 'path', 'relative_path'),
    'storage_disk': (
        'disk_advpowermgmt', 'disk_bus', 'disk_hddstandby', 'disk_identifier', 'disk_kmip_uid', 'disk_lunid',
        'disk_model', 'disk_name', 'disk_serial', 'disk_size', 'disk_subsystem', 'disk_transfermode', 'disk_type',
        'disk_zfs_guid'
    ),
    'storage_encrypteddataset': ('kmip_uid', 'name'),
    'storage_jbof': ('jbof_mgmt_ip1', 'jbof_mgmt_ip2', 'jbof_mgmt_username', 'jbof_uuid'),
    'storage_replication': (
        'repl_compression', 'repl_direction', 'repl_encryption_key_format', 'repl_encryption_key_location',
        'repl_lifetime_unit', 'repl_logging_level', 'repl_name', 'repl_name_regex', 'repl_netcat_active_side',
        'repl_netcat_active_side_listen_address', 'repl_netcat_passive_side_connect_address', 'repl_readonly',
        'repl_restrict_schedule_daymonth', 'repl_restrict_schedule_dayweek', 'repl_restrict_schedule_hour',
        'repl_restrict_schedule_minute', 'repl_restrict_schedule_month', 'repl_retention_policy',
        'repl_schedule_daymonth', 'repl_schedule_dayweek', 'repl_schedule_hour', 'repl_schedule_minute',
        'repl_schedule_month', 'repl_state', 'repl_target_dataset', 'repl_transport'
    ),
    'storage_resilver': ('weekday',),
    'storage_scrub': ('scrub_daymonth', 'scrub_dayweek', 'scrub_hour', 'scrub_minute', 'scrub_month'),
    'storage_task': (
        'task_dataset', 'task_daymonth', 'task_dayweek', 'task_hour', 'task_lifetime_unit', 'task_minute',
        'task_month', 'task_naming_schema', 'task_state'
    ),
    'storage_vmwareplugin': ('datastore', 'filesystem', 'hostname', 'username'),
    'storage_volume': ('vol_guid', 'vol_name'),
    'system_acmednsauthenticator': ('name',),
    'system_acmeregistration': (
        'directory', 'new_account_uri', 'new_nonce_uri', 'new_order_uri', 'revoke_cert_uri', 'tos', 'uri'
    ),
    'system_acmeregistrationbody': ('status',),
    'system_advanced': (
        'adv_anonstats_token', 'adv_kernel_extra_options', 'adv_kmip_uid', 'adv_sed_user', 'adv_serialport',
        'adv_serialspeed', 'adv_sysloglevel'
    ),
    'system_alert': ('key', 'klass', 'node', 'source', 'uuid'),
    'system_alertservice': ('level', 'name', 'type'),
    'system_certificate': ('cert_acme_uri', 'cert_name'),
    'system_cloudcredentials': ('name', 'provider'),
    'system_email': ('em_fromemail', 'em_fromname', 'em_outgoingserver', 'em_security', 'em_user'),
    'system_failover': ('master_node',),
    'system_globalid': ('system_uuid',),
    'system_keychaincredential': ('name', 'type'),
    'system_keyvalue': ('key',),
    'system_kmip': ('server', 'ssl_version'),
    'system_migration': ('name',),
    'system_ntpserver': ('ntp_address',),
    'system_settings': ('stg_guix_frame_options', 'stg_kbdmap', 'stg_pwenc_check', 'stg_timezone'),
    'system_support': (
        'email', 'name', 'phone', 'secondary_email', 'secondary_name', 'secondary_phone', 'secondary_title', 'title'
    ),
    'system_systemdataset': ('sys_pool', 'sys_uuid', 'sys_uuid_b'),
    'system_truecommand': (
        'api_key_state', 'endpoint', 'remote_address', 'tc_public_key', 'wg_address', 'wg_public_key'
    ),
    'system_tunable': ('tun_orig_value', 'tun_type', 'tun_value', 'tun_var'),
    'system_update': ('upd_profile',),
    'tasks_cloud_backup': (
        'args', 'cache_path', 'dataset', 'daymonth', 'dayweek', 'hour', 'minute', 'month', 'path', 'relative_path',
        'transfer_setting'
    ),
    'tasks_cloudsync': (
        'args', 'dataset', 'daymonth', 'dayweek', 'direction', 'hour', 'minute', 'month', 'path', 'relative_path',
        'transfer_mode'
    ),
    'tasks_cronjob': (
        'cron_command', 'cron_daymonth', 'cron_dayweek', 'cron_hour', 'cron_minute', 'cron_month', 'cron_user'
    ),
    'tasks_initshutdown': ('ini_script', 'ini_type', 'ini_when'),
    'tasks_rsync': (
        'rsync_dataset', 'rsync_daymonth', 'rsync_dayweek', 'rsync_desc', 'rsync_direction', 'rsync_hour',
        'rsync_minute', 'rsync_mode', 'rsync_month', 'rsync_path', 'rsync_relative_path', 'rsync_remotehost',
        'rsync_remotemodule', 'rsync_remotepath', 'rsync_user'
    ),
    'truenas_connect': (
        'account_service_base_url', 'heartbeat_url', 'last_heartbeat_failure_datetime', 'leca_service_base_url',
        'status', 'tnc_base_url'
    ),
    'truenas_s3_accesskey': ('access_key', 'name', 'user_identifier'),
    'truenas_s3_bucket': (
        'audit_overflow', 'dataset', 'layout', 'multipart_etag', 'name', 'object_lock_default_mode',
        'object_ownership', 'permissions_model', 'versioning'
    ),
    'virt_global': ('bridge', 'pool', 'storage_pools', 'v4_network', 'v6_network'),
    'vm_vm': (
        'arch_type', 'bootloader', 'bootloader_ovmf', 'command_line_args', 'cpu_mode', 'cpu_model', 'cpuset',
        'machine_type', 'name', 'nodeset', 'time', 'uuid', 'video_model'
    ),
}

JSON_COLUMNS = {
    'account_bsdgroups': ('bsdgrp_sudo_commands', 'bsdgrp_sudo_commands_nopasswd'),
    'account_bsdusers': ('bsdusr_sudo_commands', 'bsdusr_sudo_commands_nopasswd'),
    'account_privilege': ('ds_groups', 'local_groups', 'roles'),
    'container_container': ('capabilities_state',),
    'directoryservices': ('ipa_smb_domain', 'ldap_server_urls'),
    'filesystem_acltemplate': ('acltemplate_acl',),
    'network_bridge': ('members',),
    'network_globalconfiguration': ('gc_activity', 'gc_service_announcement'),
    'services_catalog': ('preferred_trains',),
    'services_cifs': ('cifs_srv_search_protocols',),
    'services_docker': ('address_pools', 'registry_mirrors'),
    'services_iscsitarget': ('iscsi_target_auth_networks', 'iscsi_target_iscsi_parameters'),
    'services_nfs': ('nfs_srv_protocols',),
    'services_ssh': ('ssh_password_login_groups', 'ssh_weak_ciphers'),
    'services_truenas_s3': ('default_audit', 'global_grants', 'listeners'),
    'services_webshare': ('bindip', 'groups', 'mcp_allowed_groups'),
    'sharing_cifs_share': ('cifs_audit',),
    'sharing_nfs_share': ('nfs_aliases',),
    'storage_replication': (
        'repl_exclude', 'repl_lifetimes', 'repl_naming_schema', 'repl_properties_exclude',
        'repl_properties_override', 'repl_source_datasets'
    ),
    'storage_task': ('task_exclude',),
    'system_advanced': ('adv_isolated_gpu_pci_ids', 'adv_syslogservers'),
    'system_alertclasses': ('classes',),
    'system_security': ('password_complexity_ruleset',),
    'system_settings': ('stg_guiaddress', 'stg_guiallowlist', 'stg_guihttpsprotocols', 'stg_guiv6address'),
    'system_twofactorauthentication': ('services',),
    'tasks_cloud_backup': ('exclude', 'include'),
    'tasks_cloudsync': ('bwlimit', 'exclude', 'include'),
    'tasks_rsync': ('rsync_extra',),
    'truenas_s3_bucket': ('audit', 'grants', 'snapshot_versions'),
}

CONDITIONS = {
    # A udev rules file is legitimately more than one line. A `SYSCTL` value is written as `var=value`
    # into `sysctl.d`, and a `ZFS` value into the `modprobe.d` file baked into the initramfs, so a line
    # break in either appends a directive of the caller's own.
    'system_tunable.tun_value': "tun_type != 'UDEV'",
    'system_tunable.tun_orig_value': "tun_type != 'UDEV'",
}


def upgrade():
    connection = op.get_bind()
    scrubbed = 0
    for table, columns in COLUMNS.items():
        for column in columns:
            statement = (
                f'UPDATE "{table}" SET "{column}" = replace(replace(replace('
                f'"{column}", char(13) || char(10), \' \'), char(10), \' \'), char(13), \' \') '
                f'WHERE (instr("{column}", char(10)) > 0 OR instr("{column}", char(13)) > 0)'
            )
            condition = CONDITIONS.get(f'{table}.{column}')
            if condition:
                statement += f' AND {condition}'

            try:
                result = connection.execute(sa.text(statement))
            except sa.exc.SQLAlchemyError:
                # A scrubbed value can collide with another row of a column that is unique.
                logger.warning('Unable to replace the line breaks stored in %s.%s', table, column, exc_info=True)
                continue

            if result.rowcount > 0:
                logger.info('Replaced the line breaks stored in %s.%s (%d rows)', table, column, result.rowcount)
                scrubbed += result.rowcount

    scrubbed += _upgrade_json(connection)
    if scrubbed:
        logger.info('Replaced a line break in %d stored value(s)', scrubbed)


def _replace(value):
    """Replace every line break of every string `value` holds, at any depth."""
    if isinstance(value, str):
        return value.replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ')

    if isinstance(value, list):
        return [_replace(item) for item in value]

    if isinstance(value, dict):
        return {_replace(key): _replace(item) for key, item in value.items()}

    return value


def _upgrade_json(connection):
    scrubbed = 0
    for table, columns in JSON_COLUMNS.items():
        for column in columns:
            rows = connection.execute(sa.text(f'SELECT rowid, "{column}" FROM "{table}"')).fetchall()
            for rowid, stored in rows:
                # A line break inside an element is stored escaped, as a backslash and an `n`.
                if not stored or not any(sequence in stored for sequence in ('\\n', '\\r', '\n', '\r')):
                    continue

                try:
                    value = json.loads(stored)
                except ValueError:
                    logger.warning('Unable to parse the value stored in %s.%s, row %d', table, column, rowid)
                    continue

                replaced = _replace(value)
                if replaced == value:
                    continue

                connection.execute(
                    sa.text(f'UPDATE "{table}" SET "{column}" = :value WHERE rowid = :rowid'),
                    {'value': json.dumps(replaced), 'rowid': rowid},
                )
                logger.info('Replaced the line breaks stored in %s.%s, row %d', table, column, rowid)
                scrubbed += 1

    return scrubbed


def downgrade():
    pass
