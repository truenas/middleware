from django.utils.translation import ugettext as _

from freenasUI.freeadmin.hook import AppHook
from freenasUI.support.utils import jails_enabled


class PluginsHook(AppHook):

    name = 'plugins'
    unlock_restart = True

    def top_menu(self, request):
        if jails_enabled():
            return [
                {
                    'name': _('Plugins'),
                    'icon': 'images/ui/menu/plugins.png',
                    'onclick': 'Menu.openPlugins();',
                    'weight': 0,
                },
            ]
        return []
