<%
    from middlewared.plugins.network_.global_config import HOSTS_FILE_EARMARKER
    from middlewared.utils.directoryservices.common import ds_config_to_fqdn
    from middlewared.utils.directoryservices.constants import DSType

    network_config = middleware.call_sync('network.configuration.config')
    ds_config = middleware.call_sync('directoryservices.config')
    hostname = network_config['hostname_local']
    domain_name = network_config['domain']
    ds_fqdn = None
    if ds_config['enable'] and ds_config['service_type'] in (DSType.AD.value, DSType.IPA.value):
        # The name registered in the domain is not necessarily this server's own FQDN. In
        # the HA case it is the virtual hostname rather than the local one, and an IPA
        # hostname may itself be a complete FQDN placing the server in a DNS zone other
        # than the IPA domain. Both names must resolve when they differ.
        ds_fqdn = ds_config_to_fqdn(ds_config).lower()
%>
% if ds_fqdn and ds_fqdn != f'{hostname}.{domain_name}':
127.0.0.1	${ds_fqdn} ${ds_fqdn.split('.')[0]}
% endif
127.0.0.1	${hostname}.${domain_name} ${hostname}
127.0.0.1	localhost

# The following lines are desirable for IPv6 capable hosts
::1	localhost ip6-localhost ip6-loopback
ff02::1 ip6-allnodes
ff02::2 ip6-allrouters

${HOSTS_FILE_EARMARKER}
% for host in network_config['hosts']:
${host}
% endfor
