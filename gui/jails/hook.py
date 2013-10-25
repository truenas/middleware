from django.utils.translation import ugettext as _

from freenasUI.freeadmin.hook import AppHook


class JailsHook(AppHook):

    def top_menu(self, request):
        return [
            {
                'name': _('Jails'),
                'icon': 'images/ui/menu/jails.png',
                'onclick': 'Menu.openJails();',
                'weight': 0,
            },
        ]
