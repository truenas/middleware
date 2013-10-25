from django.utils.translation import ugettext as _

from freenasUI.freeadmin.hook import AppHook


class PluginsHook(AppHook):

    name = 'plugins'

    def top_menu(self, request):
        return [
            {
                'name': _('Plugins'),
                'icon': 'images/ui/menu/plugins.png',
                'onclick': 'Menu.openPlugins();',
                'weight': 0,
            },
        ]
