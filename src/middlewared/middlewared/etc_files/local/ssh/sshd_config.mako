<%
	import os
	import ipaddress
	import stat
        from middlewared.utils import filter_list

	ssh_config = render_ctx['ssh.config']

	os.makedirs('/root/.ssh', mode=0o700, exist_ok=True)
	for p in ['/root/.ssh', '/root']:
		st = os.stat(p)
		if stat.S_IMODE(st.st_mode) != 0o700:
			middleware.logger.debug("%s: adjusting permissions to 0o700", p)
			os.chmod(p, 0o700)
		if st.st_uid != 0 or st.st_gid != 0:
			middleware.logger.debug("%s: changing owner to root:root", p)
			os.chown(p, 0, 0)

	if not ssh_config['sftp_log_level']:
		ssh_config['sftp_log_level'] = 'ERROR'

	if not ssh_config['sftp_log_facility']:
		ssh_config['sftp_log_facility'] = 'AUTH'

	ifaces = filter_list(render_ctx['interface.query'], [['name', 'in', ssh_config['bindiface']]])
	bind_ifaces = []
	for iface in ifaces:
		for alias in iface.get('state', {}).get('aliases', []):
			if alias.get('type') in ('INET', 'INET6') and alias.get('address'):
				if ipaddress.ip_address(alias['address']).is_link_local:
					bind_ifaces.append(f"{alias['address']}%{iface['name']}")
				else:
					bind_ifaces.append(alias['address'])

	if bind_ifaces:
		bind_ifaces.insert(0, '127.0.0.1')

	twofactor_auth = render_ctx['auth.twofactor.config']
	twofactor_enabled = twofactor_auth['enabled'] and twofactor_auth['services']['ssh']
	ad_allow_pam = False
	ldap_enabled = False
	ad = render_ctx["activedirectory.config"]
	if ad['enable'] and not ad['restrict_pam']:
		ad_allow_pam = True
	if not ad['enable']:
		ldap_enabled = render_ctx["ldap.config"]["enable"]

%>\
Subsystem	sftp	internal-sftp -l ${ssh_config['sftp_log_level']} -f ${ssh_config['sftp_log_facility']}
% if 'Protocol' not in ssh_config['options']:
Protocol 2
% endif
% if 'UseDNS' not in ssh_config['options']:
UseDNS no
% endif
% if 'ChallengeResponseAuthentication' not in ssh_config['options'] and not twofactor_enabled:
ChallengeResponseAuthentication no
% endif
% if 'ClientAliveCountMax' not in ssh_config['options']:
ClientAliveCountMax 3
% endif
% if 'ClientAliveInterval' not in ssh_config['options']:
ClientAliveInterval 15
% endif
## Scale doesnt have HPN patches yet
% if 'NONE' in ssh_config['weak_ciphers'] and IS_FREEBSD:
NoneEnabled yes
% endif
% if 'VersionAddendum' not in ssh_config['options']:
VersionAddendum none
% endif
## Add aes128-cbc by default. See #20044
% if 'Ciphers' not in ssh_config['options'] and 'AES128-CBC' in ssh_config['weak_ciphers']:
Ciphers +aes128-cbc
% endif
% if ssh_config['tcpport'] > 0:
Port ${ssh_config['tcpport']}
% endif
% for ip in bind_ifaces:
ListenAddress ${ip}
% endfor
% if ssh_config['rootlogin']:
PermitRootLogin yes
% else:
PermitRootLogin without-password
% endif
% if ssh_config['tcpfwd']:
AllowTcpForwarding yes
% else:
AllowTcpForwarding no
% endif
% if ssh_config['compression']:
Compression delayed
% else:
Compression no
% endif
PasswordAuthentication ${"yes" if ssh_config['passwordauth'] else "no"}
% if ssh_config['kerberosauth']:
GSSAPIAuthentication yes
% endif
PubkeyAuthentication yes
${ssh_config['options']}
% if twofactor_enabled or ad_allow_pam or ldap_enabled:
# These are forced to be enabled with 2FA
UsePAM yes
ChallengeResponseAuthentication yes
## We want to set this to no because in linux we have pam_motd being used as well when we use pam_oath.so resulting in duplicate motd's
PrintMotd no
% endif
SetEnv LC_ALL=C.UTF-8
