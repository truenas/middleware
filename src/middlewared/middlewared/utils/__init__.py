import asyncio
import dataclasses
import errno
import functools
import json
import logging
import subprocess
import time
import typing
from typing import Any, Sequence

from .prctl import die_with_parent


# Define Product Strings
@dataclasses.dataclass(slots=True, frozen=True)
class ProductTypes:
    COMMUNITY_EDITION: str = 'COMMUNITY_EDITION'
    ENTERPRISE: str = 'ENTERPRISE'


@dataclasses.dataclass(slots=True, frozen=True)
class ProductNames:
    PRODUCT_NAME: str = 'TrueNAS'


ProductType = ProductTypes()
ProductName = ProductNames()

MIDDLEWARE_RUN_DIR = '/run/middleware'
# Private unix socket that nginx reverse-proxies all external API/UI traffic over.
# Locked down to the nginx worker uid so this traffic is not exposed on loopback TCP.
MIDDLEWARE_NGINX_SOCK = f'{MIDDLEWARE_RUN_DIR}/middlewared-nginx.sock'
MIDDLEWARE_BOOT_ENV_STATE_DIR = '/var/lib/truenas-middleware'
MIDDLEWARE_STARTED_SENTINEL_PATH = f'{MIDDLEWARE_RUN_DIR}/middlewared-started'
BOOTREADY = f'{MIDDLEWARE_RUN_DIR}/.bootready'
BOOT_POOL_NAME_VALID = ['freenas-boot', 'boot-pool']
MANIFEST_FILE = '/data/manifest.json'
UPDATE_TRAINS_FILE_NAME = 'trains_v2.json'
BRAND = ProductName.PRODUCT_NAME

logger = logging.getLogger(__name__)


class UnexpectedFailure(Exception):
    pass


currently_running_subprocesses: set[str] = set()


@typing.overload
async def run(*args: Any, encoding: None = None, **kwargs: Any) -> subprocess.CompletedProcess[bytes]: ...


@typing.overload
async def run(*args: Any, encoding: str, **kwargs: Any) -> subprocess.CompletedProcess[str]: ...


async def run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[bytes] | subprocess.CompletedProcess[str]:
    if isinstance(args[0], list):
        args = tuple(args[0])

    kwargs.setdefault('stdout', subprocess.PIPE)
    kwargs.setdefault('stderr', subprocess.PIPE)
    kwargs.setdefault('check', True)
    if 'encoding' in kwargs:
        kwargs.setdefault('errors', 'strict')
    kwargs.setdefault('close_fds', True)
    kwargs['preexec_fn'] = die_with_parent

    subprocess_identifier = f"{time.monotonic()}: {args!r}"
    try:
        currently_running_subprocesses.add(subprocess_identifier)
        try:
            return await asyncio.to_thread(functools.partial(subprocess.run, args, **kwargs))
        finally:
            currently_running_subprocesses.discard(subprocess_identifier)
    except OSError as e:
        if e.errno == errno.EMFILE:
            logger.warning("Currently running async subprocesses: %r", currently_running_subprocesses)

        raise


@dataclasses.dataclass(slots=True, frozen=True, kw_only=True)
class SwInfo:
    stable: bool
    version: str
    fullname: str
    buildtime: int


@functools.cache
def sw_info() -> SwInfo:
    """Returns the various software information from the manifest file."""
    with open(MANIFEST_FILE) as f:
        manifest = json.load(f)
        version = manifest['version']
        return SwInfo(
            stable='MASTER' not in manifest['version'],
            version=version,
            fullname=f'{BRAND}-{version}',
            buildtime=manifest['buildtime'],
        )


def sw_buildtime() -> int:
    return sw_info().buildtime


def sw_version() -> str:
    return sw_info().fullname


def are_indices_in_consecutive_order(arr: Sequence[int]) -> bool:
    """
    Determine if the integers in an array form a consecutive sequence
    with respect to their indices.

    This function checks whether each integer at a given index position is
    exactly one greater than the integer at the previous index. In other
    words, it verifies that the sequence of numbers increases by exactly one
    as you move from left to right through the array.

    Parameters:
    arr (list[int]): A list of integers whose index-based order needs to be
                     validated.

    Returns:
    bool:
        - True if the numbers are consecutive.
        - False if any number does not follow the previous number by exactly one.

    Examples:
    >>> are_indices_in_consecutive_order([1, 2])
    True

    >>> are_indices_in_consecutive_order([1, 3])
    False

    >>> are_indices_in_consecutive_order([5, 6, 7])
    True

    >>> are_indices_in_consecutive_order([4, 6, 7])
    False

    Edge Cases:
    - An empty array will return True as there are no elements to violate
      the order.
    - A single-element array will also return True for the same reason.

    Notes:
    - The function does not modify the input array and operates in O(n) time
      complexity, where n is the number of elements in the list.
    """
    for i in range(1, len(arr)):
        if arr[i] != arr[i - 1] + 1:
            return False
    return True
