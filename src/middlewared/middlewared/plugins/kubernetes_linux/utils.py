import os
import re

from middlewared.service import CallError


BACKUP_NAME_PREFIX = 'ix-applications-backup-'
CGROUP_ROOT_PATH = '/sys/fs/cgroup'
KUBECONFIG_FILE = '/etc/rancher/k3s/k3s.yaml'
KUBERNETES_WORKER_NODE_PASSWORD = 'e3d26cefbdf2f81eff5181e68a02372f'
KUBEROUTER_RULE_PRIORITY = 32764
KUBEROUTER_TABLE_ID = 77
KUBEROUTER_TABLE_NAME = 'kube-router'
MIGRATION_NAMING_SCHEMA = 'ix-app-migrate-%Y-%m-%d_%H-%M'
NODE_NAME = 'ix-truenas'
OPENEBS_ZFS_GROUP_NAME = 'zfs.openebs.io'
RE_CGROUP_CONTROLLERS = re.compile(r'(\w+)\s+')
UPDATE_BACKUP_PREFIX = 'system-update-'


def applications_ds_name(pool):
    return os.path.join(pool, 'ix-applications')


def get_available_controllers_for_consumption() -> set:
    system_available_controllers_path = os.path.join(CGROUP_ROOT_PATH, 'cgroup.subtree_control')
    try:
        with open(system_available_controllers_path, 'r') as f:
            return set(RE_CGROUP_CONTROLLERS.findall(f.read()))
    except FileNotFoundError:
        raise CallError(
            'Unable to determine cgroup controllers which are available for consumption as '
            f'{system_available_controllers_path!r} does not exist'
        )
