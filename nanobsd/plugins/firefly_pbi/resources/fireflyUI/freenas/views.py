from subprocess import Popen, PIPE
import json
import os
import re
import sys
import time

from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.shortcuts import render
from django.template import RequestContext
from django.template.loader import render_to_string
from django.utils import simplejson

from fireflyUI.freenas import forms, models, utils

import jsonrpclib
import urllib2
import oauth2 as oauth


class OAuthTransport(jsonrpclib.jsonrpc.SafeTransport):
    def __init__(self, host, verbose=None, use_datetime=0, key=None, secret=None):
        jsonrpclib.jsonrpc.SafeTransport.__init__(self)
        self.verbose = verbose
        self._use_datetime = use_datetime
        self.host = host
        self.key = key
        self.secret = secret

    def oauth_request(self, url, moreparams={}, body=''):
        params = {
            'oauth_version': "1.0",
            'oauth_nonce': oauth.generate_nonce(),
            'oauth_timestamp': int(time.time())
        }
        consumer = oauth.Consumer(key=self.key, secret=self.secret)
        params['oauth_consumer_key'] = consumer.key
        params.update(moreparams)

        req = oauth.Request(method='POST', url=url, parameters=params, body=body)
        signature_method = oauth.SignatureMethod_HMAC_SHA1()
        req.sign_request(signature_method, consumer, None)
        return req

    def request(self, host, handler, request_body, verbose=0):
        request = self.oauth_request(url=self.host, body=request_body)
        req = urllib2.Request(request.to_url())
        req.add_header('Content-Type', 'text/json')
        req.add_data(request_body)
        f = urllib2.urlopen(req)
        return(self.parse_response(f))


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
            kwargs['content'] = (
                "<html><body><textarea>"
                + json.dumps(data) +
                "</textarea></body></html>"
                )
        super(JsonResponse, self).__init__(*args, **kwargs)

    @staticmethod
    def form_field_all(form):
        if form.prefix:
            field = form.prefix + "-__all__"
        else:
            field = "__all__"
        return field


def start(request):
    firefly_key, firefly_secret = utils.get_firefly_oauth_creds()

    url = utils.get_rpc_url(request)
    trans = OAuthTransport(url, key=firefly_key,
        secret=firefly_secret)
    server = jsonrpclib.Server(url, transport=trans)
    auth = server.plugins.is_authenticated(request.COOKIES.get("sessionid", ""))
    jail = json.loads(server.plugins.jail.info())[0]
    assert auth

    try:
        firefly = models.Firefly.objects.order_by('-id')[0]
        firefly.enable = True
        firefly.save()
    except IndexError:
        firefly = models.Firefly.objects.create(enable=True)

    try:
        form = forms.FireflyForm(firefly.__dict__, instance=firefly, jail=jail)
        form.is_valid()
        form.save()
    except ValueError:
        return HttpResponse(simplejson.dumps({
            'error': True,
            'message': 'Firefly data did not validate, please configure it first.',
            }), content_type='application/json')

    cmd = "%s onestart" % utils.firefly_control
    pipe = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE,
        shell=True, close_fds=True)

    out = pipe.communicate()[0]
    return HttpResponse(simplejson.dumps({
        'error': False,
        'message': out,
        }))


def stop(request):
    firefly_key, firefly_secret = utils.get_firefly_oauth_creds()

    url = utils.get_rpc_url(request)
    trans = OAuthTransport(url, key=firefly_key,
        secret=firefly_secret)
    server = jsonrpclib.Server(url, transport=trans)
    auth = server.plugins.is_authenticated(request.COOKIES.get("sessionid", ""))
    jail = json.loads(server.plugins.jail.info())[0]
    assert auth

    try:
        firefly = models.Firefly.objects.order_by('-id')[0]
        firefly.enable = False
        firefly.save()
    except IndexError:
        firefly = models.Firefly.objects.create(enable=False)

    try:
        form = forms.FireflyForm(firefly.__dict__, instance=firefly, jail=jail)
        form.is_valid()
        form.save()
    except ValueError:
        pass

    cmd = "%s onestop" % utils.firefly_control
    pipe = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE,
        shell=True, close_fds=True)

    out = pipe.communicate()[0]
    return HttpResponse(simplejson.dumps({
        'error': False,
        'message': out,
        }))


def edit(request):
    firefly_key, firefly_secret = utils.get_firefly_oauth_creds()

    url = utils.get_rpc_url(request)
    trans = OAuthTransport(url, key=firefly_key,
        secret=firefly_secret)

    """
    Get the Firefly object
    If it does not exist create a new entry
    """
    try:
        firefly = models.Firefly.objects.order_by('-id')[0]
    except IndexError:
        firefly = models.Firefly.objects.create()

    try:
        server = jsonrpclib.Server(url, transport=trans)
        jail = json.loads(server.plugins.jail.info())[0]
        auth = server.plugins.is_authenticated(request.COOKIES.get("sessionid", ""))
        assert auth
    except Exception, e:
        raise

    if request.method == "GET":
        form = forms.FireflyForm(instance=firefly,
            jail=jail)
        return render(request, "edit.html", {
            'form': form,
        })

    if not request.POST:
        return JsonResponse(request, error=True, message="A problem occurred.")

    form = forms.FireflyForm(request.POST,
        instance=firefly,
        jail=jail)
    if form.is_valid():
        form.save()
        return JsonResponse(request, error=True, message="Firefly settings successfully saved.")

    return JsonResponse(request, form=form)


def treemenu(request):
    """
    This is how we inject nodes to the Tree Menu

    The FreeNAS GUI will access this view, expecting for a JSON
    that describes a node and possible some children.
    """

    plugin = {
        'name': 'Firefly',
        'append_to': 'services.PluginsJail',
        'icon': reverse("treemenu_icon"),
        'type': 'pluginsfcgi',
        'url': reverse('firefly_edit'),
        'kwargs': {'plugin_name': 'firefly'},
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

    proc = Popen(["/usr/bin/pgrep", "mt-daap"], stdout=PIPE, stderr=PIPE)

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


def treemenu_icon(request):
    with open(utils.firefly_icon, 'rb') as f:
        icon = f.read()

    return HttpResponse(icon, content_type='image/png')
