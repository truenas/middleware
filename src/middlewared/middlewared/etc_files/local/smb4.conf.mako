#
# SMB.CONF(5)		The configuration file for the Samba suite 
#

<%
    from middlewared.utils import filter_list
    from middlewared.plugins.smb_.constants import LOGLEVEL_MAP, SMBPath
    from middlewared.plugins.directoryservices import DSStatus, SSL

    guest_enabled = any(filter_list(render_ctx['sharing.smb.query'], [['guestok', '=', True]]))
    fsrvp_enabled = any(filter_list(render_ctx['sharing.smb.query'], [['fsrvp', '=', True]]))
    home_share = filter_list(render_ctx['sharing.smb.query'], [['home', '=', True]])
    home_path = home_share[0]['path'] if home_share else None
    ad_enabled = render_ctx['directoryservices.get_state']['activedirectory'] != 'DISABLED'
    ad_idmap = filter_list(idmap, [('name', '=', 'DS_TYPE_ACTIVEDIRECTORY')], {'get': True}) if ad_enabled else None
    ldap_enabled = render_ctx['directoryservices.get_state']['ldap'] != 'DISABLED'
    loglevelint = int(LOGLEVEL_MAP.inv.get(render_ctx['smb.config']['loglevel'], 1))

    smbconf = {
        'disable spoolss': True,
        'dns proxy': False,
        'load printers': False,
        'max log size': 5120,
        'printcap': '/dev/null',
        'bind interfaces only': True,
        'fruit:nfs_aces': False,
        'fruit:zero_file_id': False,
        'restrict anonymous': 0 if guest_enabled else 2,
        'winbind request timeout': 60 if ad_enabled else 2,
        'passdb backend': f'tdbsam:{SMBPath.PASSDB_DIR.value[0]}/passdb.tdb',
        'workgroup': render_ctx['smb.config']['workgroup'],
        'netbios name': render_ctx['smb.config']['netbiosname_local'],
        'netbios aliases': ' '.join(render_ctx['smb.config']['netbiosalias']),
        'guest account': render_ctx['smb.config']['guest'] if render_ctx['smb.config']['guest'] else 'nobody',
        'obey pam restrictions': any(home_share),
        'create mask': render_ctx['smb.config']['filemask'] or '0744',
        'directory mask': render_ctx['smb.config']['dirmask'] or '0755',
        'ntlm auth': render_ctx['smb.config']['ntlmv1_auth'],
        'server multichannel support': render_ctx['smb.config']['multichannel'],
        'unix charset': render_ctx['smb.config']['unixcharset'],
        'local master': render_ctx['smb.config']['localmaster'],
        'server string': render_ctx['smb.config']['description'],
        'log level': loglevelint,
        'logging': 'file',
        'registry shares': True,
        'include': 'registry',
    }

    if guest_enabled:
        smbconf['map to guest'] = 'Bad User'

    if fsrvp_enabled:
        smbconf.update({
            'rpc_daemon:fssd': 'fork',
            'fss:prune stale': True,
        })

    if render_ctx['smb.config']['enable_smb1']:
       smbconf['server min protocol'] = 'NT1'

    if render_ctx['smb.config']['syslog']:
       smbconf['logging'] = f'syslog@{min(3, loglevelint)} file'

    if smb_bindips := render_ctx['smb.config']['bindip']:
       allowed_ips = set(middleware.call_sync('smb.bindip_choices').values())
       if (rejected := set(smb_bindips) - allowed_ips):
           middleware.logger.warning(
               '%s: IP address(es) are no longer in use and should be removed '
               'from SMB configuration.', rejected
           )

       smbconf['interfaces'] = ' '.join(allowed_ips & set(smb_bindips))

    if ldap_enabled:
        lc = middleware.call_sync('ldap.config')
        if lc['smb']:
            # Legacy LDAP parameters
            smbconf.update({
                'server role': 'member server',
                'passdb backend': f'ldapsam:{" ".join(lc["uri_list"])}',
                'ldap admin dn': lc['binddn'],
                'ldap suffix': lc['basedn'],
                'ldap ssl': 'start tls' if lc['ssl'] == SSL.STARTTLS.value else 'off',
                'local master': False,
                'domain master': False,
                'preferred master': False,
                'security': 'user',
            })
            if lc['kerberos_principal']:
                smbconf['kerberos method'] = 'system keytab'

    if ad_enabled:
        ac = middleware.call_sync('activedirectory.config')
        smbconf.update({
            'server role': 'member server',
            'kerberos method': 'secrets and keytab',
            'security': 'ADS',
            'local master': False,
            'domain master': False,
            'preferred master': False,
            'winbind cache time': 7200,
            'winbind max domain connections': 10,
            'client ldap sasl wrapping': 'seal',
            'template shell': '/bin/sh',
            'allow trusted domains': ac['allow_trusted_doms'],
            'realm': ac['domainname'],
            'ads dns update': False,
            'winbind nss info': ac['nss_info'].lower(),
            'template homedir': home_path if home_path is not None else '/var/empty',
            'winbind enum users': not ac['disable_freenas_cache'],
            'winbind enum groups': not ac['disable_freenas_cache'],
        })

    for i in render_ctx['idmap.query']:
        match i['name']:
            case 'DS_TYPE_DEFAULT_DOMAIN':
                if ad_idmap and ad_idmap['idmap_backend'] == 'AUTORID':
                    continue

                domain = '*'
            case 'DS_TYPE_ACTIVEDIRECTORY':
                if not ad_enabled:
                    continue
                if i['idmap_backend'] == 'AUTORID':
                    domain = '*'
                else:
                    domain = render_ctx['smb.config']['workgroup']
            case 'DS_TYPE_LDAP':
                # This will be removed at future point
                continue
            case _:
                domain = i['name']

        idmap_prefix = f'idmap config {domain} :'
        smbconf.update({
            f'{idmap_prefix} backend': i['idmap_backend'].lower(),
            f'{idmap_prefix} range': f'{i["range_low"]} - {i["range_high"]}',
        })

        disable_starttls = False
        for k, v in i['options'].items():
            backend_parameter = 'realm' if k == 'cn_realm' else k
            match k:
                case 'ldap_server':
                    value = 'ad' if v == 'AD' else 'stand-alone'
                case 'ldap_url':
                    value = f'{"ldaps://" if i["options"]["ssl"]  == "ON" else "ldap://"}{v}'
                case 'ssl':
                    if v != 'STARTTLS':
                        disable_startls = True
                    continue
                case _:
                    value = v

            smbconf.update({f'{idmap_prefix} {backend_parameter}': value})

%>\

[global]
% if render_ctx['failover.status'] in ('SINGLE', 'MASTER'):
% for param, value in smbconf.items():
    ${param} = ${value}
% endfor
% else:
    netbiosname = TN_STANDBY
% endif
