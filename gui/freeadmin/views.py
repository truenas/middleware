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
import logging
import hashlib
import os
import sys

from django import forms as dforms
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.views import debug
from django.conf import settings
from django.template import (Context, TemplateDoesNotExist,
    TemplateSyntaxError)
from django.template.defaultfilters import force_escape, pprint
from django.template.loader import get_template, template_source_loaders
from django.utils import simplejson
from django.utils.translation import ugettext as _
from django.utils.encoding import smart_unicode

from dojango.views import datagrid_list
from dojango.forms.models import inlineformset_factory
from freenasUI.common.system import get_sw_name, get_sw_version
from freenasUI.freeadmin.navtree import navtree
from freenasUI.freeadmin.utils import get_related_objects
from freenasUI.middleware.exceptions import MiddlewareError
from freenasUI.network.models import GlobalConfiguration
from freenasUI.services.exceptions import ServiceFailed
from freenasUI.system.models import Advanced

log = logging.getLogger('freeadmin.views')


class JsonResponse(HttpResponse):

    error = False
    enclosed = False
    message = ''
    events = []

    def __init__(self, *args, **kwargs):
        self.error = kwargs.pop('error', False)
        self.message = kwargs.pop('message', '')
        self.events = kwargs.pop('events', [])
        self.enclosed = kwargs.pop('enclosed', False)

        data = {
            'error': self.error,
            'message': self.message,
            'events': self.events,
        }

        if self.enclosed:
            kwargs['content'] = ("<html><body><textarea>"
                + simplejson.dumps(data) +
                "</textarea></boby></html>")
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
            pass
            #ctx = RequestContext(request, kwargs.pop('ctx', {}))
            #content = render_to_string(self.template, ctx)
        elif self.type == 'form':
            data.update({
                'type': 'form',
                'formid': request.POST.get("__form_id"),
                })
            error = False
            errors = {}
            if self.form.errors:
                for key, val in self.form.errors.items():
                    if key == '__all__':
                        field = self.__class__.form_field_all(self.form)
                        errors[field] = [unicode(v) for v in val]
                    else:
                        errors[key] = [unicode(v) for v in val]
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
                                errors["%s-%s" % (
                                    form.prefix,
                                    key,
                                    )] = [unicode(v) for v in val]
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
            kwargs['content'] = ("<html><body><textarea>"
                + simplejson.dumps(data) +
                "</textarea></boby></html>")
        super(JsonResp, self).__init__(*args, **kwargs)

    @staticmethod
    def form_field_all(form):
        if form.prefix:
            field = form.prefix + "-__all__"
        else:
            field = "__all__"
        return field


def adminInterface(request, objtype=None):

    try:
        console = Advanced.objects.all().order_by('-id')[0].adv_consolemsg
    except:
        console = False
    try:
        hostname = GlobalConfiguration.objects.order_by('-id')[0].gc_hostname
    except:
        hostname = None
    sw_version = get_sw_version()
    return render(request, 'freeadmin/index.html', {
        'consolemsg': console,
        'hostname': hostname,
        'sw_name': get_sw_name(),
        'sw_version': sw_version,
        'cache_hash': hashlib.md5(sw_version).hexdigest(),
    })


def menu(request, objtype=None):

    try:
        navtree.generate(request)
        final = navtree.dijitTree()
        json = simplejson.dumps(final)
    except Exception, e:
        log.debug("Fatal error while generating the tree json: %s", e)
        json = ""

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
              status == 'CRIT' and current in ('OK', 'WARN'):
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
        return HttpResponse(
            _("It was not possible to retrieve the current status")
            )


class ExceptionReporter(debug.ExceptionReporter):
    """
    We use the django debug 500 classes to show the traceback to the user
    instead of the useless "An error occurred" used by dojo in case of
    HTTP 500 responses.

    As this is not a public API of django we need to duplicate some code
    """

    is_email = False

    def get_traceback_html(self):
        """
        Copied from debug.ExceptionReporter
        The Template was replaced to use 500_freenas.html instead
        of the hard-coded one

        Return HTML code for traceback."
        """

        t = get_template("500_freenas.html")
        #t = Template(TECHNICAL_500_TEMPLATE, name='Technical 500 template')
        data = self.get_traceback_data()
        data.update({
            'sw_version': get_sw_version(),
        })
        c = Context(data)
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


def page_not_found(request, *args, **kwargs):
    return HttpResponseRedirect('/')


def generic_model_add(request, app, model, mf=None):
    """
    Magic happens here

    We dynamically import the module based on app and model names
    passed as view argument

    From there we retrieve the ModelForm associated (which was discovered
    previously on the auto_generate process)
    """

    try:
        _temp = __import__('freenasUI.%s.models' % app, globals(), locals(), [model], -1)
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

    instance = m()
    formsets = {}
    if request.method == "POST":
        mf = mf(request.POST, request.FILES, instance=instance)
        if m._admin.advanced_fields:
            mf.advanced_fields.extend(m._admin.advanced_fields)

        valid = True
        if m._admin.inlines:
            for inlineopts in m._admin.inlines:
                inline = inlineopts.get("form")
                prefix = inlineopts.get("prefix")
                _temp = __import__('%s.forms' % app,
                    globals(),
                    locals(),
                    [inline],
                    -1)
                inline = getattr(_temp, inline)
                extrakw = {
                    'can_delete': False
                    }
                fset = inlineformset_factory(m, inline._meta.model,
                    form=inline,
                    extra=0,
                    **extrakw)
                try:
                    fsname = 'formset_%s' % (
                        inline._meta.model._meta.module_name,
                        )
                    formsets[fsname] = fset(request.POST,
                        prefix=prefix,
                        instance=instance)
                except dforms.ValidationError:
                    pass

        for name, fs in formsets.items():
            for frm in fs.forms:
                frm.parent = mf
            valid &= fs.is_valid()

        valid &= mf.is_valid(formsets=formsets)

        if valid:
            try:
                mf.save()
                for name, fs in formsets.items():
                    fs.save()
                events = []
                if hasattr(mf, "done") and callable(mf.done):
                    # FIXME: temporary workaround to do not change all MF to
                    # accept this arg
                    try:
                        mf.done(request=request, events=events)
                    except TypeError:
                        mf.done()
                return JsonResp(request, form=mf,
                    formsets=formsets,
                    message=_("%s successfully updated.") % (
                        m._meta.verbose_name,
                        ),
                    events=events)
            except MiddlewareError, e:
                return JsonResp(request,
                    error=True,
                    message=_("Error: %s") % str(e))
            except ServiceFailed, e:
                return JsonResp(request,
                    error=True,
                    message=_("The service failed to restart.")
                    )
        else:
            return JsonResp(request, form=mf, formsets=formsets)

    else:
        mf = mf()
        if m._admin.advanced_fields:
            mf.advanced_fields.extend(m._admin.advanced_fields)
        if m._admin.inlines:
            extrakw = {
                'can_delete': False
                }
            for inlineopts in m._admin.inlines:
                inline = inlineopts.get("form")
                prefix = inlineopts.get("prefix")
                _temp = __import__('%s.forms' % app,
                    globals(),
                    locals(),
                    [inline],
                    -1)
                inline = getattr(_temp, inline)
                fset = inlineformset_factory(m, inline._meta.model,
                    form=inline,
                    extra=1,
                    **extrakw)
                fsname = 'formset_%s' % inline._meta.model._meta.module_name
                formsets[fsname] = fset(prefix=prefix, instance=instance)
                formsets[fsname].verbose_name = (
                    inline._meta.model._meta.verbose_name
                    )

    context.update({
        'form': mf,
        'formsets': formsets,
    })

    template = "%s/%s_add.html" % (
        m._meta.app_label,
        m._meta.object_name.lower(),
        )
    try:
        get_template(template)
    except:
        template = 'freeadmin/generic_model_add.html'

    return render(request, template, context)


def generic_model_view(request, app, model):

    try:
        _temp = __import__('freenasUI.%s.models' % app, globals(), locals(),
            [model], -1)
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
        _temp = __import__('freenasUI.%s.models' % app, globals(), locals(),
            [model], -1)
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
            _temp = __import__('freenasUI.%s.models' % app_name,
                globals(),
                locals(),
                [model_name],
                -1)
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
        _temp = __import__('freenasUI.%s.models' % app, globals(), locals(),
            [model], -1)
    except ImportError:
        raise
    m = getattr(_temp, model)

    if 'inline' in request.GET:
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
    if 'deletable' in request.GET and 'deletable' not in context:
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

    formsets = {}
    if request.method == "POST":
        mf = mf(request.POST, request.FILES, instance=instance)
        if m._admin.advanced_fields:
            mf.advanced_fields.extend(m._admin.advanced_fields)

        valid = True
        if m._admin.inlines:
            for inlineopts in m._admin.inlines:
                inline = inlineopts.get("form")
                prefix = inlineopts.get("prefix")
                _temp = __import__('%s.forms' % app,
                    globals(),
                    locals(),
                    [inline],
                    -1)
                inline = getattr(_temp, inline)
                extrakw = {
                    'can_delete': True,
                    }
                fset = inlineformset_factory(m, inline._meta.model,
                    form=inline,
                    extra=0,
                    **extrakw)
                try:
                    fsname = 'formset_%s' % (
                        inline._meta.model._meta.module_name,
                        )
                    formsets[fsname] = fset(request.POST,
                        prefix=prefix,
                        instance=instance)
                except dforms.ValidationError:
                    pass

        for name, fs in formsets.items():
            for frm in fs.forms:
                frm.parent = mf
            valid &= fs.is_valid()

        valid &= mf.is_valid(formsets=formsets)

        if valid:
            try:
                mf.save()
                for name, fs in formsets.items():
                    fs.save()
                events = []
                if hasattr(mf, "done") and callable(mf.done):
                    # FIXME: temporary workaround to do not change all MF to
                    # accept this arg
                    try:
                        mf.done(request=request, events=events)
                    except TypeError:
                        mf.done()
                if 'iframe' in request.GET:
                    return JsonResp(request,
                        form=mf,
                        formsets=formsets,
                        message=_("%s successfully updated.") % (
                            m._meta.verbose_name,
                            ))
                else:
                    return JsonResp(request,
                        form=mf,
                        formsets=formsets,
                        message=_("%s successfully updated.") % (
                            m._meta.verbose_name,
                            ),
                        events=events)
            except ServiceFailed, e:
                return JsonResp(request,
                    form=mf,
                    error=True,
                    message=_("The service failed to restart."),
                    events=["serviceFailed(\"%s\")" % e.service])
            except MiddlewareError, e:
                return JsonResp(request,
                    form=mf,
                    error=True,
                    message=_("Error: %s") % str(e))
        else:
            return JsonResp(request, form=mf, formsets=formsets)

    else:
        mf = mf(instance=instance)
        if m._admin.advanced_fields:
            mf.advanced_fields.extend(m._admin.advanced_fields)

        if m._admin.inlines:
            extrakw = {
                'can_delete': True,
                }
            for inlineopts in m._admin.inlines:
                inline = inlineopts.get("form")
                prefix = inlineopts.get("prefix")
                _temp = __import__('%s.forms' % app,
                    globals(),
                    locals(),
                    [inline],
                    -1)
                inline = getattr(_temp, inline)
                fset = inlineformset_factory(m, inline._meta.model,
                    form=inline,
                    extra=1,
                    **extrakw)
                fsname = 'formset_%s' % inline._meta.model._meta.module_name
                formsets[fsname] = fset(prefix=prefix, instance=instance)
                formsets[fsname].verbose_name = (
                    inline._meta.model._meta.verbose_name
                    )

    context.update({
        'form': mf,
        'formsets': formsets,
    })

    template = "%s/%s_edit.html" % (
        m._meta.app_label,
        m._meta.object_name.lower(),
        )
    try:
        get_template(template)
    except:
        template = 'freeadmin/generic_model_edit.html'

    if 'iframe' in request.GET:
        resp = render(request, template, context,
                mimetype='text/html')
        resp.content = ("<html><body><textarea>"
            + resp.content +
            "</textarea></boby></html>")
        return resp
    else:
        return render(request, template, context, \
                content_type='text/html')


def generic_model_empty_formset(request, app, model):

    try:
        _temp = __import__('%s.models' % app, globals(), locals(), [model], -1)
    except ImportError:
        raise
    m = getattr(_temp, model)

    if not m._admin.inlines:
        return None

    inline = None
    for inlineopts in m._admin.inlines:
        _inline = inlineopts.get("form")
        prefix = inlineopts.get("prefix")
        if prefix == request.GET.get("fsname"):
            _temp = __import__('%s.forms' % app,
                globals(),
                locals(),
                [_inline],
                -1)
            inline = getattr(_temp, _inline)
            break

    if inline:
        fset = inlineformset_factory(m, inline._meta.model,
            form=inline,
            extra=1)
        fsins = fset(prefix=prefix)

        return HttpResponse(fsins.empty_form.as_table())
    return HttpResponse()


def generic_model_delete(request, app, model, oid, mf=None):

    try:
        _temp = __import__('%s.models' % app, globals(), locals(), [model], -1)
    except ImportError:
        raise

    m = getattr(_temp, model)
    instance = get_object_or_404(m, pk=oid)

    try:
        if m._admin.delete_form_filter:
            find = m.objects.filter(id=instance.id,
                **m._admin.delete_form_filter)
            if find.count() == 0:
                raise
        _temp = __import__('%s.forms' % app,
            globals(),
            locals(),
            [m._admin.delete_form],
            -1)
        form = getattr(_temp, m._admin.delete_form)
    except:
        form = None

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

    related, related_num = get_related_objects(instance)
    context = {
        'app': app,
        'model': model,
        'oid': oid,
        'object': instance,
        'verbose_name': instance._meta.verbose_name,
        'related': related,
        'related_num': related_num,
    }

    form_i = None
    mf = mf(instance=instance)
    if request.method == "POST":
        if form:
            form_i = form(request.POST, instance=instance)
            if form_i.is_valid():
                events = []
                if hasattr(form_i, "done"):
                    form_i.done(events=events)
                mf.delete(events=events)
                return JsonResponse(
                    message=_("%s successfully deleted.") % (
                        m._meta.verbose_name,
                        ),
                    events=events)

        else:
            events = []
            mf.delete(events=events)
            return JsonResponse(message=_("%s successfully deleted.") % (
                m._meta.verbose_name,
                ), events=events)
    if form and form_i is None:
        form_i = form(instance=instance)
    if form:
        context.update({'form': form_i})
    template = "%s/%s_delete.html" % (
        m._meta.app_label,
        m._meta.object_name.lower(),
        )
    try:
        get_template(template)
    except:
        template = 'freeadmin/generic_model_delete.html'

    return render(request, template, context)
