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

def helperViewEx(request, formClass, model, variable, key, data=None, prefix=""):
    if request.method == 'POST' and variable == key:
        form = formClass(request.POST, prefix=prefix)
        if form.is_valid():
            form.save()
            if model.objects.count() > 3:
                stale_id = model.objects.order_by("-id")[3].id
                model.objects.filter(id__lte=stale_id).delete()
        # Pass through so that the errors would appear
    else:
        if data is not None:
            e = data
        else:
            try:
                e = model.objects.order_by("-id").values()[0]
            except:
                e = None
        form = formClass(data=e, prefix=prefix)
    return form

def helperViewEmpty(request, formClass, variable, key, prefix=""):
    if request.method == 'POST' and variable == key:
        form = formClass(request.POST, prefix=prefix)
        if form.is_valid():
            form.save()
    else:
        form = formClass(prefix=prefix)
    return form
