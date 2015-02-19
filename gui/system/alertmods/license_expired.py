from datetime import datetime, timedelta
import os

from django.utils.translation import ugettext as _

from freenasUI.system.alert import alertPlugins, Alert, BaseAlert
from freenasUI.support.utils import LICENSE_FILE
from licenselib.license import License


class LicenseExpiredAlert(BaseAlert):

    def run(self):
        if not os.path.exists(LICENSE_FILE):
            return None
        with open(LICENSE_FILE, 'rb') as f:
            data = f.read()
        try:
            license = License.load(data)
        except:
            return [Alert(
                Alert.CRIT,
                _('Unable to decode TrueNAS license'),
            )]

        end_date = license.contract_end
        if end_date < datetime.now().date():
            return [Alert(
                Alert.CRIT,
                _('Your TrueNAS license has expired'),
            )]
        elif end_date - timedelta(days=30) < datetime.now().date():
            return [Alert(
                Alert.WARN,
                _('Your TrueNAS license is going to expire in %s') % end_date,
            )]


alertPlugins.register(LicenseExpiredAlert)
