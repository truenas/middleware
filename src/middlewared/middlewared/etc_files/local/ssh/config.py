import base64
import os
import re
import stat
import shutil

from contextlib import suppress

SSH_CONFIG_PATH = '/etc/ssh'

SSH_KEYS = [
    'ssh_host_key', 'ssh_host_key.pub', 'ssh_host_dsa_key', 'ssh_host_dsa_key.pub', 'ssh_host_dsa_key-cert.pub',
    'ssh_host_ecdsa_key', 'ssh_host_ecdsa_key.pub', 'ssh_host_ecdsa_key-cert.pub', 'ssh_host_rsa_key',
    'ssh_host_rsa_key.pub', 'ssh_host_rsa_key-cert.pub', 'ssh_host_ed25519_key', 'ssh_host_ed25519_key.pub',
    'ssh_host_ed25519_key-cert.pub'
]

DEFAULT_FILES = ['moduli', 'ssh_config', 'ssh_config.d', 'sshd_config', 'sshd_config.d']


def generate_ssh_config(middleware, ssh_config, dirfd):
    mode = 0o600

    def opener(path, flags):
        return os.open(path, flags, mode=mode, dir_fd=dirfd)

    for k in SSH_KEYS:
        s_key = re.sub(r'([.-])', '_', k).replace('ssh_', '', 1)
        if ssh_config[s_key]:
            decoded_key = base64.b64decode(ssh_config[s_key])
            if decoded_key:
                mode = 0o644 if k.endswith('.pub') else 0o600

                with open(k, 'wb', opener=opener) as f:
                    st = os.fstat(f.fileno())
                    if stat.S_ISREG(st.st_mode) == 0:
                        middleware.logger.warning(
                            "%s/%s: is not a regular file and will be removed. "
                            "This may impact SSH access to the server.",
                            SSH_CONFIG_PATH, k
                        )
                        with suppress(FileNotFoundError):
                            os.remove(os.path.join(SSH_CONFIG_PATH, k))

                    if stat.S_IMODE(st.st_mode) != mode:
                        middleware.logger.debug(
                            "%s/%s: file has unexpected permissions [%s]. "
                            "Changing to new value [%s].",
                            SSH_CONFIG_PATH, k, stat.S_IMODE(st.st_mode), mode
                        )
                        os.fchmod(f.fileno(), mode)

                    if st.st_uid != 0 or st.st_gid != 0:
                        middleware.logger.debug(
                            "%s/%s: unexpected user or group ownership [%d:%d]. "
                            "Changing to new value [0:0]. ",
                            SSH_CONFIG_PATH, k, st.st_uid, st.st_gid
                        )
                        os.fchown(f.fileno(), 0, 0)

                    f.write(decoded_key)

    expected_files = SSH_KEYS + DEFAULT_FILES
    with os.scandir(dirfd) as entries:
        for entry in filter(lambda x: x.name not in expected_files, entries):
            if entry.is_dir():
                middleware.logger.debug("%s: removing unexpected directory.",
                                        os.path.join(SSH_CONFIG_PATH, entry.name))
                shutil.rmtree(os.path.join(SSH_CONFIG_PATH, entry.name))
            else:
                middleware.logger.debug("%s: removing unexpected file.",
                                        os.path.join(SSH_CONFIG_PATH, entry.name))
                os.remove(entry.name, dir_fd=dirfd)


def render(service, middleware, render_ctx):
    dirfd = os.open(SSH_CONFIG_PATH, os.O_RDONLY | os.O_DIRECTORY)
    try:
        generate_ssh_config(middleware, render_ctx['ssh.config'], dirfd)
    finally:
        os.close(dirfd)
