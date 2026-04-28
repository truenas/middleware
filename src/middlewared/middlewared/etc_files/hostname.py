from socket import sethostname

from truenas_os_pyutils.io import atomic_write

from middlewared.service import CallError


def render(service, middleware):
    hostname = middleware.call_sync("network.configuration.config")['hostname_local']

    with atomic_write("/etc/hostname", "w") as f:
        f.write(hostname)

    # set the new hostname in kernel
    try:
        sethostname(hostname)
    except Exception as e:
        raise CallError(f'Failed to set hostname: {e}')
