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
from collections import OrderedDict
from functools import update_wrapper
import json
import logging

from django import forms as dforms
from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import get_template
from django.utils.translation import ugettext as _

from dojango.forms.models import inlineformset_factory
from freenasUI.freeadmin.api.utils import (DojoModelResource,
    DjangoAuthentication)
from freenasUI.middleware.exceptions import MiddlewareError
from freenasUI.services.exceptions import ServiceFailed

log = logging.getLogger('freeadmin.options')


class BaseFreeAdmin(object):

    create_modelform = None
    edit_modelform = None
    delete_form = None
    delete_form_filter = {}  # Ugly workaround for Extent/DeviceExtent
    exclude_fields = ('id', )
    deletable = True
    menu_child_of = None

    resource = None

    advanced_fields = []

    inlines = []

    nav_extra = {}

    object_filters = {}
    object_num = -1

    icon_model = None
    icon_object = None
    icon_add = None
    icon_view = None

    composed_fields = []

    extra_js = ''

    def __init__(self, c=None, model=None, admin=None):

        if model is not None:
            self._model = model

        if admin is not None:
            self._admin = admin

        if c is not None:
            obj = c()
            for i in dir(obj):
                if not i.startswith("__"):
                    if not hasattr(self, i):
                        raise Exception("The attribute '%s' is a not valid "
                            "in FreeAdmin" % i)
                    self.__setattr__(i, getattr(obj, i))

        if self.resource is None:
            myMeta = type('Meta', (object, ), dict(
                queryset=self._model.objects.all(),
                resource_name=self._model._meta.module_name,
                allowed_methods=['get'],
                include_resource_uri=False,
                authentication=DjangoAuthentication(),
                ))

            myres = type(
                self._model._meta.object_name + 'Resource',
                (DojoModelResource, ),
                dict(Meta=myMeta)
                )
            res = myres()
            self.resource = myres
        elif self.resource is False:
            res = None
        else:
            res = self.resource()

        if res:
            self._admin.v1_api.register(res)

    def get_urls(self):
        from django.conf.urls import patterns, url

        def wrap(view):
            def wrapper(*args, **kwargs):
                return self._admin.admin_view(view)(*args, **kwargs)
            return update_wrapper(wrapper, view)

        info = self._model._meta.app_label, self._model._meta.module_name

        urlpatterns = patterns('',
            url(r'^add/(?P<mf>.+?)?$',
                wrap(self.add),
                name='freeadmin_%s_%s_add' % info),
            url(r'^edit/(?P<oid>\d+)/(?P<mf>.+?)?$',
                wrap(self.edit),
                name='freeadmin_%s_%s_edit' % info),
            url(r'^delete/(?P<oid>\d+)/$',
                wrap(self.delete),
                name='freeadmin_%s_%s_delete' % info),
            url(r'^datagrid/$',
                wrap(self.datagrid),
                name='freeadmin_%s_%s_datagrid' % info),
            url(r'^structure/$',
                wrap(self.structure),
                name='freeadmin_%s_%s_structure' % info),
            url(r'^actions/$',
                wrap(self.actions),
                name='freeadmin_%s_%s_actions' % info),
            url(r'^empty-formset/$',
                wrap(self.empty_formset),
                name='freeadmin_%s_%s_empty_formset' % info),
        )
        return urlpatterns

    @property
    def urls(self):
        return self.get_urls()

    def add(self, request, mf=None):
        """
        Magic happens here

        We dynamically import the module based on app and model names
        passed as view argument

        From there we retrieve the ModelForm associated (which was discovered
        previously on the auto_generate process)
        """
        from freenasUI.freeadmin.navtree import navtree
        from freenasUI.freeadmin.views import JsonResp

        m = self._model
        app = self._model._meta.app_label
        context = {
            'app': app,
            'model': m,
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
                        # FIXME: temporary workaround to do not change all MF
                        # to accept this arg
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
                    fsname = 'formset_%s' % (
                        inline._meta.model._meta.module_name,
                        )
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

    def edit(self, request, oid, mf=None):

        from freenasUI.freeadmin.navtree import navtree
        from freenasUI.freeadmin.views import JsonResp
        m = self._model

        if 'inline' in request.GET:
            inline = True
        else:
            inline = False

        context = {
            'app': m._meta.app_label,
            'model': m,
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
            if mf is None:
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
                    _temp = __import__('%s.forms' % m._meta.app_label,
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
                        # FIXME: temporary workaround to do not change all MF
                        # to accept this arg
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
                    _temp = __import__('%s.forms' % m._meta.app_label,
                        globals(),
                        locals(),
                        [inline],
                        -1)
                    inline = getattr(_temp, inline)
                    fset = inlineformset_factory(m, inline._meta.model,
                        form=inline,
                        extra=1,
                        **extrakw)
                    fsname = 'formset_%s' % (
                        inline._meta.model._meta.module_name,
                        )
                    formsets[fsname] = fset(prefix=prefix, instance=instance)
                    formsets[fsname].verbose_name = (
                        inline._meta.model._meta.verbose_name
                        )

        context.update({
            'form': mf,
            'formsets': formsets,
            'instance': instance,
            'delete_url': reverse('freeadmin_%s_%s_delete' % (
                m._meta.app_label,
                m._meta.module_name,
                ), kwargs={
                'oid': instance.id,
                }),
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
            return render(request, template, context,
                content_type='text/html')

    def delete(self, request, oid, mf=None):
        from freenasUI.freeadmin.navtree import navtree
        from freenasUI.freeadmin.views import JsonResp
        from freenasUI.freeadmin.utils import get_related_objects

        m = self._model
        instance = get_object_or_404(m, pk=oid)

        try:
            if m._admin.delete_form_filter:
                find = m.objects.filter(id=instance.id,
                    **m._admin.delete_form_filter)
                if find.count() == 0:
                    raise
            _temp = __import__('%s.forms' % m._meta.app_label,
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
            'app': m._meta.app_label,
            'model': m._meta.module_name,
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
                    return JsonResp(request,
                        message=_("%s successfully deleted.") % (
                            m._meta.verbose_name,
                            ),
                        events=events)

            else:
                events = []
                mf.delete(events=events)
                return JsonResp(request,
                    message=_("%s successfully deleted.") % (
                        m._meta.verbose_name,
                    ),
                    events=events)
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

    def empty_formset(self, request):

        m = self._model

        if not m._admin.inlines:
            return None

        inline = None
        for inlineopts in m._admin.inlines:
            _inline = inlineopts.get("form")
            prefix = inlineopts.get("prefix")
            if prefix == request.GET.get("fsname"):
                _temp = __import__('%s.forms' % m._meta.app_label,
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

    def datagrid(self, request):

        m = self._model

        context = {
            'model': m,
            'resource_name': self.resource._meta.resource_name,
            'structure_url': reverse('freeadmin_%s_%s_structure' % (
                m._meta.app_label,
                m._meta.module_name,
                )),
            'actions_url': reverse('freeadmin_%s_%s_actions' % (
                m._meta.app_label,
                m._meta.module_name,
                )),
        }

        template = "%s/%s_datagrid.html" % (
            m._meta.app_label,
            m._meta.module_name,
            )
        try:
            get_template(template)
        except:
            template = 'freeadmin/generic_model_datagrid.html'

        return render(request, template, context)

    def get_datagrid_columns(self):

        columns = []
        for field in self._model._meta.fields:

            if field.name in self.exclude_fields:
                continue

            data = {
                'name': field.name,
                'label': field.verbose_name.encode('utf-8'),
            }

            """
            This is a hook to get extra options for the column in dgrid

            A method get_column_<field_name>_extra is looked for
            and a dict is expected as a return that will update `data`
            """
            funcname = "get_column_%s_extra" % (field.name, )
            if hasattr(self, funcname):
                extra = getattr(self, funcname)()
                data.update(extra)

            columns.append(data)

        return columns

    def structure(self, request):

        columns = self.get_datagrid_columns()
        data = OrderedDict()
        for column in columns:
            name = column.pop('name')
            data[name] = column

        enc = json.dumps(data)
        return HttpResponse(enc)

    def get_actions(self):

        actions = {}
        actions['Edit'] = {
            'on_select': """function(numrows) {
                if(numrows > 1 || numrows == 0) {
                    query(".gridEdit").forEach(function(item, idx) {
                        domStyle.set(item, "display", "none");
                    });
                } else {
                    query(".gridEdit").forEach(function(item, idx) {
                        domStyle.set(item, "display", "block");
                    });
                }
            }""",
            'button_name': 'Edit',
            'on_click': """function() {
                var mybtn = this;
                for (var i in grid.selection) {
                    grid.store.get(i).then(function(data) {
                        editObject('Edit', data._edit_url, [mybtn,]);
                    });
                }
            }""",
        }

        actions['Delete'] = {
            'on_select': """function(numrows) {
                if(numrows > 1 || numrows == 0) {
                    query(".gridDelete").forEach(function(item, idx) {
                        domStyle.set(item, "display", "none");
                    });
                } else {
                    query(".gridDelete").forEach(function(item, idx) {
                        domStyle.set(item, "display", "block");
                    });
                }
            }""",
            'button_name': 'Delete',
            'on_click': """function() {
                var mybtn = this;
                for (var i in grid.selection) {
                    grid.store.get(i).then(function(data) {
                        editObject('Delete', data._delete_url, [mybtn,]);
                    });
                }
            }""",
        }

        return actions

    def actions(self, request):
        actions = self.get_actions()
        enc = json.dumps(actions)
        return HttpResponse(enc)
