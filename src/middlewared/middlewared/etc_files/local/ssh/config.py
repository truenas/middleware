import base64
import os
import shutil

from truenas_os_pyutils.io import atomic_write

from middlewared.plugins.ssh.keys import SSHHostKey

SSH_CONFIG_PATH = '/etc/ssh'

DEFAULT_FILES = ['moduli', 'ssh_config', 'ssh_config.d', 'sshd_config', 'sshd_config.d']


def render(service, middleware, render_ctx):
    ssh_config = render_ctx['ssh.config']
    for key in SSHHostKey:
        data = getattr(ssh_config, key.column.removeprefix('ssh_'))
        if data:
            decoded_key = base64.b64decode(data)
            if decoded_key:
                mode = 0o644 if key.value.endswith('.pub') else 0o600
                with atomic_write(key.path, 'wb', perms=mode) as f:
                    f.write(decoded_key)

    expected_files = [key.value for key in SSHHostKey] + DEFAULT_FILES
    with os.scandir(SSH_CONFIG_PATH) as entries:
        for entry in filter(lambda x: x.name not in expected_files, entries):
            if entry.is_dir():
                middleware.logger.debug("%s: removing unexpected directory.", entry.path)
                shutil.rmtree(entry.path)
            else:
                middleware.logger.debug("%s: removing unexpected file.", entry.path)
                os.remove(entry.path)
