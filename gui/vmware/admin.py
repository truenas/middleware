import logging

from collections import OrderedDict

from django.conf import settings
from django.utils.html import escapejs
from django.utils.translation import ugettext as _

from freenasUI.freeadmin.options import BaseFreeAdmin
from freenasUI.freeadmin.site import site
from freenasUI.vmware import models

log = logging.getLogger('vmware.admin')

class SettingsFAdmin(BaseFreeAdmin):

    deletable = False


site.register(models.Settings, SettingsFAdmin)
