from .recover_utils import get_instance_configuration, mount_instance_ds, update_instance_configuration


MIGRATION_NAMING_SCHEMA = 'ix-virt-migrate-%Y-%m-%d_%H-%M'


def virt_ds_name(pool: str) -> str:
    return f'{pool}/.ix-virt'


def get_containers_parent_ds(incus_pool: str) -> str:
    return f'{virt_ds_name(incus_pool)}/containers'


def get_vms_parent_ds(incus_pool: str) -> str:
    return f'{virt_ds_name(incus_pool)}/virtual-machines'


def replace_source_pool_references_in_devices(devices: dict, source_pool: str, target_pool: str) -> None:
    for device_config in devices.values():
        if device_config.get('pool') == source_pool:
            device_config['pool'] = target_pool


def normalize_instances(source_pool: str, target_pool: str, datasets: list[dict]):
    for instance_ds_config in datasets:
        instance_ds = instance_ds_config['id']
        with mount_instance_ds(instance_ds) as mounted:
            # It seems for instance we need to do the following:
            # Make sure if any source_pool refs are found in following places, we patch them
            # 1) Devices i.e root
            # 2) Exapnded config devices i.e root
            # 3) pool config
            config = get_instance_configuration(mounted)
            devices = config.get('container', {}).get('devices', {})
            expanded_config_devices = config.get('container', {}).get('expanded_devices', {})
            replace_source_pool_references_in_devices(devices, source_pool, target_pool)
            replace_source_pool_references_in_devices(expanded_config_devices, source_pool, target_pool)
            pool_config = config['pool']
            '''
            Pool config looks like this
            pool:
              config:
                source: evo/.ix-virt
                zfs.pool_name: evo/.ix-virt
              description: ""
              name: evo
              driver: zfs
              used_by: []
              status: Created
              locations:
              - none
            '''
            pool_config['name'] = target_pool
            pool_config['config'].update({
                'source': virt_ds_name(target_pool),
                'zfs.pool_name': virt_ds_name(target_pool),
            })
            update_instance_configuration(mounted, config)
