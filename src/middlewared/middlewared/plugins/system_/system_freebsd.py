# -*- coding=utf-8 -*-
import logging

import sysctl

from middlewared.service import private, Service

logger = logging.getLogger(__name__)


class SystemService(Service):
    is_vm = None

    @private
    def vm(self):
        if self.is_vm is None:
            self.is_vm = sysctl.filter("kern.vm_guest")[0].value != "none"

        return self.is_vm
