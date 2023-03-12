import contextlib
import os
import re

from middlewared.service import CallError


BACKUP_NAME_PREFIX = 'ix-applications-backup-'
CGROUP_ROOT_PATH = '/sys/fs/cgroup'
CGROUP_AVAILABLE_CONTROLLERS_PATH = os.path.join(CGROUP_ROOT_PATH, 'cgroup.subtree_control')
KUBECONFIG_FILE = '/etc/rancher/k3s/k3s.yaml'
KUBERNETES_WORKER_NODE_PASSWORD = 'e3d26cefbdf2f81eff5181e68a02372f'
KUBEROUTER_RULE_PRIORITY = 32764
KUBEROUTER_TABLE_ID = 77
KUBEROUTER_TABLE_NAME = 'kube-router'
MIGRATION_NAMING_SCHEMA = 'ix-app-migrate-%Y-%m-%d_%H-%M'
NODE_NAME = 'ix-truenas'
NVIDIA_RUNTIME_CLASS_NAME = 'nvidia'
OPENEBS_ZFS_GROUP_NAME = 'zfs.openebs.io'
RE_CGROUP_CONTROLLERS = re.compile(r'(\w+)\s+')
UPDATE_BACKUP_PREFIX = 'system-update-'


def applications_ds_name(pool):
    return os.path.join(pool, 'ix-applications')


def get_available_controllers_for_consumption() -> set:
    try:
        with open(CGROUP_AVAILABLE_CONTROLLERS_PATH, 'r') as f:
            return set(RE_CGROUP_CONTROLLERS.findall(f.read()))
    except FileNotFoundError:
        raise CallError(
            'Unable to determine cgroup controllers which are available for consumption as '
            f'{CGROUP_AVAILABLE_CONTROLLERS_PATH!r} does not exist'
        )


def update_available_controllers_for_consumption(to_add_controllers: set) -> set:
    # This will try to update available controllers for consumption and return the current state
    # regardless of the update failing
    with contextlib.suppress(FileNotFoundError, OSError):
        with open(CGROUP_AVAILABLE_CONTROLLERS_PATH, 'w') as f:
            f.write(f'{" ".join(map(lambda s: f"+{s}", to_add_controllers))}')

    return get_available_controllers_for_consumption()
