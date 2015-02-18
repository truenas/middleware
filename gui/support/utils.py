import json
import logging
import requests
import simplejson

from django.utils.translation import ugettext as _

from freenasUI.common.system import get_sw_name

log = logging.getLogger('support.utils')
ADDRESS = 'support-proxy.ixsystems.com'


def get_port():
    if get_sw_name().lower() == 'freenas':
        return 8080
    else:
        return 8081


def new_ticket(data):

    log.error("url %r", 'https://%s:%d/api/v1.0/ticket' % (ADDRESS, get_port()))
    try:
        r = requests.post(
            'https://%s:%d/api/v1.0/ticket' % (ADDRESS, get_port()),
            data=json.dumps(data),
            headers={'Content-Type': 'application/json'},
            timeout=10,
        )
        data = r.json()
    except simplejson.JSONDecodeError, e:
        log.debug("Failed to decode ticket attachment response: %s", r.text)
        return False, r.text, None
    except requests.ConnectionError, e:
        return False, _('Connection failed: %s') % e, None
    except requests.Timeout, e:
        return False, _('Connection timed out: %s') % e, None
    if r.status_code != 200:
        log.debug('Support Ticket failed (%d): %s', r.status_code, r.text)
        return False, _('Ticket creation failed, try again later.'), None

    return (not data['error'], data['message'], data.get('ticketnum'))


def ticket_attach(data, file_handler):

    try:
        r = requests.post(
            'https://%s:%d/api/v1.0/ticket/attachment' % (ADDRESS, get_port()),
            data=data,
            timeout=10,
            files={'file': (file_handler.name, file_handler.file)},
        )
        data = r.json()
    except simplejson.JSONDecodeError, e:
        log.debug("Failed to decode ticket attachment response: %s", r.text)
        return False, r.text
    except requests.ConnectionError, e:
        return False, _('Connection failed: %s') % e
    except requests.Timeout, e:
        return False, _('Connection timed out: %s') % e

    return (not data['error'], data['message'])


if __name__ == '__main__':
    print new_ticket({
        'user': 'william',
        'password': '',
        'title': 'API Test',
        'body': 'Testing proxy',
        'version': '9.3-RELEASE'
    })
