import os
import re

from middlewared.utils import MIDDLEWARE_RUN_DIR, MIDDLEWARE_BOOT_ENV_STATE_DIR


DEBUG_MAX_SIZE = 30
FIRST_INSTALL_SENTINEL = '/data/first-boot'
BOOTENV_FIRSTBOOT_SENTINEL = os.path.join(MIDDLEWARE_BOOT_ENV_STATE_DIR, '.first-boot')
RE_KDUMP_CONFIGURED = re.compile(r'current state\s*:\s*(ready to kdump)', flags=re.M)


class Lifecycle:
    def __init__(self):
        self.SYSTEM_BOOT_ID = None
        self.SYSTEM_FIRST_BOOT = False
        # Flag telling whether the system completed boot and is ready to use
        self.SYSTEM_READY = False
        # Flag telling whether the system is shutting down
        self.SYSTEM_SHUTTING_DOWN = False
        self.SYSTEM_BOOT_ENV_FIRST_BOOT = False
        # Flag telling whether this is the first boot for the boot environment


def get_debug_execution_dir(system_dataset_path: str, iteration: int = 0) -> str:
    debug_name = f'ixdiagnose-{iteration}' if iteration else 'ixdiagnose'
    return os.path.join(MIDDLEWARE_RUN_DIR, debug_name) if system_dataset_path is None else os.path.join(
        system_dataset_path, debug_name
    )


lifecycle_conf = Lifecycle()
