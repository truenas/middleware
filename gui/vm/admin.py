from freenasUI.freeadmin.options import BaseFreeAdmin
from freenasUI.freeadmin.site import site
from freenasUI.vm import models


class VMFAdmin(BaseFreeAdmin):

    icon_model = u"VMIcon"
    icon_object = u"VMIcon"
    icon_add = u"AddVMIcon"
    icon_view = u"ViewVMIcon"


site.register(models.VM, VMFAdmin)
