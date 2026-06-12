<%
    uris = " ".join([
        connection.uri
        for connection in middleware.libvirt_domains_manager.connection_manager.connections
    ])

    # Using `container.query`/`vm.query` here will result in a deadlock, as these methods retrieve container/VM status,
    # which means ensureing libvirtd is started, which means this file needs to be generated.
    containers = middleware.call_sync('datastore.query', 'container.container')
    vms = middleware.call_sync('datastore.query', 'vm.vm')
    vm_max_shutdown = max((g['shutdown_timeout'] for g in containers + vms), default=10)
    # PARALLEL_SHUTDOWN is applied independently per URI (lxc, qemu), so the cap only needs to cover the larger batch.
    parallel_shutdown = max(len(containers), len(vms), 1)
%>\
URIS="${uris}"
ON_SHUTDOWN=shutdown
SHUTDOWN_TIMEOUT=${vm_max_shutdown}
PARALLEL_SHUTDOWN=${parallel_shutdown}
