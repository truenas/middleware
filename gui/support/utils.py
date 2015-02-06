import json
import logging
import requests
import simplejson

from django.utils.translation import ugettext as _

log = logging.getLogger('support.utils')
ADDRESS = 'support-proxy.ixsystems.com:8080'


def new_ticket(data):

    try:
        r = requests.post(
            'https://%s/api/v1.0/ticket' % ADDRESS,
            data=json.dumps(data),
            headers={'Content-Type': 'application/json'},
            timeout=10,
        )
        data = r.json()
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
            'https://%s/api/v1.0/ticket/attachment' % ADDRESS,
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
