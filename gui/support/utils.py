import logging
import os

from licenselib.license import Features, License
from freenasUI.common.system import get_sw_name

log = logging.getLogger('support.utils')
ADDRESS = 'support-proxy.ixsystems.com'
LICENSE_FILE = '/data/license'


def dedup_enabled():
    license, reason = get_license()
    sw_name = get_sw_name().lower()
    if sw_name == 'freenas' or (
        license and Features.dedup in license.features
    ):
        return True
    return False


def get_license():
    if not os.path.exists(LICENSE_FILE):
        return None, 'ENOFILE'

    with open(LICENSE_FILE, 'r') as f:
        license_file = f.read().strip('\n')

    try:
        license = License.load(license_file)
    except Exception, e:
        return None, unicode(e)

    return license, None


# We removed jails so commenting this out for now
# def jails_enabled():
#     license, reason = get_license()
#     sw_name = get_sw_name().lower()
#     if sw_name == 'freenas' or (
#         license and Features.jails in license.features
#     ):
#         return True
    return False


def fc_enabled():
    license, reason = get_license()
    sw_name = get_sw_name().lower()
    if sw_name == 'truenas' and (
        license and Features.fiberchannel in license.features
    ):
        return True
    return False
