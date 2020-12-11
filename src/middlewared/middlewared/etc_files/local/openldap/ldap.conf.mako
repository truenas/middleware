<%
        def safe_call(*args):
            try:
                val = middleware.call_sync(*args)
            except:
                val = False
            return val

        uri = None
        base = None
        ssl = False
        tls_cacert = None
        tls_reqcert = True
        binddn = None

        ldap = middleware.call_sync('ldap.config')
        ldap_enabled = ldap['enable']
        is_kerberized = False
        krb_realm = None
        network_timeout = 60
        timeout = 10

        ad = middleware.call_sync('activedirectory.config')
        ad_enabled = ad['enable']
        idmap = middleware.call_sync('idmap.query',
                                     [('name', '=', 'DS_TYPE_ACTIVEDIRECTORY')],
                                     {'get': True})

        if ad['enable'] and idmap['idmap_backend'] in ["rfc2307", "ldap"]:
            is_kerberized = True
            krb_realm = ad['kerberos_realm']
            base = idmap['ldap_base_dn']
            idmap_url = idmap['ldap_url']
            idmap_url = re.sub('^(ldaps?://)', '', idmap_url)
            uri = "%s://%s" % ("ldaps" if idmap['ssl'] == "ON" else "ldap", idmap_url)
            if idmap['ssl'] in ('start_tls', 'on'):
                cert = safe_call('certificate.query', [('id', '=', idmap['certificate']['id'])], {'get': True})
                tls_certfile = cert['certificate_path']
                tls_keyfile = cert['privatekey_path']
                ssl = idmap['ssl']
            timeout = ad['timeout']
            network_timeout = ad['dns_timeout']
            tls_reqcert = ad['validate_certificates']

        elif ldap_enabled and ldap:
            uri = " ".join(ldap['uri_list'])
            if ldap['kerberos_realm']:
                krb_realm = ldap['kerberos_realm']
                is_kerberized = True
            else:
                binddn = ldap['binddn']

            base = ldap['basedn']
            timeout = ldap['timeout']
            network_timeout = ldap['dns_timeout']
            tls_reqcert = ldap['validate_certificates']
            tls_certfile = None

            if ldap['ssl'] in ("START_TLS", "ON"):
                if ldap['certificate']:
                    cert = safe_call('certificate.query', [('id', '=', ldap['certificate'])], {'get': True})
                    tls_certfile = cert['certificate_path']
                    tls_keyfile = cert['privatekey_path']
                ssl = ldap['ssl']
%>
% if (ldap_enabled and ldap) or (ad_enabled and ad):
# This file is used by Samba. If NETWORK_TIMEOUT is too high, then ldap failover
# in Samba's ldapsam passdb backend may not occur.
    %if uri:
URI ${uri}
    %endif
    %if base:
BASE ${base}
    %endif
NETWORK_TIMEOUT ${network_timeout}
TIMEOUT ${timeout}
TLS_CACERT /etc/ssl/truenas_cacerts.pem
    % if ssl:
        % if tls_certfile:
TLS_CERT ${tls_certfile}
TLS_KEY ${tls_keyfile}
SASL_MECH EXTERNAL
        % endif
TLS_REQCERT ${'demand' if tls_reqcert else 'allow'}
    % endif
    % if is_kerberized:
SASL_MECH GSSAPI
SASL_REALM ${krb_realm}
    % elif binddn:
BINDDN ${binddn}
    % endif
% endif
