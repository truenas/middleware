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
import sys
import re
import datetime

from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import simplejson
from django.template.loader import get_template
from django.utils.translation import ugettext as _
from django.views import debug
from django.template import (Context, TemplateDoesNotExist, TemplateSyntaxError)
from django.conf import settings
from django.template.defaultfilters import force_escape, pprint
from django.utils.encoding import smart_unicode, smart_str

from freenasUI.common.system import get_freenas_version
from freeadmin import navtree
from system.models import Advanced
from services.exceptions import ServiceFailed
from dojango.views import datagrid_list
from django.views.defaults import server_error

def adminInterface(request, objtype = None):

    try:
        console = Advanced.objects.all().order_by('-id')[0].adv_consolemsg
    except:
        console = False
    return render(request, 'freeadmin/index.html', {
        'consolemsg': console,
    })

def menu(request, objtype = None):

    try:
        final = navtree.dijitTree()
        json = simplejson.dumps(final, indent=3)
    except:
        json = ""
    #from freenasUI.nav import json2nav
    #json2nav(json)['main']

    return HttpResponse(json, mimetype="application/json")

"""
We use the django debug 500 classes to show the traceback to the user
instead of the useless "An error ocurried" used by dojo in case of 
HTTP 500 responses.

As this is not a public API of django we need to duplicate some code
"""
class ExceptionReporter(debug.ExceptionReporter):

    is_email = False
    def get_traceback_html(self):
        """
        Copied from debug.ExceptionReporter
        The Template was replaced to use 500_freenas.html instead 
        of the hard-coded one

        Return HTML code for traceback."
        """

        if self.exc_type and issubclass(self.exc_type, TemplateDoesNotExist):
            from django.template.loader import template_source_loaders
            self.template_does_not_exist = True
            self.loader_debug_info = []
            for loader in template_source_loaders:
                try:
                    module = import_module(loader.__module__)
                    if hasattr(loader, '__class__'):
                        source_list_func = loader.get_template_sources
                    else: # NOTE: Remember to remove this branch when we deprecate old template loaders in 1.4
                        source_list_func = module.get_template_sources
                    # NOTE: This assumes exc_value is the name of the template that
                    # the loader attempted to load.
                    template_list = [{'name': t, 'exists': os.path.exists(t)} \
                        for t in source_list_func(str(self.exc_value))]
                except (ImportError, AttributeError):
                    template_list = []
                if hasattr(loader, '__class__'):
                    loader_name = loader.__module__ + '.' + loader.__class__.__name__
                else: # NOTE: Remember to remove this branch when we deprecate old template loaders in 1.4
                    loader_name = loader.__module__ + '.' + loader.__name__
                self.loader_debug_info.append({
                    'loader': loader_name,
                    'templates': template_list,
                })
        if (settings.TEMPLATE_DEBUG and hasattr(self.exc_value, 'source') and
            isinstance(self.exc_value, TemplateSyntaxError)):
            self.get_template_exception_info()

        frames = self.get_traceback_frames()
        for i, frame in enumerate(frames):
            if 'vars' in frame:
                frame['vars'] = [(k, force_escape(pprint(v))) for k, v in frame['vars']]
            frames[i] = frame

        unicode_hint = ''
        if self.exc_type and issubclass(self.exc_type, UnicodeError):
            start = getattr(self.exc_value, 'start', None)
            end = getattr(self.exc_value, 'end', None)
            if start is not None and end is not None:
                unicode_str = self.exc_value.args[1]
                unicode_hint = smart_unicode(unicode_str[max(start-5, 0):min(end+5, len(unicode_str))], 'ascii', errors='replace')
        from django import get_version
        from django.template.loader import get_template
        t = get_template("500_freenas.html")
        #t = Template(TECHNICAL_500_TEMPLATE, name='Technical 500 template')
        c = Context({
            'is_email': self.is_email,
            'unicode_hint': unicode_hint,
            'frames': frames,
            'request': self.request,
            'settings': debug.get_safe_settings(),
            'sys_executable': sys.executable,
            'sys_version_info': '%d.%d.%d' % sys.version_info[0:3],
            'server_time': datetime.datetime.now(),
            'django_version_info': get_version(),
            'sys_path' : sys.path,
            'template_info': self.template_info,
            'template_does_not_exist': self.template_does_not_exist,
            'loader_debug_info': self.loader_debug_info,
        })
        # Check whether exception info is available
        if self.exc_type:
            c['exception_type'] = self.exc_type.__name__
        if self.exc_value:
            c['exception_value'] = smart_unicode(self.exc_value, errors='replace')
        if frames:
            c['lastframe'] = frames[-1]
        return t.render(c)

def server_error(request, *args, **kwargs):
    try:
        adv = Advanced.objects.all().order_by('-id')[0]
        if adv.adv_traceback:
            reporter = ExceptionReporter(request, *sys.exc_info())
            html = reporter.get_traceback_html()
            return HttpResponse(html, mimetype='text/html')
        else:
            raise
    except:
        return debug.technical_500_response(request, *sys.exc_info())

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
    except ImportError:
        raise

    m = getattr(_temp, model)
    context = {
        'app': app,
        'model': model,
        'mf': mf,
        'verbose_name': m._meta.verbose_name,
        'extra_js': m._admin.extra_js,
    }
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
            mf.save()
            return HttpResponse(simplejson.dumps({"error": False, "message": _("%s successfully added.") % m._meta.verbose_name}))

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

    return render(request, template, context)

def generic_model_view(request, app, model):

    try:
        _temp = __import__('%s.models' % app, globals(), locals(), [model], -1)
    except ImportError:
        raise

    context = {
        'app': app,
        'model': model,
    }
    m = getattr(_temp, model)

    names = [x.verbose_name for x in m._meta.fields]
    _n = [x.name for x in m._meta.fields]
    object_list = m.objects.all()

    context.update({
        'object_list': object_list,
        'field_names': names,
        'fields': _n,
    })

    return render(request, 'freeadmin/generic_model_view.html', context)

def generic_model_datagrid(request, app, model):

    try:
        _temp = __import__('%s.models' % app, globals(), locals(), [model], -1)
    except ImportError:
        raise

    context = {
        'app': app,
        'model': model,
    }
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
    return render(request, 'freeadmin/generic_model_datagrid.html', context)

def generic_model_datagrid_json(request, app, model):

    def mycallback(app_name, model_name, attname, request, data):

        try:
            _temp = __import__('%s.models' % app_name, globals(), locals(), [model_name], -1)
        except ImportError:
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
    except ImportError:
        raise
    m = getattr(_temp, model)

    if request.GET.has_key("inline"):
        inline = True
    else:
        inline = False

    context = {
        'app': app,
        'model': model,
        'mf': mf,
        'oid': oid,
        'inline': inline,
        'extra_js': m._admin.extra_js,
        'verbose_name': m._meta.verbose_name,
    }

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
            try:
                mf.save()
                if request.GET.has_key("iframe"):
                    return HttpResponse("<html><body><textarea>"+simplejson.dumps({"error": False, "message": _("%s successfully updated.") % m._meta.verbose_name})+"</textarea></boby></html>")
                else:
                    return HttpResponse(simplejson.dumps({"error": False, "message": _("%s successfully updated.") % m._meta.verbose_name}))
            except ServiceFailed, e:
                return HttpResponse(simplejson.dumps({"error": True, "message": _("The service failed to restart.") % m._meta.verbose_name}))

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
        resp = render(request, template, context, \
                mimetype='text/html')
        resp.content = "<html><body><textarea>"+resp.content+"</textarea></boby></html>"
        return resp
    else:
        return render(request, template, context, \
                mimetype='text/html')

def generic_model_delete(request, app, model, oid):

    try:
        _temp = __import__('%s.models' % app, globals(), locals(), [model], -1)
    except ImportError:
        raise

    m = getattr(_temp, model)
    instance = get_object_or_404(m, pk=oid)

    try:
        if m._admin.delete_form_filter:
            find = m.objects.filter(id=instance.id, **m._admin.delete_form_filter)
            if find.count() == 0:
                raise
        _temp = __import__('%s.forms' % app, globals(), locals(), [m._admin.delete_form], -1)
        form = getattr(_temp, m._admin.delete_form)
    except:
        form = None

    context = {
        'app': app,
        'model': model,
        'oid': oid,
        'object': instance,
        'verbose_name': instance._meta.verbose_name,
    }

    form_i = None
    if request.method == "POST":
        if form:
            form_i = form(request.POST, instance=instance)
            if form_i.is_valid():
                if hasattr(form_i, "done"):
                    form_i.done()
                instance.delete()
                return HttpResponse(simplejson.dumps({"error": False, "message": _("%s successfully deleted.") % m._meta.verbose_name}), mimetype="application/json")

        else:
            instance.delete()
            return HttpResponse(simplejson.dumps({"error": False, "message": _("%s successfully deleted.") % m._meta.verbose_name}), mimetype="application/json")
    if form and form_i is None:
        form_i = form(instance=instance)
        context.update({'form': form})
    template = "%s/%s_delete.html" % (m._meta.app_label, m._meta.object_name.lower())
    try:
        get_template(template)
    except:
        template = 'freeadmin/generic_model_delete.html'

    return render(request, template, context)
