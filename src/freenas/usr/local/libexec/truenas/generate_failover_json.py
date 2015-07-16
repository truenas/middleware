#!/usr/bin/env python
#-
# Copyright (c) 2015 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.

import json
import os
import sys

sys.path.extend([
    '/usr/local/www',
    '/usr/local/www/freenasUI',
])

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'freenasUI.settings')

# Make sure to load all modules
from django.db.models.loading import cache
cache.get_apps()


def main():
    # Data structure is a tuple of three items
    # 1. A dictionary in which the key is the intervace group, and the value is a list
    #       of interfaces in that group.
    # 2. Whether failover is enabled or disabled.  Note that a true value means failover is disabled
    # 3. In the case that failover is disabled, whether this node is the active or passive node.

    from freenasUI.failover.models import Failover
    from freenasUI.failover.models import CARP
    from freenasUI.network.models import Interfaces

    disabled = Failover.objects.all()[0].disabled
    master = Failover.objects.all()[0].master
    failover_dict = {}

    for item in CARP.objects.all().exclude(carp_number__in=[1, 2]):
        if item.carp_critical:
            failover_dict[item.carp_group] = []
            failover_dict[item.carp_group].append((Interfaces.objects.filter(id=item.carp_interface_id)[0].int_interface))

    object = (failover_dict, disabled, master)
    fh = open("/tmp/failover.json", "w")
    fh.write(json.dumps(object))
    fh.close()

if __name__ == "__main__":
    main()
