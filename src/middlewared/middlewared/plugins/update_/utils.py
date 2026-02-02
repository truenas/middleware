from __future__ import annotations

import configparser
import itertools
import os
import re

from middlewared.utils import MIDDLEWARE_RUN_DIR

DEFAULT_SCALE_UPDATE_SERVER = "https://update.ixsystems.com/scale"
DOWNLOAD_UPDATE_FILE = "update.sqsh"
UPLOAD_LOCATION = os.path.join(MIDDLEWARE_RUN_DIR, "upload_image")
SEP = re.compile(r"[-.+]")


def can_update(old_version: str, new_version: str) -> bool:
    """
    Determine whether an update from an old version to a new version is allowed.

    This function compares two version strings component-by-component, splitting
    on common separators (``-``, ``.``, and ``+``). It supports numeric and special
    tokens and applies custom ordering rules for certain version markers such as
    ``CUSTOM``, ``MASTER`` and ``INTERNAL``.

    The comparison logic follows these rules:
    - Numeric components are compared numerically.
    - Non-numeric components are considered lower priority than numeric ones.
    - The presence of special markers (``CUSTOM``, ``MASTER``, ``INTERNAL``) can
      force an update to be allowed or disallowed.
    - A special case exists to allow updates from versions like ``26.04`` to
      ``26.0.0``.

    Args:
        old_version (str): The currently installed version string.
        new_version (str): The target version string to compare against.

    Returns:
        bool: ``True`` if updating from ``old_version`` to ``new_version`` is
        allowed, ``False`` otherwise.
    """
    prev_x = None
    prev_y = None
    for x, y in itertools.zip_longest(SEP.split(old_version), SEP.split(new_version), fillvalue=''):
        if x.startswith('U') and x[1:].isdigit():
            x = x[1:]
        if y.startswith('U') and y[1:].isdigit():
            y = y[1:]

        for special in ['CUSTOM']:
            if x == special and y != special:
                return False
            elif x != special and y == special:
                return True

        if not x.isdigit() and (y.isdigit() or y == ''):
            return True
        if (x.isdigit() or x == '') and not y.isdigit():
            return False

        if x == 'MASTER' and y != 'MASTER':
            return False
        elif x != 'MASTER' and y == 'MASTER':
            return True

        if (x == 'INTERNAL') != (y == 'INTERNAL'):
            return True

        # 26.04 -> 26.0.0 update
        if prev_x == 26 and prev_y == 26:
            if x == '04' and y == '0':
                return True
            elif x == '0' and y == '04':
                return False

        if x.isdigit() and y.isdigit():
            x = int(x)
            y = int(y)

        if x < y:
            return True
        if x > y:
            return False

        prev_x = x
        prev_y = y

    return False


def scale_update_server() -> str:
    cfp = configparser.ConfigParser()
    cfp.read("/data/update.conf")
    return cfp.get("Defaults", "url", fallback=DEFAULT_SCALE_UPDATE_SERVER)
