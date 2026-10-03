from auto_config import pool_name
from middlewared.test.integration.assets.roles import common_checks

SET_ARGS = [{"path": f"{pool_name}/does_not_exist", "properties": {"compression": "lz4"}}]


def test_read_role_cannot_set(unprivileged_user_fixture):
    common_checks(unprivileged_user_fixture, "zfs.resource.set", "ZFS_RESOURCE_READ", False, method_args=SET_ARGS)


def test_write_role_can_set(unprivileged_user_fixture):
    common_checks(unprivileged_user_fixture, "zfs.resource.set", "ZFS_RESOURCE_WRITE", True, method_args=SET_ARGS)
