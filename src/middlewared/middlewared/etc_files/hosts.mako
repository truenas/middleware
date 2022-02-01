<%
	network_config = middleware.call_sync('network.configuration.config')
	ad_config = middleware.call_sync('datastore.config', 'directoryservice.activedirectory')
	hostname = network_config['hostname_local']
	domain_name = network_config['domain']
	if ad_config['ad_enable']:
		hostname = middleware.call_sync('smb.config')['netbiosname_local'].lower()
		domain_name = ad_config['ad_domainname'].lower()

	k8s_entry_add = middleware.call_sync('kubernetes.config')['dataset'] and not middleware.call_sync('kerberos.keytab.has_nfs_principal')
	k8s_node = middleware.call_sync('k8s.node.node_name')
%>
% if network_config['hosts']:
${network_config['hosts']}
% endif
127.0.0.1	localhost
127.0.0.1	${hostname}.${domain_name} ${hostname}
% if k8s_entry_add:
127.0.0.1	${k8s_node}
% endif

# The following lines are desirable for IPv6 capable hosts
::1	localhost ip6-localhost ip6-loopback
ff02::1 ip6-allnodes
ff02::2 ip6-allrouters
