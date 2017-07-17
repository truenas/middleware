import subprocess

from django.core.urlresolvers import reverse
from django.utils.html import escapejs
from django.utils.translation import ugettext as _

from freenasUI.freeadmin.hook import AppHook


class SystemHook(AppHook):

    name = 'system'

    def top_menu(self, request):
        from freenasUI.middleware.notifier import notifier
        if (
            hasattr(notifier, 'failover_status') and
            notifier().failover_status() == 'BACKUP'
        ):
            return []
        return [
            {
                'name': _('Wizard'),
                'icon': 'images/ui/menu/wizard.png',
                'onclick': 'editObject("%s", "%s", [])' % (
                    escapejs(_('Wizard')),
                    reverse('system_initialwizard'),
                ),
                'weight': 90,
            },
        ]

    def system_info(self, request):
        arr = []
        tn_serial_numbers = ('A1-', 'R1-', 'R2-', 'R3-', 'R4-')
        serial = subprocess.Popen(
            ['/usr/local/sbin/dmidecode', '-s', 'system-serial-number'],
            stdout=subprocess.PIPE,
            encoding='utf8',
        ).communicate()[0].split('\n')[0].upper()
        if serial.startswith(tn_serial_numbers):
            arr.append({'name': _('Serial Number'), 'value': serial})
        return arr

    def hook_app_tabs_system(self, request):
        from freenasUI.freeadmin.sqlite3_ha.base import NO_SYNC_MAP
        from freenasUI.middleware.notifier import notifier
        from freenasUI.system import models
        from freenasUI.support.utils import get_license
        tabmodels = [
            models.Settings,
            models.Advanced,
            models.Email,
            models.SystemDataset,
            models.Tunable,
            models.ConsulAlerts,
            models.CertificateAuthority,
            models.Certificate,
        ]

        idx_skip = 0
        if not notifier().is_freenas():
            idx_skip += 1
            tabmodels.insert(5, models.CloudCredentials)

        tabs = []
        if (
            hasattr(notifier, 'failover_status') and
            notifier().failover_status() == 'BACKUP'
        ):
            backup = True
        else:
            backup = False
        tabs.append({
            'name': 'SysInfo',
            'focus': 'system.SysInfo',
            'verbose_name': _('Information'),
            'url': reverse('system_info'),
        })

        for model in tabmodels:
            if backup and model._meta.db_table not in NO_SYNC_MAP:
                continue
            # System Dataset has only one hidden field
            if backup and model._meta.db_table == 'system_systemdataset':
                continue
            if model._admin.deletable is False:
                try:
                    obj = model.objects.order_by('-id')[0]
                except IndexError:
                    obj = model.objects.create()
                url = obj.get_edit_url() + '?inline=true'
                verbose_name = model._meta.verbose_name
                focus = 'system.%s' % model._meta.object_name
            else:
                url = reverse('freeadmin_%s_%s_datagrid' % (
                    model._meta.app_label,
                    model._meta.model_name,
                ))
                verbose_name = model._meta.verbose_name_plural
                focus = 'system.%s.View' % model._meta.object_name
            tabs.append({
                'name': model._meta.object_name,
                'focus': focus,
                'verbose_name': verbose_name,
                'url': url,
            })

        tabs.insert(2, {
            'name': 'BootEnv',
            'focus': 'system.BootEnv',
            'verbose_name': _('Boot'),
            'url': reverse('system_bootenv_datagrid'),
        })

        tabs.insert(7, {
            'name': 'Update',
            'focus': 'system.Update',
            'verbose_name': _('Update'),
            'url': reverse('system_update_index'),
        })

        tabs.insert(11 + idx_skip, {
            'name': 'Support',
            'focus': 'system.Support',
            'verbose_name': _('Support'),
            'url': reverse('support_home'),
        })

        license = get_license()[0]
        if license is not None and not notifier().is_freenas():
            support = models.Support.objects.order_by('-id')[0]
            tabs.insert(12 + idx_skip, {
                'name': 'Proactive Support',
                'focus': 'system.ProactiveSupport',
                'verbose_name': _('Proactive Support'),
                'url': support.get_edit_url() + '?inline=true',
            })

        return tabs
