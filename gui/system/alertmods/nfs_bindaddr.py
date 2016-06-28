import os

from django.utils.translation import ugettext as _

from freenasUI.system.alert import alertPlugins, Alert, BaseAlert


class NFSBindAlert(BaseAlert):

    def run(self):
        if os.path.exists('/tmp/.nfsbindip_notfound'):
            return [
                Alert(
                    Alert.WARN,
                    _('NFS services could not bind specific IPs, using wildcard'),
                )
            ]

alertPlugins.register(NFSBindAlert)
