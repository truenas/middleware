#
# NSLCD.CONF(5)		The configuration file for LDAP nameservice daemon
#
<%
        ldap = middleware.call_sync('ldap.config')
        kerberos_realm = None
        aux = []
        min_uid = 1000
        kerberos_realm = None
        if ldap:
            certpath = None
            if ldap['certificate']:
                try:
                    cert = middleware.call_sync('certificate.query', [('id', '=', ldap['certificate'])], {'get': True})
                except IndexError:
                    pass
                else:
                    certpath = cert['certificate_path']
                    keypath = cert['privatekey_path']
            if ldap['kerberos_realm']:
                kerberos_realm = middleware.call_sync(
                    'kerberos.realm.query',
                    [('id', '=', ldap['kerberos_realm'])],
                    {'get': True}
                )['realm']
        else:
            ldap = None

        ldap_enabled = ldap['enable']
        for param in ldap['auxiliary_parameters'].splitlines():
            param = param.strip()
            if not param.startswith('nss_min_uid'):
                aux.append(param)
            else:
                try:
                    min_uid = param.split()[1]
                except Exception:
                    pass
%>
% if ldap_enabled:
    uri 	${' '.join(ldap['uri_list'])}
    base 	${ldap['basedn']}
  % if ldap['ssl'] in ('START_TLS', 'ON'):
    ssl 	${ldap['ssl'].lower()}
    tls_cacert	/etc/ssl/certs/ca-certificates.crt
    % if certpath:
    tls_cert	${certpath}
    tls_key	${keypath}
    sasl_mech	EXTERNAL
    % endif
    tls_reqcert ${'demand' if ldap['validate_certificates'] else 'allow'}
  % endif
  % if ldap['binddn'] and ldap['bindpw']:
    binddn 	${ldap['binddn']}
    bindpw 	${ldap['bindpw']}
  % endif
  % if ldap['disable_freenas_cache']:
    nss_disable_enumeration yes
  % endif
  % if kerberos_realm:
    sasl_mech 	GSSAPI
    sasl_realm	${kerberos_realm}
  % endif
    scope 	sub
    timelimit	${ldap['timeout']}
    bind_timelimit ${ldap['dns_timeout']}
  % if ldap['schema'] == 'RFC2307BIS':
    nss_nested_groups yes
  % endif
  % if aux:
    ${'\n'.join(aux)}
  % endif
    nss_min_uid ${min_uid}
    nss_initgroups_ignoreusers ALLLOCAL
% endif
