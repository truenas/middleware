import os

from middlewared.plugins.container.lifecycle import apply_idmapped_root_acl
from middlewared.utils.io import write_if_changed

LIBVIRTD_CONF_PATH = '/etc/libvirt/libvirtd.conf'


def render(service, middleware):
    os.makedirs('/run/truenas_libvirt', exist_ok=True)
    apply_idmapped_root_acl()
    write_if_changed(LIBVIRTD_CONF_PATH, 'unix_sock_dir = "/run/truenas_libvirt"')
