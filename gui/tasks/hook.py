import subprocess

from django.core.urlresolvers import reverse
from django.utils.html import escapejs
from django.utils.translation import ugettext as _

from freenasUI.freeadmin.hook import AppHook


class TasksHook(AppHook):

    name = 'tasks'

    def hook_app_tabs_tasks(self, request):
        from freenasUI.middleware.notifier import notifier

        tabs = [{
            'name': 'CronJob',
            'focus': 'tasks.CronJob.View',
            'verbose_name': _('Cron Jobs'),
            'url': reverse('freeadmin_tasks_cronjob_datagrid'),
        }, {
            'name': 'InitShutdown',
            'focus': 'tasks.InitShutdown.View',
            'verbose_name': _('Init/Shutdown Scripts'),
            'url': reverse('freeadmin_tasks_initshutdown_datagrid'),
        }, {
            'name': 'Rsync',
            'focus': 'tasks.Rsync.View',
            'verbose_name': _('Rsync Tasks'),
            'url': reverse('freeadmin_tasks_rsync_datagrid'),
        }, {
            'name': 'SMARTTest',
            'focus': 'tasks.SMARTTest.View',
            'verbose_name': _('S.M.A.R.T. Tests'),
            'url': reverse('freeadmin_tasks_smarttest_datagrid'),
        }]

        if not notifier().is_freenas():
            tabs.insert(0, {
                'name': 'CloudSync',
                'focus': 'tasks.CloudSync.View',
                'verbose_name': _('Cloud Sync'),
                'url': reverse('freeadmin_tasks_cloudsync_datagrid'),
            })

        return tabs
