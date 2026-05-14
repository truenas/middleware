import os

from middlewared.utils.filesystem.perms import enforce_dir_perms
from middlewared.utils.io import write_if_changed

LIBVIRTD_CONF_PATH = "/etc/libvirt/libvirtd.conf"
IDMAPPED_ROOT_DIR = "/run/truenas_containers/root"


def render(service, middleware):
    os.makedirs("/run/truenas_libvirt", exist_ok=True)
    # makedirs(exist_ok=True) does NOT chmod a pre-existing dir, so follow
    # with enforce_dir_perms to make perms idempotent across reboots.
    os.makedirs(IDMAPPED_ROOT_DIR, mode=0o700, exist_ok=True)
    enforce_dir_perms(IDMAPPED_ROOT_DIR)
    write_if_changed(LIBVIRTD_CONF_PATH, 'unix_sock_dir = "/run/truenas_libvirt"')
