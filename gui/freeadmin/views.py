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

import os, commands

from django.forms.models import modelformset_factory
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponse, Http404
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.utils import simplejson
from django.views.generic.list_detail import object_detail, object_list
from django.template.loader import get_template

from freenasUI.middleware.notifier import notifier
from django_nav import nav_groups

@login_required
def adminInterface(request, objtype = None):
    context = RequestContext(request)

    return render_to_response('freeadmin/test.html', context)

@login_required
def menu(request, objtype = None):
    context = RequestContext(request)

    class ByRef(object):
        def __init__(self, val):
            self.val = val
        def new(self):
            old = self.val
            self.val += 1
            return old

    def build_nav():

        navs = []
        for nav in nav_groups['main']:

            nav.option_list = build_options(nav.options)
            nav.active = False
            url = nav.get_absolute_url()
            nav.active = nav.active_if(url, request.path)
            navs.append(nav)

        return navs

    def build_options(nav_options):
        options = []
        for option in nav_options:
            try:
                option = option()
            except:
                pass
            url = option.get_absolute_url()
            option.active = option.active_if(url, request.path)
            option.option_list = build_options(option.options)
            options.append(option)
        return options

    def sernav(o, **kwargs):

        items = []

        # info about current node
        my = {
            'id': str(kwargs['uid'].new()),
            'view': o.get_absolute_url(),
        }
        if hasattr(o, 'rename'):
            my['name'] = o.rename
        else:
            my['name'] = o.name
        for attr in ('model', 'app', 'type'):
            if hasattr(o, attr):
                my[attr] = getattr(o, attr)

        # root nodes identified as type app
        if kwargs['level'] == 0:
            my['type'] = 'app'

        if not kwargs['parents'].has_key(kwargs['level']):
            kwargs['parents'][kwargs['level']] = []

        if kwargs['level'] > 0:
            kwargs['parents'][kwargs['level']].append(my['id'])

        # this node has no childs
        if o.option_list is None:
            return items

        for i in o.option_list:
            kwargs['level'] += 1
            opts = sernav(i, **kwargs)
            kwargs['level'] -= 1
            items += opts

        # if this node has childs
        # then we may found then in [parents][level+1]
        if len(o.option_list) > 0:
        
            my['children'] = []
            for all in kwargs['parents'][ kwargs['level']+1 ]:
                my['children'].append( {'_reference': all } )
                #kwargs['parents'][ kwargs['level']+1 ].remove(all)
            kwargs['parents'][ kwargs['level']+1 ] = []

        items.append(my)

        return items

    items = []
    uid = ByRef(1)
    for n in build_nav():
        items += sernav(n, level=0, uid=uid, parents={})
    final = {
        'items': items,
        'label': 'name',
        'identifier': 'id',
    }

    json = simplejson.dumps(final, indent=3)
    #from freenasUI.nav import json2nav
    #json2nav(json)['main']

    return HttpResponse( json )

"""
Magic happens here

We dynamically import the module based on app and model names
passed as view argument

From there we retrieve the ModelForm associated (which was discovered
previously on the auto_generate process)
"""
@login_required
def generic_model_add(request, app, model, mf=None):

    try:
        _temp = __import__('%s.models' % app, globals(), locals(), [model], -1)
    except ImportError, e:
        raise

    from freenasUI.nav import _modelforms
    context = RequestContext(request, {
        'app': app,
        'model': model,
        'mf': mf,
    })
    m = getattr(_temp, model)
    if not isinstance(_modelforms[m], dict):
        mf = _modelforms[m]
    else:
        if mf == None:
            try:
                mf = _modelforms[m][m.FreeAdmin.create_modelform]
            except:
                try:
                    mf = _modelforms[m][m.FreeAdmin.edit_modelform]
                except:
                    mf = _modelforms[m].values()[-1]
        else:
            mf = _modelforms[m][mf]


    if request.method == "POST":
        instance = m()
        mf = mf(request.POST, request.FILES, instance=instance)
        if mf.is_valid():
            obj = mf.save()
            return render_to_response('freeadmin/generic_model_add_ok.html', context)

    else:
        mf = mf()

    context.update({
        'form': mf,
    })

    return render_to_response('freeadmin/generic_model_add.html', context)

@login_required
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

@login_required
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

    names = [x.verbose_name for x in m._meta.fields]
    _n = [x.name for x in m._meta.fields]
    #width = [len(x.verbose_name)*10 for x in m._meta.fields]
    """
    Nasty hack to calculate the width of the datagrid column
    dojo DataGrid width="auto" doesnt work correctly and dont allow
         column resize with mouse
    """
    width = []
    for x in m._meta.fields:
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
    object_list = m.objects.all()

    context.update({
        'object_list': object_list,
        'fields': fields,
    })
    return render_to_response('freeadmin/generic_model_datagrid.html', context)

@login_required
def generic_model_edit(request, app, model, oid, mf=None):

    try:
        _temp = __import__('%s.models' % app, globals(), locals(), [model], -1)
    except ImportError, e:
        raise

    from freenasUI.nav import _modelforms
    context = RequestContext(request, {
        'app': app,
        'model': model,
        'mf': mf,
        'oid': oid,
    })

    m = getattr(_temp, model)

    if hasattr(m, 'FreeAdmin') and hasattr(m.FreeAdmin, 'deletable'):
        context.update({'deletable': m.FreeAdmin.deletable})

    instance = get_object_or_404(m, pk=oid)
    if not isinstance(_modelforms[m], dict):
        mf = _modelforms[m]
    else:
        if mf == None:
            try:
                mf = _modelforms[m][m.FreeAdmin.edit_modelform]
            except:
                mf = _modelforms[m].values()[-1]
        else:
            mf = _modelforms[m][mf]

    if request.method == "POST":
        mf = mf(request.POST, instance=instance)
        if mf.is_valid():
            obj = mf.save()
            #instance.save()
            return render_to_response('freeadmin/generic_model_edit_ok.html', context, mimetype='text/html')

    else:
        mf = mf(instance=instance)

    context.update({
        'form': mf,
    })

    template = "%s/%s_form.html" % (m._meta.app_label, m._meta.object_name.lower())
    try:
        get_template(template)
    except:
        template = 'freeadmin/generic_model_edit.html'

    return render_to_response('freeadmin/generic_model_edit.html', context, mimetype='text/html')


@login_required
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
    })

    if request.method == "POST":
        instance.delete()
        return render_to_response('freeadmin/generic_model_delete_ok.html', context)

    return render_to_response('freeadmin/generic_model_delete.html', context)
