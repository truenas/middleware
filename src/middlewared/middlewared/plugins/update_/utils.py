# -*- coding=utf-8 -*-
import configparser
import itertools
import os
import re

from middlewared.utils import MIDDLEWARE_RUN_DIR

DEFAULT_SCALE_UPDATE_SERVER = "https://update.ixsystems.com/scale"
DOWNLOAD_UPDATE_FILE = "update.sqsh"
UPLOAD_LOCATION = os.path.join(MIDDLEWARE_RUN_DIR, "upload_image")
SEP = re.compile(r"[-.]")


def can_update(old_version: str, new_version: str) -> bool:
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

        if x.isdigit() and y.isdigit():
            x = int(x)
            y = int(y)

        if x < y:
            return True
        if x > y:
            return False

    return False


def scale_update_server() -> str:
    cfp = configparser.ConfigParser()
    cfp.read("/data/update.conf")
    return cfp.get("Defaults", "url", fallback=DEFAULT_SCALE_UPDATE_SERVER)
