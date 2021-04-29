import logging
import subprocess

from middlewared.service import CallError

logger = logging.getLogger(__name__)


def render(service, middleware):
    config = middleware.call_sync("network.configuration.config")
    hostname = config['hostname_local']
    if config['domain']:
        hostname += f'.{config["domain"]}'
    with open("/etc/hostname", "w") as f:
        f.write(hostname)

    cp = subprocess.Popen(["hostname", hostname], stderr=subprocess.PIPE, stdout=subprocess.DEVNULL)
    stderr = cp.communicate()[1]
    if cp.returncode:
        raise CallError(f'Failed to set hostname: {stderr.decode()}')
