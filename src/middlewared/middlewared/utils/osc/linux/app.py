# -*- coding=utf-8 -*-
import logging

import apt

logger = logging.getLogger(__name__)

__all__ = ['get_app_version']


def get_app_version():
    cache = apt.Cache()
    # FIXME: use virtual package
    package = cache.get('apt')
    return {
        'stable': 'git' not in package.installed.version,
        'version': package.installed.version,
        'fullname': f'TrueNAS-{package.installed.version.split("+")[0]}',
        'buildtime': None,
    }
