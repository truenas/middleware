from middlewared.schema import Bool, Dict, Int, List, Str, accepts
from middlewared.service import Service

import os
import sys

if '/usr/local/www' not in sys.path:
    sys.path.append('/usr/local/www')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'freenasUI.settings')

import django
django.setup()

from freenasUI.common.system import send_mail


class MailService(Service):

    @accepts(Dict(
        'mail-message',
        Str('subject'),
        Str('text'),
        List('to', items=[Str('email')]),
        Int('interval'),
        Str('channel'),
        Int('timeout'),
        Bool('queue', default=True),
    ))
    def send(self, message):
        """
        Sends mail using configured mail settings.
        """
        # TODO: For now this is just a wrapper for freenasUI send_mail,
        #       when the time comes we will do the reverse, logic here
        #       and calling this method from freenasUI.
        return send_mail(**message)
