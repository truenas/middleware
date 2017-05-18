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
import psutil
import re
import subprocess

from collections import OrderedDict
from django.core.exceptions import SuspiciousOperation
from django.db.models import CASCADE
from django.db.models.fields.related import OneToOneRel
from django.utils import translation
from django.utils.datastructures import MultiValueDict

from freenasUI.common.pipesubr import pipeopen

from raven.contrib.django.utils import get_host
from raven.utils.wsgi import get_headers, get_environ

log = logging.getLogger('freeadmin.utils')


def get_related_objects(obj):
    """
    Find, recursively, all related objects

    Returns:
        tuple(dict, num)
    """
    reldict = {}
    relnum = 0
    for related in [
        f for f in obj._meta.get_fields()
        if (f.one_to_many or f.one_to_one) and f.auto_created and not f.concrete
    ]:

        # Do not account if it is not going to CASCADE
        if related.field.rel.on_delete is not CASCADE:
            continue
        try:
            relset = getattr(obj, related.get_accessor_name())
        except:
            continue
        if isinstance(related, OneToOneRel):
            qs = [relset]
            relnum += 1
        else:
            qs = relset.all()
            count = qs.count()
            if count == 0:
                continue
            relnum += count

        for o in qs:
            _reld, _reln = get_related_objects(o)
            for key, val in list(_reld.items()):
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
    from freenasUI.system.models import Settings
    language = Settings.objects.order_by('-id')[0].stg_language
    translation.activate(language)


def key_order(form, index, name, instance=False):

    if instance:
        d = form.fields
    else:
        d = form.base_fields

    value = d.pop(name)
    new_d = OrderedDict()
    added = False
    for i, kv in enumerate(d.items()):
        k, v = kv
        if i == index:
            new_d[name] = value
            added = True
        new_d[k] = v
    if not added:
        new_d[name] = value

    if instance:
        form.fields = new_d
    else:
        form.base_fields = new_d


def log_db_locked():
    """
    Log the processes with the database file open for write.
    """
    proc = pipeopen('fuser /data/freenas-v1.db', stderr=subprocess.STDOUT, quiet=True)
    output = proc.communicate()[0]
    log.debug('Processes with database file open:')
    for pid, flags in re.findall(r'\b(\d+)([a-z]+)\b', output):
        if 'w' not in flags:
            continue
        try:
            proc = psutil.Process(int(pid))
            log.debug(f'PID {pid}: {" ".join(proc.cmdline())}')
        except Exception as e:
            pass


def request2crashreporting(request):
    """
    Transform django/wsgi request object to a dict the crash reporting
    can understand.
    """
    data = {}
    # Pieces grabbed from raven.contrib.django.client
    try:
        uri = request.build_absolute_uri()
    except SuspiciousOperation:
        # attempt to build a URL for reporting as Django won't allow us to
        # use get_host()
        if request.is_secure():
            scheme = 'https'
        else:
            scheme = 'http'
        host = get_host(request)
        uri = '%s://%s%s' % (scheme, host, request.path)

    rdata = None
    if request.method not in ('GET', 'HEAD'):
        try:
            rdata = request.body
        except Exception:
            try:
                rdata = request.raw_post_data
            except Exception:
                # assume we had a partial read.
                try:
                    rdata = request.POST or '<unavailable>'
                except Exception:
                    rdata = '<unavailable>'
                else:
                    if isinstance(rdata, MultiValueDict):
                        rdata = dict(
                            (k, v[0] if len(v) == 1 else v)
                            for k, v in iter(rdata.lists()))


    data['request'] = {
        'method': request.method,
        'url': uri,
        'query_string': request.META.get('QUERY_STRING'),
        'data': rdata,
        'cookies': dict(request.COOKIES),
        'headers': dict(get_headers(request.META)),
        'env': dict(get_environ(request.META)),
    }
