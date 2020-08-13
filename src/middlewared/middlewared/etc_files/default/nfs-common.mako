<%
    config = middleware.call_sync("nfs.config")
%>
% if config["rpcstatd_port"]:
    STATDOPTS="--port ${config["rpcstatd_port"]}"
% endif;
