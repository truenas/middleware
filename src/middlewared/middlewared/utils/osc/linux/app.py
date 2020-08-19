# -*- coding=utf-8 -*-
import re
import json
import logging

logger = logging.getLogger(__name__)

__all__ = ['get_app_version']

RE_UNSTABLE = re.compile('.+-[0-9]{12}$')


def get_app_version():
    with open('/data/manifest.json') as f:
        manifest = json.load(f)

    return {
        'stable': not RE_UNSTABLE.match(manifest['version']),
        'version': manifest['version'],
        'fullname': f"TrueNAS-SCALE-{manifest['version']}",
        'buildtime': manifest['buildtime'],
    }
