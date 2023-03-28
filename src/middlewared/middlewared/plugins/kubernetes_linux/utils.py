import os


BACKUP_NAME_PREFIX = 'ix-applications-backup-'
KUBECONFIG_FILE = '/etc/rancher/k3s/k3s.yaml'
KUBERNETES_WORKER_NODE_PASSWORD = 'e3d26cefbdf2f81eff5181e68a02372f'
KUBEROUTER_RULE_PRIORITY = 32764
KUBEROUTER_TABLE_ID = 77
KUBEROUTER_TABLE_NAME = 'kube-router'
MIGRATION_NAMING_SCHEMA = 'ix-app-migrate-%Y-%m-%d_%H-%M'
NODE_NAME = 'ix-truenas'
NVIDIA_RUNTIME_CLASS_NAME = 'nvidia'
OPENEBS_ZFS_GROUP_NAME = 'zfs.openebs.io'
UPDATE_BACKUP_PREFIX = 'system-update-'


def applications_ds_name(pool):
    return os.path.join(pool, 'ix-applications')
