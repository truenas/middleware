from django.utils.translation import ugettext as _

from freenasUI.freeadmin.api.resources import CronJobResource, RsyncResource
from freenasUI.freeadmin.options import BaseFreeAdmin
from freenasUI.freeadmin.site import site
from freenasUI.system import models

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


class CronJobFAdmin(BaseFreeAdmin):

    exclude_fields = (
        'id',
        'cron_daymonth',
        'cron_dayweek',
        'cron_hour',
        'cron_minute',
        'cron_month',
        )
    resource = CronJobResource

    def get_datagrid_columns(self):
        columns = super(CronJobFAdmin, self).get_datagrid_columns()
        for idx, column in enumerate(human_colums):
            columns.insert(3 + idx, column)
        return columns


class RsyncFAdmin(BaseFreeAdmin):

    icon_model = u"rsyncIcon"
    icon_object = u"rsyncIcon"
    icon_add = u"AddrsyncTaskIcon"
    icon_view = u"ViewrsyncTaskIcon"
    exclude_fields = (
        'id',
        'rsync_daymonth',
        'rsync_dayweek',
        'rsync_hour',
        'rsync_minute',
        'rsync_month',
        )
    resource = RsyncResource

    def get_datagrid_columns(self):
        columns = super(RsyncFAdmin, self).get_datagrid_columns()
        for idx, column in enumerate(human_colums):
            columns.insert(6 + idx, column)
        return columns

site.register(models.CronJob, CronJobFAdmin)
site.register(models.Rsync, RsyncFAdmin)
