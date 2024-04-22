<%
    from middlewared.plugins.nfs import NFSPath
    state_path = NFSPath.STATEDIR.path()
    cld_storedir = NFSPath.CLDDIR.path()
    cltrack_storedir = NFSPath.CLDTRKDIR.path()
    config = render_ctx["nfs.config"]

    # Fail-safe setting is two nfsd
    num_nfsd = config['servers'] if config['servers'] > 0 else 2

    # man page for mountd says "The default is 1 thread, which is probably enough.",
    # but mount storms at restart benefit from additional mountd.  As such, we recommend
    # the number of mountd be 1/4 the number of nfsd.
    num_mountd = max(int(num_nfsd / 4), 1)
    manage_gids = 'y' if config["userd_manage_gids"] else 'n'
%>
[nfsd]
syslog = 1
vers2 = n
threads = ${num_nfsd}
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
host = ${','.join(config['bindip'])}
% endif

[exportd]
state-directory-path = ${state_path}
[nfsdcld]
storagedir = ${cld_storedir}
[nfsdcltrack]
storagedir = ${cltrack_storedir}

[mountd]
state-directory-path = ${state_path}
threads = ${num_mountd}
% if config['mountd_port']:
port = ${config['mountd_port']}
% endif
manage-gids = ${manage_gids}

[statd]
state-directory-path = ${state_path}
% if config['rpcstatd_port']:
port = ${config['rpcstatd_port']}
% endif

[lockd]
% if config['rpclockd_port']:
port = ${config['rpclockd_port']}
% endif
