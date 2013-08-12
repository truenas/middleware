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

from tastypie.authentication import Authentication
from tastypie.paginator import Paginator
from tastypie.resources import ModelResource, Resource

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


class DojoPaginator(Paginator):

    def __init__(self, request, *args, **kwargs):
        super(DojoPaginator, self).__init__(request.GET, *args, **kwargs)
        r = request.META.get("HTTP_RANGE", None)
        if r:
            r = r.split('=', 1)[1].split('-')
            self.offset = int(r[0])
            if r[1]:
                self.limit = int(r[1]) + 1 - self.offset


class DojoModelResource(ModelResource):

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


class DojoResource(Resource):

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
