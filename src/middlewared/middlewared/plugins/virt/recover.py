from middlewared.service import CallError, Service

from .recover_utils import (
    clean_incus_devices, get_instance_ds, get_instance_configuration, mount_instance_ds, update_instance_configuration,
)


class VirtRecoverService(Service):

    class Config:
        namespace = 'virt.recover'
        private = True

    def instance(self, instance):
        # Here instance must have these 3 attributes
        # name/pool/type
        try:
            return self.recover_instance_impl(instance)
        except Exception as e:
            raise CallError(f'Failed to recover instance {instance["name"]}: {e}')

    def recover_instance_impl(self, instance):
        instance_ds = get_instance_ds(instance)

        with mount_instance_ds(instance_ds) as mounted:
            config = get_instance_configuration(mounted)
            devices = config.get('container', {}).get('devices', {})
            expanded_config_devices = config.get('container', {}).get('expanded_devices', {})
            searched_paths = set()
            found_paths = set()
            # So it seems incus relies on devices but still keeps the expanded devices config
            # However in my testing if we removed problematic device from devices only it worked
            # I think we should still try to update this on both these keys regardless
            clean_incus_devices(devices, searched_paths, found_paths)
            clean_incus_devices(expanded_config_devices, searched_paths, found_paths)
            update_instance_configuration(mounted, config)
