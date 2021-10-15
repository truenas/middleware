from socket import sethostname

from middlewared.service import CallError


def render(service, middleware):
    config = middleware.call_sync("network.configuration.config")
    hostname = config['hostname_local']
    if config['domain']:
        hostname += f'.{config["domain"]}'

    # write the hostname to the file
    with open("/etc/hostname", "w") as f:
        f.write(hostname)

    # set the new hostname in kernel
    try:
        sethostname(hostname)
    except Exception as e:
        raise CallError(f'Failed to set hostname: {e}')
