<%
    uris = " ".join([
        connection.uri
        for connection in middleware.libvirt_domains_manager.connection_manager.connections
    ])

    # Using `container.query`/`vm.query` here will result in a deadlock, as these methods retrieve container/VM status,
    # which means ensureing libvirtd is started, which means this file needs to be generated.
    vm_max_shutdown = max(map(
        lambda v: v['shutdown_timeout'],
        (
            middleware.call_sync('datastore.query', 'container.container') +
            middleware.call_sync('datastore.query', 'vm.vm')
        ),
    ), default=10)
%>\
URIS="${uris}"
ON_SHUTDOWN=shutdown
SHUTDOWN_TIMEOUT=${vm_max_shutdown}
