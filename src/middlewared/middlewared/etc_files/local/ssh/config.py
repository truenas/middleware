import base64
import os
import re
import shutil

from truenas_os_pyutils.io import atomic_write

SSH_CONFIG_PATH = '/etc/ssh'

SSH_KEYS = [
    'ssh_host_key', 'ssh_host_key.pub', 'ssh_host_dsa_key', 'ssh_host_dsa_key.pub', 'ssh_host_dsa_key-cert.pub',
    'ssh_host_ecdsa_key', 'ssh_host_ecdsa_key.pub', 'ssh_host_ecdsa_key-cert.pub', 'ssh_host_rsa_key',
    'ssh_host_rsa_key.pub', 'ssh_host_rsa_key-cert.pub', 'ssh_host_ed25519_key', 'ssh_host_ed25519_key.pub',
    'ssh_host_ed25519_key-cert.pub'
]

DEFAULT_FILES = ['moduli', 'ssh_config', 'ssh_config.d', 'sshd_config', 'sshd_config.d']


def render(service, middleware, render_ctx):
    ssh_config = render_ctx['ssh.config']
    for k in SSH_KEYS:
        s_key = re.sub(r'([.-])', '_', k).replace('ssh_', '', 1)
        if ssh_config[s_key]:
            decoded_key = base64.b64decode(ssh_config[s_key])
            if decoded_key:
                mode = 0o644 if k.endswith('.pub') else 0o600
                with atomic_write(os.path.join(SSH_CONFIG_PATH, k), 'wb', perms=mode) as f:
                    f.write(decoded_key)

    expected_files = SSH_KEYS + DEFAULT_FILES
    with os.scandir(SSH_CONFIG_PATH) as entries:
        for entry in filter(lambda x: x.name not in expected_files, entries):
            if entry.is_dir():
                middleware.logger.debug("%s: removing unexpected directory.", entry.path)
                shutil.rmtree(entry.path)
            else:
                middleware.logger.debug("%s: removing unexpected file.", entry.path)
                os.remove(entry.path)
