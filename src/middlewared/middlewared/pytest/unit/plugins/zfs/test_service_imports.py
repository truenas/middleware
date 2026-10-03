from middlewared.plugins.zfs import resource


def test_zfs_resource_service_module_imports():
    assert resource.ZFSResourceService._config.namespace == "zfs.resource"
