# -*- coding=utf-8 -*-
import configparser
import itertools
import re

DEFAULT_SCALE_UPDATE_SERVER = "https://update.freenas.org/scale"
SCALE_MANIFEST_FILE = "/data/manifest.json"

UPLOAD_LOCATION = "/var/tmp/firmware"

SEP = re.compile(r"[-.]")


def can_update(old_version, new_version):
    for x, y in itertools.zip_longest(SEP.split(old_version), SEP.split(new_version), fillvalue=''):
        if not x.isdigit() and y.isdigit():
            return True
        if x.isdigit() and not y.isdigit():
            return False

        for special in ['CUSTOM', 'MASTER', 'INTERNAL']:
            if x == special and y != special:
                return False
            elif x != special and y == special:
                return True

        if x < y:
            return True
        if x > y:
            return False

    return False


def scale_update_server():
    cfp = configparser.ConfigParser()
    cfp.read("/data/update.conf")
    return cfp.get("Defaults", "url", fallback=DEFAULT_SCALE_UPDATE_SERVER)
