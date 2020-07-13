<%
    ups_config = middleware.call_sync('ups.config')
%>\
MODE=${"netserver" if ups_config["mode"] else "netclient"}
