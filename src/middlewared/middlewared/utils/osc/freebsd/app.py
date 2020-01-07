# -*- coding=utf-8 -*-
import logging
import sys

logger = logging.getLogger(__name__)

__all__ = ['get_app_version']


def get_app_version():
    if '/usr/local/lib' not in sys.path:
        sys.path.append('/usr/local/lib')
    # Lazy import to avoid freenasOS configure logging for us
    from freenasOS import Configuration
    conf = Configuration.Configuration()
    sys_mani = conf.SystemManifest()
    if sys_mani:
        buildtime = sys_mani.TimeStamp()
        version = sys_mani.Version()
    else:
        buildtime = version = None
    train = conf.CurrentTrain()
    stable = bool(train and 'stable' in train.lower())
    return {
        'stable': stable,
        'version': version.split('-')[1],
        'fullname': version,
        'buildtime': buildtime,
    }
