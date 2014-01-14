import os

from django.utils.translation import ugettext_lazy as _

from freenasUI.system.alert import alertPlugins, Alert, BaseAlert
from freenasUI.system.models import Settings


class HTTPDBindAlert(BaseAlert):

    def run(self):
        address = Settings.objects.all().order_by('-id')[0].stg_guiaddress
        with open('/usr/local/etc/nginx/nginx.conf') as f:
            # XXX: this is parse the file instead of slurping in the contents
            # (or in reality, just be moved somewhere else).
            if f.read().find('0.0.0.0') != -1 and address not in ('0.0.0.0', ''):
                # XXX: IPv6
                return [
                    Alert(
                        Alert.WARN,
                        _('The WebGUI Address could not bind to %s; using '
                        'wildcard') % (address,),
                    )
                ]

alertPlugins.register(HTTPDBindAlert)
