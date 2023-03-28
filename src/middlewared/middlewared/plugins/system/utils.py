import contextlib
import enum
import os
import re

from middlewared.service import CallError

CGROUP_ROOT_PATH = '/sys/fs/cgroup'
CGROUP_AVAILABLE_CONTROLLERS_PATH = os.path.join(CGROUP_ROOT_PATH, 'cgroup.subtree_control')
DEBUG_MAX_SIZE = 30
FIRST_INSTALL_SENTINEL = '/data/first-boot'
RE_CGROUP_CONTROLLERS = re.compile(r'(\w+)\s+')
RE_KDUMP_CONFIGURED = re.compile(r'current state\s*:\s*(ready to kdump)', flags=re.M)


class VMProvider(enum.Enum):
    AZURE = 'AZURE'
    NONE = 'NONE'


class Lifecycle:
    def __init__(self):
        self.SYSTEM_BOOT_ID = None
        self.SYSTEM_FIRST_BOOT = False
        # Flag telling whether the system completed boot and is ready to use
        self.SYSTEM_READY = False
        # Flag telling whether the system is shutting down
        self.SYSTEM_SHUTTING_DOWN = False


lifecycle_conf = Lifecycle()


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
