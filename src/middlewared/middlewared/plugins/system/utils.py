import enum
import os
import re
import typing

from middlewared.utils import MIDDLEWARE_RUN_DIR


DEBUG_MAX_SIZE = 30
FIRST_INSTALL_SENTINEL = '/data/first-boot'
RE_KDUMP_CONFIGURED = re.compile(r'current state\s*:\s*(ready to kdump)', flags=re.M)


class VMProvider(enum.Enum):
    AZURE = 'AZURE'
    NONE = 'NONE'


def get_debug_execution_dir(system_dataset_path: str, iteration: typing.Optional[int] = 0) -> str:
    debug_name = f'ixdiagnose-{iteration}' if iteration else 'ixdiagnose'
    return os.path.join(MIDDLEWARE_RUN_DIR, debug_name) if system_dataset_path is None else os.path.join(
        system_dataset_path, debug_name
    )
