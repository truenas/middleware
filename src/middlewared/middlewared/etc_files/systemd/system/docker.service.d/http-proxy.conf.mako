<%
    config = middleware.call_sync('network.configuration.config')
    if not config['httpproxy']:
        raise FileShouldNotExist()
%>\
[Service]
Environment="HTTP_PROXY=${config['httpproxy']}"
Environment="HTTPS_PROXY=${config['httpproxy']}"
