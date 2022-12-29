<%
    import ipaddress
    base_name = middleware.call_sync('iscsi.global.config')['basename']
    targets = middleware.call_sync('iscsi.target.query', [['auth_networks', '!=', []]])

    def parse_auth(auth):
        try:
            ipobj = ipaddress.ip_interface(auth)
        except ValueError:
            middleware.logger.warning("Invalid IP address: %s", auth, exc_info=True)
        else:
            if ipobj.network.prefixlen in (32, 128):
                return str(ipobj.ip)
            return str(ipobj.network)
%>\
% for target in targets:
${base_name}:${target['name']} ${', '.join([parse_auth(auth) for auth in target['auth_networks']])}
% endfor
