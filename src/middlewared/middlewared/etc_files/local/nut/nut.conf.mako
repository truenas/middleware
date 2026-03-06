<%
    ups_config = render_ctx['ups.config']
%>\
MODE=${"netserver" if ups_config.mode == "MASTER" else "netclient"}
