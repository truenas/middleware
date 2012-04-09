from subprocess import Popen, PIPE
import json
import os
import re
import sys

from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.shortcuts import render
from django.template import RequestContext
from django.template.loader import render_to_string

from transmissionUI.freenas import forms, models, utils
import jsonrpclib


class JsonResponse(HttpResponse):
    """
    This is a response class which implements FreeNAS GUI API

    It is not required, the user can implement its own
    or even open/code an entire new UI just for the plugin
    """

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
        self.template = kwargs.pop('tpl', None)
        self.form = kwargs.pop('form', None)
        self.node = kwargs.pop('node', None)
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
            if self.node:
                data['node'] = self.node
            ctx = RequestContext(request, kwargs.pop('ctx', {}))
            content = render_to_string(self.template, ctx)
            data.update({
                'type': self.type,
                'error': self.error,
                'content': content,
            })
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
            kwargs['content'] = json.dumps(data)
            kwargs['content_type'] = 'application/json'
        else:
            kwargs['content'] = "<html><body><textarea>"+json.dumps(data)+"</textarea></boby></html>"
        super(JsonResponse, self).__init__(*args, **kwargs)

    @staticmethod
    def form_field_all(form):
        if form.prefix:
            field = form.prefix + "-__all__"
        else:
            field = "__all__"
        return field


def all(request):
    print request.path
    return HttpResponse()


def start(request):

    server = jsonrpclib.Server('http%s://%s/plugins/json/' % (
        's' if request.is_secure() else '',
        request.get_host(),
        ))
    auth = server.plugins.is_authenticated(request.COOKIES.get("sessionid", ""))
    assert auth

    cmd = "%s start" % utils.transmission_control
    pipe = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE,
        shell=True, close_fds=True)

    out = pipe.communicate()[0]
    return HttpResponse(out)


def stop(request):

    server = jsonrpclib.Server('http%s://%s/plugins/json/' % (
        's' if request.is_secure() else '',
        request.get_host(),
        ))
    auth = server.plugins.is_authenticated(request.COOKIES.get("sessionid", ""))
    assert auth

    cmd = "%s stop " % utils.transmission_control
    pipe = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE,
        shell=True, close_fds=True)

    out = pipe.communicate()[0]
    return HttpResponse(out)


def edit(request):

    """
    Get the Transmission object
    If it does not exist create a new entry
    """
    try:
        transmission = models.Transmission.objects.order_by('-id')[0]
    except IndexError:
        transmission = models.Transmission.objects.create()

    try:
        server = jsonrpclib.Server('http%s://%s/plugins/json/' % (
            's' if request.is_secure() else '',
            request.get_host(),
            ))
        auth = server.plugins.is_authenticated(request.COOKIES.get("sessionid", ""))
        assert auth
        plugin = json.loads(server.plugins.plugins.get("transmission"))[0]
        mounted = server.fs.mounted.get(plugin['fields']['plugin_path'])
        jail = json.loads(server.plugins.jail.info())[0]
    except Exception, e:
        raise

    if request.method == "GET":
        form = forms.TransmissionForm(instance=transmission,
            plugin=plugin,
            mountpoints=mounted,
            jail=jail)
        return render(request, "edit.html", {
            'form': form,
        })

    if not request.POST:
        return JsonResponse(request, error=True, message="A problem occurred.")

    form = forms.TransmissionForm(request.POST,
        instance=transmission,
        plugin=plugin,
        mountpoints=mounted,
        jail=jail)
    if form.is_valid():
        form.save()
        return JsonResponse(request, error=True, message="Transmission settings successfully saved.")

    return JsonResponse(request, form=form)


def treemenu(request):
    """
    This is how we inject nodes to the Tree Menu

    The FreeNAS GUI will access this view, expecting for a JSON
    that describes a node and possible some children.
    """

    plugin = {
        'name': 'Transmission',
        'append_to': 'services.PluginsJail',
        'icon': 'SettingsIcon',
        'type': 'pluginsfcgi',
        'url': reverse('transmission_edit'),
        'kwargs': {'plugin_name': 'transmission'},
    }

    return HttpResponse(json.dumps([plugin]), content_type='application/json')


def status(request):
    """
    Returns a dict containing the current status of the services

    status can be one of:
        - STARTING
        - RUNNING
        - STOPPING
        - STOPPED
    """
    pid = None

    proc = Popen(["/usr/bin/pgrep", "transmission-daemon"], stdout=PIPE, stderr=PIPE)

    stdout = proc.communicate()[0]

    if proc.returncode == 0:
        status = 'RUNNING'
        pid = stdout.split('\n')[0]
    else:
        status = 'STOPPED'

    return HttpResponse(json.dumps({
            'status': status,
            'pid': pid,
        }),
        content_type='application/json')
