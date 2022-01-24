<%
    config = middleware.call_sync("nfs.config")
    options = ["-w"]
    for ip in config["bindip"]:
        options.append(f'-h {ip}')
%>
# /etc/init.d/rpcbind

OPTIONS=${' '.join(options)}
