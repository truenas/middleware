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
# $FreeBSD$
#####################################################################

from django.http import HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.utils import simplejson
from django.template.loader import get_template
from django.utils.translation import ugettext as _

from freenasUI.common.system import get_freenas_version
from freeadmin import navtree
from system.models import Advanced
from dojango.views import datagrid_list

def adminInterface(request, objtype = None):

    adv = Advanced.objects.all().order_by('-id')[0]
    context = RequestContext(request, {
        'consolemsg': adv.adv_consolemsg,
        'freenas_version': get_freenas_version(),
    })

    return render_to_response('freeadmin/index.html', context)

def menu(request, objtype = None):

    final = navtree.dijitTree()
    json = simplejson.dumps(final, indent=3)
    #from freenasUI.nav import json2nav
    #json2nav(json)['main']

    return HttpResponse( json , mimetype="application/json")

"""
Magic happens here

We dynamically import the module based on app and model names
passed as view argument

From there we retrieve the ModelForm associated (which was discovered
previously on the auto_generate process)
"""
def generic_model_add(request, app, model, mf=None):

    try:
        _temp = __import__('%s.models' % app, globals(), locals(), [model], -1)
    except ImportError, e:
        raise

    m = getattr(_temp, model)
    context = RequestContext(request, {
        'app': app,
        'model': model,
        'mf': mf,
        'verbose_name': m._meta.verbose_name,
        'extra_js': m._admin.extra_js,
    })
    if not isinstance(navtree._modelforms[m], dict):
        mf = navtree._modelforms[m]
    else:
        if mf == None:
            try:
                mf = navtree._modelforms[m][m._admin.create_modelform]
            except:
                try:
                    mf = navtree._modelforms[m][m._admin.edit_modelform]
                except:
                    mf = navtree._modelforms[m].values()[-1]
        else:
            mf = navtree._modelforms[m][mf]


    if request.method == "POST":
        instance = m()
        mf = mf(request.POST, request.FILES, instance=instance)
        if mf.is_valid():
            obj = mf.save()
            return HttpResponse(simplejson.dumps({"error": False, "message": _("%s successfully added.") % m._meta.verbose_name}))
            #return render_to_response('freeadmin/generic_model_add_ok.html', context)

    else:
        mf = mf()

    context.update({
        'form': mf,
    })

    template = "%s/%s_add.html" % (m._meta.app_label, m._meta.object_name.lower())
    try:
        get_template(template)
    except:
        template = 'freeadmin/generic_model_add.html'

    return render_to_response(template, context)

def generic_model_view(request, app, model):

    try:
        _temp = __import__('%s.models' % app, globals(), locals(), [model], -1)
    except ImportError, e:
        raise

    context = RequestContext(request, {
        'app': app,
        'model': model,
    })
    m = getattr(_temp, model)

    names = [x.verbose_name for x in m._meta.fields]
    _n = [x.name for x in m._meta.fields]
    object_list = m.objects.all()

    context.update({
        'object_list': object_list,
        'field_names': names,
        'fields': _n,
    })

    return render_to_response('freeadmin/generic_model_view.html', context)

def generic_model_datagrid(request, app, model):

    try:
        _temp = __import__('%s.models' % app, globals(), locals(), [model], -1)
    except ImportError, e:
        raise

    context = RequestContext(request, {
        'app': app,
        'model': model,
    })
    m = getattr(_temp, model)

    exclude = m._admin.exclude_fields
    names = []
    for x in m._meta.fields:
        if not x.name in exclude:
            names.append(x.verbose_name)
    #names = [if not x.name in exclude: x.verbose_name for x in m._meta.fields]

    _n = []
    for x in m._meta.fields:
        if not x.name in exclude:
            _n.append(x.name)
    #_n = [x.name for x in m._meta.fields]
    #width = [len(x.verbose_name)*10 for x in m._meta.fields]
    """
    Nasty hack to calculate the width of the datagrid column
    dojo DataGrid width="auto" doesnt work correctly and dont allow
         column resize with mouse
    """
    width = []
    for x in m._meta.fields:
        if x.name in exclude:
            continue
        val = 8
        for letter in x.verbose_name:
            if letter.isupper():
                val += 10
            elif letter.isdigit():
                val += 9
            else:
                val += 7
        width.append(val)
    fields = zip(names, _n, width)

    context.update({
        'fields': fields,
    })
    return render_to_response('freeadmin/generic_model_datagrid.html', context)

def generic_model_datagrid_json(request, app, model):

    def mycallback(app_name, model_name, attname, request, data):

        try:
            _temp = __import__('%s.models' % app_name, globals(), locals(), [model_name], -1)
        except ImportError, e:
            return True

        m = getattr(_temp, model)
        if attname in ('detele', '_state'):
            return False

        if attname in m._admin.exclude_fields:
            return False

        return True

    return datagrid_list(request, app, model, access_field_callback=mycallback)

def generic_model_edit(request, app, model, oid, mf=None):

    try:
        _temp = __import__('%s.models' % app, globals(), locals(), [model], -1)
    except ImportError, e:
        raise
    m = getattr(_temp, model)

    if request.GET.has_key("inline"):
        inline = True
    else:
        inline = False

    context = RequestContext(request, {
        'app': app,
        'model': model,
        'mf': mf,
        'oid': oid,
        'inline': inline,
        'extra_js': m._admin.extra_js,
        'verbose_name': m._meta.verbose_name,
    })

    if m._admin.deletable is False:
        context.update({'deletable': False})
    if request.GET.has_key("deletable") and not context.has_key("deletable"):
        context.update({'deletable': False})

    instance = get_object_or_404(m, pk=oid)
    if not isinstance(navtree._modelforms[m], dict):
        mf = navtree._modelforms[m]
    else:
        if mf == None:
            try:
                mf = navtree._modelforms[m][m.FreeAdmin.edit_modelform]
            except:
                mf = navtree._modelforms[m].values()[-1]
        else:
            mf = navtree._modelforms[m][mf]

    if request.method == "POST":
        mf = mf(request.POST, request.FILES, instance=instance)
        if mf.is_valid():
            obj = mf.save()
            #instance.save()
            if request.GET.has_key("iframe"):
                return HttpResponse("<html><body><textarea>"+simplejson.dumps({"error": False, "message": _("%s successfully updated.") % m._meta.verbose_name})+"</textarea></boby></html>")
            else:
                return HttpResponse(simplejson.dumps({"error": False, "message": _("%s successfully updated.") % m._meta.verbose_name}))
            #return render_to_response('freeadmin/generic_model_edit_ok.html', context, mimetype='text/html')

    else:
        mf = mf(instance=instance)

    context.update({
        'form': mf,
    })

    template = "%s/%s_edit.html" % (m._meta.app_label, m._meta.object_name.lower())
    try:
        get_template(template)
    except:
        template = 'freeadmin/generic_model_edit.html'

    if request.GET.has_key("iframe"):
        resp = render_to_response(template, context, \
                mimetype='text/html')
        resp.content = "<html><body><textarea>"+resp.content+"</textarea></boby></html>"
        return resp
    else:
        return render_to_response(template, context, \
                mimetype='text/html')

def generic_model_delete(request, app, model, oid):

    try:
        _temp = __import__('%s.models' % app, globals(), locals(), [model], -1)
    except ImportError, e:
        raise

    m = getattr(_temp, model)
    instance = get_object_or_404(m, pk=oid)

    context = RequestContext(request, {
        'app': app,
        'model': model,
        'oid': oid,
        'object': instance,
        'verbose_name': instance._meta.verbose_name,
    })

    if request.method == "POST":
        instance.delete()
        return HttpResponse(simplejson.dumps({"error": False, "message": _("%s successfully deleted.") % m._meta.verbose_name}), mimetype="application/json")
        #return render_to_response('freeadmin/generic_model_delete_ok.html', context)

    return render_to_response('freeadmin/generic_model_delete.html', context)
