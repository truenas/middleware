<%
    gc = middleware.call_sync('datastore.config', 'network.globalconfiguration', {'prefix': 'gc_'})
    hostname = gc['hostname']
    use_fqdn = False
    if gc['hostname'] and gc['domain']:
        use_fqdn = True
        hostname = f"{gc['hostname']}.{gc['domain']}"

    nameservers = ', '.join([gc[f'nameserver{i}'] for i in range(1, 4) if gc[f'nameserver{i}']]) or None
    use_ns = nameservers is not None
%>
option rfc3442-classless-static-routes code 121 = array of unsigned integer 8;
% if use_fqdn:
send fqdn.fqdn "${hostname}";
% else:
send host-name "${hostname}";
% endif
% if gc['ipv4gateway']:
supersede routers ${gc['ipv4gateway']};
% endif
% if use_ns:
supersede domain-name-servers ${nameservers};
% endif
request subnet-mask, broadcast-address, time-offset, routers,
        domain-name, domain-name-servers, domain-search, host-name,
        dhcp6.name-servers, dhcp6.domain-search, dhcp6.fqdn, dhcp6.sntp-servers,
        netbios-name-servers, netbios-scope, interface-mtu,
        rfc3442-classless-static-routes, ntp-servers;
