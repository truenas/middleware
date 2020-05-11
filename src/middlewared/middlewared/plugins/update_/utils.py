# -*- coding=utf-8 -*-
import itertools
import re

SCALE_MANIFEST_FILE = "/data/manifest.json"
SCALE_UPDATE_SERVER = "http://pivnoy.thelogin.ru/scale"

UPLOAD_LOCATION = "/var/tmp/firmware"

SEP = re.compile(r"[-.]")


def can_update(old_version, new_version):
    return all(x <= y for x, y in itertools.zip_longest(SEP.split(old_version), SEP.split(new_version), fillvalue=''))
