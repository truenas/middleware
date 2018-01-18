import datetime
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
    except Exception as e:
        return None, str(e)

    return license, None


def jails_enabled():
    license, reason = get_license()
    sw_name = get_sw_name().lower()
    if sw_name == 'freenas' or (
        license and Features.jails in license.features
    ):
        return True
    return False


def fc_enabled():
    license, reason = get_license()
    if not license:
        return False
    sw_name = get_sw_name().lower()
    if sw_name == 'truenas':
        # Licenses issued before 2017-04-14 had a bug in the feature bit
        # for fibre channel, which means they were issue having
        # dedup+jails instead.
        if (
            Features.fibrechannel in license.features
        ) or (
            Features.dedup in license.features and
            Features.jails in license.features and
            license.contract_start < datetime.date(2017, 4, 14)
        ):
            return True
    return False


def vm_enabled():
    license, reason = get_license()
    sw_name = get_sw_name().lower()
    if sw_name == 'freenas' or (
        license and Features.vm in license.features
    ):
        return True
    return False
