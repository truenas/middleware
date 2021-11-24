# -*- coding=utf-8 -*-
import json
import logging

logger = logging.getLogger(__name__)

__all__ = ['get_app_version']


def get_app_version():
    with open('/data/manifest.json') as f:
        manifest = json.load(f)

    return {
        'stable': 'MASTER' not in manifest['version'],
        'version': manifest['version'],
        'fullname': f"TrueNAS-SCALE-{manifest['version']}",
        'buildtime': manifest['buildtime'],
    }
