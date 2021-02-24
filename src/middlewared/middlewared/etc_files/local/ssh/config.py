import base64
import os
import re

from middlewared.utils import osc

if osc.IS_FREEBSD:
    SSH_CONFIG_PATH = '/usr/local/etc/ssh'
else:
    SSH_CONFIG_PATH = '/etc/ssh'


def generate_ssh_config(middleware):
    ssh_config = middleware.call_sync('ssh.config')
    for k in [
        'ssh_host_key', 'ssh_host_key.pub', 'ssh_host_dsa_key', 'ssh_host_dsa_key.pub', 'ssh_host_dsa_key-cert.pub',
        'ssh_host_ecdsa_key', 'ssh_host_ecdsa_key.pub', 'ssh_host_ecdsa_key-cert.pub', 'ssh_host_rsa_key',
        'ssh_host_rsa_key.pub', 'ssh_host_rsa_key-cert.pub', 'ssh_host_ed25519_key', 'ssh_host_ed25519_key.pub',
        'ssh_host_ed25519_key-cert.pub'
    ]:
        s_key = re.sub(r'([.-])', '_', k).replace('ssh_', '', 1)
        if ssh_config[s_key]:
            decoded_key = base64.b64decode(ssh_config[s_key])
            if decoded_key:
                with open(os.path.join(SSH_CONFIG_PATH, k), 'wb') as f:
                    f.write(decoded_key)

    for f in [
        'ssh_host_key', 'ssh_host_dsa_key', 'ssh_host_ecdsa_key', 'ssh_host_rsa_key', 'ssh_host_ed25519_key'
    ]:
        if os.path.exists(os.path.join(SSH_CONFIG_PATH, f)):
            os.chmod(os.path.join(SSH_CONFIG_PATH, f), 0o600)


def render(service, middleware):
    generate_ssh_config(middleware)
