import contextlib
import os
import shutil
import subprocess
import tempfile
import typing
import yaml

from middlewared.service import CallError


INSTANCE_CONFIG_FILE = 'backup.yaml'


class NoDatesSafeLoader(yaml.SafeLoader):
    pass


# We do not want the incus files we manipulate to change format of date time strings
# as incus breaks afterwards
NoDatesSafeLoader.add_constructor(
    'tag:yaml.org,2002:timestamp',
    lambda loader, node: node.value
)


def get_instance_config_file_path(instance_path: str) -> str:
    return os.path.join(instance_path, INSTANCE_CONFIG_FILE)


def get_instance_ds_type(instance: dict) -> str:
    return 'containers' if instance['type'] == 'container' else 'virtual-machines'


def get_instance_ds(instance: dict) -> str:
    return os.path.join(instance['pool'], '.ix-virt', get_instance_ds_type(instance), instance['name'])


@contextlib.contextmanager
def mount_instance_ds(instance_ds: str) -> typing.Iterator[str]:
    with tempfile.TemporaryDirectory() as mounted:
        try:
            subprocess.run(['mount', '-t', 'zfs', instance_ds, mounted])
        except subprocess.CalledProcessError as e:
            raise CallError(f'Invalid instance dataset: {e.stdout}')
        try:
            yield mounted
        finally:
            subprocess.run(['umount', mounted])


def get_instance_configuration(instance_path: str) -> dict:
    path = get_instance_config_file_path(instance_path)
    try:
        with open(path, 'r') as f:
            return yaml.load(f.read(), NoDatesSafeLoader)
    except FileNotFoundError:
        raise CallError(f'Instance configuration file not found at {path!r}')
    except yaml.YAMLError as e:
        raise CallError(f'Failed to parse instance configuration file: {e}')


def update_instance_configuration(instance_path: str, config: dict) -> None:
    path = get_instance_config_file_path(instance_path)
    # We will always keep a backup of the current configuration before applying the modified version
    shutil.copy(path, f'{path}.backup')
    with open(path, 'w') as f:
        yaml.safe_dump(config, f)


def clean_incus_devices(devices: dict, searched_paths: set, found_paths: set) -> None:
    for device_name in list(devices):
        device_config = devices[device_name]
        if device_config.get('type') != 'disk' or 'source' not in device_config or not os.path.isabs(
            device_config['source']
        ):
            continue

        source = device_config['source']
        if source in searched_paths:
            if source not in found_paths:
                # This source does not exist, remove the device
                devices.pop(device_name)
                continue
            else:
                # Nothing to do, this path exists
                continue

        searched_paths.add(source)
        if os.path.exists(source):
            # This source exists, add it to found_paths
            found_paths.add(source)
            continue
        else:
            devices.pop(device_name)
