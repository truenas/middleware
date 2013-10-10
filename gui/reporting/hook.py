from django.core.urlresolvers import reverse
from django.utils.html import escapejs
from django.utils.translation import ugettext as _

from freenasUI.freeadmin.hook import AppHook


class ReportingHook(AppHook):

    name = 'reporting'

    def top_menu(self, request):
        return [
            {
                'name': _('Reporting'),
                'icon': 'reporting/images/reporting.png',
                'onclick': 'viewModel("%s", "%s")' % (
                    escapejs(_('Reporting')),
                    reverse('reporting_index'),
                ),
                'weight': 0,
            },
        ]
