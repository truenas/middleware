from django.core.urlresolvers import reverse
from django.utils.html import escapejs
from django.utils.translation import ugettext as _

from freenasUI.freeadmin.hook import AppHook


class SystemHook(AppHook):

    name = 'system'

    def hook_form_buttons_AdvancedForm(self, form, action, *args, **kwargs):
        from freenasUI.middleware.notifier import notifier
        has_failover = hasattr(notifier, 'failover_status')
        btns = []
        if (
            has_failover and notifier().failover_status() in ('MASTER', 'SINGLE')
            or not has_failover
        ):
            btns.append({
                'name': 'PerfTester',
                'verbose_name': _('Performance Test'),
                'onclick': 'editScaryObject(\'%s\', \'%s\');' % (
                    escapejs(_('Performance Test')),
                    escapejs(reverse('system_perftest')),
                ),
            })
        return btns
