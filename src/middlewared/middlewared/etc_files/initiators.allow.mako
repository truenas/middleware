<%
    import ipaddress
    base_name = middleware.call_sync('iscsi.global.config')['basename']
    targets = middleware.call_sync('iscsi.target.query', [['auth_networks', '!=', []]])

    def parse_auth(auth):
        s = auth.split('/')
        if len(s) == 2:
            try:
                ipobj = ipaddress.ip_interface(s[0])
            except ValueError:
                middleware.logger.warning(f"Invalid IP address: {s[0]}", exc_info=True)
            else:
                if (ipobj.version == 4 and s[1] == '32') or (ipobj.version == 6 and s[1] == '128'):
                    return str(ipobj.ip)
        return auth
%>\
% for target in targets:
${base_name}:${target['name']} ${', '.join([parse_auth(auth) for auth in target['auth_networks']])}
% endfor
