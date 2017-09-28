from middlewared.schema import Bool, Dict, Int, List, Str, accepts
from middlewared.service import ConfigService, ValidationErrors

import os
import sys

if '/usr/local/www' not in sys.path:
    sys.path.append('/usr/local/www')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'freenasUI.settings')

import django
from django.apps import apps
if not apps.ready:
    django.setup()

from freenasUI.common.system import send_mail


class MailService(ConfigService):

    class Config:
        datastore = 'system.email'
        datastore_prefix = 'em_'

    @accepts(Dict(
        'mail',
        Str('fromemail'),
        Str('outgoingserver'),
        Int('port'),
        Str('security', enum=['PLAIN', 'SSL', 'TLS']),
        Bool('smtp'),
        Str('user'),
        Str('pass'),
    ))
    async def do_update(self, data):
        config = await self.config()

        new = config.copy()
        new.update(data)
        new['security'] = new['security'].lower()  # Django Model compatibility

        verrors = ValidationErrors()

        if new['smtp'] and new['user'] == '':
            verrors.add('user', 'This field is required when SMTP authentication is enabled')

        if verrors:
            raise verrors

        await self.middleware.call('datastore.update', 'system.email', config['id'], new)
        return config['id']

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
