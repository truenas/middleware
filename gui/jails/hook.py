from django.utils.translation import ugettext as _

from freenasUI.freeadmin.hook import AppHook
from freenasUI.support.utils import jails_enabled


class JailsHook(AppHook):

    name = 'jails'

    def top_menu(self, request):
        if jails_enabled():
            return [
                {
                    'name': _('Jails'),
                    'icon': 'images/ui/menu/jails.png',
                    'onclick': 'Menu.openJails();',
                    'weight': 5,
                },
            ]
        return []
