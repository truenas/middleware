from django.utils.translation import ugettext_lazy as _
from freenasUI.freeadmin.tree import TreeNode
from freenasUI.middleware.notifier import notifier

NAME = _('Tasks')
BLACKLIST = []
ICON = u'TasksIcon'
ORDER = 5


class CloudSync(TreeNode):

    gname = 'CloudSync'
    replace_only = True
    append_to = 'tasks'

    def pre_build_options(self):
        if not notifier().is_freenas():
            return
        raise ValueError


class CronJobView(TreeNode):

    gname = 'View'
    type = 'opentasks'
    append_to = 'tasks.CronJob'


class InitShutdownView(TreeNode):

    gname = 'View'
    type = 'opentasks'
    append_to = 'tasks.InitShutdown'


class RsyncView(TreeNode):

    gname = 'View'
    type = 'opentasks'
    append_to = 'tasks.Rsync'


class SMARTTestView(TreeNode):

    gname = 'View'
    type = 'opentasks'
    append_to = 'tasks.SMARTTest'
