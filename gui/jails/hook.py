from django.utils.translation import ugettext as _

from licenselib.license import Features
from freenasUI.common.system import get_sw_name
from freenasUI.freeadmin.hook import AppHook
from freenasUI.support.utils import get_license


class JailsHook(AppHook):

    name = 'jails'

    def top_menu(self, request):
        license, reason = get_license()
        sw_name = get_sw_name().lower()
        if sw_name == 'freenas' or (license and Features.jails in license.features):
            return [
                {
                    'name': _('Jails'),
                    'icon': 'images/ui/menu/jails.png',
                    'onclick': 'Menu.openJails();',
                    'weight': 5,
                },
            ]
        return []
