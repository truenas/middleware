<%
	import os

	network_config = middleware.call_sync('network.configuration.config')
	ad_config = middleware.call_sync('datastore.config', 'directoryservice.activedirectory')
	if IS_FREEBSD:
		nis_enabled = middleware.call_sync('datastore.config', 'directoryservice.nis')['nis_enable']
	else:
		nis_enabled = False

	hostname = network_config['hostname_local']
	domain_name = network_config['domain']

	# Following is the hard coded value of NIS_HOSTSSTR which comes from rc.NIS
	NIS_HOSTSSTR = '+::'

	host_conf = '/etc/host.conf'
	if nis_enabled:
		with open(host_conf, 'a') as f:
			f.write('nis\n')
	elif ad_config['ad_enable']:
		hostname = middleware.call_sync('smb.config')['netbiosname_local'].lower()
		domain_name = ad_config['ad_domainname'].lower()
	else:
		if not os.path.isfile(host_conf):
			open(host_conf, 'w').close()
		else:
			with open(host_conf, 'r+') as f:
				content = f.read()
				f.seek(0)
				f.write('\n'.join([line for line in content.split('\n') if line.strip() != 'nis']))
				f.truncate()

		os.chmod('/etc/host.conf', 0o644)

%>
# $FreeBSD$
#
# Host Database
#
# This file should contain the addresses and aliases for local hosts that
# share this file.  Replace 'my.domain' below with the domainname of your
# machine.
#
# In the presence of the domain name service or NIS, this file may
# not be consulted at all; see /etc/nsswitch.conf for the resolution order.
#
#
::1			localhost localhost.my.domain
127.0.0.1		localhost localhost.my.domain
#
# Imaginary network.
#10.0.0.2		myname.my.domain myname
#10.0.0.3		myfriend.my.domain myfriend
#
# According to RFC 1918, you can use the following IP networks for
# private nets which will never be connected to the Internet:
#
#	10.0.0.0	-   10.255.255.255
#	172.16.0.0	-   172.31.255.255
#	192.168.0.0	-   192.168.255.255
#
# In case you want to be able to connect to the Internet, you need
# real official assigned numbers.  Do not try to invent your own network
# numbers but instead get one from your network provider (if any) or
# from your regional registry (ARIN, APNIC, LACNIC, RIPE NCC, or AfriNIC.)
#
${network_config['hosts']}
127.0.0.1	${hostname}.${domain_name} ${hostname}
::1		${hostname}.${domain_name} ${hostname}
% if IS_FREEBSD and nis_enabled:
${NIS_HOSTSSTR}
% endif
