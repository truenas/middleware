#+
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

import datetime
import os
import re
import sys

from django import forms as dforms
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views import debug
from django.conf import settings
from django.template import Context, TemplateDoesNotExist, TemplateSyntaxError, RequestContext
from django.template.defaultfilters import force_escape, pprint
from django.template.loader import get_template, template_source_loaders, render_to_string
from django.utils import simplejson
from django.utils.translation import ugettext as _
from django.utils.encoding import smart_unicode, smart_str
from django.utils.importlib import import_module

from freenasUI.common.system import get_sw_name, get_sw_version
from freenasUI.middleware.exceptions import MiddlewareError
from freeadmin import navtree
from system.models import Advanced
from network.models import GlobalConfiguration
from services.exceptions import ServiceFailed
from dojango.views import datagrid_list
from dojango.forms.models import inlineformset_factory


class JsonResponse(HttpResponse):

    error = False
    enclosed = False
    message = ''
    events = []
    def __init__(self, *args, **kwargs):
        if kwargs.has_key("error"):
            self.error = kwargs.pop('error')
        if kwargs.has_key("message"):
            self.message = kwargs.pop('message')
        if kwargs.has_key("events"):
            self.events = kwargs.pop('events')
        if kwargs.has_key("enclosed"):
            self.enclosed = kwargs.pop('enclosed')

        data = {
            'error': self.error,
            'message': self.message,
            'events': self.events,
        }

        if self.enclosed:
            kwargs['content'] = "<html><body><textarea>"+simplejson.dumps(data)+"</textarea></boby></html>"
        else:
            kwargs['content'] = simplejson.dumps(data)
            kwargs['content_type'] = 'application/json'
        super(JsonResponse, self).__init__(*args, **kwargs)

class JsonResp(HttpResponse):

    error = False
    type = 'page'
    force_json = False
    message = ''
    events = []

    def __init__(self, request, *args, **kwargs):

        self.error = kwargs.pop('error', False)
        self.message = kwargs.pop('message', '')
        self.events = kwargs.pop('events', [])
        self.force_json = kwargs.pop('force_json', False)
        self.type = kwargs.pop('type', None)
        self.template = kwargs.pop('template', None)
        self.form = kwargs.pop('form', None)
        self.formsets = kwargs.pop('formsets', {})
        self.request = request

        if self.form:
            self.type = 'form'
        elif self.message:
            self.type = 'message'
        if not self.type:
            self.type = 'page'

        data = dict()

        if self.type == 'page':
            ctx = RequestContext(request, kwargs.pop('ctx', {}))
            content = render_to_string(self.template, ctx)
        elif self.type == 'form':
            data.update({
                'type': 'form',
                'formid': request.POST.get("__form_id"),
                'form_auto_id': self.form.auto_id,
                })
            error = False
            errors = {}
            if self.form.errors:
                for key, val in self.form.errors.items():
                    if key == '__all__':
                        field = self.__class__.form_field_all(self.form)
                        errors[field] = [unicode(v) for v in val]
                    else:
                        errors[self.form.auto_id % key] = [unicode(v) for v in val]
                error = True

            for name, fs in self.formsets.items():
                for i, form in enumerate(fs.forms):
                    if form.errors:
                        error = True
                        for key, val in form.errors.items():
                            if key == '__all__':
                                field = self.__class__.form_field_all(form)
                                errors[field] = [unicode(v) for v in val]
                            else:
                                errors["%s-%s" % (form.auto_id % form.prefix, key)] = [unicode(v) for v in val]
            data.update({
                'error': error,
                'errors': errors,
                'message': self.message,
            })
        elif self.type == 'message':
            data.update({
                'error': self.error,
                'message': self.message,
            })
        else:
            raise NotImplementedError

        data.update({
            'events': self.events,
        })

        if request.is_ajax() or self.force_json:
            kwargs['content'] = simplejson.dumps(data)
            kwargs['content_type'] = 'application/json'
        else:
            kwargs['content'] = "<html><body><textarea>"+simplejson.dumps(data)+"</textarea></boby></html>"
        super(JsonResp, self).__init__(*args, **kwargs)

    @staticmethod
    def form_field_all(form):
        if form.prefix:
            field = form.auto_id % form.prefix + "-__all__-" + type(form).__name__
        else:
            field = form.auto_id % "__all__-" + type(form).__name__
        return field

def adminInterface(request, objtype = None):

    try:
        console = Advanced.objects.all().order_by('-id')[0].adv_consolemsg
    except:
        console = False
    try:
        hostname = GlobalConfiguration.objects.order_by('-id')[0].gc_hostname
    except:
        hostname = None
    return render(request, 'freeadmin/index.html', {
        'consolemsg': console,
        'hostname': hostname,
        'sw_name': get_sw_name(),
        'sw_version': get_sw_version(),
    })

def menu(request, objtype = None):

    try:
        navtree.generate(request)
        final = navtree.dijitTree()
        json = simplejson.dumps(final, indent=3)
    except Exception, e:
        #FIX ME
        print e
        json = ""
    #from freenasUI.nav import json2nav
    #json2nav(json)['main']

    return HttpResponse(json, mimetype="application/json")

def alert_status(request):
    if os.path.exists('/var/tmp/alert'):
        current = 'OK'
        with open('/var/tmp/alert') as f:
            entries = f.readlines()
        for entry in entries:
            if not entry:
                continue
            status, message = entry.split(': ', 1)
            if (status == 'WARN' and current == 'OK') or \
              status == 'CRIT' and current in ('OK','WARN'):
                current = status
        return HttpResponse(current)
    else:
        return HttpResponse('WARN')

def alert_detail(request):
    if os.path.exists('/var/tmp/alert'):
        with open('/var/tmp/alert') as f:
            entries = f.read().split('\n')
        alerts = []
        for entry in entries:
            if not entry:
                continue
            status, message = entry.split(': ', 1)
            alerts.append({
                'status': status,
                'message': message,
            })

        return render(request, "freeadmin/alert_status.html", {
            'alerts': alerts,
            })
    else:
        return HttpResponse(_("It was not possible to retrieve the current status"))

"""
We use the django debug 500 classes to show the traceback to the user
instead of the useless "An error occurred" used by dojo in case of
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
            'django_version_info': get_sw_version(),
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
        'modeladmin': m._admin,
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

    if m._admin.advanced_fields:
        mf.advanced_fields.extend(m._admin.advanced_fields)

    instance = m()
    formsets = {}
    if request.method == "POST":
        mf = mf(request.POST, request.FILES, instance=instance)
        if mf.is_valid():
            valid = True
        else:
            valid = False

        if m._admin.inlines:
            for inline, prefix in m._admin.inlines:
                _temp = __import__('%s.forms' % app, globals(), locals(), [inline], -1)
                inline = getattr(_temp, inline)
                extrakw = {
                    'can_delete': False
                    }
                fset = inlineformset_factory(m, inline._meta.model, form=inline, extra=0, **extrakw)
                try:
                    formsets['formset_%s' % inline._meta.model._meta.module_name] = fset(request.POST, prefix=prefix, instance=instance)
                except dforms.ValidationError:
                    pass

        for name, fs in formsets.items():
            for frm in fs.forms:
                frm.parent  = mf
            valid &= fs.is_valid()

        if valid:
            try:
                mf.save()
                for name, fs in formsets.items():
                    fs.save()
                events = []
                if hasattr(mf, "done") and callable(mf.done):
                    #FIXME: temporary workaround to do not change all MF to accept this arg
                    try:
                        mf.done(request=request, events=events)
                    except TypeError:
                        mf.done()
                return JsonResp(request, form=mf, formsets=formsets, message=_("%s successfully updated.") % m._meta.verbose_name, events=events)
            except MiddlewareError, e:
                return JsonResp(request, error=True, message=_("Error: %s") % str(e))
            except ServiceFailed, e:
                return JsonResp(request, error=True, message=_("The service failed to restart.") % m._meta.verbose_name)
        else:
            return JsonResp(request, form=mf, formsets=formsets)

    else:
        mf = mf()
        if m._admin.inlines:
            extrakw = {
                'can_delete': False
                }
            for inline, prefix in m._admin.inlines:
                _temp = __import__('%s.forms' % app, globals(), locals(), [inline], -1)
                inline = getattr(_temp, inline)
                fset = inlineformset_factory(m, inline._meta.model, form=inline, extra=1, **extrakw)
                formsets['formset_%s' % inline._meta.model._meta.module_name] = fset(prefix=prefix, instance=instance)

    context.update({
        'form': mf,
        'formsets': formsets,
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
        'modeladmin': m._admin,
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

    if m._admin.advanced_fields:
        mf.advanced_fields.extend(m._admin.advanced_fields)

    formsets = {}
    if request.method == "POST":
        mf = mf(request.POST, request.FILES, instance=instance)
        if mf.is_valid():
            valid = True
        else:
            valid = False

        if m._admin.inlines:
            for inline, prefix in m._admin.inlines:
                _temp = __import__('%s.forms' % app, globals(), locals(), [inline], -1)
                inline = getattr(_temp, inline)
                extrakw = {
                    'can_delete': True,
                    }
                fset = inlineformset_factory(m, inline._meta.model, form=inline, extra=0, **extrakw)
                try:
                    formsets['formset_%s' % inline._meta.model._meta.module_name] = fset(request.POST, prefix=prefix, instance=instance)
                except dforms.ValidationError:
                    pass

        for name, fs in formsets.items():
            for frm in fs.forms:
                frm.parent  = mf
            valid &= fs.is_valid()

        if valid:
            try:
                mf.save()
                for name, fs in formsets.items():
                    fs.save()
                events = []
                if hasattr(mf, "done") and callable(mf.done):
                    #FIXME: temporary workaround to do not change all MF to accept this arg
                    try:
                        mf.done(request=request, events=events)
                    except TypeError:
                        mf.done()
                if request.GET.has_key("iframe"):
                    return JsonResp(request, form=mf, formsets=formsets, message=_("%s successfully updated.") % m._meta.verbose_name)
                else:
                    return JsonResp(request, form=mf, formsets=formsets, message=_("%s successfully updated.") % m._meta.verbose_name, events=events)
            except ServiceFailed, e:
                return JsonResp(request, form=mf, error=True, message=_("The service failed to restart.") % m._meta.verbose_name, events=["serviceFailed(\"%s\")" % e.service])
            except MiddlewareError, e:
                return JsonResp(request, form=mf, error=True, message=_("Error: %s") % str(e))
        else:
            return JsonResp(request, form=mf, formsets=formsets)

    else:
        mf = mf(instance=instance)
        if m._admin.inlines:
            extrakw = {
                'can_delete': True,
                }
            for inline, prefix in m._admin.inlines:
                _temp = __import__('%s.forms' % app, globals(), locals(), [inline], -1)
                inline = getattr(_temp, inline)
                fset = inlineformset_factory(m, inline._meta.model, form=inline, extra=1, **extrakw)
                formsets['formset_%s' % inline._meta.model._meta.module_name] = fset(prefix=prefix, instance=instance)

    context.update({
        'form': mf,
        'formsets': formsets,
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
                content_type='text/html')

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
                return JsonResponse(message=_("%s successfully deleted.") % m._meta.verbose_name)

        else:
            instance.delete()
            return JsonResponse(message=_("%s successfully deleted.") % m._meta.verbose_name)
    if form and form_i is None:
        form_i = form(instance=instance)
    if form:
        context.update({'form': form_i})
    template = "%s/%s_delete.html" % (m._meta.app_label, m._meta.object_name.lower())
    try:
        get_template(template)
    except:
        template = 'freeadmin/generic_model_delete.html'

    return render(request, template, context)
