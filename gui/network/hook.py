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

        _n = notifier()
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
                focus = 'network.%s' % model._meta.object_name
                url = obj.get_edit_url() + '?inline=true'
                verbose_name = model._meta.verbose_name
            else:
                focus = 'network.%s.View' % model._meta.object_name
                url = reverse('freeadmin_%s_%s_datagrid' % (
                    model._meta.app_label,
                    model._meta.model_name,
                ))
                verbose_name = model._meta.verbose_name_plural
            tabs.append({
                'name': model._meta.object_name,
                'focus': focus,
                'verbose_name': verbose_name,
                'url': url,
            })

        index = 2
        if _n.ipmi_loaded():
            tabs.insert(index, {
                'name': 'IPMI',
                'focus': 'network.IPMI',
                'verbose_name': _('IPMI'),
                'url': reverse('network_ipmi'),
            })
            index += 1

            if not _n.is_freenas() and _n.failover_licensed():
                node = _n.failover_node()
                tabs.insert(index, {
                    'name': 'IPMI_B',
                    'focus': 'network.IPMI_B',
                    'verbose_name': _('IPMI (Node %s)') % ('B' if node == 'A' else 'A'),
                    'url': reverse('failover_ipmi'),
                })
                index += 1

        tabs.insert(index, {
            'name': 'NetworkSummary',
            'focus': 'network.NetworkSummary',
            'verbose_name': _('Network Summary'),
            'url': reverse('network_summary'),
        })

        return tabs
