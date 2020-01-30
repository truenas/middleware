# -*- coding=utf-8 -*-
import logging

import apt

logger = logging.getLogger(__name__)

__all__ = ['get_app_version']


def get_app_version():
    cache = apt.Cache()
    package = cache.get('truenas')
    return {
        'stable': 'git' not in package.installed.version,
        'version': package.installed.version,
        'fullname': f'TrueNAS-{package.installed.version.split("+")[0]}',
        'buildtime': None,
    }
