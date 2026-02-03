<%
    gc = middleware.call_sync('datastore.config', 'network.globalconfiguration', {'prefix': 'gc_'})
    hostname = gc['hostname']
    use_fqdn = False
    if gc['hostname'] and gc['domain']:
        use_fqdn = True
        hostname = f"{gc['hostname']}.{gc['domain']}"

    nameservers = ' '.join([gc[f'nameserver{i}'] for i in range(1, 4) if gc[f'nameserver{i}']]) or None
%>
# TrueNAS dhcpcd configuration
# Generated automatically, do not edit

# Global options
% if use_fqdn:
# Send FQDN to DHCP server
hostname ${hostname}
% elif hostname:
# Send hostname to DHCP server
hostname ${hostname}
% endif

# Don't overwrite resolv.conf - TrueNAS manages it
nohook resolv.conf

# Request standard DHCP options
option domain_name_servers, domain_name, domain_search
option classless_static_routes, interface_mtu
option routers, subnet_mask, broadcast_address
option host_name, ntp_servers
# IPv6 options
option dhcp6_name_servers, dhcp6_domain_search

% if gc['ipv4gateway']:
# Override gateway from DHCP
static routers=${gc['ipv4gateway']}
% endif

% if nameservers:
# Override DNS servers from DHCP
static domain_name_servers=${nameservers}
% endif

# Disable IPv4LL (169.254.x.x addresses)
noipv4ll