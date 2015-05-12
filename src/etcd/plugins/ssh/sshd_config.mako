Subsystem sftp /usr/libexec/sftp-server -l ${config.get("service.sshd.sftp_log_level")} -f ${config.get("service.sshd.sftp_log_facility")}
Protocol 2
UseDNS no
ChallengeResponseAuthentication no
ClientAliveCountMax 3
ClientAliveInterval 15
NoneEnabled yes
PermitRootLogin ${"yes" if config.get("service.sshd.permit_root_login") else "without-password"}
AllowTcpForwarding ${"yes" if config.get("service.sshd.allow_port_forwarding") else "no"}
Compression ${"delayed" if config.get("service.sshd.compression") else "no"}
PasswordAuthentication ${"yes" if config.get("service.sshd.allow_password_auth") else "no"}
PubkeyAuthentication ${"yes" if config.get("service.sshd.allow_pubkey_auth") else "no"}
