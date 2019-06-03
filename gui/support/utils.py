import logging

from freenasUI.middleware.client import client

log = logging.getLogger('support.utils')
ADDRESS = 'support-proxy.ixsystems.com'
LICENSE_FILE = '/data/license'


def dedup_enabled():
    with client as c:
        return c.call('system.feature_enabled', 'DEDUP')


def get_license():
    try:
        with client as c:
            license = c.call('system.info')['license']
    except Exception as e:
        return None, str(e)

    return license, None


def jails_enabled():
    with client as c:
        return c.call('system.feature_enabled', 'JAILS')


def fc_enabled():
    with client as c:
        return c.call('system.feature_enabled', 'FIBRECHANNEL')


def vm_enabled():
    with client as c:
        return c.call('system.feature_enabled', 'VM')
