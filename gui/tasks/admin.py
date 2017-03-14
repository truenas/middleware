from django.utils.html import escapejs
from django.utils.translation import ugettext as _

from freenasUI.api.resources import (
    CloudSyncResourceMixin,
    CronJobResourceMixin, RsyncResourceMixin, SMARTTestResourceMixin
)
from freenasUI.freeadmin.options import BaseFreeAdmin
from freenasUI.freeadmin.site import site
from freenasUI.tasks import models

human_colums = [
    {
        'name': 'human_minute',
        'label': _('Minute'),
        'sortable': False,
    },
    {
        'name': 'human_hour',
        'label': _('Hour'),
        'sortable': False,
    },
    {
        'name': 'human_daymonth',
        'label': _('Day of month'),
        'sortable': False,
    },
    {
        'name': 'human_month',
        'label': _('Month'),
        'sortable': False,
    },
    {
        'name': 'human_dayweek',
        'label': _('Day of week'),
        'sortable': False,
    },
]


class CloudSyncFAdmin(BaseFreeAdmin):

    icon_model = "cronJobIcon"
    icon_object = "cronJobIcon"
    icon_add = "AddcronJobIcon"
    icon_view = "ViewcronJobIcon"
    exclude_fields = (
        'id',
        'daymonth',
        'dayweek',
        'hour',
        'minute',
        'month',
        'attributes',
    )
    menu_child_of = 'tasks'
    refresh_time = 12000
    resource_mixin = CloudSyncResourceMixin

    def get_actions(self):
        actions = super(CloudSyncFAdmin, self).get_actions()
        actions['RunNow'] = {
            'button_name': _('Run Now'),
            'on_click': """function() {
                var mybtn = this;
                for (var i in grid.selection) {
                    var data = grid.row(i).data;
                    editObject('%s', data._run_url, [mybtn,]);
                }
            }""" % (escapejs(_('Run Now')), ),
        }
        return actions

    def get_datagrid_columns(self):
        columns = super(CloudSyncFAdmin, self).get_datagrid_columns()
        columns.insert(3, {
            'name': 'status',
            'label': _('Status'),
            'sortable': False,
        })
        for idx, column in enumerate(human_colums):
            columns.insert(4 + idx, dict(column))
        return columns


class CronJobFAdmin(BaseFreeAdmin):

    icon_model = "cronJobIcon"
    icon_object = "cronJobIcon"
    icon_add = "AddcronJobIcon"
    icon_view = "ViewcronJobIcon"
    exclude_fields = (
        'id',
        'cron_daymonth',
        'cron_dayweek',
        'cron_hour',
        'cron_minute',
        'cron_month',
    )
    menu_child_of = 'tasks'
    resource_mixin = CronJobResourceMixin

    def get_actions(self):
        actions = super(CronJobFAdmin, self).get_actions()
        actions['RunNow'] = {
            'button_name': _('Run Now'),
            'on_click': """function() {
                var mybtn = this;
                for (var i in grid.selection) {
                    var data = grid.row(i).data;
                    editObject('%s', data._run_url, [mybtn,]);
                }
            }""" % (escapejs(_('Run Now')), ),
        }
        return actions

    def get_datagrid_columns(self):
        columns = super(CronJobFAdmin, self).get_datagrid_columns()
        for idx, column in enumerate(human_colums):
            columns.insert(3 + idx, dict(column))
        return columns


class RsyncFAdmin(BaseFreeAdmin):

    icon_model = "rsyncIcon"
    icon_object = "rsyncIcon"
    icon_add = "AddrsyncTaskIcon"
    icon_view = "ViewrsyncTaskIcon"
    exclude_fields = (
        'id',
        'rsync_mode',
        'rsync_daymonth',
        'rsync_dayweek',
        'rsync_hour',
        'rsync_minute',
        'rsync_month',
        'rsync_recursive',
        'rsync_times',
        'rsync_compress',
        'rsync_archive',
        'rsync_delete',
        'rsync_quiet',
        'rsync_preserveperm',
        'rsync_preserveattr',
        'rsync_extra',
    )
    menu_child_of = 'tasks'
    resource_mixin = RsyncResourceMixin

    def get_actions(self):
        actions = super(RsyncFAdmin, self).get_actions()
        actions['RunNow'] = {
            'button_name': _('Run Now'),
            'on_click': """function() {
                var mybtn = this;
                for (var i in grid.selection) {
                    var data = grid.row(i).data;
                    editObject('%s', data._run_url, [mybtn,]);
                }
            }""" % (escapejs(_('Run Now')), ),
        }
        return actions

    def get_datagrid_columns(self):
        columns = super(RsyncFAdmin, self).get_datagrid_columns()
        for idx, column in enumerate(human_colums):
            columns.insert(6 + idx, dict(column))
        return columns


class SMARTTestFAdmin(BaseFreeAdmin):

    icon_model = "SMARTIcon"
    icon_object = "SMARTIcon"
    icon_add = "AddSMARTTestIcon"
    icon_view = "ViewSMARTTestIcon"
    exclude_fields = (
        'id',
        'smarttest_daymonth',
        'smarttest_dayweek',
        'smarttest_hour',
        'smarttest_month',
    )
    menu_child_of = 'tasks'
    resource_mixin = SMARTTestResourceMixin

    def get_datagrid_columns(self):
        columns = super(SMARTTestFAdmin, self).get_datagrid_columns()
        for idx, column in enumerate(human_colums[1:]):
            columns.insert(3 + idx, dict(column))
        return columns

site.register(models.CloudSync, CloudSyncFAdmin)
site.register(models.CronJob, CronJobFAdmin)
site.register(models.Rsync, RsyncFAdmin)
site.register(models.SMARTTest, SMARTTestFAdmin)
