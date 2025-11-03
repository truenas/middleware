<%
	import os
	import ipaddress
	import stat
	from middlewared.utils.filter_list import filter_list

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

	users = middleware.call_sync('user.query', [['local', '=', True]])
	root_user = filter_list(users, [['username', '=', 'root']], {'get': True})
	login_banner = render_ctx['system.advanced.login_banner']
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
% if root_user['ssh_password_enabled']:
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
PasswordAuthentication no
% if ssh_config['kerberosauth']:
GSSAPIAuthentication yes
% endif
PubkeyAuthentication yes

# These are forced to be enabled with 2FA
UsePAM yes
## Motd is handled by pam_motd
PrintMotd no
SetEnv LC_ALL=C.UTF-8

% if ssh_config['passwordauth']:
% for user in filter_list(users, [['ssh_password_enabled', '=', True]]):
Match User "${user['username']}"
	PasswordAuthentication yes
	ChallengeResponseAuthentication yes
% endfor
% for group in ssh_config['password_login_groups']:
Match Group "${group}"
	PasswordAuthentication yes
	ChallengeResponseAuthentication yes
% endfor
% endif
% if login_banner != '':
Banner /etc/login_banner
% endif
# These are aux params that MUST COME LAST
# in the config. User provided "Match" blocks,
# for example, need to come AFTER the UsePam
# line. Otherwise ssh service WILL NOT START.
${ssh_config['options']}
