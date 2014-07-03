from freenasUI.freeadmin.tree import TreeNode
from django.utils.translation import ugettext_lazy as _

NAME = _('Tasks')
BLACKLIST = []
ICON = u'TasksIcon'
ORDER = 5


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
