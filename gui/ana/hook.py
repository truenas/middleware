from django.core.urlresolvers import reverse
from django.utils.html import escapejs
from django.utils.translation import ugettext as _

from freenasUI.freeadmin.hook import AppHook


class AnaHook(AppHook):

    name = 'ana'

    def base_js(self, request):
        return [
            'lib/js/freeadmin/reporting/jquery.min-1.7.2.js',
            'lib/js/freeadmin/reporting/highstock.js',
            'lib/js/freeadmin/reporting/highcharts-more.js',
            'lib/js/freeadmin/reporting/chart_def.js',
            'lib/js/freeadmin/reporting/themes/gray.js',
        ]

    def top_menu(self, request):
        return [
            {
                'name': _('Reporting'),
                'icon': 'images/ui/menu/ana.png',
                'onclick': 'viewModel("%s", "%s")' % (
                    escapejs(_('Reporting')),
                    escapejs(reverse('ana_index')),
                ),
                'weight': 0,
            },
        ]
