<%
    uris = " ".join([
        connection.uri
        for connection in middleware.libvirt_domains_manager.connection_manager.connections
    ])

    vm_max_shutdown = max(map(
        lambda v: v['shutdown_timeout'],
        middleware.call_sync('container.query') + middleware.call_sync('vm.query'),
    ), default=10)
%>\
URIS="${uris}"
ON_SHUTDOWN=shutdown
SHUTDOWN_TIMEOUT=${vm_max_shutdown}
