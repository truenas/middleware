<%
    from middlewared.plugins.vm.utils import LIBVIRT_URI


    vm_max_shutdown = max(map(lambda v: v['shutdown_timeout'], middleware.call_sync('vm.query')), default=10)
%>\
URIS="${LIBVIRT_URI}"
ON_SHUTDOWN=shutdown
SHUTDOWN_TIMEOUT=${vm_max_shutdown}
