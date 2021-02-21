#
# SMB.CONF(5)		The configuration file for the Samba suite 
# $FreeBSD$
#
<%
        import os
        import sys
        import logging
        from middlewared.utils import osc
        from middlewared.plugins.smb import SMBPath
        from middlewared.plugins.idmap import IdmapBackend

        logger = logging.getLogger(__name__)

        LOGLEVEL_UNMAP = {
            'NONE': '0',
            'MINIMUM': '1',
            'NORMAL': '2',
            'FULL': '3',
            'DEBUG': '10',
        }

        parsed_conf = {}

        def get_db_config():
            conf = {}

            conf['cifs'] = middleware.call_sync('smb.config')
            conf['ad'] = middleware.call_sync('activedirectory.config')
            conf['ldap'] = middleware.call_sync('ldap.config')
            if IS_FREEBSD:
                conf['nis'] = middleware.call_sync('datastore.config', 'directoryservice.nis')
            conf['gc'] = middleware.call_sync('network.configuration.config')
            conf['shares'] = middleware.call_sync('sharing.smb.query', [['enabled', '=', True], ['locked', '=', False]])
            conf['role'] = 'standalone'
            conf['guest_enabled'] = False
            conf['loglevel'] = LOGLEVEL_UNMAP.get(conf['cifs']['loglevel'])
            conf['fruit_enabled'] = False
            conf['fsrvp_enabled'] = False

            conf['truenas_conf'] = {'is_truenas_ha': False, 'failover_status': 'DEFAULT', 'smb_ha_mode': 'LEGACY'}
            conf['truenas_conf']['smb_ha_mode'] = middleware.call_sync('smb.get_smb_ha_mode')
            if conf['truenas_conf']['smb_ha_mode'] != 'STANDALONE':
                conf['truenas_conf']['is_truenas_ha'] = True
                conf['truenas_conf']['failover_status'] = middleware.call_sync('failover.status')

            if conf['ad']['enable']:
                conf['role'] = 'ad_member'
            elif conf['ldap']['enable'] and conf['ldap']['has_samba_schema']:
                conf['role'] = 'ldap_member'

            if any(filter(lambda x: x['guestok'], conf['shares'])):
                conf['guest_enabled'] = True

            if any(filter(lambda x: x['fsrvp'], conf['shares'])):
                conf['fsrvp_enabled'] = True

            conf['fruit_enabled'] = conf['cifs']['aapl_extensions']

            return conf

        def get_cifs_homedir():
            cifs_homedir = "/home"
            config_homedir = middleware.call_sync('sharing.smb.query', [["enabled", "=", True], ["home", "=", True]])
            if config_homedir:
                cifs_homedir = config_homedir[0]['path']

            return cifs_homedir

        def pam_is_required(conf):
            """
            obey pam restictions parameter is requried to allow pam_mkhomedir to operate on share connect.
            It is also required to enable kerberos auth in LDAP environments
            """
            if middleware.call_sync('sharing.smb.query', [["enabled", "=", True], ["home", "=", True]]):
                return True
            if conf['role'] == 'ldap_member':
                return True

            return False

        def add_bind_interfaces(pc, db):
            """
            smbpasswd by default connects to 127.0.0.1 as an SMB client. For this reason, localhost is added
            to the list of bind ip addresses here.
            """
            allowed_ips = middleware.call_sync('smb.bindip_choices')
            validated_bind_ips = []
            for address in db['cifs']['bindip']:
                if allowed_ips.get(address):
                    validated_bind_ips.append(address)
                else:
                    logger.warning("IP address [%s] is no longer in use "
                                   "and should be removed from SMB configuration.",
                                   address)

            if validated_bind_ips:
                bindips = (db['cifs']['bindip'])
                bindips.insert(0, "127.0.0.1")
                pc.update({'interfaces': " ".join(bindips)})

            pc.update({'bind interfaces only': 'Yes'})

        def add_general_params(pc, db):
            """
            Allocation roundup size is a legacy performance optimization. It generates user confusion at
            default value. The setting we have here is the new default in 4.11.

            `dos filemode` was originally set for windows behavior regarding changing owner. This should be
            reviewed for accuracy. `kernel change notify` is disabled because it will result in an open fd for
            every file that is monitored, leading to resource exhaustion on moderately busy servers.
            `directory name cache size` is a parameter to work around a bug in directory caching in SMB1 for
            FreeBSD. Recent testing could not reproduce the bug, but the issue is moot since SMB1 is being
            deprecated. `username map` is used to map Microsoft accounts to local accounts
            (bob@microsoft.com to bob). `unix extensions` are legacy SMB1 Unix Extensions. We disable
            by default if SMB1 is disabled.
            """
            pc.update({
                'dns proxy': 'No',
                'max log size': '5120',
                'load printers': 'No',
                'printing': 'bsd',
                'printcap name': '/dev/null',
                'disable spoolss': 'Yes',
                'dos filemode': 'Yes',
                'kernel change notify': 'No' if IS_FREEBSD else 'Yes',
                'directory name cache size': '0' if IS_FREEBSD else '100',
                'unix charset': db['cifs']['unixcharset'],
                'log level': f"{db['loglevel']} auth_json_audit:3@/var/log/samba4/auth_audit.log",
                'obey pam restrictions': 'True' if pam_is_required(db) else 'False',
            })
            pc.update({'enable web service discovery': 'True'})

            if not db['ad']['enable'] and middleware.call_sync('user.query', [('microsoft_account', '=', True)], {"count": True}):
                pc.update({
                    'username map': '/usr/local/etc/smbusername.map' if IS_FREEBSD else '/etc/smbusername.map',
                    'username map cache time': '60',
                })

            if db['cifs']['syslog']:
                pc.update({'logging': f'syslog@{"3" if int(db["loglevel"]) > 3 else db["loglevel"]} file'})
            else:
                pc.update({'logging': 'file'})

            if db['cifs']['enable_smb1']:
                pc.update({'server min protocol': 'NT1'})
            else:
                pc.update({'server min protocol': 'SMB2_02'})
                pc.update({'unix extensions': 'No'})
            if db['cifs']['guest'] != "nobody":
                pc.update({'guest account': db['cifs']['guest']})
            if db['guest_enabled']:
                pc.update({'map to guest': 'Bad User'})
            else:
                pc.update({'restrict anonymous': '2'})
            if db['cifs']['ntlmv1_auth']:
                pc.update({'ntlm auth': 'Yes'})
                pc.update({'client ntlmv2 auth': 'No'})
            if db['cifs']['description']:
                pc.update({'server string': db['cifs']['description']})
            if db['cifs']['filemask']:
                pc.update({'create mask': db['cifs']['filemask']})
            if db['cifs']['dirmask']:
                pc.update({'directory mask': db['cifs']['dirmask']})
            if db['fruit_enabled']:
                pc.update({'fruit:nfs_aces': 'No'})
            if db['fsrvp_enabled']:
                pc.update({
                    'rpc_daemon:fssd': 'fork',
                    'fss:prune stale': 'true',
                })

            return pc

        def add_licensebased_params(pc, db):
            if db['truenas_conf']['smb_ha_mode'] == 'UNIFIED':
                pc.update({
                    'netbios name': db['gc']['hostname_virtual'],
                    'netbios aliases': db['cifs']['netbiosalias'],
                    'private dir': SMBPath.PRIVATEDIR.platform(),
                    'state directory': SMBPath.STATEDIR.platform(),
                })
            elif db['truenas_conf']['is_truenas_ha']:
                node = middleware.call_sync('failover.node')
                pc.update({
                    'netbios name': db['cifs']['netbiosname'] if node == 'A' else db['cifs']['netbiosname_b'],
                    'netbios aliases': db['cifs']['netbiosalias'],
                    'private dir': SMBPath.LEGACYPRIVATE.platform(),
                    'state directory': SMBPath.LEGACYSTATE.platform(),
                    'winbind netbios alias spn': 'true'
                })
            else:
                pc.update({
                    'netbios name': db['cifs']['netbiosname'],
                    'netbios aliases': db['cifs']['netbiosalias'],
                    'private dir': SMBPath.PRIVATEDIR.platform(),
                    'state directory': SMBPath.STATEDIR.platform(),
                })

            return pc


        def generate_ldap_backend(ldap):
            """
            LDAP connections should be secured where possible. This may
            be done with Start-TLS or by specifying ldaps:// in the URL
            argument. Multiple servers may be specified in double-quotes.
            """
            prefix = "ldaps://" if ldap["ssl"] == "ON" else "ldap://"
            uri_string = ' '.join(ldap['uri_list'])
            return f'ldapsam:"{uri_string}"'

        def add_rolebased_params(pc, db):
            """
            `AD MEMBER` Ability to become Master Browser is disabled. `enum users`
            and `enum groups` are disabled if the active caching is disabled.
            `allow dns updates` controls whether the server will dynamically
            update its DNS record in AD. This should be disabled in clustered
            or HA configurations. Maximum number of domain connections is increased
            from default of 1 to improve scalability in large AD environments.

            `LDAP MEMBER` configures ldapsam passdb backend for samba. This requires
            that the openldap server have the Samba LDAP schema extensions.
            """
            if db['role'] == "ad_member":
                pc.update({
                    'server role': 'member server',
                    'kerberos method': 'secrets and keytab',
                    'workgroup': db['cifs']['workgroup'].upper(),
                    'realm': db['ad']['domainname'].upper(),
                    'security': 'ADS',
                    'local master': 'No',
                    'domain master': 'No',
                    'preferred master': 'No',
                    'winbind cache time': '7200',
                    'winbind max domain connections': '10',
                    'client ldap sasl wrapping': 'seal',
                    'template shell': '/bin/sh',
                    'template homedir': f'{get_cifs_homedir()}/%D/%U',
                    'ads dns update': 'Yes' if db['ad']['allow_dns_updates'] else 'No',
                    'allow trusted domains': 'Yes' if db['ad']['allow_trusted_doms'] else 'No'
                })
                if db['truenas_conf']['smb_ha_mode'] == 'UNIFIED':
                    pc.update({'ads dns update': 'No'})
                elif db['truenas_conf']['smb_ha_mode'] == "LEGACY":
                    pc.update({'kerberos method': 'secrets only'})
                if not db['ad']['disable_freenas_cache']:
                    pc.update({'winbind enum users': 'Yes'})
                    pc.update({'winbind enum groups': 'Yes'})
                if db['ad']['use_default_domain']:
                    pc.update({'winbind use default domain': 'Yes'})
                if db['ad']['nss_info']:
                    pc.update({'winbind nss info': db['ad']['nss_info'].lower()})

            elif db['role'] == 'ldap_member':
                pc.update({
                    'server role': 'member server',
                    'security': 'user',
                    'ldap admin dn': db['ldap']['binddn'],
                    'ldap suffix': db['ldap']['basedn'],
                    'ldap replication sleep': '1000',
                    'ldap passwd sync': 'Yes',
                    'ldap ssl': 'off' if db['ldap']['ssl'] != 'START_TLS' else 'start tls',
                    'ldapsam:trusted': 'Yes',
                    'domain logons': 'Yes',
                    'passdb backend': generate_ldap_backend(db['ldap']),
                    'workgroup': db['cifs']['workgroup'].upper(),
                })

            elif db['role'] == "standalone":
                pc.update({'server role': 'standalone'})
                pc.update({'workgroup': db['cifs']['workgroup'].upper()})

            return pc

        def check_required_options(idmap, options, domain):
            required_keys = idmap.required_keys()
            missing_keys = []
            for key in required_keys:
                if not options.get(key):
                    missing_keys.append(key)

            if missing_keys:
                logger.warning("Idmap backend for domain [%s] lacks "
                               "required configuration option(s): %s. User "
                               "authentication and apects of domain integration "
                               "may be negatively impacted.", domain, missing_keys)

        def add_idmap_domain(pc, db, idmap, autorid_enabled=False):
            """
            Generate idmap settings. DS_TYPE_LDAP, DS_TYPE_ACTIVEDIRECTORY, and DS_TYPE_DEFAULT_DOMAIN
            are reflected in the UI under Directory Service-> LDAP, Directory Service-> ActiveDirectory,
            and Services-> SMB respectively. These three domains will always exist in the output of
            'idmap.query'. The DS_TYPE_LDAP and DS_TYPE_ACTIVEDIRECTORY entries
            are ignored during idmap generation if the Directory Service is disabled.
            DS_TYPE_DEFAULT_DOMAIN is likewise ignored if AD is enabled and the autorid backend is
            enabled. This is because autorid can only apply to the default domain '*'.
            """
            if db['role'] == 'ad_member':
                if idmap['name'] == 'DS_TYPE_LDAP':
                    return
                if autorid_enabled and idmap['name'] == 'DS_TYPE_DEFAULT_DOMAIN':
                    return

            if db['ldap']['enable'] and idmap['name'] == 'DS_TYPE_ACTIVEDIRECTORY':
                return

            if db['role'] == 'standalone':
                if idmap['name'] in ['DS_TYPE_ACTIVEDIRECTORY', 'DS_TYPE_LDAP']:
                    return

            low_range = idmap['range_low']
            high_range = idmap['range_high']
            backend = IdmapBackend[idmap['idmap_backend']]

            check_required_options(backend, idmap['options'], idmap['name'])

            if idmap['name'] in ['DS_TYPE_ACTIVEDIRECTORY', 'DS_TYPE_LDAP']:
                domain = db['cifs']['workgroup']
            elif idmap['name'] == 'DS_TYPE_DEFAULT_DOMAIN':
                domain = '*'
            else:
                domain = idmap['name']

            if backend != IdmapBackend.AUTORID:
                pc.update({
                    f'idmap config {domain}: backend': backend.name.lower(),
                    f'idmap config {domain}: range': f'{low_range}-{high_range}'
                })

            if backend == IdmapBackend.AUTORID:
                pc.update({
                    f'idmap config * : backend': backend.name.lower(),
                    f'idmap config * : range': f'{low_range}-{high_range}'
                })
                if 'rangesize' in idmap['options']:
                    pc.update({'idmap config * : rangesize': idmap['options']['rangesize']})
                if idmap['options'].get('readonly'):
                    pc.update({'idmap config * : readonly': 'Yes'})
                if idmap['options'].get('ignore_builtin'):
                    pc.update({'idmap config * : ignore_builtin': 'Yes'})

            elif backend == IdmapBackend.AD:
                pc.update({f'idmap config {domain}: schema_mode': idmap['options']['schema_mode'].lower()})
                if idmap['options'].get('unix_nss_info'):
                    pc.update({f'idmap config {domain}: unix_nss_info': 'Yes'})
                if idmap['options'].get('unix_primary_group'):
                    pc.update({f'idmap config {domain}: unix_primary_group': 'Yes'})

            elif backend == IdmapBackend.LDAP:
                if idmap['options'].get('ldap_base_dn'):
                    pc.update({f'idmap config {domain}: ldap_base_dn': idmap['options']['ldap_base_dn']})
                elif db['role'] == 'ldap_member':
                    pc.update({f'idmap config {domain}: ldap_base_dn': db['ldap']['basedn']})

                if idmap['options'].get('ldap_user_dn'):
                    pc.update({f'idmap config {domain}: ldap_user_dn': idmap['options']['ldap_user_dn']})

                if idmap['options'].get('ldap_url'):
                    pc.update({f'idmap config {domain}: ldap_url': idmap['options']['ldap_url']})
                elif db['role'] == 'ldap_member':
                    ldap_uri = generate_ldap_backend(db['ldap']).lstrip('ldapsam: ')
                    pc.update({f'idmap config {domain}: ldap_url': ldap_uri})

                pc.update({f'idmap config {domain}: read only': 'Yes'})
                
            elif backend == IdmapBackend.RFC2307:
                pc.update({f'idmap config {domain}: ldap_server': idmap['options']['ldap_server']})
                if idmap['options'].get('ldap_url'):
                    pc.update({f'idmap config {domain}: ldap_url': idmap['options']['ldap_url']})
                if idmap['options'].get('bind_path_user'):
                    pc.update({f'idmap config {domain}: bind_path_user': idmap['options']['bind_path_user']})
                if idmap['options'].get('bind_path_group'):
                    pc.update({f'idmap config {domain}: bind_path_group': idmap['options']['bind_path_group']})
                if idmap['options'].get('user_cn'):
                    pc.update({f'idmap config {domain}: user_cn': "Yes"})
                if idmap['options'].get('ldap_realm'):
                    pc.update({f'idmap config {domain}: realm': "Yes"})
                if idmap['options'].get('ldap_domain'):
                    pc.update({f'idmap config {domain}: ldap_domain': idmap['options']['ldap_domain']})
                if idmap['options'].get('ldap_user_dn'):
                    pc.update({f'idmap config {domain}: ldap_user_dn': idmap['options']['ldap_user_dn']})
                if idmap['options'].get('ssl'):
                    pc.update({'ldap ssl': 'start tls'})

            return pc

        def add_idmap_params(pc, db):
            idmap_domains = middleware.call_sync('idmap.query')
            autorid_enabled = False
            if db['role'] == "ad_member":
                autorid_enabled = any(filter(lambda x: x['idmap_backend'] == 'AUTORID', idmap_domains))

            for domain in idmap_domains:
                add_idmap_domain(pc, db, domain, autorid_enabled)

            return pc

        def add_aux_params(pc, db):
            for param in db['cifs']['smb_options'].splitlines():
                if not param.strip():
                    continue

                try:
                    aux_key = param.split("=")[0].strip()
                    aux_val = param.split(aux_key)[1].strip()[1:]
                    pc.update({aux_key: aux_val})
                except Exception:
                    logger.debug(f"[global] contains invalid auxiliary parameter: ({param})")

        def parse_config(db):
            pc = {}
            if db['truenas_conf']['smb_ha_mode'] == 'UNIFIED' and db['truenas_conf']['failover_status'] != 'MASTER':
                stub_config = {
                    'netbios name': f"{db['gc']['hostname_virtual']}_STANDBY",
                    'logging': 'file'
                }
                return stub_config

            add_general_params(pc, db)
            add_bind_interfaces(pc, db)
            add_licensebased_params(pc, db)
            add_rolebased_params(pc, db)
            add_idmap_params(pc, db)
            add_aux_params(pc, db)

            return pc

        db = get_db_config()
        parsed_conf = parse_config(db)

%>

[global]
    % for param, value in parsed_conf.items():
      % if type(value) == list:
        ${param} = ${' '.join(value)}
      % else:
        ${param} = ${value}
      % endif
    % endfor
        registry shares = yes
        include = registry
