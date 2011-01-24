#+
# Copyright 2010 iXsystems
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
from django.template import RequestContext
from django.shortcuts import render_to_response
import collections

def helperView(request, theForm, model, url, focused_tab = "system", defaults_callback=None, prefix=""):
    if request.method == 'POST':
        form = theForm(request.POST, prefix=prefix)
        if form.is_valid():
            form.save()
            if model.objects.count() > 3:
                stale_id = model.objects.order_by("-id")[3].id
                model.objects.filter(id__lte=stale_id).delete()
        else:
            # This is a debugging aid to raise exception when validation
            # is not passed.
            form.save()
    else:
        try:
            _entity = model.objects.order_by("-id").values()[0]
        except:
            if isinstance(defaults_callback, collections.Callable):
                _entity = defaults_callback()
            else:
                raise
        form = theForm(data = _entity, prefix=prefix)
    variables = RequestContext(request, {
        'focused_tab' : focused_tab,
        'form': form
    })
    return render_to_response(url, variables)

def helperViewEm(request, theForm, model, defaults_callback=None, prefix=""):
    data_saved = 0
    if request.method == 'POST':
        form = theForm(request.POST, prefix=prefix)
        if form.is_valid():
            # TODO: test if the data is the same as what is in the database?
            form.save()
            data_saved = 1
            if model.objects.count() > 3:
                stale_id = model.objects.order_by("-id")[3].id
                model.objects.filter(id__lte=stale_id).delete()
        else:
            pass
    else:
        try:
            _entity = model.objects.order_by("-id").values()[0]
        except:
            if isinstance(defaults_callback, collections.Callable):
                _entity = defaults_callback()
            else:
                _entity = None
        form = theForm(data = _entity, prefix=prefix)
    return (data_saved, form)

