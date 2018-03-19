# Copyright (c) 2017 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.

from freenasUI.system.models import Support

from middlewared.alert.base import Alert, AlertLevel, ThreadedAlertSource


class IxAlertSource(ThreadedAlertSource):
    level = AlertLevel.WARNING
    title = 'The Proactive Support feature is not enabled.'

    def check_sync(self):
        available, support = Support.is_available()
        if available and support.enabled is None:
            return Alert('The Proactive Support feature is not enabled. Please see the System -> Proactive Support tab.')
        elif support.is_enabled():
            # This is for people who had ix alert enabled before Proactive Support
            # feature and have not filled all the new fields.
            unfilled = []
            for field in Support._meta.fields:
                if not getattr(support, field.name):
                    unfilled.append(field)
            if unfilled:
                return Alert('Please fill in these fields on the System -> Proactive Support tab: %s.',
                             args=[', '.join([str(i.verbose_name) for i in unfilled])])
