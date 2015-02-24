#!/usr/bin/env python
#-
# Copyright (c) 2015 iXsystems, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS ``AS IS'' AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
# OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
# SUCH DAMAGE.
#

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
