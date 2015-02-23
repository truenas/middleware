from django.utils.translation import ugettext as _

from licenselib.license import Features
from freenasUI.common.system import get_sw_name
from freenasUI.freeadmin.hook import AppHook
from freenasUI.support.utils import get_license


class PluginsHook(AppHook):

    name = 'plugins'
    unlock_restart = True

    def top_menu(self, request):
        license, reason = get_license()
        sw_name = get_sw_name().lower()
        if sw_name == 'freenas' or Features.jails in license.features:
            return [
                {
                    'name': _('Plugins'),
                    'icon': 'images/ui/menu/plugins.png',
                    'onclick': 'Menu.openPlugins();',
                    'weight': 0,
                },
            ]
        return []
