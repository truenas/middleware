<%
	import os

	ssh_config = middleware.call_sync('ssh.config')
	if not os.path.exists('/root/.ssh'):
		os.makedirs('/root/.ssh')

	if not ssh_config['sftp_log_level']:
		ssh_config['sftp_log_level'] = 'ERROR'

	if not ssh_config['sftp_log_facility']:
		ssh_config['sftp_log_facility'] = 'AUTH'

	ifaces = middleware.call_sync('interface.query', [['name', 'in', ssh_config['bindiface']]])
	bind_ifaces = []
	for iface in ifaces:
		for alias in iface.get('state', {}).get('aliases', []):
			if alias.get('type') in ('INET', 'INET6') and alias.get('address'):
				bind_ifaces.append(alias['address'])

	if bind_ifaces:
		bind_ifaces.insert(0, '127.0.0.1')

	twofactor_auth = middleware.call_sync('auth.twofactor.config')
	twofactor_enabled = twofactor_auth['enabled'] and twofactor_auth['services']['ssh']

%>\
Subsystem	sftp	${"internal-sftp" if IS_LINUX else "/usr/libexec/sftp-server"} -l ${ssh_config['sftp_log_level']} -f ${ssh_config['sftp_log_facility']}
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
% if twofactor_enabled:
# These are forced to be enabled with 2FA
UsePAM yes
ChallengeResponseAuthentication yes
    % if IS_LINUX:
## We want to set this to no because in linux we have pam_motd being used as well when we use pam_oath.so resulting in duplicate motd's
PrintMotd no
    % endif
% endif
% if IS_LINUX:
SetEnv LC_ALL=C.UTF-8
% endif
