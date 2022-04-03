<%
    config = render_ctx["nfs.config"]
    mountd_opts = [f'--num-threads {config["servers"]}', '-N 2']
    nfsd_opts = ['-s', '-N 2']

    if not config["v4"]:
        nfsd_opts.append('-N 4')

    if config["userd_manage_gids"]:
        mountd_opts.append("--manage-gids")

    if not config["udp"]:
        # mountd_opts.append("--no-udp")
        nfsd_opts.append("--no-udp")

    if config["mountd_port"]:
        mountd_opts.append(f'--port {config["mountd_port"]}')

    for ip in config["bindip"]:
        nfsd_opts.append(f'-H {ip}')

%>
# Number of servers to start up
RPCNFSDCOUNT="${config["servers"]}"

# Runtime priority of server (see nice(1))
RPCNFSDPRIORITY=0

# Options for rpc.nfsd.
RPCNFSDOPTS="${' '.join(nfsd_opts)}"

# Options for rpc.mountd.
RPCMOUNTDOPTS="${' '.join(mountd_opts)}"

# Kerberos-related options
% if config["v4_krb_enabled"]:
NEED_SVCGSSD=yes
NEED_GSSD=yes
NEED_IDMAPD=yes
% else:
NEED_GSSD=no
NEED_SVCGSSD=no
% endif
