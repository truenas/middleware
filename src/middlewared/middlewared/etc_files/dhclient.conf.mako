<%
    gc = middleware.call_sync('datastore.config', 'network.globalconfiguration', {'prefix': 'gc_'})
    hostname = gc['hostname']
    use_fqdn = False
    if gc['hostname'] and gc['domain']:
        use_fqdn = True
        hostname = f"{gc['hostname']}.{gc['domain']}"
%>
% if use_fqdn:
send fqdn.fqdn "${hostname}";
% else:
send host-name "${hostname}";
% endif
% if gc['ipv4gateway']:
supersede routers ${gc['ipv4gateway']}
request subnet-mask, broadcast-address, time-offset,
% else:
request subnet-mask, broadcast-address, time-offset, routers,
% endif
        domain-name, domain-name-servers, domain-search, host-name,
        dhcp6.name-servers, dhcp6.domain-search, dhcp6.fqdn, dhcp6.sntp-servers,
        netbios-name-servers, netbios-scope, interface-mtu,
        ntp-servers;
