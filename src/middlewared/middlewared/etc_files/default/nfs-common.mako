<%
    config = render_ctx["nfs.config"]
    statd_opts = ["-N 2"]
    if config["rpcstatd_port"]:
        statd_opts.append(f'--port {config["rpcstatd_port"]}')

    if config["rpclockd_port"]:
        statd_opts.append(f'--nlm-port {config["rpclockd_port"]}')
%>
STATDOPTS="${' '.join(statd_opts)}"
NEED_STATD=yes
% if config["v4_krb_enabled"]:
NEED_GSSD=yes
NEED_IDMAPD=yes
% else:
NEED_GSSD=no
% endif
