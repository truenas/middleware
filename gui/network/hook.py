from django.core.urlresolvers import reverse
from django.utils.translation import ugettext as _

from freenasUI.freeadmin.hook import AppHook


class NetworkHook(AppHook):

    name = 'network'

    def hook_app_tabs_network(self, request):
        from freenasUI.freeadmin.sqlite3_ha.base import NO_SYNC_MAP
        from freenasUI.middleware.notifier import notifier
        from freenasUI.network import models
        tabmodels = [
            models.GlobalConfiguration,
            models.Interfaces,
            models.LAGGInterface,
            models.StaticRoute,
            models.VLAN,
        ]

        tabs = []
        if (
            hasattr(notifier, 'failover_status') and
            notifier().failover_status() == 'BACKUP'
        ):
            backup = True
        else:
            backup = False

        for model in tabmodels:
            if backup and model._meta.db_table not in NO_SYNC_MAP:
                continue
            if model._admin.deletable is False:
                try:
                    obj = model.objects.order_by('-id')[0]
                except IndexError:
                    obj = model.objects.create()
                url = obj.get_edit_url() + '?inline=true'
                verbose_name = model._meta.verbose_name
            else:
                url = reverse('freeadmin_%s_%s_datagrid' % (
                    model._meta.app_label,
                    model._meta.model_name,
                ))
                verbose_name = model._meta.verbose_name_plural
            tabs.append({
                'name': model._meta.object_name,
                'focus': 'system.%s' % model._meta.object_name,
                'verbose_name': verbose_name,
                'url': url,
            })

        if notifier().ipmi_loaded():
            tabs.insert(2, {
                'name': 'IPMI',
                'focus': 'network.IPMI',
                'verbose_name': _('IPMI'),
                'url': reverse('network_ipmi'),
            })

        tabs.insert(3, {
            'name': 'NetworkSummary',
            'focus': 'network.NetworkSummary',
            'verbose_name': _('Network Summary'),
            'url': reverse('network_summary'),
        })

        return tabs
