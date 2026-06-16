<%
    gc = middleware.call_sync('datastore.config', 'network.globalconfiguration', {'prefix': 'gc_'})
    hostname = gc['hostname']
    use_fqdn = False
    if gc['hostname'] and gc['domain']:
        use_fqdn = True
        hostname = f"{gc['hostname']}.{gc['domain']}"

    nameservers = ' '.join([gc[f'nameserver{i}'] for i in range(1, 4) if gc[f'nameserver{i}']]) or None

    interfaces = middleware.call_sync('datastore.query', 'network.interfaces', [], {'prefix': 'int_'})
    no_autoconf = [i['interface'] for i in interfaces if not i['ipv6auto']]
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

# Per-interface IPv6 autoconfiguration ("Autoconfigure IPv6") control.
# dhcpcd does SLAAC in userspace by default, independent of the
# net.ipv6.conf.<if>.autoconf sysctl, so disabling it via sysctl has no
# effect on dhcpcd-managed interfaces. Suppress Router Solicitation here
# instead so neither dhcpcd nor the kernel assigns a SLAAC address or an
# RA-derived default route when autoconf is disabled.
% for iface in no_autoconf:
interface ${iface}
    noipv6rs
% endfor