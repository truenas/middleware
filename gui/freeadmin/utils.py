# Copyright 2010 iXsystems, Inc.
# All rights reserved
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
#####################################################################
import logging

from django.db.models import CASCADE
from django.utils import translation

from freenasUI.system.models import Settings

log = logging.getLogger('freeadmin.utils')


def get_related_objects(obj):
    """
    Find, recursively, all related objects

    Returns:
        tuple(dict, num)
    """
    reldict = {}
    relnum = 0
    for related in obj._meta.get_all_related_objects():

        # Do not acount if it is not going to CASCADE
        if related.field.rel.on_delete is not CASCADE:
            continue
        relset = getattr(obj, related.get_accessor_name())
        qs = relset.all()
        count = qs.count()
        if count == 0:
            continue
        relnum += count

        for o in qs:
            _reld, _reln = get_related_objects(o)
            for key, val in _reld.items():
                if key in reldict:
                    reldict[key] += list(val)
                else:
                    reldict[key] = list(val)
            relnum += _reln

        if related.model._meta.verbose_name in reldict:
            reldict[related.model._meta.verbose_name] += list(qs)
        else:
            reldict[related.model._meta.verbose_name] = list(qs)

    return reldict, relnum


def set_language():
    language = Settings.objects.order_by('-id')[0].stg_language
    translation.activate(language)
