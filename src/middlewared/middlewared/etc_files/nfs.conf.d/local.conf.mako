<%
    config = render_ctx["nfs.config"]
%>
[nfsd]
syslog = 1
vers2 = n
% if config['servers']:
threads = ${config['servers']}
% endif
% if config['udp']:
udp = y
% else:
udp = n
% endif
% if "NFSV3" in config["protocols"]:
vers3 = y
% else:
vers3 = n
% endif
% if "NFSV4" in config["protocols"]:
vers4 = y
% else:
vers4 = n
% endif
% if config['bindip']:
host = ','.join(config['bindip'])
% endif

[mountd]
% if config['servers']:
threads = ${config['servers']}
% endif
% if config['mountd_port']:
port = ${config['mountd_port']}
% endif
% if config['userd_manage_gids']:
manage-gids = ${config['userd_manage_gids']}
% endif

[statd]
% if config['rpcstatd_port']:
port = ${config['rpcstatd_port']}
% endif

[lockd]
% if config['rpclockd_port']:
port = ${config['rpclockd_port']}
% endif
