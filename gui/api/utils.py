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
import logging
import re

import oauth2
from tastypie.authentication import Authentication, MultiAuthentication
from tastypie.authorization import Authorization
from tastypie.paginator import Paginator
from tastypie.resources import ModelResource, Resource
from freenasUI.api.models import APIClient

RE_SORT = re.compile(r'^sort\((.*)\)$')
log = logging.getLogger('api.resources')


class DjangoAuthentication(Authentication):
    def is_authenticated(self, request, **kwargs):
        if request.user.is_authenticated():
            return True
        return False

    # Optional but recommended
    def get_identifier(self, request):
        return request.user.username


class OAuth2Authentication(Authentication):
    """OAuth2 authenticator.

    This Authentication method checks for a provided HTTP_AUTHORIZATION
    and looks up to see if this is a valid OAuth Access Token
    """
    def __init__(self, realm='API'):
        self.realm = realm

    def verify_access_token(self, request, key):

        uurl = "%s://%s%s" % (
            'https' if request.is_secure() else 'http',
            request.get_host(),
            request.path,
        )

        auth_header = {}
        if 'Authorization' in request.META:
            auth_header = {'Authorization': request.META['Authorization']}
        elif 'HTTP_AUTHORIZATION' in request.META:
            auth_header = {'Authorization': request.META['HTTP_AUTHORIZATION']}

        oreq = oauth2.Request.from_request(
            request.method,
            uurl,
            headers=auth_header,
            query_string=request.META.get('QUERY_STRING', None),
        )

        key = oreq.get("oauth_consumer_key", None)

        secret = None
        client = APIClient.objects.get(name=key)
        if client:
            secret = client.secret

        if not key or not secret:
            return False

        try:
            server = oauth2.Server()
            cons = oauth2.Consumer(key, secret)
            server.add_signature_method(oauth2.SignatureMethod_HMAC_SHA1())
            server.verify_request(oreq, cons, None)
            authorized = True
        except Exception:
            log.exception("auth2 error")
            authorized = False

        return authorized

    def is_authenticated(self, request, **kwargs):
        """Verify 2-legged oauth request. Parameters accepted as
        values in "Authorization" header, or as a GET request
        or in a POST body.
        """
        log.debug("OAuth2Authentication")

        try:
            key = request.GET.get('oauth_consumer_key')
            if not key:
                key = request.POST.get('oauth_consumer_key')
            if not key:
                auth_header_value = request.META.get('HTTP_AUTHORIZATION')
                if auth_header_value:
                    key = auth_header_value.split(' ')[1]
            if not key:
                log.error('No consumer key found')
                return None

            assert self.verify_access_token(request, key)

            #request.user = token.user
            # If OAuth authentication is successful, set oauth_consumer_key
            # on request in case we need it later
            request.META['oauth_consumer_key'] = key
            return True
        except KeyError:
            log.exception("Error in OAuth2Authentication")
            #request.user = AnonymousUser()
            return False
        except Exception:
            log.exception("Error in OAuth2Authentication")
            return False
        return True


class APIAuthorization(Authorization):
    pass


class DojoPaginator(Paginator):

    def __init__(self, request, *args, **kwargs):
        super(DojoPaginator, self).__init__(request.GET, *args, **kwargs)
        r = request.META.get("HTTP_RANGE", None)
        if r:
            r = r.split('=', 1)[1].split('-')
            self.offset = int(r[0])
            if r[1]:
                self.limit = int(r[1]) + 1 - self.offset


class ResourceMixin(object):

    def method_check(self, request, allowed=None):
        """
        Make sure only OAuth2 is allowed to POST/PUT/DELETE
        """
        if request.user.is_authenticated():
            allowed = ['get']
        return super(ResourceMixin, self).method_check(request, allowed=allowed)


class DojoModelResource(ResourceMixin, ModelResource):

    def apply_sorting(self, obj_list, options=None):
        """
        Dojo aware filtering
        """
        fields = []
        for key in options.keys():
            if RE_SORT.match(key):
                fields = RE_SORT.search(key).group(1)
                fields = [f.strip() for f in fields.split(',')]
                break
        if fields:
            obj_list = obj_list.order_by(",".join(fields))
        return obj_list

    def get_list(self, request, **kwargs):
        """
        XXXXXX
        This method was retrieved from django-tastypie
        It had to be modified that way to set the Content-Range
        response header so ranges could workd well with dojo
        XXXXXX
        """
        base_bundle = self.build_bundle(request=request)
        objects = self.obj_get_list(bundle=base_bundle, **self.remove_api_resource_names(kwargs))
        sorted_objects = self.apply_sorting(objects, options=request.GET)

        paginator = self._meta.paginator_class(request, sorted_objects, resource_uri=self.get_resource_uri(), limit=self._meta.limit)
        to_be_serialized = paginator.page()

        bundles = [self.build_bundle(obj=obj, request=request) for obj in to_be_serialized['objects']]
        to_be_serialized['objects'] = [self.full_dehydrate(bundle) for bundle in bundles]
        length = len(to_be_serialized['objects'])
        to_be_serialized = self.alter_list_data_to_serialize(request, to_be_serialized)
        response = self.create_response(request, to_be_serialized)
        response['Content-Range'] = 'items %d-%d/%d' % (paginator.offset, paginator.offset+length-1, len(sorted_objects))
        return response

    def alter_list_data_to_serialize(self, request, data):
        return data['objects']

    def dehydrate(self, bundle):
        bundle.data['_edit_url'] = bundle.obj.get_edit_url()
        bundle.data['_delete_url'] = bundle.obj.get_delete_url()
        return bundle


class DojoResource(ResourceMixin, Resource):

    def _apply_sorting(self, options=None):
        """
        Dojo aware filtering
        """
        fields = []
        for key in options.keys():
            if RE_SORT.match(key):
                fields = RE_SORT.search(key).group(1)
                fields = [f.strip() for f in fields.split(',')]
                break
        return fields

    def alter_list_data_to_serialize(self, request, data):
        return data['objects']


APIAuthentication = MultiAuthentication(
    DjangoAuthentication(),
    OAuth2Authentication(),
)
