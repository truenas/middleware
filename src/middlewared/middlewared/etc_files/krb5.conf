#
# krb5.conf(5) - configuration file for Kerberos 5
# $FreeBSD$
#
<%
        import logging
        logger = logging.getLogger(__name__)
        from middlewared.utils import filter_list
        from middlewared.plugins.kerberos import KRB_AppDefaults, KRB_LibDefaults

        def parse_defaults(section_name, section_conf, db_def=None):
            default_section = "krb5_main"
            if section_name == "appdefault":
                supported_options = [i.value[0] for i in KRB_AppDefaults]
            elif section_name == "libdefault":
                supported_options = [i.value[0] for i in KRB_LibDefaults]

            db_def_lines = db_def.splitlines()
            for line in db_def_lines:
                ws_lines = line.split()
                if len(ws_lines) < 1:
                    continue
                if ws_lines[-1] == "{":
                    default_section = ws_lines[0]
                elif ws_lines[0] == "}":
                    default_section = "krb5_main"
                    continue
                elif ws_lines[0] in supported_options:
                    binding = line.split("=")
                    if default_section in section_conf:
                        section_conf[default_section].update({binding[0].strip(): binding[1].strip()})
                    else:
                        section_conf.update({default_section: {binding[0].strip(): binding[1].strip()}})
                else:
                    continue

            return section_conf

        db = {}
        db_realms = []
        environment_is_kerberized = False
        db['ad'] = middleware.call_sync('activedirectory.config')
        db['ldap'] = middleware.call_sync('datastore.query', 'directoryservice.ldap', [], {'get': True})
        db['krb_aux'] = middleware.call_sync('kerberos.config')
        db_realms = middleware.call_sync('kerberos.realm.query')
        appdefaults = {'pam': {
            KRB_AppDefaults.FORWARDABLE.parm(): 'true',
            KRB_AppDefaults.TICKET_LIFETIME.parm(): '86400',
            KRB_AppDefaults.RENEW_LIFETIME.parm(): '86400'
        }}

        libdefaults = {'krb5_main': {
            KRB_LibDefaults.DNS_LOOKUP_REALM.parm(): 'true',
            KRB_LibDefaults.DNS_LOOKUP_KDC.parm(): 'true',
            KRB_LibDefaults.TICKET_LIFETIME.parm(): '24h',
            KRB_LibDefaults.CLOCKSKEW.parm(): '300',
            KRB_LibDefaults.FORWARDABLE.parm(): 'true'
        }}

        """
            Active Directory environments are always kerberized. This means
            we make best effort to make a valid krb5.conf and update set correct
            values in the configuration database.

            On the other hand, not all LDAP environments are kerberized so we cannot guess the correct
            realm in this case.
        """
        if db['ad']['enable'] and db['ad']['kerberos_realm']:
            environment_is_kerberized = True
            c_realm = db['ad']['kerberos_realm']
            krb_default_realm = (filter_list(db_realms, [('id', '=', c_realm)]))[0]['realm']
        elif db['ad']['enable']:
            environment_is_kerberized = True
            krb_default_realm = db['ad']['domainname']

            if db_realms:
                db_realm_entry = next((item for item in db_realms if item['realm'] == krb_default_realm), None)
            else:
                db_realm_entry = None

            if db_realm_entry:
                logger.debug(f'Updating Active Directory configuration to use kerberos realm: {db_realm_entry}')
                middleware.call_sync(
                    'datastore.update',
                    'directoryservice.activedirectory', '1',
                    {'ad_kerberos_realm': db_realm_entry['id']}
                )
                db_realms.append({
                    'realm': db_realm_entry['realm'],
                    'kdc': [],
                    'admin_server': [],
                    'kpasswd_server': []
                })
            else:
                logger.debug(f'Generating kerberos realm entry for {krb_default_realm}')
                middleware.call_sync(
                    'datastore.insert',
                    'directoryservice.kerberosrealm',
                    {'krb_realm': krb_default_realm}
                )
                new_realm = middleware.call_sync('kerberos.realm.query', [('realm', '=', krb_default_realm)])
                middleware.call_sync(
                    'datastore.update',
                    'directoryservice.activedirectory', '1',
                    {'ad_kerberos_realm': new_realm[0]['id']}
                )
                db_realms.append({
                    'realm': krb_default_realm,
                    'kdc': [],
                    'admin_server': [],
                    'kpasswd_server': []
                })

        elif db['ldap']['ldap_enable'] and db['ldap']['ldap_kerberos_realm']:
            environment_is_kerberized = True
            krb_default_realm = db['ldap']['ldap_kerberos_realm']['krb_realm']
        else:
            krb_default_realm = None

        if krb_default_realm:
            libdefaults['krb5_main'].update({KRB_LibDefaults.DEFAULT_REALM: krb_default_realm})

        parsed_appdefaults = parse_defaults("appdefault", appdefaults, db_def=db['krb_aux']['appdefaults_aux'])
        parsed_libdefaults = parse_defaults("libdefault", libdefaults, db_def=db['krb_aux']['libdefaults_aux'])

%>
% if db_realms:
[appdefaults]
% for section_name, section in parsed_appdefaults.items():
            % if section_name == "krb5_main":
            % for binding, value in section.items():
            ${binding} = ${value}
            % endfor
            % else:
            ${section_name} = {
            % for binding, value in section.items():
                   ${binding} = ${value}
            % endfor
            }
            % endif
% endfor

[libdefaults]
% for section_name, section in parsed_libdefaults.items():
            % for binding, value in section.items():
            ${binding} = ${value}
            % endfor
% endfor

[domain_realm]
% for realm in db_realms:
            ${realm["realm"].lower()} = ${realm["realm"]}
            .${realm["realm"].lower()} = ${realm["realm"]}
            ${realm["realm"].upper()} = ${realm["realm"]}
            .${realm["realm"].upper()} = ${realm["realm"]}
% endfor

[realms]
% for realm in db_realms:
            ${f'{realm["realm"]}'} = {
                   default_domain = ${realm["realm"]}
                % if realm["kdc"]:
                   kdc = ${' '.join(realm["kdc"])}
                % endif
                % if realm["admin_server"]:
                   admin_server = ${' '.join(realm["admin_server"])}
                % endif
                % if realm["kpasswd_server"]:
                   kpasswd_server = ${' '.join(realm["kpasswd_server"])}
                % endif
            }
% endfor

[logging]
            default = SYSLOG:INFO:LOCAL7
% endif
