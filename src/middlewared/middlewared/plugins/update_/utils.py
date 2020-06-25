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
        if x < y:
            return True
        if 'MASTER' in x and 'INTERNAL' in y:
            return True
        if x > y:
            return False

    return False


def scale_update_server():
    cfp = configparser.ConfigParser()
    cfp.read("/data/update.conf")
    return cfp.get("Defaults", "url", fallback=DEFAULT_SCALE_UPDATE_SERVER)
