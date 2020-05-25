# -*- coding=utf-8 -*-
import itertools
import re

SCALE_MANIFEST_FILE = "/data/manifest.json"
SCALE_UPDATE_SERVER = "https://update.freenas.org/scale"

UPLOAD_LOCATION = "/var/tmp/firmware"

SEP = re.compile(r"[-.]")


def can_update(old_version, new_version):
    for x, y in itertools.zip_longest(SEP.split(old_version), SEP.split(new_version), fillvalue=''):
        if x < y:
            return True
        if x > y:
            return False

    return False
