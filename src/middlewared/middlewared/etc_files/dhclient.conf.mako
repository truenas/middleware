<%
    gconf = middleware.call_sync('datastore.config', 'network.globalconfiguration')
%>
% if gconf['gc_ipv4gateway']:
## If there is a gateway configured in Network, do not request it from DHCP
## Defaults can be found on sbin/dhclient/clparse.c on freebsd
supersede routers ${gconf['gc_ipv4gateway']};

request subnet-mask, broadcast-address, time-offset,
        domain-name, domain-name-servers, domain-search, host-name,
        interface-mtu;
% endif
