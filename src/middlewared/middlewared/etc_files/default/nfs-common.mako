<%
    config = render_ctx["nfs.config"]
    statd_opts = []
    if config["rpcstatd_port"]:
        statd_opts.append(f'--port {config["rpcstatd_port"]}')

    if config["rpclockd_port"]:
        statd_opts.append(f'--nlm-port {config["rpclockd_port"]}')
%>
% if statd_opts:
STATDOPTS="${' '.join(statd_opts)}"
%endif
NEED_STATD=yes
% if config["v4_krb_enabled"]:
NEED_GSSD=yes
NEED_IDMAPD=yes
% else:
NEED_GSSD=no
% endif
