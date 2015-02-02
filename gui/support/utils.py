import json
import logging
import requests

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
    except requests.ConnectionError, e:
        return False, _('Connection failed: %s') % e
    except requests.Timeout, e:
        return False, _('Connection timed out: %s') % e
    if r.status_code != 200:
        log.debug('Support Ticket failed (%d): %s', r.status_code, r.text)
        return False, _('Ticket creation failed, try again later.')

    return True, r.text


if __name__ == '__main__':
    print new_ticket({
        'user': 'william',
        'password': '',
        'title': 'API Test',
        'body': 'Testing proxy',
        'version': '9.3-RELEASE'
    })
