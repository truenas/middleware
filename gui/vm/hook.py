from django.core.urlresolvers import reverse
from django.utils.html import escapejs
from django.utils.translation import ugettext as _

from freenasUI.freeadmin.hook import AppHook


class VMHook(AppHook):

    name = 'vm'

    def hook_app_tabs_vm(self, request):
        from freenasUI.middleware.notifier import notifier

        tabs = [{
            'name': 'VM',
            'focus': 'vm.VM.View',
            'verbose_name': _('VMs'),
            'url': reverse('freeadmin_vm_vm_datagrid'),
        }]

        return tabs

    def top_menu(self, request):
        return [
            {
                'name': _('VMs'),
                'icon': 'images/ui/menu/vm.png',
                'onclick': 'viewModel("%s", "%s")' % (
                    escapejs(_('VMs')),
                    reverse('vm_home'),
                ),
                'weight': 10,
            },
        ]
