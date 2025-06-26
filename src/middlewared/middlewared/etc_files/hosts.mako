<%
    from middlewared.plugins.network_.global_config import HOSTS_FILE_EARMARKER
    from middlewared.utils.directoryservices.constants import DSType

    network_config = middleware.call_sync('network.configuration.config')
    ds_config = middleware.call_sync('directoryservices.config')
    hostname = network_config['hostname_local']
    ds_hostname = None
    domain_name = network_config['domain']
    if ds_config['enable'] and ds_config['service_type'] in (DSType.AD.value, DSType.IPA.value):
        # In HA case the virtual hostname and local hostname may not match
        # but must both be resolvable.
        ds_hostname = ds_config['configuration']['hostname'].lower()
        domain_name = ds_config['configuration']['domain'].lower()
%>
% if ds_hostname and ds_hostname != hostname:
127.0.0.1	${ds_hostname}.${domain_name} ${ds_hostname}
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
