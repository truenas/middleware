#
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
import base64
import logging
import re
import six
import sys
import traceback
import urllib.request, urllib.parse, urllib.error

from django.contrib.auth import authenticate
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.db.models import FieldDoesNotExist
from django.db.models.fields.related import ForeignKey
from django.http import Http404, QueryDict

from freenasUI.account.models import bsdUsers
from freenasUI.common.log import log_traceback
from freenasUI.freeadmin.apppool import appPool
from freenasUI.freeadmin.models.fields import DictField, MultiSelectField
from freenasUI.middleware.exceptions import MiddlewareError
from freenasUI.services.exceptions import ServiceFailed

from tastypie.authentication import (
    Authentication, BasicAuthentication, MultiAuthentication
)
from tastypie import fields, http
from tastypie.authorization import Authorization
from tastypie.exceptions import ImmediateHttpResponse, NotFound, UnsupportedFormat
from tastypie.http import HttpUnauthorized, HttpNotFound
from tastypie.paginator import Paginator
from tastypie.resources import DeclarativeMetaclass, ModelResource, Resource, sanitize
from tastypie.utils import dict_strip_unicode_keys

RE_SORT = re.compile(r'^sort\((.*)\)$')
log = logging.getLogger('api.utils')


class DjangoAuthentication(Authentication):
    def is_authenticated(self, request, **kwargs):
        if request.user.is_authenticated:
            return True

        # Allow access to the API of no root password has been set yet
        if not bsdUsers.has_root_password():
            return True

        return False

    # Optional but recommended
    def get_identifier(self, request):
        return request.user.bsdusr_username


class FreeBasicAuthentication(BasicAuthentication):
    """
    Override to do not show WWW-Authenticate for requests from WebUI
    """

    def is_authenticated(self, request, **kwargs):
        """
        Copied from BasicAuthentication due to the call to private
        _unauthorized without arguments
        """
        if not request.META.get('HTTP_AUTHORIZATION'):
            return self._unauthorized(request)

        try:
            (auth_type, data) = request.META['HTTP_AUTHORIZATION'].split()
            if auth_type.lower() != 'basic':
                return self._unauthorized(request)
            user_pass = base64.b64decode(data).decode('utf-8')
        except:
            return self._unauthorized(request)

        bits = user_pass.split(':', 1)

        if len(bits) != 2:
            return self._unauthorized(request)

        if self.backend:
            user = self.backend.authenticate(username=bits[0], password=bits[1])
        else:
            user = authenticate(username=bits[0], password=bits[1])

        if user is None:
            return self._unauthorized(request)

        if not self.check_active(user):
            return False

        request.user = user
        return True

    def _unauthorized(self, request):
        if request.META.get('HTTP_X_REQUESTED_FROM') == 'WebUI':
            return HttpUnauthorized()
        else:
            return super(FreeBasicAuthentication, self)._unauthorized()


APIAuthentication = MultiAuthentication(
    DjangoAuthentication(),
    FreeBasicAuthentication(),
)


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


class DjangoDeclarativeMetaclass(DeclarativeMetaclass):

    def __new__(cls, name, bases, attrs):
        defaultMeta = type('Meta', (), dict(
            include_resource_uri=False,
            always_return_data=True,
            paginator_class=DojoPaginator,
            authentication=APIAuthentication,
            authorization=APIAuthorization(),
        ))
        meta = attrs.get('Meta', None)
        if not meta:
            meta = type('Meta')
        attrs['Meta'] = type('Meta', (meta, defaultMeta), {})
        return DeclarativeMetaclass.__new__(cls, name, bases, attrs)


class ResourceMixin(object):

    def method_check(self, request, allowed=None):
        """
        Make sure only OAuth2 is allowed to POST/PUT/DELETE
        """
        if self.is_webclient(request):
            try:
                self.is_authenticated(request)
                allowed = ['get']
            except:
                pass
        return super(ResourceMixin, self).method_check(
            request,
            allowed=allowed
        )

    def is_webclient(self, request):
        # Do not treat passwordless API auth as webclient
        if not bsdUsers.has_root_password():
            return None

        if (
            request.META.get('HTTP_X_REQUESTED_FROM') == 'WebUI' or
            not request.META.get('HTTP_AUTHORIZATION', '').startswith('Basic')
        ):
            return True

    def get_list(self, request, **kwargs):
        """
        XXXXXX
        This method was retrieved from django-tastypie
        It had to be modified that way to set the Content-Range
        response header so ranges could workd well with dojo
        XXXXXX
        """
        base_bundle = self.build_bundle(request=request)
        objects = self.obj_get_list(
            bundle=base_bundle, **self.remove_api_resource_names(kwargs)
        )
        sorted_objects = self.apply_sorting(objects, options=request.GET)

        paginator = self._meta.paginator_class(
            request,
            sorted_objects,
            resource_uri=self.get_resource_uri(),
            limit=self._meta.limit
        )
        to_be_serialized = paginator.page()

        bundles = [
            self.build_bundle(obj=obj, request=request)
            for obj in to_be_serialized['objects']
        ]
        to_be_serialized['objects'] = [
            self.full_dehydrate(bundle) for bundle in bundles
        ]
        length = len(to_be_serialized['objects'])
        to_be_serialized = self.alter_list_data_to_serialize(
            request, to_be_serialized
        )
        response = self.create_response(request, to_be_serialized)
        response['Content-Range'] = 'items %d-%d/%d' % (
            paginator.offset, paginator.offset + length - 1, len(sorted_objects)
        )
        return response

    def _handle_500(self, request, exception, *args, **kwargs):
        log_traceback(log=log)
        if isinstance(exception, (NotFound, ObjectDoesNotExist, Http404, UnsupportedFormat)):
            return super(ResourceMixin, self)._handle_500(request, exception, *args, **kwargs)
        else:
            the_trace = '\n'.join(traceback.format_exception(*(sys.exc_info())))
            data = {
                "error_message": sanitize(six.text_type(exception)),
                "traceback": the_trace,
            }
            return self.error_response(request, data, response_class=http.HttpApplicationError)

    def dispatch(self, request_type, request, *args, **kwargs):
        try:
            return super(ResourceMixin, self).dispatch(
                request_type, request, *args, **kwargs
            )
        except (MiddlewareError, ServiceFailed, UnsupportedFormat) as e:
            log_traceback(log=log)
            raise ImmediateHttpResponse(
                response=self.error_response(request, {
                    'error_message': str(e),
                })
            )
        except Exception as e:
            log_traceback(log=log)
            raise

    def dehydrate(self, bundle):
        bundle = super(ResourceMixin, self).dehydrate(bundle)
        name = str(type(self).__name__)
        appPool.hook_resource_bundle(name, self, bundle)
        return bundle


class DojoModelResource(ResourceMixin, ModelResource):

    @classmethod
    def api_field_from_django_field(cls, f, default=fields.CharField):
        if isinstance(f, MultiSelectField):
            return fields.ListField
        if isinstance(f, DictField):
            return fields.DictField
        else:
            return super(DojoModelResource, cls).api_field_from_django_field(f, default=default)

    def apply_sorting(self, obj_list, options=None):
        """
        Dojo aware filtering
        """
        fields = []
        for key in list(options.keys()):
            if RE_SORT.match(key):
                fields = RE_SORT.search(key).group(1)
                fields = [f.strip() for f in fields.split(',')]
                break
        if fields:
            for f in fields:
                reverse = False
                if f.startswith('-'):
                    reverse = True
                    f = f[1:]
                sorting_map = getattr(self, 'SORTING_MAP', {})
                key = sorting_map.get(f, lambda x: getattr(x, f))
                obj_list = sorted(obj_list, key=key, reverse=reverse)

        return obj_list

    def is_form_valid(self, bundle, form):
        valid = form.is_valid()
        if not valid:
            bundle.errors = form._errors
        return valid

    def get_list(self, request, **kwargs):
        # Treat models that represent a single object as such
        if self._meta.queryset.model._admin.deletable is False:
            return self.get_detail(request, **kwargs)
        return super(DojoModelResource, self).get_list(request, **kwargs)

    def put_list(self, request, **kwargs):
        # Treat models that represent a single object as such
        if self._meta.queryset.model._admin.deletable is False:
            return self.put_detail(request, **kwargs)
        return super(DojoModelResource, self).put_list(request, **kwargs)

    def put_detail(self, request, **kwargs):
        """
        Copied from tastypie ModelResource so we dont try to create one
        if it doesn't exist.
        """
        deserialized = self.deserialize(request, request.body, format=request.META.get('CONTENT_TYPE', 'application/json'))
        deserialized = self.alter_deserialized_detail_data(request, deserialized)
        bundle = self.build_bundle(data=dict_strip_unicode_keys(deserialized), request=request)

        try:
            updated_bundle = self.obj_update(bundle=bundle, **self.remove_api_resource_names(kwargs))

            if not self._meta.always_return_data:
                return http.HttpNoContent()
            else:
                # Invalidate prefetched_objects_cache for bundled object
                # because we might have changed a prefetched field
                updated_bundle.obj._prefetched_objects_cache = {}
                updated_bundle = self.full_dehydrate(updated_bundle)
                updated_bundle = self.alter_detail_data_to_serialize(request, updated_bundle)
                return self.create_response(request, updated_bundle)
        except (NotFound, MultipleObjectsReturned):
            return self.create_response(request, 'Object not found', response_class=HttpNotFound)

    def save(self, bundle, skip_errors=False):

        # Check if they're authorized.
        if bundle.obj.pk:
            self.authorized_update_detail(
                self.get_object_list(bundle.request), bundle
            )
        else:
            self.authorized_create_detail(
                self.get_object_list(bundle.request), bundle
            )

        # Remove all "private" attributes
        data = dict(bundle.obj.__dict__)
        for key, val in list(data.items()):
            if key.startswith('_'):
                del data[key]
                continue
            # Add the pk of the foreign key in the mix
            if key.endswith('_id'):
                noid = key[:-3]
                field = getattr(bundle.obj.__class__, noid, None)
                if not field:
                    continue
                if field and isinstance(field.field, ForeignKey):
                    data[noid] = val
                    del data[key]
            else:
                try:
                    bundle.obj.__class__._meta.get_field(key)
                except FieldDoesNotExist:
                    del data[key]
        data.update(bundle.data)
        bundle.data = data

        """
        Get rid of None values, it means they were not
        passed to the API and will faill serialization
        """
        querydict = data.copy()
        for key, val in list(querydict.items()):
            if val is None:
                del querydict[key]
        querydict = QueryDict(urllib.parse.urlencode(querydict, doseq=True))

        # Allow one form validation for each method
        method_validation = '%s_validation' % bundle.request.method.lower()
        validation = getattr(self._meta, method_validation, self._meta.validation)

        form = validation.form_class(
            querydict,
            instance=bundle.obj,
            api_validation=True,
        )
        if not self.is_form_valid(bundle, form):
            raise ImmediateHttpResponse(response=self.error_response(
                bundle.request,
                bundle.errors,
                response_class=http.HttpConflict,
            ))

        """
        FIXME
        Saving the objects under a transaction won't work very well
        because some rc.d scripts and rc.conf will not be able to visualize
        the changes until the transaction is committed.
        # with transaction.atomic():
        """
        form.save()
        self.post_form_save_hook(bundle, form)
        bundle.obj = form.instance
        bundle.objects_saved.add(self.create_identifier(bundle.obj))

        # Now pick up the M2M bits.
        m2m_bundle = self.hydrate_m2m(bundle)
        self.save_m2m(m2m_bundle)

        if hasattr(form, 'done') and callable(form.done):
            form.done(request=bundle.request, events=[])

        return bundle

    def post_form_save_hook(self, bundle, form):
        pass

    def alter_list_data_to_serialize(self, request, data):
        return data['objects']

    def dehydrate(self, bundle):
        bundle = super(DojoModelResource, self).dehydrate(bundle)
        if self.is_webclient(bundle.request):
            bundle.data['_edit_url'] = bundle.obj.get_edit_url()
            bundle.data['_delete_url'] = bundle.obj.get_delete_url()
        return bundle


class DojoResource(ResourceMixin, Resource, metaclass=DjangoDeclarativeMetaclass):

    def _apply_sorting(self, options=None):
        """
        Dojo aware filtering
        """
        fields = []
        for key in list(options.keys()):
            if RE_SORT.match(key):
                fields = RE_SORT.search(key).group(1)
                fields = [f.strip() for f in fields.split(',')]
                break
        return fields

    def _get_form_initial(self, form):
        initial = {}
        for k, v in form.base_fields.items():
            initial[k] = v.initial
        return initial

    def alter_list_data_to_serialize(self, request, data):
        return data['objects']
