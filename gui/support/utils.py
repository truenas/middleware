import datetime
import json
import logging
import os
import requests
import simplejson

from django.utils.translation import ugettext as _

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


def fetch_categories(data):

    sw_name = get_sw_name().lower()
    try:
        r = requests.post(
            'https://%s/%s/api/v1.0/categories' % (ADDRESS, sw_name),
            data=json.dumps(data),
            headers={'Content-Type': 'application/json'},
            timeout=10,
        )
        data = r.json()
    except simplejson.JSONDecodeError as e:
        log.debug("Failed to decode ticket attachment response: %s", r.text)
        return False, r.text
    except requests.ConnectionError as e:
        return False, _('Connection failed: %s') % e
    except requests.Timeout as e:
        return False, _('Connection timed out: %s') % e

    if 'error' in data:
        return False, data['message']

    return True, data


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


def new_ticket(data):

    sw_name = get_sw_name().lower()
    try:
        r = requests.post(
            'https://%s/%s/api/v1.0/ticket' % (ADDRESS, sw_name),
            data=json.dumps(data),
            headers={'Content-Type': 'application/json'},
            timeout=10,
        )
        data = r.json()
    except simplejson.JSONDecodeError as e:
        log.debug("Failed to decode ticket attachment response: %s", r.text)
        return False, r.text, None
    except requests.ConnectionError as e:
        return False, _('Connection failed: %s') % e, None
    except requests.Timeout as e:
        return False, _('Connection timed out: %s') % e, None
    if r.status_code != 200:
        log.debug('Support Ticket failed (%d): %s', r.status_code, r.text)
        return False, _('Ticket creation failed, try again later.'), None

    return (not data['error'], data['message'], data.get('ticketnum'))


def ticket_attach(data, file_handler):

    sw_name = get_sw_name().lower()
    try:
        r = requests.post(
            'https://%s/%s/api/v1.0/ticket/attachment' % (ADDRESS, sw_name),
            data=data,
            timeout=10,
            files={'file': (file_handler.name, file_handler.file)},
        )
        data = r.json()
    except simplejson.JSONDecodeError as e:
        log.debug("Failed to decode ticket attachment response: %s", r.text)
        return False, r.text
    except requests.ConnectionError as e:
        return False, _('Connection failed: %s') % e
    except requests.Timeout as e:
        return False, _('Connection timed out: %s') % e

    return (not data['error'], data['message'])


if __name__ == '__main__':
    print(new_ticket({
        'user': 'william',
        'password': '',
        'title': 'API Test',
        'body': 'Testing proxy',
        'version': '9.3-RELEASE'
    }))
