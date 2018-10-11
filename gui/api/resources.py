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
import calendar
import errno
import json
import logging
import os
import re
import subprocess
import urllib.parse
import sysctl

from collections import OrderedDict
from croniter import croniter
from django.conf.urls import url
from django.core.exceptions import MultipleObjectsReturned, ObjectDoesNotExist
from django.core.urlresolvers import reverse
from django.db.models import Q
from django.http import HttpResponse, QueryDict
from django.utils.translation import ugettext as _

from dojango.forms.models import inlineformset_factory
from freenasOS import Configuration, Update, Train
from freenasUI import choices
from freenasUI.account.forms import (
    bsdUsersForm,
    bsdUserPasswordForm,
)
from freenasUI.account.forms import bsdUserToGroupForm
from freenasUI.account.models import bsdUsers, bsdGroups, bsdGroupMembership
from freenasUI.api.utils import DojoResource
from freenasUI.common import humanize_size, humanize_number_si
from freenasUI.common.freenascache import (
    FLAGS_CACHE_READ_USER,
    FLAGS_CACHE_WRITE_USER,
    FLAGS_CACHE_READ_GROUP,
    FLAGS_CACHE_WRITE_GROUP
)
from freenasUI.common.freenasldap import (
    FLAGS_DBINIT,
    FreeNAS_ActiveDirectory_Users,
    FreeNAS_LDAP_Users,
    FreeNAS_ActiveDirectory_Groups,
    FreeNAS_LDAP_Groups
)
from freenasUI.common.freenasnis import FreeNAS_NIS_Users, FreeNAS_NIS_Groups
from freenasUI.common.freenasusers import FreeNAS_Groups, FreeNAS_Users
from freenasUI.common.system import (
    get_sw_login_version,
    get_sw_name,
    get_sw_version,
)
from freenasUI.common.warden import Warden
from freenasUI.freeadmin.options import FreeBaseInlineFormSet
from freenasUI.jails.forms import (
    JailsEditForm, JailTemplateCreateForm, JailTemplateEditForm
)
from freenasUI.jails.models import JailTemplate
from freenasUI.middleware import zfs
from freenasUI.middleware.client import client
from freenasUI.middleware.exceptions import MiddlewareError
from freenasUI.middleware.notifier import notifier
from freenasUI.middleware.util import run_alerts
from freenasUI.network.forms import AliasForm
from freenasUI.network.models import Alias, Interfaces
from freenasUI.plugins.models import Plugins
from freenasUI.plugins.utils import get_base_url, get_plugin_status
from freenasUI.services.forms import iSCSITargetPortalIPForm
from freenasUI.services.models import (
    iSCSITargetGlobalConfiguration,
    iSCSITargetPortal, iSCSITargetPortalIP, FibreChannelToTarget
)
from freenasUI.sharing.models import NFS_Share, NFS_Share_Path
from freenasUI.sharing.forms import NFS_SharePathForm
from freenasUI.storage.forms import (
    CloneSnapshotForm,
    MountPointAccessForm,
    ReKeyForm,
    CreatePassphraseForm,
    ChangePassphraseForm,
    ManualSnapshotForm,
    UnlockPassphraseForm,
    VolumeAutoImportForm,
    VolumeManagerForm,
    ZFSDiskReplacementForm,
    ZVol_CreateForm,
    ZVol_EditForm,
    ZFSDatasetCreateForm,
    ZFSDatasetEditForm
)
from freenasUI.storage.models import Disk, VMWarePlugin
from freenasUI.system.forms import (
    BootEnvAddForm,
    BootEnvRenameForm,
    CertificateAuthorityCreateInternalForm,
    CertificateAuthorityCreateIntermediateForm,
    CertificateAuthorityImportForm,
    CertificateCreateCSRForm,
    CertificateCreateInternalForm,
    CertificateImportForm,
    CertificateCSRImportForm,
    ManualUpdateTemporaryLocationForm,
    ManualUpdateUploadForm,
    ManualUpdateWizard,
)
from freenasUI.system.models import Update as mUpdate
from freenasUI.system.utils import BootEnv, debug_generate, factory_restore
from freenasUI.system.views import restart_httpd, restart_httpd_all
from middlewared.client import ClientException
from tastypie import fields, http
from tastypie.http import (
    HttpAccepted, HttpCreated, HttpMethodNotAllowed, HttpMultipleChoices,
    HttpNotFound, HttpNoContent,
)
from tastypie.exceptions import ImmediateHttpResponse, NotFound
from tastypie.utils import trailing_slash
from tastypie.validation import FormValidation

log = logging.getLogger('api.resources')


def _common_human_fields(bundle):
    for index, human in enumerate((
        'human_minute',
        'human_hour',
        'human_daymonth',
        'human_month',
        'human_dayweek',
    )):

        field = next((v for v in dir(bundle.obj) if human[len('human_'):] in v.split('_')), None)
        if not field:
            continue

        expression = ''
        for i in range(0, 5):
            expression += ('* ' if i != index else f'{getattr(bundle.obj, field)} ')
        field_value = croniter(expression).expanded[index]

        bundle.data[field] = field_value

        def _wording_helper(w, v_choices):
            if isinstance(v_choices, int):
                v_choices = {v: v for v in range(0, v_choices)}
            if field_value[0] == '*' or len(field_value) >= len(v_choices):
                return f'Every {w}'
            else:
                return ', '.join([
                    str(v_choices[v]) for v in field_value
                ])

        if index == 0:
            bundle.data[human] = _wording_helper('minute', 60)
        elif index == 1:
            bundle.data[human] = _wording_helper('hour', 24)
        elif index == 2:
            bundle.data[human] = _wording_helper('day', 30)
        elif index == 3:
            bundle.data[human] = _wording_helper(
                'month', {int(k): v for k, v in dict(choices.MONTHS_CHOICES).items()}
            )
        else:
            # TODO:
            # 1. Carve out the days input so that way one can say:
            #    Mon-Fri + Saturday -> Weekdays + Saturday
            if field_value == list(map(str, range(1, 6))):
                bundle.data[human] = _('Weekdays')
            elif field_value == list(map(str, range(6, 8))):
                bundle.data[human] = _('Weekends')
            else:
                field_value = [v or 7 for v in field_value]
                bundle.data[human] = _wording_helper(
                    'day of week', {int(k): v for k, v in dict(choices.WEEKDAYS_CHOICES).items()}
                )


class NestedMixin(object):

    def _get_parent(self, request, kwargs):
        self.is_authenticated(request)
        try:
            bundle = self.build_bundle(
                data={'pk': kwargs['pk']}, request=request
            )
            obj = self.cached_obj_get(
                bundle=bundle, **self.remove_api_resource_names(kwargs)
            )
        except ObjectDoesNotExist:
            raise ImmediateHttpResponse(response=HttpNotFound())
        except MultipleObjectsReturned:
            raise ImmediateHttpResponse(response=HttpMultipleChoices(
                "More than one resource is found at this URI."
            ))
        return bundle, obj


class AlertResource(DojoResource):

    class Meta:
        allowed_methods = ['get']
        resource_name = 'system/alert'

    def prepend_urls(self):
        return [
            url(
                r"^(?P<resource_name>%s)/dismiss%s$" % (
                    self._meta.resource_name, trailing_slash()
                ),
                self.wrap_view('dismiss'),
                name="api_alert_dismiss"
            ),
        ]

    def get_list(self, request, **kwargs):
        with client as c:
            results = c.call("alert.list")

        for alert in results:
            alert["timestamp"] = calendar.timegm(alert["datetime"].timetuple())

        if (
            'timestamp' in request.GET or
            'timestamp__gte' in request.GET or
            'timestamp__lte' in request.GET
        ):
            for res in list(results):
                eq = request.GET.get('timestamp')
                if eq and int(eq) != res["timestamp"]:
                    results.remove(res)
                    continue

                gte = request.GET.get('timestamp__gte')
                if gte and int(gte) > res["timestamp"]:
                    results.remove(res)
                    continue

                lte = request.GET.get('timestamp__lte')
                if lte and int(lte) < res["timestamp"]:
                    results.remove(res)
                    continue

        paginator = self._meta.paginator_class(
            request,
            results,
            resource_uri=self.get_resource_uri(),
            limit=self._meta.limit,
            max_limit=self._meta.max_limit,
            collection_name=self._meta.collection_name,
        )
        to_be_serialized = paginator.page()
        to_be_serialized["objects"] = [
            {
                "id": alert["id"],
                "level": alert["level"],
                "message": alert["formatted"],
                "dismissed": alert["dismissed"],
                "timestamp": alert["timestamp"],
            }
            for alert in to_be_serialized["objects"]
        ]
        response = self.create_response(request, to_be_serialized)
        response['Content-Range'] = 'items %d-%d/%d' % (
            paginator.offset,
            paginator.offset + len(to_be_serialized) - 1,
            len(results)
        )
        return response

    def dismiss(self, request, **kwargs):
        if request.method != 'PUT':
            response = HttpMethodNotAllowed('PUT')
            response['Allow'] = 'PUT'
            raise ImmediateHttpResponse(response=response)

        self.is_authenticated(request)

        dismiss = self.deserialize(
            request,
            request.body,
            format=request.META.get('CONTENT_TYPE', 'application/json'),
        )

        with client as c:
            if dismiss["dismiss"]:
                c.call("alert.dismiss", dismiss["id"])
            else:
                c.call("alert.restore", dismiss["id"])

        return HttpResponse(status=202)

    def dehydrate(self, bundle):
        return bundle


class SettingsResourceMixin(object):

    def prepend_urls(self):
        return [
            url(
                r"^(?P<resource_name>%s)/restart-httpd%s$" % (
                    self._meta.resource_name, trailing_slash()
                ),
                self.wrap_view('restart_httpd'),
            ),
            url(
                r"^(?P<resource_name>%s)/restart-httpd-all%s$" % (
                    self._meta.resource_name, trailing_slash()
                ),
                self.wrap_view('restart_httpd_all'),
            ),
        ]

    def restart_httpd(self, request, **kwargs):
        self.method_check(request, allowed=['post'])
        self.is_authenticated(request)

        return restart_httpd(request)

    def restart_httpd_all(self, request, **kwargs):
        self.method_check(request, allowed=['post'])
        self.is_authenticated(request)

        return restart_httpd_all(request)

    def dehydrate(self, bundle):
        bundle = super(SettingsResourceMixin, self).dehydrate(bundle)
        if bundle.obj.stg_guicertificate:
            bundle.data['stg_guicertificate'] = bundle.obj.stg_guicertificate.id
        else:
            bundle.data['stg_guicertificate'] = None
        return bundle

    def hydrate(self, bundle):
        bundle = super(SettingsResourceMixin, self).hydrate(bundle)
        for key in ['stg_guiaddress', 'stg_guiv6address']:
            if isinstance(bundle.data.get(key), str):
                bundle.data[key] = bundle.data[key].split()
        return bundle


class DiskResourceMixin(object):

    class Meta:
        queryset = Disk.objects.filter(
            disk_expiretime=None,
        ).exclude(
            Q(disk_name__startswith='multipath') | Q(disk_name='')
        )
        allowed_methods = ['get', 'put']

    def obj_update(self, bundle, skip_errors=False, **kwargs):
        try:
            return super(DiskResourceMixin, self).obj_update(bundle, skip_errors=skip_errors, **kwargs)
        except Exception:
            raise ImmediateHttpResponse(response=HttpNotFound())

    def dispatch_list(self, request, **kwargs):
        try:
            with client as c:
                self._disks_unused = [i['name'] for i in c.call('disk.get_unused')]
        except Exception:
            log.debug('Failed to get unused disks', exc_info=True)
        return super(DiskResourceMixin, self).dispatch_list(request, **kwargs)

    def dehydrate(self, bundle):
        bundle = super(DiskResourceMixin, self).dehydrate(bundle)
        if self.is_webclient(bundle.request):
            bundle.data['id'] = bundle.obj.pk
            bundle.data['_edit_url'] += '?deletable=false'
            unused = getattr(self, '_disks_unused', None)
            if unused is not None and bundle.obj.disk_name in unused:
                bundle.data['_wipe_url'] = reverse('storage_disk_wipe', kwargs={
                    'devname': bundle.obj.disk_name,
                })
            bundle.data['_editbulk_url'] = reverse('storage_disk_editbulk')
            if bundle.data['disk_size']:
                bundle.data['disk_size'] = humanize_number_si(
                    bundle.data['disk_size']
                )
        if 'disk_number' in bundle.data:
            del bundle.data['disk_number']
        if 'disk_subsystem' in bundle.data:
            del bundle.data['disk_subsystem']
        if 'disk_passwd' in bundle.data:
            if bundle.data['disk_passwd'] != '':
                bundle.data['disk_passwd'] = '********'
        return bundle


class PermissionResource(DojoResource):

    class Meta:
        allowed_methods = ['put']
        resource_name = 'storage/permission'

    def put_list(self, request, **kwargs):
        deserialized = self.deserialize(
            request,
            request.body,
            format=request.META.get('CONTENT_TYPE', 'application/json'),
        )
        deserialized.update({
            'mp_group_en': deserialized.get('mp_group_en', True),
            'mp_mode_en': deserialized.get('mp_mode_en', True),
            'mp_user_en': deserialized.get('mp_user_en', True),
        })
        form = MountPointAccessForm(data=deserialized)
        if form.is_valid():
            if form.commit(deserialized.get('mp_path')):
                return HttpResponse(
                    'Mount Point permissions successfully updated.',
                    status=201,
                )
        raise ImmediateHttpResponse(
            response=self.error_response(request, form.errors)
        )


class Uid(object):
    def __init__(self, start):
        self._start = start
        self._counter = start

    def __next__(self):
        number = self._counter
        self._counter += 1
        return number


class DatasetResource(DojoResource):

    name = fields.CharField(attribute='name')
    pool = fields.CharField(attribute='pool')
    used = fields.IntegerField(attribute='used')
    avail = fields.IntegerField(attribute='avail')
    refer = fields.IntegerField(attribute='refer')
    mountpoint = fields.CharField(attribute='mountpoint')
    quota = fields.IntegerField(attribute='quota')
    refquota = fields.IntegerField(attribute='refquota')
    reservation = fields.IntegerField(attribute='reservation')
    refreservation = fields.IntegerField(attribute='refreservation')
    recordsize = fields.IntegerField(attribute='recordsize')
    comments = fields.CharField(attribute='description', null=True)
    sync = fields.CharField(attribute='sync')
    compression = fields.CharField(attribute='compression')
    dedup = fields.CharField(attribute='dedup')
    atime = fields.CharField(attribute='atime')
    readonly = fields.CharField(attribute='readonly')
    exec = fields.CharField(attribute='exec')
    inherit_props = fields.ListField(attribute='inherit')

    class Meta:
        allowed_methods = ['get', 'post', 'put', 'delete']
        object_class = zfs.ZFSDataset
        resource_name = 'storage/dataset'

    def post_list(self, request, **kwargs):

        if 'parent' not in kwargs:
            raise ImmediateHttpResponse(
                response=self.error_response(request, 'Creating a top level dataset is not supported.')
            )
        return self.__create_dataset(kwargs.get('parent').vol_name, request, **kwargs)

    def post_detail(self, request, **kwargs):
        return self.__create_dataset(kwargs['pk'], request, **kwargs)

    def __create_dataset(self, fs, request, **kwargs):

        self.is_authenticated(request)
        deserialized = self._meta.serializer.deserialize(
            request.body,
            format=request.META.get('CONTENT_TYPE') or 'application/json'
        )

        name = deserialized.get('name')

        for k in list(deserialized.keys()):
            deserialized['dataset_%s' % k] = deserialized.pop(k)

        data = self._get_form_initial(ZFSDatasetCreateForm)
        data.update(deserialized)
        form = ZFSDatasetCreateForm(data=data, fs=fs)
        if not form.is_valid() or not form.save():
            for k in list(form.errors.keys()):
                if k == '__all__':
                    continue
                if k.startswith('dataset_'):
                    form.errors[k[len('dataset_'):]] = form.errors.pop(k)
            raise ImmediateHttpResponse(
                response=self.error_response(request, form.errors)
            )

        if 'parent' in kwargs:
            kwargs['pk'] = name
        else:
            kwargs['pk'] = f'{fs}/{name}'
        response = self.get_detail(request, **kwargs)
        response.status_code = 201
        return response

    def obj_update(self, bundle, **kwargs):
        bundle = self.full_hydrate(bundle)

        if 'parent' in kwargs:
            name = f'{kwargs["parent"].vol_name}/{kwargs["pk"]}'
        else:
            name = kwargs['pk']

        data = self.deserialize(
            bundle.request,
            bundle.request.body,
            format=bundle.request.META.get('CONTENT_TYPE', 'application/json'),
        )

        for k in list(data.keys()):
            data[f'dataset_{k}'] = data.pop(k)

        initial = ZFSDatasetEditForm.get_initial_data(name)
        initial.update(data)

        form = ZFSDatasetEditForm(fs=name, data=initial)
        if not form.is_valid() or not form.save():
            for k in list(form.errors.keys()):
                if k == '__all__':
                    continue
                if k.startswith('dataset_'):
                    form.errors[k[len('dataset_'):]] = form.errors.pop(k)
            raise ImmediateHttpResponse(
                response=self.error_response(bundle.request, form.errors)
            )
        bundle.obj = self.obj_get(bundle, **kwargs)
        return bundle

    def obj_get_list(self, request=None, **kwargs):
        dsargs = {'recursive': True}
        if 'parent' in kwargs:
            dsargs['path'] = kwargs.get('parent').vol_name
        else:
            dsargs['include_root'] = True
        zfslist = zfs.list_datasets(**dsargs)
        return zfslist

    def obj_get(self, bundle, **kwargs):
        dsargs = {}
        if 'parent' in kwargs:
            dsargs['path'] = f'{kwargs["parent"].vol_name}/{kwargs["pk"]}'
        else:
            dsargs['path'] = kwargs['pk']
            dsargs['include_root'] = True
        zfslist = zfs.list_datasets(**dsargs)
        try:
            return zfslist[dsargs['path']]
        except KeyError:
            raise NotFound("Dataset not found.")

    def obj_delete(self, bundle, **kwargs):
        if 'parent' in kwargs:
            path = f'{kwargs["parent"].vol_name}/{kwargs["pk"]}'
        else:
            path = kwargs['pk']
        retval = notifier().destroy_zfs_dataset(path=path, recursive=True)
        if retval:
            raise ImmediateHttpResponse(
                response=self.error_response(bundle.request, retval)
            )
        return HttpResponse(status=204)

    def detail_uri_kwargs(self, bundle_or_obj):
        return {}


class ZVolResource(DojoResource):

    name = fields.CharField(attribute='name')
    volsize = fields.IntegerField(attribute='volsize')
    refer = fields.IntegerField(attribute='refer')
    used = fields.IntegerField(attribute='used')
    avail = fields.IntegerField(attribute='avail')
    sync = fields.CharField(attribute='sync')
    compression = fields.CharField(attribute='compression')
    dedup = fields.CharField(attribute='dedup')
    comments = fields.CharField(attribute='description')

    class Meta:
        allowed_methods = ['get', 'post', 'delete', 'put']
        object_class = zfs.ZFSVol
        resource_name = 'storage/zvol'

    def post_list(self, request, **kwargs):
        self.is_authenticated(request)
        deserialized = self._meta.serializer.deserialize(
            request.body,
            format=request.META.get('CONTENT_TYPE') or 'application/json'
        )

        # We need to get the parent dataset (if there is any)
        # without the pool name
        name = deserialized.get('name')
        parent = kwargs['parent'].vol_name
        if name and '/' in name:
            parent_ds, deserialized['name'] = name.rsplit('/', 1)
            parent = f"{parent}/{parent_ds}"

        # Add zvol_ prefix to match form field names
        for k in list(deserialized.keys()):
            deserialized[f'zvol_{k}'] = deserialized.pop(k)
        data = self._get_form_initial(ZVol_CreateForm)
        data.update(deserialized)
        form = ZVol_CreateForm(data=data, parentds=parent)
        if not form.is_valid() or not form.save():
            for k in list(form.errors.keys()):
                if k == '__all__':
                    continue
                if k.startswith('zvol_'):
                    form.errors[k[5:]] = form.errors.pop(k)
            raise ImmediateHttpResponse(
                response=self.error_response(request, form.errors)
            )
        # Re-query for a proper response
        response = self.get_detail(request, pk=f"{name}", **kwargs)
        response.status_code = 202
        return response

    def put_detail(self, request, **kwargs):
        self.is_authenticated(request)
        name = "{}/{}".format(kwargs.get('parent').vol_name, kwargs.get('pk'))

        if not zfs.zfs_list(path=name):
            return HttpNotFound()

        deserialized = self._meta.serializer.deserialize(
            request.body,
            format=request.META.get('CONTENT_TYPE') or 'application/json'
        )
        # Add zvol_ prefix to match form field names
        for k in list(deserialized.keys()):
            deserialized[f'zvol_{k}'] = deserialized.pop(k)

        data = self._get_form_initial(ZVol_EditForm(name=name), instance=True)
        data.update(deserialized)

        form = ZVol_EditForm(name=name, data=data)
        if not form.is_valid() or not form.save():
            for k in list(form.errors.keys()):
                if k == '__all__':
                    continue
                if k.startswith('zvol_'):
                    form.errors[k[5:]] = form.errors.pop(k)
            raise ImmediateHttpResponse(
                response=self.error_response(request, form.errors)
            )
        response = self.get_detail(request, **kwargs)
        response.status_code = 201
        return response

    def obj_get_list(self, request=None, **kwargs):
        dsargs = {
            'recursive': True,
            'types': ["volume"],
        }
        if 'parent' in kwargs:
            dsargs['path'] = kwargs.get('parent').vol_name
        zfslist = zfs.zfs_list(**dsargs)
        return zfslist

    def obj_get(self, bundle, **kwargs):
        zfslist = zfs.zfs_list(path="%s/%s" % (
            kwargs.get('parent').vol_name,
            kwargs.get('pk'),
        ), types=["volume"])
        try:
            return zfslist['%s/%s' % (
                kwargs.get('parent').vol_name,
                kwargs.get('pk')
            )]
        except KeyError:
            raise NotFound("Dataset not found.")

    def obj_delete(self, bundle, **kwargs):
        retval = notifier().destroy_zfs_vol("%s/%s" % (
            kwargs.get('parent').vol_name,
            kwargs.get('pk'),
        ))
        if retval:
            raise ImmediateHttpResponse(
                response=self.error_response(bundle.request, retval)
            )
        return HttpResponse(status=204)

    def detail_uri_kwargs(self, bundle_or_obj):
        return {}


class VolumeResourceMixin(NestedMixin):

    class Meta:
        validation = FormValidation(form_class=VolumeManagerForm)
        filtering = {
            'vol_name': ['exact'],
        }

    def obj_get(self, bundle, **kwargs):
        if 'pk' in kwargs and not kwargs['pk'].isdigit():
            kwargs['vol_name'] = kwargs.pop('pk')
        return super(VolumeResourceMixin, self).obj_get(bundle, **kwargs)

    def prepend_urls(self):
        return [
            url(
                r"^(?P<resource_name>%s)/(?P<pk>\w[\w/-]*)/datasets%s$" % (
                    self._meta.resource_name, trailing_slash()
                ),
                self.wrap_view('datasets_list'),
                name="api_volume_datasets"
            ),
            url(
                r"^(?P<resource_name>%s)/(?P<pk>\w[\w/-]*)/datasets/"
                "(?P<pk2>\w[\w/-]*)%s$" % (
                    self._meta.resource_name, trailing_slash()
                ),
                self.wrap_view('datasets_detail'),
                name="api_volume_datasets_detail"
            ),
            url(
                r"^(?P<resource_name>%s)/(?P<pk>\w[\w/-]*)/zvols%s$" % (
                    self._meta.resource_name, trailing_slash()
                ),
                self.wrap_view('zvols_list'),
                name="api_volume_zvols"
            ),
            url(
                r"^(?P<resource_name>%s)/(?P<pk>\w[\w/-]*)/zvols/"
                "(?P<pk2>\w[\w/\-\._]*)%s$" % (
                    self._meta.resource_name, trailing_slash()
                ),
                self.wrap_view('zvols_detail'),
                name="api_volume_zvols_detail"
            ),
            url(
                r"^(?P<resource_name>%s)/(?P<pk>\w[\w/-]*)/replace%s$" % (
                    self._meta.resource_name, trailing_slash()
                ),
                self.wrap_view('replace_disk')
            ),
            url(
                r"^(?P<resource_name>%s)/(?P<pk>\w[\w/-]*)/offline%s$" % (
                    self._meta.resource_name, trailing_slash()
                ),
                self.wrap_view('offline_disk')
            ),
            url(
                r"^(?P<resource_name>%s)/(?P<pk>\w[\w/-]*)/online%s$" % (
                    self._meta.resource_name, trailing_slash()
                ),
                self.wrap_view('online_disk')
            ),
            url(
                r"^(?P<resource_name>%s)/(?P<pk>\w[\w/-]*)/detach%s$" % (
                    self._meta.resource_name, trailing_slash()
                ),
                self.wrap_view('detach_disk')
            ),
            url(
                r"^(?P<resource_name>%s)/(?P<pk>\w[\w/-]*)/remove%s$" % (
                    self._meta.resource_name, trailing_slash()
                ),
                self.wrap_view('remove_disk')
            ),
            url(
                r"^(?P<resource_name>%s)/(?P<pk>\w[\w/-]*)/scrub%s$" % (
                    self._meta.resource_name, trailing_slash()
                ),
                self.wrap_view('scrub')
            ),
            url(
                r"^(?P<resource_name>%s)/(?P<pk>\w[\w/-]*)/status%s$" % (
                    self._meta.resource_name, trailing_slash()
                ),
                self.wrap_view('status')
            ),
            url(
                r"^(?P<resource_name>%s)/(?P<pk>\w[\w/-]*)/unlock%s$" % (
                    self._meta.resource_name, trailing_slash()
                ),
                self.wrap_view('unlock')
            ),
            url(
                r"^(?P<resource_name>%s)/(?P<pk>\w[\w/-]*)/lock%s$" % (
                    self._meta.resource_name, trailing_slash()
                ),
                self.wrap_view('lock')
            ),
            url(
                r"^(?P<resource_name>%s)/(?P<pk>\w[\w/-]*)/upgrade%s$" % (
                    self._meta.resource_name, trailing_slash()
                ),
                self.wrap_view('upgrade')
            ),
            url(
                r"^(?P<resource_name>%s)/(?P<pk>\w[\w/-]*)/recoverykey%s$" % (
                    self._meta.resource_name, trailing_slash()
                ),
                self.wrap_view('recoverykey')
            ),
            url(
                r"^(?P<resource_name>%s)/(?P<pk>\w[\w/-]*)/rekey%s$" % (
                    self._meta.resource_name, trailing_slash()
                ),
                self.wrap_view('rekey')
            ),
            url(
                r"^(?P<resource_name>%s)/(?P<pk>\w[\w/-]*)/keypassphrase%s$" % (
                    self._meta.resource_name, trailing_slash()
                ),
                self.wrap_view('keypassphrase')
            ),
        ]

    def replace_disk(self, request, **kwargs):
        self.method_check(request, allowed=['post'])

        bundle, obj = self._get_parent(request, kwargs)

        deserialized = self.deserialize(
            request,
            request.body,
            format=request.META.get('CONTENT_TYPE', 'application/json'),
        )
        deserialized['force'] = deserialized.get('force', False)
        if deserialized.get('pass') and not deserialized.get('pass2'):
            deserialized['pass2'] = deserialized.get('pass')
        form = ZFSDiskReplacementForm(
            volume=obj,
            label=deserialized.get('label'),
            data=deserialized,
        )
        if not form.is_valid():
            raise ImmediateHttpResponse(
                response=self.error_response(request, form.errors)
            )
        else:
            form.done()
        return HttpResponse('Disk replacement started.', status=202)

    def offline_disk(self, request, **kwargs):
        self.method_check(request, allowed=['post'])

        bundle, obj = self._get_parent(request, kwargs)

        deserialized = self.deserialize(
            request,
            request.body,
            format=request.META.get('CONTENT_TYPE', 'application/json'),
        )
        notifier().zfs_offline_disk(obj, deserialized.get('label'))
        return HttpResponse('Disk offline\'d.', status=202)

    def online_disk(self, request, **kwargs):
        self.method_check(request, allowed=['post'])

        bundle, obj = self._get_parent(request, kwargs)

        deserialized = self.deserialize(
            request,
            request.body,
            format=request.META.get('CONTENT_TYPE', 'application/json'),
        )
        notifier().zfs_online_disk(obj, deserialized.get('label'))
        return HttpResponse('Disk online\'d.', status=202)

    def detach_disk(self, request, **kwargs):
        self.method_check(request, allowed=['post'])

        bundle, obj = self._get_parent(request, kwargs)

        deserialized = self.deserialize(
            request,
            request.body,
            format=request.META.get('CONTENT_TYPE', 'application/json'),
        )
        notifier().zfs_detach_disk(obj, deserialized.get('label'))
        return HttpResponse('Disk detached.', status=202)

    def remove_disk(self, request, **kwargs):
        self.method_check(request, allowed=['post'])

        bundle, obj = self._get_parent(request, kwargs)

        deserialized = self.deserialize(
            request,
            request.body,
            format=request.META.get('CONTENT_TYPE', 'application/json'),
        )
        notifier().zfs_remove_disk(obj, deserialized.get('label'))
        return HttpResponse('Disk removed.', status=202)

    def scrub(self, request, **kwargs):
        self.method_check(request, allowed=['post', 'delete'])

        bundle, obj = self._get_parent(request, kwargs)

        with client as c:
            if request.method == 'POST':
                c.call('pool.scrub', obj.id, 'START', job=True)
                return HttpResponse('Volume scrub started.', status=202)
            elif request.method == 'DELETE':
                c.call('pool.scrub', obj.id, 'STOP', job=True)
                return HttpResponse('Volume scrub stopped.', status=202)

    def unlock(self, request, **kwargs):
        self.method_check(request, allowed=['post'])

        bundle, obj = self._get_parent(request, kwargs)

        deserialized = self.deserialize(
            request,
            request.body,
            format=request.META.get('CONTENT_TYPE', 'application/json'),
        )
        form = UnlockPassphraseForm(
            data=deserialized,
        )
        if not form.is_valid():
            raise ImmediateHttpResponse(
                response=self.error_response(request, form.errors)
            )
        else:
            form.done(obj)
        return HttpResponse('Volume has been unlocked.', status=202)

    def lock(self, request, **kwargs):
        self.method_check(request, allowed=['post'])

        bundle, obj = self._get_parent(request, kwargs)

        if obj.vol_encrypt == 0:
            raise ImmediateHttpResponse(
                response=self.error_response(request, _('Volume is not encrypted.'))
            )

        with client as c:
            c.call('pool.lock', obj.id, job=True)

        return HttpResponse('Volume has been locked.', status=202)

    def upgrade(self, request, **kwargs):
        self.method_check(request, allowed=['post'])

        bundle, obj = self._get_parent(request, kwargs)

        with client as c:
            c.call('pool.upgrade', obj.id)

        return HttpResponse('Volume has been upgraded.', status=202)

    def recoverykey(self, request, **kwargs):
        self.method_check(request, allowed=['post', 'delete'])

        bundle, obj = self._get_parent(request, kwargs)

        if request.method == 'POST':
            reckey = notifier().geli_recoverykey_add(obj)
            with open(reckey, 'rb') as f:
                data = f.read()
            data = base64.b64encode(data).decode()
            return HttpResponse(json.dumps({
                'message': 'New recovery key has been added.',
                'content': data,
            }), status=202)
        elif request.method == 'DELETE':
            notifier().geli_delkey(obj)
            return HttpResponse('Recovery key has been removed.', status=204)

    def rekey(self, request, **kwargs):
        self.method_check(request, allowed=['post'])

        bundle, obj = self._get_parent(request, kwargs)

        deserialized = self.deserialize(
            request,
            request.body,
            format=request.META.get('CONTENT_TYPE', 'application/json'),
        )
        form = ReKeyForm(data=deserialized, volume=obj, api_validation=True)
        if not (form.is_valid() and form.done()):
            raise ImmediateHttpResponse(
                response=self.error_response(request, form.errors)
            )
        return HttpResponse('Volume has been rekeyed.', status=202)

    def keypassphrase(self, request, **kwargs):
        self.method_check(request, allowed=['post', 'put'])

        bundle, obj = self._get_parent(request, kwargs)

        deserialized = self.deserialize(
            request,
            request.body,
            format=request.META.get('CONTENT_TYPE', 'application/json'),
        )

        if request.method == 'POST':

            form = CreatePassphraseForm(deserialized)
            if not form.is_valid():
                raise ImmediateHttpResponse(
                    response=self.error_response(request, form.errors)
                )
            else:
                form.done(obj)

        elif request.method == 'PUT':

            if 'passphrase2' not in deserialized:
                deserialized['passphrase2'] = deserialized.get('passphrase')

            form = ChangePassphraseForm(deserialized)
            if not (form.is_valid() and form.done(obj)):
                raise ImmediateHttpResponse(
                    response=self.error_response(request, form.errors)
                )

            if deserialized.get('remove'):
                return HttpResponse('Volume passphrase has been removed', status=201)

        return HttpResponse('Volume passphrase has been set', status=201)

    def status(self, request, **kwargs):
        self.method_check(request, allowed=['get'])

        bundle, obj = self._get_parent(request, kwargs)

        bundle.data['id'] = bundle.obj.id
        bundle.data['name'] = bundle.obj.vol_name

        if not obj.is_decrypted():
            bundle.data['status'] = 'LOCKED'
            return self.create_response(request, [bundle.data])

        pool = notifier().zpool_parse(bundle.obj.vol_name)

        bundle.data['children'] = []
        bundle.data.update({
            'read': pool.data.read,
            'write': pool.data.write,
            'cksum': pool.data.cksum,
        })
        uid = Uid(bundle.obj.id * 100)
        for key in ('data', 'cache', 'spares', 'logs'):
            root = getattr(pool, key, None)
            if not root:
                continue

            current = root
            parent = bundle.data
            tocheck = []
            while True:

                if isinstance(current, zfs.Root):
                    data = {
                        'name': current.name,
                        'type': 'root',
                        'status': current.status,
                        'read': current.read,
                        'write': current.write,
                        'cksum': current.cksum,
                        'children': [],
                    }
                elif isinstance(current, zfs.Vdev):
                    data = {
                        'name': current.name,
                        'type': 'vdev',
                        'status': current.status,
                        'read': current.read,
                        'write': current.write,
                        'cksum': current.cksum,
                        'children': [],
                    }
                    if (
                        current.parent.name == "logs" and
                        not current.name.startswith("stripe")
                    ):
                        data['_remove_url'] = reverse(
                            'storage_zpool_disk_remove',
                            kwargs={
                                'vname': pool.name,
                                'label': current.name,
                            })
                elif isinstance(current, zfs.Dev):
                    data = {
                        'name': current.devname,
                        'label': current.name,
                        'type': 'dev',
                        'status': current.status,
                        'read': current.read,
                        'write': current.write,
                        'cksum': current.cksum,
                    }
                    if self.is_webclient(bundle.request):
                        try:
                            disk = Disk.objects.filter(
                                disk_expiretime=None, disk_name=current.disk
                            )[0]
                            data['_disk_url'] = "%s?deletable=false" % (
                                disk.get_edit_url(),
                            )
                        except IndexError:
                            disk = None
                        if current.status in ('ONLINE', 'FAULTED'):
                            data['_offline_url'] = reverse(
                                'storage_disk_offline',
                                kwargs={
                                    'vname': pool.name,
                                    'label': current.name,
                                })

                        elif (
                            current.status == 'OFFLINE' and
                            bundle.obj.vol_encrypt == 0
                        ):
                            pname = (
                                current.parent.parent.name
                                if current.parent.parent else None
                            )
                            dev = pool.get_dev_by_name(current.name)
                            if (
                                dev and dev.path and os.path.exists(dev.path)
                            ) and pname not in (
                                'cache',
                            ):
                                data['_online_url'] = reverse(
                                    'storage_disk_online',
                                    kwargs={
                                        'vname': pool.name,
                                        'label': current.name,
                                    })

                        if (
                                current.replacing
                        ) and current.status not in (
                            'ONLINE',
                            'OFFLINE'
                        ):
                            data['_detach_url'] = reverse(
                                'storage_disk_detach',
                                kwargs={
                                    'vname': pool.name,
                                    'label': current.name,
                                })

                        """
                        Replacing might go south leaving multiple UNAVAIL
                        disks, for that reason replace button should be
                        enable even for disks already under replacing
                        subtree
                        """
                        if (
                                current.parent.parent.name != 'spares' and (
                                    not current.parent.name.startswith('spare-') or
                                    current.status == 'UNAVAIL'
                                )
                        ):
                            # spares can't be replaced - so no replace url should be available for them
                            data['_replace_url'] = reverse(
                                'storage_zpool_disk_replace',
                                kwargs={
                                    'vname': pool.name,
                                    'label': current.name,
                                })
                        if current.parent.parent.name in (
                            'spares',
                            'cache',
                            'logs',
                        ):
                            if not current.parent.name.startswith(
                                "stripe"
                            ):
                                data['_detach_url'] = reverse(
                                    'storage_disk_detach',
                                    kwargs={
                                        'vname': pool.name,
                                        'label': current.name,
                                    })
                            else:
                                if current.status != 'INUSE':
                                    data['_remove_url'] = reverse(
                                        'storage_zpool_disk_remove',
                                        kwargs={
                                            'vname': pool.name,
                                            'label': current.name,
                                        })

                else:
                    raise ValueError("Invalid node")

                if key == 'data' and isinstance(current, zfs.Root):
                    parent.update(data)
                else:
                    data['id'] = next(uid)
                    parent['children'].append(data)

                for child in current:
                    tocheck.append((data, child))

                if tocheck:
                    parent, current = tocheck.pop()
                else:
                    break

        bundle = self.alter_detail_data_to_serialize(request, bundle)
        response = self.create_response(request, [bundle.data])
        response['Content-Range'] = 'items 0-0/1'
        return response

    def datasets_list(self, request, **kwargs):
        bundle, obj = self._get_parent(request, kwargs)

        child_resource = DatasetResource()
        return child_resource.dispatch_list(request, parent=obj)

    def datasets_detail(self, request, **kwargs):
        pk = kwargs.pop('pk2')
        bundle, obj = self._get_parent(request, kwargs)

        child_resource = DatasetResource()
        return child_resource.dispatch_detail(request, pk=pk, parent=obj)

    def zvols_list(self, request, **kwargs):
        bundle, obj = self._get_parent(request, kwargs)

        child_resource = ZVolResource()
        return child_resource.dispatch_list(request, parent=obj)

    def zvols_detail(self, request, **kwargs):
        pk = kwargs.pop('pk2')
        bundle, obj = self._get_parent(request, kwargs)

        child_resource = ZVolResource()
        return child_resource.dispatch_detail(request, pk=pk, parent=obj)

    def _get_children(self, bundle, vol, children, uid):
        rv = []
        attr_fields = ('avail', 'used', 'used_pct')
        for path, child in list(children.items()):
            if child.name.rsplit('/', 1)[-1].startswith('.'):
                continue

            data = {
                'id': next(uid),
                'name': child.name.rsplit('/', 1)[-1],
                'type': 'dataset' if child.category == 'filesystem' else 'zvol',
                'status': '-',
                'path': child.path,
            }
            if child.category == 'filesystem':
                data['mountpoint'] = child.mountpoint
            for attr in attr_fields:
                data[attr] = getattr(child, attr)

            if self.is_webclient(bundle.request):
                data['_promote_dataset_url'] = reverse(
                    'storage_promote_zfs',
                    kwargs={
                        'name': child.path,
                    })
                data['compression'] = self.__zfsopts.get(
                    child.path,
                    {},
                ).get('compression', ('', '-'))[1]
                data['compressratio'] = self.__zfsopts.get(
                    child.path,
                    {},
                ).get('compressratio', ('', '-'))[1]

                data['used'] = "%s (%s%%)" % (
                    humanize_size(data['used']),
                    data['used_pct'],
                )
                data['avail'] = humanize_size(data['avail'])

                data['readonly'] = self.__zfsopts.get(
                    child.path,
                    {},
                ).get('readonly', ('', '-'))[1]

                description = self.__zfsopts.get(
                    child.path,
                    {},
                ).get('org.freenas:description', ('', '-', 'inherit'))
                data['comments'] = description[1] if description[2] == 'local' else ''

            if self.is_webclient(bundle.request):
                data['_promote_zvol_url'] = reverse(
                    'storage_promote_zfs',
                    kwargs={
                        'name': child.path,
                    })
                data['_add_zfs_volume_url'] = reverse(
                    'storage_zvol',
                    kwargs={
                        'parent': child.path,
                    })
                if child.category == 'filesystem':
                    data['_dataset_delete_url'] = reverse(
                        'storage_dataset_delete',
                        kwargs={
                            'name': child.path,
                        })
                    data['_dataset_edit_url'] = reverse(
                        'storage_dataset_edit',
                        kwargs={
                            'dataset_name': child.path,
                        })
                    data['_dataset_create_url'] = reverse(
                        'storage_dataset',
                        kwargs={
                            'fs': child.path,
                        })
                    data['_permissions_url'] = reverse(
                        'storage_mp_permission',
                        kwargs={
                            'path': child.mountpoint,
                        })
                elif child.category == 'volume':
                    data['_zvol_delete_url'] = reverse(
                        'storage_zvol_delete',
                        kwargs={
                            'name': child.path,
                        })
                    data['_zvol_edit_url'] = reverse(
                        'storage_zvol_edit',
                        kwargs={
                            'name': child.path,
                        })
                data['_add_zfs_volume_url'] = reverse(
                    'storage_zvol', kwargs={
                        'parent': child.path,
                    })
                data['_manual_snapshot_url'] = reverse(
                    'storage_manualsnap',
                    kwargs={
                        'fs': child.path,
                    })

            if child.children:
                _children = OrderedDict()
                for child in child.children:
                    _children[child.name] = child
                data['children'] = self._get_children(
                    bundle, vol, _children, uid
                )

            rv.append(data)
        return rv

    def hydrate(self, bundle):
        bundle = super(VolumeResourceMixin, self).hydrate(bundle)
        if 'layout' not in bundle.data:
            return bundle
        layout = bundle.data.pop('layout')
        i = -1
        for i, item in enumerate(layout):
            disks = item.get("disks")
            vtype = item.get("vdevtype")
            bundle.data['layout-%d-disks' % i] = disks
            bundle.data['layout-%d-vdevtype' % i] = vtype
        bundle.data['layout-INITIAL_FORMS'] = 0
        bundle.data['layout-TOTAL_FORMS'] = i + 1
        return bundle

    def dispatch_list(self, request, **kwargs):
        # Only for webclient to do not break API
        if self.is_webclient(request):
            self.__zfsopts = notifier().zfs_get_options(
                recursive=True,
                props=['compression', 'compressratio', 'readonly', 'org.freenas:description'],
            )
        self._uid = Uid(100)
        return super(VolumeResourceMixin, self).dispatch_list(
            request, **kwargs
        )

    def dehydrate(self, bundle):
        bundle = super(VolumeResourceMixin, self).dehydrate(bundle)

        for key in list(bundle.data.keys()):
            if key.startswith('layout-'):
                del bundle.data[key]

        bundle.data['name'] = bundle.obj.vol_name
        if self.is_webclient(bundle.request):
            bundle.data['compression'] = '-'
            bundle.data['compressratio'] = '-'

        if self.is_webclient(bundle.request):
            bundle.data['_detach_url'] = reverse(
                'storage_detach',
                kwargs={
                    'vid': bundle.obj.id,
                })

        attr_fields = ('avail', 'used', 'used_pct')
        for attr in attr_fields + ('status', ):
            bundle.data[attr] = getattr(bundle.obj, attr)

        bundle.data['is_upgraded'] = bundle.obj.is_upgraded

        is_decrypted = bundle.obj.is_decrypted()
        bundle.data['is_decrypted'] = is_decrypted

        if self.is_webclient(bundle.request):
            bundle.data['_status_url'] = "%s?id=%d" % (
                reverse('freeadmin_storage_volumestatus_datagrid'),
                bundle.obj.id,
            )

            bundle.data['_scrub_url'] = reverse(
                'storage_scrub',
                kwargs={
                    'vid': bundle.obj.id,
                })
            bundle.data['_upgrade_url'] = reverse(
                'storage_volume_upgrade',
                kwargs={
                    'object_id': bundle.obj.id,
                })
            if bundle.obj.vol_encrypt > 0:
                bundle.data['_unlock_url'] = reverse(
                    'storage_volume_unlock',
                    kwargs={
                        'object_id': bundle.obj.id,
                    })
                bundle.data['_download_key_url'] = reverse(
                    'storage_volume_key',
                    kwargs={
                        'object_id': bundle.obj.id,
                    })
                bundle.data['_rekey_url'] = reverse(
                    'storage_volume_rekey',
                    kwargs={
                        'object_id': bundle.obj.id,
                    })
                bundle.data['_add_reckey_url'] = reverse(
                    'storage_volume_recoverykey_add',
                    kwargs={'object_id': bundle.obj.id})
                bundle.data['_rem_reckey_url'] = reverse(
                    'storage_volume_recoverykey_remove',
                    kwargs={'object_id': bundle.obj.id})
                bundle.data['_create_passphrase_url'] = reverse(
                    'storage_volume_create_passphrase',
                    kwargs={'object_id': bundle.obj.id})
                bundle.data['_change_passphrase_url'] = reverse(
                    'storage_volume_change_passphrase',
                    kwargs={'object_id': bundle.obj.id})
                bundle.data['_volume_lock_url'] = reverse(
                    'storage_volume_lock',
                    kwargs={'object_id': bundle.obj.id})

        if is_decrypted:
            if self.is_webclient(bundle.request):
                if isinstance(bundle.data['used'], int):
                    bundle.data['used'] = "%s (%s)" % (
                        humanize_size(bundle.data['used']),
                        bundle.data['used_pct'],
                    )
                if isinstance(bundle.data['avail'], int):
                    bundle.data['avail'] = humanize_size(bundle.data['avail'])
        else:
            bundle.data['used'] = _("Locked")

        bundle.data['mountpoint'] = '/mnt/%s' % bundle.obj.vol_name

        try:
            uid = self._uid
        except Exception:
            uid = Uid(bundle.obj.id * 1000)

        bundle.data['children'] = self._get_children(
            bundle,
            bundle.obj,
            bundle.obj.get_children(),
            uid=uid,
        )

        return bundle

    def obj_delete(self, bundle, **kwargs):
        """Custom delete method to allow detach, not destroy
        """
        if not hasattr(bundle.obj, 'delete'):
            try:
                bundle.obj = self.obj_get(bundle=bundle, **kwargs)
            except ObjectDoesNotExist:
                raise NotFound("A model instance matching the provided arguments could not be found.")

        self.authorized_delete_detail(self.get_object_list(bundle.request), bundle)
        _format = bundle.request.META.get('CONTENT_TYPE', 'application/json')
        if not _format:
            _format = 'application/json'
        deserialized = self._meta.serializer.deserialize(
            bundle.request.body or '{}',
            format=_format,
        )
        with client as c:
            c.call('pool.export', bundle.obj.id, {
                'destroy': deserialized.get('destroy', True),
                'cascade': deserialized.get('cascade', True),
            }, job=True)


class ScrubResourceMixin(object):

    def dehydrate(self, bundle):
        bundle = super(ScrubResourceMixin, self).dehydrate(bundle)
        bundle.data['scrub_volume'] = bundle.obj.scrub_volume.vol_name
        if self.is_webclient(bundle.request):
            _common_human_fields(bundle)
        return bundle


class VolumeImportResource(DojoResource):

    class Meta:
        allowed_methods = ['get', 'post']
        resource_name = 'storage/volume_import'

    def get_list(self, request, **kwargs):
        self.is_authenticated(request)
        with client as c:
            vols = c.call('pool.import_find')
        for vol in vols:
            vol['id'] = '%s|%s' % (vol['name'], vol['guid'])
        return self.create_response(request, vols)

    def post_list(self, request, **kwargs):
        self.is_authenticated(request)
        _format = request.META.get('CONTENT_TYPE') or 'application/json'
        deserialized = self._meta.serializer.deserialize(
            request.body,
            format=_format,
        )
        form = VolumeAutoImportForm(data=deserialized)
        if not form.is_valid():
            raise ImmediateHttpResponse(
                response=self.error_response(request, form.errors)
            )
        volume = form.cleaned_data['volume']
        with client as c:
            c.call('pool.import_pool', {
                'guid': volume['guid'],
            }, job=True)
        return self.create_response(
            request,
            'Volume imported.',
            response_class=HttpAccepted
        )


class ReplicationResourceMixin(object):

    def dehydrate(self, bundle):
        bundle = super(ReplicationResourceMixin, self).dehydrate(bundle)
        bundle.data['repl_status'] = bundle.obj.status
        bundle.data['repl_remote_hostname'] = (
            bundle.obj.repl_remote.ssh_remote_hostname
        )
        bundle.data['repl_remote_hostkey'] = (
            bundle.obj.repl_remote.ssh_remote_hostkey
        )
        bundle.data['repl_remote_port'] = (
            bundle.obj.repl_remote.ssh_remote_port
        )
        bundle.data['repl_remote_dedicateduser_enabled'] = (
            bundle.obj.repl_remote.ssh_remote_dedicateduser_enabled
        )
        bundle.data['repl_remote_dedicateduser'] = (
            bundle.obj.repl_remote.ssh_remote_dedicateduser
        )
        bundle.data['repl_remote_cipher'] = (
            bundle.obj.repl_remote.ssh_cipher
        )
        if 'repl_remote' in bundle.data:
            del bundle.data['repl_remote']
        result = bundle.obj.repl_lastresult or {}
        if 'last_snapshot' in result:
            last_snapshot = result['last_snapshot']
        else:
            last_snapshot = 'Not ran since boot'
        bundle.data['repl_lastsnapshot'] = last_snapshot
        return bundle

    def hydrate(self, bundle):
        bundle = super(ReplicationResourceMixin, self).hydrate(bundle)
        if bundle.obj.id:
            if 'repl_remote_hostname' not in bundle.data:
                bundle.data['repl_remote_hostname'] = bundle.obj.repl_remote.ssh_remote_hostname
            if 'repl_remote_port' not in bundle.data:
                bundle.data['repl_remote_port'] = bundle.obj.repl_remote.ssh_remote_port
            if 'repl_remote_dedicateduser_enabled' not in bundle.data:
                bundle.data['repl_remote_dedicateduser_enabled'] = bundle.obj.repl_remote.ssh_remote_dedicateduser_enabled
            if 'repl_remote_dedicateduser' not in bundle.data:
                bundle.data['repl_remote_dedicateduser'] = bundle.obj.repl_remote.ssh_remote_dedicateduser
            if 'repl_remote_cipher' not in bundle.data:
                bundle.data['repl_remote_cipher'] = bundle.obj.repl_remote.ssh_cipher
            if 'repl_remote_hostkey' not in bundle.data:
                bundle.data['repl_remote_hostkey'] = bundle.obj.repl_remote.ssh_remote_hostkey
        else:
            if 'repl_remote_mode' not in bundle.data:
                bundle.data['repl_remote_mode'] = 'MANUAL'

        return bundle


class TaskResourceMixin(object):

    def dehydrate(self, bundle):
        bundle = super(TaskResourceMixin, self).dehydrate(bundle)
        if not self.is_webclient(bundle.request):
            return bundle
        if bundle.obj.task_repeat_unit == "daily":
            repeat = _('everyday')
        elif bundle.obj.task_repeat_unit == "weekly":
            wchoices = dict(choices.WEEKDAYS_CHOICES)
            labels = []
            for w in eval(bundle.obj.task_byweekday + ','):
                labels.append(str(wchoices[str(w)]))
            days = ', '.join(labels)
            repeat = _('on every %(days)s') % {
                'days': days,
            }
        else:
            repeat = ''
        bundle.data['when'] = _(
            "From %(begin)s through %(end)s, %(repeat)s") % {
            'begin': bundle.obj.task_begin,
            'end': bundle.obj.task_end,
            'repeat': repeat,
        }
        bundle.data['interv'] = "every %s" % (
            bundle.obj.get_task_interval_display(),
        )
        bundle.data['keepfor'] = "%s %s" % (
            bundle.obj.task_ret_count,
            bundle.obj.task_ret_unit,
        )
        if bundle.obj.task_recursive:
            lookup = (
                Q(filesystem=bundle.obj.task_filesystem) |
                Q(filesystem__startswith=bundle.obj.task_filesystem + '/')
            )
        else:
            lookup = Q(filesystem=bundle.obj.task_filesystem)
        if VMWarePlugin.objects.filter(lookup).exists():
            bundle.data['vmwaresync'] = True
        else:
            bundle.data['vmwaresync'] = False
        return bundle


class CIFSResourceMixin(object):

    class Meta:
        resource_name = 'sharing/cifs'

    def dehydrate(self, bundle):
        bundle = super().dehydrate(bundle)
        if bundle.obj.cifs_storage_task:
            bundle.data['cifs_storage_task'] = bundle.obj.cifs_storage_task.id
        else:
            bundle.data['cifs_storage_task'] = None
        return bundle


class NFSResourceMixin(object):

    def hydrate(self, bundle):
        bundle = super(NFSResourceMixin, self).hydrate(bundle)
        if 'nfs_srv_bindip' not in bundle.data and bundle.obj.id:
            bundle.data['nfs_srv_bindip'] = (
                bundle.obj.nfs_srv_bindip
                if bundle.obj.nfs_srv_bindip
                else None
            )
        return bundle


class NFSShareResourceMixin(object):

    class Meta:
        resource_name = 'sharing/nfs'

    def dehydrate(self, bundle):
        bundle = super(NFSShareResourceMixin, self).dehydrate(bundle)
        if self.is_webclient(bundle.request):
            bundle.data['nfs_paths'] = "%s" % ', '.join(bundle.obj.nfs_paths)
        else:
            bundle.data['nfs_paths'] = bundle.obj.nfs_paths

        for key in list(bundle.data.keys()):
            if key.startswith('path_set'):
                del bundle.data[key]
        return bundle

    def hydrate(self, bundle):
        bundle = super(NFSShareResourceMixin, self).hydrate(bundle)
        if 'nfs_paths' not in bundle.data and bundle.obj.id:
            qs = bundle.obj.paths.all()
            nfs_paths = []
            for i, item in enumerate(qs):
                bundle.data['path_set-%d-path' % i] = item.path
                bundle.data['path_set-%d-id' % i] = item.id
                bundle.data['path_set-%d-share' % i] = bundle.obj.id
                nfs_paths.append(item.path)
            bundle.data['nfs_paths'] = nfs_paths
        else:
            nfs_paths = bundle.data.get('nfs_paths', [])
            for i, item in enumerate(nfs_paths):
                bundle.data['path_set-%d-path' % i] = item
                bundle.data['path_set-%d-id' % i] = ''
                bundle.data['path_set-%d-share' % i] = bundle.obj.id
        bundle.data['path_set-INITIAL_FORMS'] = 0
        bundle.data['path_set-TOTAL_FORMS'] = len(nfs_paths)
        return bundle

    def is_form_valid(self, bundle, form):
        fset = inlineformset_factory(
            NFS_Share,
            NFS_Share_Path,
            form=NFS_SharePathForm,
            formset=FreeBaseInlineFormSet,
            extra=0,
        )
        formset = fset(
            bundle.data,
            instance=bundle.obj,
            prefix="path_set",
            parent=form,
        )
        valid = True
        for frm in formset.forms:
            valid &= frm.is_valid()
        valid &= formset.is_valid()
        errors = {}
        if not valid:
            for frm in formset:
                errors.update(frm.errors)
        valid &= form.is_valid(formsets={
            'formset_nfs_share_path': {
                'instance': formset,
            },
        })
        if errors:
            form.errors.update(errors)
        if form.errors:
            bundle.errors = dict(form.errors)
        return valid

    def save_m2m(self, m2m_bundle):
        paths = []
        for path in m2m_bundle.obj.paths.all():
            if path.path not in m2m_bundle.data.get("nfs_paths", []):
                path.delete()
            else:
                paths.append(path.path)

        for path in m2m_bundle.data.get("nfs_paths", []):
            if path in paths:
                continue
            sp = NFS_Share_Path()
            sp.share = m2m_bundle.obj
            sp.path = path
            sp.save()
        return m2m_bundle


class GlobalConfigurationResourceMixin(object):

    def dehydrate(self, bundle):
        bundle = super(GlobalConfigurationResourceMixin, self).dehydrate(bundle)
        if notifier().is_freenas():
            del bundle.data['gc_hostname_b']
        return bundle


class InterfacesResourceMixin(object):

    class Meta:
        resource_name = 'network/interface'

    def dehydrate(self, bundle):
        bundle = super(InterfacesResourceMixin, self).dehydrate(bundle)
        bundle.data['int_media_status'] = bundle.obj.get_media_status()
        bundle.data['ipv4_addresses'] = bundle.obj.get_ipv4_addresses()
        bundle.data['ipv6_addresses'] = bundle.obj.get_ipv6_addresses()
        bundle.data['int_aliases'] = [
            a.alias_network for a in bundle.obj.alias_set.all()
        ]
        for key in list(bundle.data.keys()):
            if key.startswith('alias_set'):
                del bundle.data[key]

        if notifier().is_freenas():
            del bundle.data['int_vhid']
            del bundle.data['int_vip']
            del bundle.data['int_pass']
            del bundle.data['int_critical']
            del bundle.data['int_group']
            del bundle.data['int_ipv4address_b']

        return bundle

    def hydrate(self, bundle):
        bundle = super(InterfacesResourceMixin, self).hydrate(bundle)
        newips = bundle.data.get('int_aliases', [])
        i = -1
        for i, item in enumerate(bundle.obj.alias_set.all()):
            bundle.data[
                'alias_set-%d-alias_v4address' % i
            ] = item.alias_v4address
            bundle.data[
                'alias_set-%d-alias_v4netmaskbit' % i
            ] = item.alias_v4netmaskbit
            bundle.data[
                'alias_set-%d-alias_v6address' % i
            ] = item.alias_v6address
            bundle.data[
                'alias_set-%d-alias_v6netmaskbit' % i
            ] = item.alias_v6netmaskbit
            bundle.data['alias_set-%d-id' % i] = item.id
        initial = i + 1
        i = initial
        for item in newips:
            ip, nm = item.rsplit('/', 1)
            if ':' in ip:
                v = 'v6'
            else:
                v = 'v4'
            for j in range(initial):
                if bundle.data['alias_set-%d-alias_%saddress' % (j, v)] == ip:
                    bundle.data['alias_set-%d-alias_%saddress' % (j, v)] = ip
                    bundle.data['alias_set-%d-alias_%snetmaskbit' % (j, v)] = nm
                    break
            else:
                bundle.data['alias_set-%d-alias_%saddress' % (i, v)] = ip
                bundle.data['alias_set-%d-alias_%snetmaskbit' % (i, v)] = nm
                i += 1
        bundle.data['int_aliases'] = newips
        bundle.data['alias_set-INITIAL_FORMS'] = initial
        bundle.data['alias_set-TOTAL_FORMS'] = i
        return bundle

    def is_form_valid(self, bundle, form):
        fset = inlineformset_factory(
            Interfaces,
            Alias,
            form=AliasForm,
            extra=0,
        )
        formset = fset(bundle.data, instance=bundle.obj, prefix='alias_set')
        for frm in formset.forms:
            frm.parent = form
        valid = formset.is_valid()
        errors = {}
        if not valid:
            for form in formset:
                errors.update(form.errors)
        valid &= form.is_valid()
        if errors:
            form.errors.update(errors)
        bundle.errors = dict(form.errors)
        return valid

    def save_m2m(self, m2m_bundle):
        aliases = []
        for alias in m2m_bundle.obj.alias_set.all():
            if alias.alias_network not in m2m_bundle.data.get(
                "int_aliases", []
            ):
                alias.delete()
            else:
                aliases.append(alias.alias_network)

        for alias in m2m_bundle.data.get("int_aliases", []):
            if alias in aliases:
                continue
            ip, netm = alias.rsplit('/', 1)
            al = Alias()
            if ':' in ip:
                al.alias_v6address = ip
                al.alias_v6netmaskbit = netm
            else:
                al.alias_v4address = ip
                al.alias_v4netmaskbit = netm
            al.alias_interface = m2m_bundle.obj
            al.save()
        return m2m_bundle


class LAGGInterfaceResourceMixin(object):

    class Meta:
        resource_name = 'network/lagg'
        allowed_methods = ['get', 'post', 'delete']

    def dehydrate(self, bundle):
        bundle = super(LAGGInterfaceResourceMixin, self).dehydrate(bundle)
        bundle.data['lagg_interface'] = bundle.obj.lagg_interface.int_interface
        if 'lagg_interfaces' in bundle.data:
            del bundle.data['lagg_interfaces']
        if 'lagg_interface_id' in bundle.data:
            del bundle.data['lagg_interface_id']
        if self.is_webclient(bundle.request):
            bundle.data['lagg_interface'] = str(bundle.obj)
            bundle.data['_edit_url'] = reverse(
                'freeadmin_network_interfaces_edit',
                kwargs={
                    'oid': bundle.obj.lagg_interface.id,
                }) + '?deletable=false'
            bundle.data['_delete_url'] = reverse(
                'freeadmin_network_interfaces_delete',
                kwargs={
                    'oid': bundle.obj.lagg_interface.id,
                })
            bundle.data['_members_url'] = reverse(
                'freeadmin_network_lagginterfacemembers_datagrid'
            ) + '?id=%d' % bundle.obj.id
        return bundle


class LAGGInterfaceMembersResourceMixin(object):

    def build_filters(self, filters=None, ignore_bad_filters=True):
        if filters is None:
            filters = {}
        orm_filters = super(
            LAGGInterfaceMembersResourceMixin,
            self).build_filters(filters, ignore_bad_filters)
        lagggrp = filters.get("lagg_interfacegroup__id")
        if lagggrp:
            orm_filters["lagg_interfacegroup__id"] = lagggrp
        return orm_filters

    def dehydrate(self, bundle):
        bundle = super(LAGGInterfaceMembersResourceMixin, self).dehydrate(
            bundle
        )
        if self.is_webclient(bundle.request):
            bundle.data['lagg_interfacegroup'] = str(
                bundle.obj.lagg_interfacegroup
            )
        else:
            bundle.data['lagg_interfacegroup'] = (
                bundle.obj.lagg_interfacegroup.id
            )
        return bundle


class CloudSyncResourceMixin(NestedMixin):

    def dispatch_list(self, request, **kwargs):
        with client as c:
            self.__tasks = {task["id"]: task for task in c.call("cloudsync.query")}
        return super(CloudSyncResourceMixin, self).dispatch_list(request, **kwargs)

    def dehydrate(self, bundle):
        bundle = super(CloudSyncResourceMixin, self).dehydrate(bundle)
        if self.is_webclient(bundle.request):
            _common_human_fields(bundle)
            bundle.data['_run_url'] = reverse('cloudsync_run', kwargs={
                'oid': bundle.obj.id
            })
            bundle.data['credential'] = str(bundle.obj.credential)
        job = self.__tasks.get(bundle.obj.id, {}).get("job")
        if job:
            bundle.data['job_id'] = job['id']
            if job['state'] == 'RUNNING':
                bundle.data['status'] = '{}{}'.format(
                    job['state'],
                    ': ' + job['progress']['description']
                    if job['progress']['description']
                    else '',
                )
            elif job['state'] == 'FAILED':
                bundle.data['status'] = '{}: {}'.format(
                    job['state'],
                    job['error'],
                )
            else:
                bundle.data['status'] = job['state']
        else:
            bundle.data['status'] = _('Not ran since last boot')
        return bundle


class CronJobResourceMixin(NestedMixin):

    def prepend_urls(self):
        return [
            url(
                r"^(?P<resource_name>%s)/(?P<pk>\w[\w/-]*)/run%s$" % (
                    self._meta.resource_name, trailing_slash()
                ),
                self.wrap_view('run')
            ),
        ]

    def run(self, request, **kwargs):
        self.method_check(request, allowed=['post'])

        bundle, obj = self._get_parent(request, kwargs)
        obj.run()
        return HttpResponse('Cron job started.', status=202)

    def dehydrate(self, bundle):
        bundle = super(CronJobResourceMixin, self).dehydrate(bundle)
        if self.is_webclient(bundle.request):
            _common_human_fields(bundle)
            bundle.data['_run_url'] = reverse('cron_run', kwargs={
                'oid': bundle.obj.id
            })
        return bundle


class RsyncResourceMixin(NestedMixin):

    def prepend_urls(self):
        return [
            url(
                r"^(?P<resource_name>%s)/(?P<pk>\w[\w/-]*)/run%s$" % (
                    self._meta.resource_name, trailing_slash()
                ),
                self.wrap_view('run')
            ),
        ]

    def run(self, request, **kwargs):
        self.method_check(request, allowed=['post'])

        bundle, obj = self._get_parent(request, kwargs)
        obj.run()
        return HttpResponse('Rsync job started.', status=202)

    def dehydrate(self, bundle):
        bundle = super(RsyncResourceMixin, self).dehydrate(bundle)
        if self.is_webclient(bundle.request):
            _common_human_fields(bundle)
            bundle.data['_run_url'] = reverse('rsync_run', kwargs={
                'oid': bundle.obj.id
            })
            if bundle.obj.rsync_mode == 'module':
                bundle.data['rsync_remoteport'] = '-'
                bundle.data['rsync_remotepath'] = '-'
            else:
                bundle.data['rsync_remotemodule'] = '-'
        return bundle


class SMARTTestResourceMixin(object):

    def dehydrate(self, bundle):
        bundle = super(SMARTTestResourceMixin, self).dehydrate(bundle)
        bundle.data['smarttest_disks'] = [
            o.pk for o in bundle.obj.smarttest_disks.all()
        ]
        if self.is_webclient(bundle.request):
            _common_human_fields(bundle)
            bundle.data['smarttest_type'] = (
                bundle.obj.get_smarttest_type_display()
            )
        return bundle


class ISCSITargetResourceMixin(object):

    class Meta:
        resource_name = 'services/iscsi/target'


class ISCSITargetGroupsResourceMixin(object):

    class Meta:
        resource_name = 'services/iscsi/targetgroup'

    def dehydrate(self, bundle):
        bundle = super(ISCSITargetGroupsResourceMixin, self).dehydrate(bundle)
        bundle.data['iscsi_target'] = bundle.obj.iscsi_target.id
        if bundle.obj.iscsi_target_initiatorgroup:
            bundle.data['iscsi_target_initiatorgroup'] = (
                bundle.obj.iscsi_target_initiatorgroup.id
            )
        else:
            bundle.data['iscsi_target_initiatorgroup'] = None
        bundle.data['iscsi_target_portalgroup'] = (
            bundle.obj.iscsi_target_portalgroup.id
        )
        return bundle


class ISCSIPortalResourceMixin(object):

    class Meta:
        resource_name = 'services/iscsi/portal'

    def dehydrate(self, bundle):
        bundle = super(ISCSIPortalResourceMixin, self).dehydrate(bundle)
        globalconf = iSCSITargetGlobalConfiguration.objects.latest('id')
        if globalconf.iscsi_alua:
            listen = []
            listen_a = []
            listen_b = []
            for p in bundle.obj.ips.all():
                if p.iscsi_target_portalip_ip == '0.0.0.0':
                    listen.append(f'{p.iscsi_target_portalip_ip}:{p.iscsi_target_portalip_port}')
                else:
                    ips = p.alua_ips()
                    listen_a.extend(ips[0])
                    listen_b.extend(ips[1])
            bundle.data['iscsi_target_portal_ips'] = f'{", ".join(listen + listen_a + listen_b)}'
            bundle.data['iscsi_target_portal_ips_a'] = listen_a
            bundle.data['iscsi_target_portal_ips_b'] = listen_b
        else:
            listen = ["%s:%s" % (
                p.iscsi_target_portalip_ip,
                p.iscsi_target_portalip_port,
            ) for p in bundle.obj.ips.all()]
            bundle.data['iscsi_target_portal_ips'] = listen
        for key in [y for y in list(bundle.data.keys()) if y.startswith('portalip_set')]:
            del bundle.data[key]
        return bundle

    def hydrate(self, bundle):
        bundle = super(ISCSIPortalResourceMixin, self).hydrate(bundle)
        newips = bundle.data.get('iscsi_target_portal_ips', [])
        i = -1
        existing_ips = []
        for i, item in enumerate(bundle.obj.ips.all()):
            bundle.data[
                'portalip_set-%d-iscsi_target_portalip_ip' % i
            ] = item.iscsi_target_portalip_ip
            bundle.data[
                'portalip_set-%d-iscsi_target_portalip_port' % i
            ] = item.iscsi_target_portalip_port
            bundle.data['portalip_set-%d-id' % i] = item.id
            existing_ips.append(f'{item.iscsi_target_portalip_ip}:{item.iscsi_target_portalip_port}')
        total = initial = i + 1
        for i, item in enumerate(newips, i + 1):
            # Skip existing IP:port
            if item in existing_ips:
                continue
            ip, prt = item.rsplit(':', 1)
            bundle.data['portalip_set-%d-iscsi_target_portalip_ip' % i] = ip
            bundle.data['portalip_set-%d-iscsi_target_portalip_port' % i] = prt
            bundle.data['portalip_set-%d-id' % i] = ''
            total += 1
        bundle.data['iscsi_target_portal_ips'] = newips
        bundle.data['portalip_set-INITIAL_FORMS'] = initial
        bundle.data['portalip_set-TOTAL_FORMS'] = total
        if bundle.obj.id is None:
            bundle.data['iscsi_target_portal_tag'] = iSCSITargetPortal.objects.all().count() + 1
        return bundle

    def is_form_valid(self, bundle, form):
        fset = inlineformset_factory(
            iSCSITargetPortal,
            iSCSITargetPortalIP,
            form=iSCSITargetPortalIPForm,
            extra=0,
        )
        formset = fset(bundle.data, instance=bundle.obj, prefix='portalip_set')
        valid = formset.is_valid()
        errors = {}
        if not valid:
            for form in formset:
                errors.update(form.errors)
        valid &= form.is_valid()
        if errors:
            form.errors.update(errors)
        bundle.errors = dict(form.errors)
        valid &= form.is_valid(formsets={'formset_iscsitargetportalip': {'instance': formset}})
        return valid

    def save_m2m(self, m2m_bundle):
        ips = []
        for ip in m2m_bundle.obj.ips.all():
            ipport = '%s:%s' % (
                ip.iscsi_target_portalip_ip,
                ip.iscsi_target_portalip_port,
            )
            if ipport not in m2m_bundle.data.get(
                "iscsi_target_portal_ips", []
            ):
                ip.delete()
            else:
                ips.append(ipport)

        for ip in m2m_bundle.data.get("iscsi_target_portal_ips", []):
            if ip in ips:
                continue
            ip, port = ip.rsplit(':', 1)
            portalip = iSCSITargetPortalIP()
            portalip.iscsi_target_portalip_portal = m2m_bundle.obj
            portalip.iscsi_target_portalip_ip = ip
            portalip.iscsi_target_portalip_port = port
            portalip.save()
        return m2m_bundle


class ISCSITargetToExtentResourceMixin(object):

    SORTING_MAP = {
        'iscsi_extent': lambda x: x.iscsi_extent.id,
        'iscsi_target': lambda x: x.iscsi_target.id,
    }

    class Meta:
        resource_name = 'services/iscsi/targettoextent'

    def dehydrate(self, bundle):
        bundle = super(ISCSITargetToExtentResourceMixin, self).dehydrate(
            bundle
        )
        if self.is_webclient(bundle.request):
            bundle.data['iscsi_target'] = bundle.obj.iscsi_target
            bundle.data['iscsi_extent'] = bundle.obj.iscsi_extent
        else:
            bundle.data['iscsi_target'] = bundle.obj.iscsi_target.id
            bundle.data['iscsi_extent'] = bundle.obj.iscsi_extent.id
        return bundle


class ISCSITargetExtentResourceMixin(object):

    class Meta:
        resource_name = 'services/iscsi/extent'

    def dehydrate(self, bundle):
        bundle = super(ISCSITargetExtentResourceMixin, self).dehydrate(bundle)
        if bundle.obj.iscsi_target_extent_type == 'Disk':
            disk = Disk.objects.filter(pk=bundle.obj.iscsi_target_extent_path)
            if disk.exists():
                bundle.data['iscsi_target_extent_path'] = "/dev/%s" % disk[0].devname
            else:
                bundle.data['iscsi_target_extent_path'] = None
        elif bundle.obj.iscsi_target_extent_type == 'ZVOL':
            bundle.data['iscsi_target_extent_path'] = "/dev/%s" % (
                bundle.data['iscsi_target_extent_path'],
            )
        return bundle


class BsdUserResourceMixin(NestedMixin):

    SORTING_MAP = {
        'bsdusr_group': lambda x: x.bsdusr_group.bsdgrp_gid,
    }

    class Meta:
        queryset = bsdUsers.objects.all().order_by(
            'bsdusr_builtin',
            'bsdusr_uid')
        validation = FormValidation(form_class=bsdUsersForm)

    def prepend_urls(self):
        return [
            url(
                r"^(?P<resource_name>%s)/(?P<pk>\w[\w/-]*)/groups%s$" % (
                    self._meta.resource_name, trailing_slash()
                ),
                self.wrap_view('groups')
            ),
            url(
                r"^(?P<resource_name>%s)/(?P<pk>\w[\w/-]*)/password%s$" % (
                    self._meta.resource_name, trailing_slash()
                ),
                self.wrap_view('change_password')
            ),
        ]

    def groups(self, request, **kwargs):
        if request.method.lower() not in ('post', 'get'):
            response = HttpMethodNotAllowed(request.method)
            response['Allow'] = 'POST,GET'
            raise ImmediateHttpResponse(response=response)
        if request.method.lower() == 'get':
            return self.groups_get_detail(request, **kwargs)
        else:
            return self.groups_post_detail(request, **kwargs)

    def groups_get_detail(self, request, **kwargs):
        bundle, obj = self._get_parent(request, kwargs)

        objects = bsdGroupMembership.objects.filter(bsdgrpmember_user=obj)

        bundles = []
        for obj in objects:
            bundles.append(obj.bsdgrpmember_group.bsdgrp_group)

        return self.create_response(request, bundles)

    def groups_post_detail(self, request, **kwargs):
        bundle, obj = self._get_parent(request, kwargs)

        deserialized = self.deserialize(
            request,
            request.body,
            format=request.META.get('CONTENT_TYPE', 'application/json'),
        )

        ids = [o.id for o in bsdGroups.objects.filter(
            bsdgrp_group__in=deserialized
        )]

        data = QueryDict(urllib.parse.urlencode({'bsduser_to_group': ids}, doseq=True))

        form = bsdUserToGroupForm(userid=obj.id, data=data)
        if not form.is_valid():
            raise ImmediateHttpResponse(
                response=self.error_response(request, form.errors)
            )
        else:
            form.save()

        response = self.groups_get_detail(request, **kwargs)
        response.status_code = 202
        return response

    def change_password(self, request, **kwargs):
        if request.method != 'POST':
            response = HttpMethodNotAllowed('POST')
            response['Allow'] = 'POST'
            raise ImmediateHttpResponse(response=response)

        self.is_authenticated(request)
        try:
            bundle = self.build_bundle(
                data={'pk': kwargs['pk']}, request=request
            )
            obj = self.cached_obj_get(
                bundle=bundle, **self.remove_api_resource_names(kwargs)
            )
        except ObjectDoesNotExist:
            return HttpNotFound()
        except MultipleObjectsReturned:
            return HttpMultipleChoices(
                "More than one resource is found at this URI."
            )

        deserialized = self.deserialize(
            request,
            request.body,
            format=request.META.get('CONTENT_TYPE', 'application/json'),
        )
        form = bsdUserPasswordForm(
            instance=obj,
            data={
                'bsdusr_username': obj.bsdusr_username,
                'bsdusr_password': deserialized.get('bsdusr_password'),
            },
            confirm=False,
        )
        if not form.is_valid():
            raise ImmediateHttpResponse(
                response=self.error_response(request, form.errors)
            )
        else:
            form.save()
        return self.get_detail(request, **kwargs)

    def dehydrate(self, bundle):
        bundle = super(BsdUserResourceMixin, self).dehydrate(bundle)
        bundle.data['bsdusr_sshpubkey'] = bundle.obj.bsdusr_sshpubkey
        if self.is_webclient(bundle.request):
            bundle.data['bsdusr_group'] = bundle.obj.bsdusr_group.bsdgrp_gid
            bundle.data['_edit_url'] += 'bsdUsersForm'
            if bundle.obj.bsdusr_builtin:
                bundle.data['_edit_url'] += '?deletable=false'
        else:
            bundle.data['bsdusr_group'] = bundle.obj.bsdusr_group.id
        return bundle

    def hydrate(self, bundle):
        if (
            bundle.request.method == 'PUT' and
            bundle.obj.id and 'bsdusr_to_group' not in bundle.data
        ):
            bundle.data['bsdusr_to_group'] = [
                o.bsdgrpmember_group.id for o in bundle.obj.bsdgroupmembership_set.all()
            ]
        bundle = super(BsdUserResourceMixin, self).hydrate(bundle)
        return bundle


class BsdGroupResourceMixin(object):

    class Meta:
        queryset = bsdGroups.objects.order_by('bsdgrp_builtin', 'bsdgrp_gid')

    def dehydrate(self, bundle):
        bundle = super(BsdGroupResourceMixin, self).dehydrate(bundle)
        if self.is_webclient(bundle.request):
            bundle.data['_members_url'] = reverse(
                'account_bsdgroup_members',
                kwargs={'object_id': bundle.obj.id})
        return bundle


class JailMountPointResourceMixin(object):

    def dehydrate(self, bundle):
        bundle = super(JailMountPointResourceMixin, self).dehydrate(bundle)
        bundle.data['mounted'] = bundle.obj.mounted
        return bundle


class JailsResourceMixin(NestedMixin):

    class Meta:
        validation = FormValidation(form_class=JailsEditForm)
        put_validation = FormValidation(form_class=JailsEditForm)

    def prepend_urls(self):
        return [
            url(
                r"^(?P<resource_name>%s)/(?P<pk>\w[\w/-]*)/restart%s$" % (
                    self._meta.resource_name, trailing_slash()
                ),
                self.wrap_view('jail_restart'),
                name="api_jails_jails_restart"
            ),
            url(
                r"^(?P<resource_name>%s)/(?P<pk>\w[\w/-]*)/start%s$" % (
                    self._meta.resource_name, trailing_slash()
                ),
                self.wrap_view('jail_start'),
                name="api_jails_jails_start"
            ),
            url(
                r"^(?P<resource_name>%s)/(?P<pk>\w[\w/-]*)/stop%s$" % (
                    self._meta.resource_name, trailing_slash()
                ),
                self.wrap_view('jail_stop'),
                name="api_jails_jails_stop"
            ),
        ]

    def jail_restart(self, request, **kwargs):
        self.method_check(request, allowed=['post'])

        bundle, obj = self._get_parent(request, kwargs)

        notifier().reload("http")
        try:
            Warden().stop(jail=obj.jail_host)
            Warden().start(jail=obj.jail_host)
        except Exception as e:
            raise ImmediateHttpResponse(
                response=self.error_response(request, {
                    'error': e,
                })
            )

        return HttpResponse('Jail restarted.', status=202)

    def jail_start(self, request, **kwargs):
        self.method_check(request, allowed=['post'])

        bundle, obj = self._get_parent(request, kwargs)

        # TODO: Duplicated code - jails.views.jail_start
        notifier().reload("http")
        try:
            Warden().start(jail=obj.jail_host)
        except Exception as e:
            raise ImmediateHttpResponse(
                response=self.error_response(request, {
                    'error': e,
                })
            )

        return HttpResponse('Jail started.', status=202)

    def jail_stop(self, request, **kwargs):
        self.method_check(request, allowed=['post'])

        bundle, obj = self._get_parent(request, kwargs)

        # TODO: Duplicated code - jails.views.jail_stop
        notifier().reload("http")
        try:
            Warden().stop(jail=obj.jail_host)
        except Exception as e:
            raise ImmediateHttpResponse(
                response=self.error_response(request, {
                    'error': e,
                })
            )

        return HttpResponse('Jail stopped.', status=202)

    def dispatch_list(self, request, **kwargs):
        proc = subprocess.Popen(
            ["/usr/sbin/jls"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf8'
        )
        self.__jls = proc.communicate()[0]
        return super(JailsResourceMixin, self).dispatch_list(request, **kwargs)

    def post_list(self, request, **kwargs):
        raise ImmediateHttpResponse(
            response=self.error_response(request, {
                'error': 'No longer possible to create jails using API 1.0',
            })
        )

    def post_form_save_hook(self, bundle, form):
        if form.errors:
            raise ImmediateHttpResponse(response=self.error_response(
                bundle.request,
                form.errors,
                response_class=http.HttpConflict,
            ))

    def dehydrate(self, bundle):
        bundle = super(JailsResourceMixin, self).dehydrate(bundle)

        if self.is_webclient(bundle.request):
            try:
                reg = re.search(
                    r'\s*?(\d+).*?\b%s\b' % bundle.obj.jail_host,
                    self.__jls,
                )
                bundle.data['jail_jid'] = int(reg.groups()[0])
            except Exception:
                bundle.data['jail_jid'] = None

            bundle.data['jail_os'] = 'FreeBSD'
            if bundle.obj.is_linux_jail():
                bundle.data['jail_os'] = 'Linux'

            bundle.data['jail_isplugin'] = False
            plugin = Plugins.objects.filter(plugin_jail=bundle.obj.jail_host)
            if plugin:
                bundle.data['jail_isplugin'] = True

        if self.is_webclient(bundle.request):
            bundle.data['_edit_url'] = reverse('jail_edit', kwargs={
                'id': bundle.obj.id
            })
            bundle.data['_jail_storage_add_url'] = reverse(
                'jail_storage_add', kwargs={'jail_id': bundle.obj.id}
            )
            bundle.data['_jail_start_url'] = reverse('jail_start', kwargs={
                'id': bundle.obj.id
            })
            bundle.data['_jail_stop_url'] = reverse('jail_stop', kwargs={
                'id': bundle.obj.id
            })
            bundle.data['_jail_restart_url'] = reverse('jail_restart', kwargs={
                'id': bundle.obj.id
            })
            bundle.data['_jail_delete_url'] = reverse('jail_delete', kwargs={
                'id': bundle.obj.id
            })
            if bundle.obj.jail_ipv4:
                bundle.data['jail_ipv4'] = bundle.obj.jail_ipv4.split('/')[0]

        return bundle


class JailTemplateResourceMixin(object):

    class Meta:
        queryset = JailTemplate.objects.exclude(jt_system=True)
        post_validation = FormValidation(form_class=JailTemplateCreateForm)
        put_validation = FormValidation(form_class=JailTemplateEditForm)

    def dehydrate(self, bundle):
        bundle = super(JailTemplateResourceMixin, self).dehydrate(bundle)
        bundle.data['jt_instances'] = bundle.obj.jt_instances

        if self.is_webclient(bundle.request):
            bundle.data['_edit_url'] = reverse(
                'jail_template_edit',
                kwargs={'id': bundle.obj.id},
            )
            bundle.data['_delete_url'] = reverse(
                'jail_template_delete',
                kwargs={'id': bundle.obj.id},
            )

        return bundle


class PluginsResourceMixin(NestedMixin):

    def prepend_urls(self):
        return [
            url(
                r"^(?P<resource_name>%s)/(?P<pk>\w[\w/-]*)/start%s$" % (
                    self._meta.resource_name, trailing_slash()
                ),
                self.wrap_view('plugin_start'),
                name="api_plugins_plugins_start"
            ),
            url(
                r"^(?P<resource_name>%s)/(?P<pk>\w[\w/-]*)/stop%s$" % (
                    self._meta.resource_name, trailing_slash()
                ),
                self.wrap_view('plugin_stop'),
                name="api_plugin_plugins_stop"
            ),
        ]

    def plugin_start(self, request, **kwargs):
        self.method_check(request, allowed=['post'])

        bundle, obj = self._get_parent(request, kwargs)

        try:
            success, errmsg = obj.service_start(request)
            if success is not True:
                raise ValueError(errmsg)
        except Exception as e:
            raise ImmediateHttpResponse(
                response=self.error_response(request, {
                    'error': e,
                })
            )

        return HttpResponse('Plugin started.', status=202)

    def plugin_stop(self, request, **kwargs):
        self.method_check(request, allowed=['post'])

        bundle, obj = self._get_parent(request, kwargs)

        try:
            success, errmsg = obj.service_stop(request)
            if success is not True:
                raise ValueError(errmsg)
        except Exception as e:
            raise ImmediateHttpResponse(
                response=self.error_response(request, {
                    'error': e,
                })
            )

        return HttpResponse('Plugin stopped.', status=202)

    def dehydrate(self, bundle):
        host = get_base_url(bundle.request)
        plugin, status, jstatus = get_plugin_status((bundle.obj, host, bundle.request))
        bundle.data['plugin_status'] = status['status'] if status and 'status' in status else 'UNKNOWN'
        return bundle


class SnapshotResource(DojoResource):

    id = fields.CharField(attribute='fullname')
    name = fields.CharField(attribute='name')
    filesystem = fields.CharField(attribute='filesystem')
    fullname = fields.CharField(attribute='fullname')
    refer = fields.IntegerField(attribute='refer')
    used = fields.IntegerField(attribute='used')
    mostrecent = fields.BooleanField(attribute='mostrecent')
    parent_type = fields.CharField(attribute='parent_type')

    class Meta:
        allowed_methods = ['delete', 'get', 'post']
        object_class = zfs.Snapshot
        resource_name = 'storage/snapshot'
        max_limit = 0

    def prepend_urls(self):
        return [
            url(
                r"^(?P<resource_name>%s)/(?P<pk>.+?)/clone%s$" % (
                    self._meta.resource_name, trailing_slash()
                ),
                self.wrap_view('clone')
            ),
            url(
                r"^(?P<resource_name>%s)/(?P<pk>.+?)/rollback%s$" % (
                    self._meta.resource_name, trailing_slash()
                ),
                self.wrap_view('rollback')
            ),
        ]

    def clone(self, request, **kwargs):
        self.method_check(request, allowed=['post'])
        self.is_authenticated(request)

        deserialized = self.deserialize(
            request,
            request.body,
            format=request.META.get('CONTENT_TYPE', 'application/json'),
        )
        form = CloneSnapshotForm(
            initial={'cs_snapshot': kwargs['pk']},
            data={
                'cs_snapshot': kwargs['pk'],
                'cs_name': deserialized.get('name'),
            },
        )
        if form.is_valid():
            err = form.commit()
            if err:
                raise ImmediateHttpResponse(
                    response=self.error_response(request, err)
                )
        else:
            raise ImmediateHttpResponse(
                response=self.error_response(request, form.errors)
            )

        return HttpResponse('Snapshot cloned.', status=202)

    def rollback(self, request, **kwargs):
        self.method_check(request, allowed=['post'])
        self.is_authenticated(request)

        deserialized = self.deserialize(
            request,
            request.body,
            format=request.META.get('CONTENT_TYPE', 'application/json'),
        )
        rv = notifier().rollback_zfs_snapshot(snapshot=kwargs['pk'], force=deserialized.get('force', False))
        if rv != '':
            raise ImmediateHttpResponse(
                response=self.error_response(request, rv)
            )

        return HttpResponse('Snapshot rolled back.', status=202)

    def get_list(self, request, **kwargs):

        snapshots = notifier().zfs_snapshot_list()

        results = []
        for snaps in list(snapshots.values()):
            results.extend(snaps)
        FIELD_MAP = {
            'extra': 'mostrecent',
        }

        for sfield in self._apply_sorting(request.GET):
            if sfield.startswith('-'):
                field = sfield[1:]
                reverse = True
            else:
                field = sfield
                reverse = False
            field = FIELD_MAP.get(field, field)
            apifield = self.fields.get(field)
            default = ''
            if apifield and isinstance(apifield, fields.IntegerField):
                default = 0
            results.sort(
                key=lambda item: getattr(item, field) or default,
                reverse=reverse)

        limit = self._meta.limit
        if 'HTTP_X_RANGE' in request.META:
            _range = request.META['HTTP_X_RANGE'].split('-')
            if len(_range) > 1 and _range[1] == '':
                limit = 0

        paginator = self._meta.paginator_class(
            request,
            results,
            resource_uri=self.get_resource_uri(),
            limit=limit,
            max_limit=self._meta.max_limit,
            collection_name=self._meta.collection_name,
        )
        to_be_serialized = paginator.page()
        # Dehydrate the bundles in preparation for serialization.
        bundles = []

        for obj in to_be_serialized[self._meta.collection_name]:
            bundle = self.build_bundle(obj=obj, request=request)
            bundles.append(self.full_dehydrate(bundle))

        length = len(bundles)
        to_be_serialized[self._meta.collection_name] = bundles
        to_be_serialized = self.alter_list_data_to_serialize(
            request,
            to_be_serialized
        )
        response = self.create_response(request, to_be_serialized)
        response['Content-Range'] = 'items %d-%d/%d' % (
            paginator.offset,
            paginator.offset + length - 1,
            len(results)
        )
        return response

    def post_list(self, request, **kwargs):
        deserialized = self.deserialize(
            request,
            request.body,
            format=request.META.get('CONTENT_TYPE', 'application/json')
        )
        form = ManualSnapshotForm(data={
            'ms_recursively': deserialized.get('recursive', False),
            'ms_name': deserialized.get('name'),
            'vmwaresync': deserialized.get('vmware_sync', False)
        }, fs=deserialized.get('dataset'))
        if not form.is_valid():
            raise ImmediateHttpResponse(
                response=self.error_response(request, form.errors)
            )
        else:
            try:
                form.commit(deserialized.get('dataset'))
            except MiddlewareError as e:
                raise ImmediateHttpResponse(
                    response=self.error_response(request, {
                        'error': e.value,
                    })
                )
            else:
                snap = list(notifier().zfs_snapshot_list(path='%s@%s' % (
                    deserialized['dataset'],
                    deserialized['name'],
                )).values())[0][0]
                bundle = self.full_dehydrate(
                    self.build_bundle(obj=snap, request=request)
                )
                return self.create_response(
                    request,
                    bundle,
                    response_class=HttpCreated,
                )

    def obj_delete(self, bundle=None, **kwargs):
        if '@' not in kwargs['pk']:
            raise ImmediateHttpResponse(
                response=self.error_response(bundle.request, {
                    'error': _('Invalid snapshot'),
                })
            )
        dataset, name = kwargs['pk'].split('@', 1)
        snap = list(notifier().zfs_snapshot_list(path='%s@%s' % (
            dataset,
            name,
        )).values())
        if not snap:
            raise ImmediateHttpResponse(
                response=self.error_response(bundle.request, {
                    'error': _('Invalid snapshot'),
                })
            )
        snap = snap[0][0]

        try:
            notifier().destroy_zfs_dataset(path=kwargs['pk'])
        except MiddlewareError as e:
            raise ImmediateHttpResponse(
                response=self.error_response(bundle.request, {
                    'error': e.value,
                })
            )

        bundle = self.full_dehydrate(
            self.build_bundle(obj=snap, request=bundle.request)
        )
        return self.create_response(
            bundle.request,
            None,
            response_class=HttpNoContent,
        )

    def dehydrate(self, bundle):
        if self.is_webclient(bundle.request):
            bundle.data['used'] = humanize_size(bundle.data['used'])
            bundle.data['refer'] = humanize_size(bundle.data['refer'])
            bundle.data['extra'] = {
                'clone_url': reverse(
                    'storage_clonesnap',
                    kwargs={
                        'snapshot': bundle.obj.fullname,
                    }
                ) + ('?volume=true' if bundle.obj.parent_type == 'volume' else ''),
                'rollback_url': reverse('storage_snapshot_rollback', kwargs={
                    'dataset': bundle.obj.filesystem,
                    'snapname': bundle.obj.name,
                }) if bundle.obj.mostrecent else None,
                'delete_url': reverse('storage_snapshot_delete', kwargs={
                    'dataset': bundle.obj.filesystem,
                    'snapname': bundle.obj.name,
                }),
            }
        return bundle


class FTPResourceMixin(object):

    def hydrate(self, bundle):
        bundle = super(FTPResourceMixin, self).hydrate(bundle)
        if bundle.request.method == 'PUT':
            """
            For easier handling the permission widget only accepts unix
            permission and not umask.
            Convert from umask to unix perm before proceesing.
            """
            if 'ftp_filemask' in bundle.data:
                fmask = bundle.data['ftp_filemask']
                try:
                    assert len(fmask) == 3
                    fmask = int(fmask, 8)
                    fmask = (~fmask & 0o666)
                    bundle.data['ftp_filemask'] = oct(fmask)[2:]
                except Exception:
                    pass

            if 'ftp_dirmask' in bundle.data:
                dmask = bundle.data['ftp_dirmask']
                try:
                    assert len(dmask) == 3
                    dmask = int(dmask, 8)
                    dmask = (~dmask & 0o777)
                    bundle.data['ftp_dirmask'] = oct(dmask)[2:]
                except Exception:
                    pass
        return bundle


class ServicesResourceMixin(object):

    class Meta:
        allowed_methods = ['get', 'put']
        filtering = {
            'srv_service': ['exact'],
        }

    def dispatch(self, *args, **kwargs):
        self.__services = {}
        try:
            with client as c:
                for service in c.call('service.query'):
                    self.__services[service['service']] = service
        except ClientException:
            log.debug('Failed to get service.query', exc_info=True)
        return super(ServicesResourceMixin, self).dispatch(*args, **kwargs)

    def hydrate(self, bundle):
        bundle = super(ServicesResourceMixin, self).hydrate(bundle)
        return bundle

    def dehydrate(self, bundle):
        bundle = super(ServicesResourceMixin, self).hydrate(bundle)
        service = self.__services.get(bundle.obj.srv_service)
        if service:
            bundle.data['srv_state'] = service['state']
        else:
            bundle.data['srv_state'] = 'UNKNOWN'
        return bundle

    def obj_get(self, bundle, **kwargs):
        if 'pk' in kwargs and not kwargs['pk'].isdigit():
            kwargs['srv_service'] = kwargs.pop('pk')
        return super(ServicesResourceMixin, self).obj_get(bundle, **kwargs)


class RebootResource(DojoResource):

    class Meta:
        allowed_methods = ['post']
        resource_name = 'system/reboot'

    def post_list(self, request, **kwargs):
        notifier().restart("system")
        return HttpResponse('Reboot process started.', status=202)


class ShutdownResource(DojoResource):

    class Meta:
        allowed_methods = ['post']
        resource_name = 'system/shutdown'

    def post_list(self, request, **kwargs):
        notifier().stop("system")
        return HttpResponse('Shutdown process started.', status=202)


class VersionResource(DojoResource):

    class Meta:
        allowed_methods = ['get']
        resource_name = 'system/version'

    def get_list(self, request, **kwargs):
        version = get_sw_version()
        login_version = get_sw_login_version()
        name = get_sw_name()
        data = {
            'fullversion': version,
            'version': login_version,
            'name': name,
        }
        return self.create_response(request, data)


class DebugResource(DojoResource):

    class Meta:
        allowed_methods = ['post']
        resource_name = 'system/debug'

    def post_list(self, request, **kwargs):
        debug_generate()
        data = {
            'url': reverse('system_debug_download'),
        }
        return self.create_response(request, data)


class ConfigFactoryRestoreResource(DojoResource):

    class Meta:
        allowed_methods = ['post']
        resource_name = 'system/config/factory_restore'

    def post_list(self, request, **kwargs):
        factory_restore(request)
        return HttpResponse('Configuration restored to defaults. Reboot required.', status=202)


class KerberosRealmResourceMixin(object):

    def dehydrate(self, bundle):
        bundle = super(KerberosRealmResourceMixin, self).dehydrate(bundle)
        return bundle


class KerberosKeytabResourceMixin(object):

    def dehydrate(self, bundle):
        bundle = super(KerberosKeytabResourceMixin, self).dehydrate(bundle)
        if self.is_webclient(bundle.request):
            bundle.data['_edit_url'] = reverse(
                'directoryservice_kerberoskeytab_edit',
                kwargs={'id': bundle.obj.id}
            )
            bundle.data['_delete_url'] = reverse(
                'directoryservice_kerberoskeytab_delete',
                kwargs={'id': bundle.obj.id}
            )

        return bundle


class KerberosPrincipalResourceMixin(object):

    def dehydrate(self, bundle):
        bundle = super(KerberosPrincipalResourceMixin, self).dehydrate(bundle)
        return bundle


class KerberosSettingsResourceMixin(object):

    def dehydrate(self, bundle):
        bundle = super(KerberosSettingsResourceMixin, self).dehydrate(bundle)
        return bundle


class CertificateAuthorityResourceMixin(object):

    def prepend_urls(self):
        return [
            url(
                r"^(?P<resource_name>%s)/import%s$" % (
                    self._meta.resource_name, trailing_slash()
                ),
                self.wrap_view('importcert'),
            ),
            url(
                r"^(?P<resource_name>%s)/intermediate%s$" % (
                    self._meta.resource_name, trailing_slash()
                ),
                self.wrap_view('intermediate'),
            ),
            url(
                r"^(?P<resource_name>%s)/internal%s$" % (
                    self._meta.resource_name, trailing_slash()
                ),
                self.wrap_view('internal'),
            ),
        ]

    def importcert(self, request, **kwargs):
        self.method_check(request, allowed=['post'])
        self.is_authenticated(request)

        if request.body:
            deserialized = self.deserialize(
                request,
                request.body,
                format=request.META.get('CONTENT_TYPE', 'application/json'),
            )
        else:
            deserialized = {}

        if 'cert_passphrase2' not in deserialized and 'cert_passphrase' in deserialized:
            deserialized['cert_passphrase2'] = deserialized.get('cert_passphrase')

        form = CertificateAuthorityImportForm(data=deserialized)
        if not form.is_valid():
            raise ImmediateHttpResponse(
                response=self.error_response(request, form.errors)
            )
        else:
            form.save()
        return HttpResponse('Certificate Authority imported.', status=201)

    def intermediate(self, request, **kwargs):
        self.method_check(request, allowed=['post'])
        self.is_authenticated(request)

        if request.body:
            deserialized = self.deserialize(
                request,
                request.body,
                format=request.META.get('CONTENT_TYPE', 'application/json'),
            )
        else:
            deserialized = {}

        form = CertificateAuthorityCreateIntermediateForm(data=deserialized)
        if not form.is_valid():
            raise ImmediateHttpResponse(
                response=self.error_response(request, form.errors)
            )
        else:
            form.save()
        return HttpResponse('Certificate Authority created.', status=201)

    def internal(self, request, **kwargs):
        self.method_check(request, allowed=['post'])
        self.is_authenticated(request)

        if request.body:
            deserialized = self.deserialize(
                request,
                request.body,
                format=request.META.get('CONTENT_TYPE', 'application/json'),
            )
        else:
            deserialized = {}

        form = CertificateAuthorityCreateInternalForm(data=deserialized)
        if not form.is_valid():
            raise ImmediateHttpResponse(
                response=self.error_response(request, form.errors)
            )
        else:
            form.save()
        return HttpResponse('Certificate Authority created.', status=201)

    def dehydrate(self, bundle):
        bundle = super(CertificateAuthorityResourceMixin,
                       self).dehydrate(bundle)

        try:
            bundle.data['cert_internal'] = bundle.obj.cert_internal
            bundle.data['cert_issuer'] = bundle.obj.cert_issuer
            bundle.data['cert_ncertificates'] = bundle.obj.cert_ncertificates
            bundle.data['cert_DN'] = bundle.obj.cert_DN
            bundle.data['cert_from'] = bundle.obj.cert_from
            bundle.data['cert_until'] = bundle.obj.cert_until
            bundle.data['cert_privatekey'] = bundle.obj.cert_privatekey

            bundle.data['CA_type_existing'] = bundle.obj.CA_type_existing
            bundle.data['CA_type_internal'] = bundle.obj.CA_type_internal
            bundle.data['CA_type_intermediate'] = bundle.obj.CA_type_intermediate

            if self.is_webclient(bundle.request):
                bundle.data['_sign_csr_url'] = reverse(
                    'CA_sign_csr',
                    kwargs={
                        'id': bundle.obj.id
                    }
                )
                bundle.data['_edit_url'] = reverse(
                    'CA_edit',
                    kwargs={
                        'id': bundle.obj.id
                    }
                )
                bundle.data['_export_certificate_url'] = reverse(
                    'CA_export_certificate',
                    kwargs={
                        'id': bundle.obj.id
                    }
                )
                bundle.data['_export_privatekey_url'] = reverse(
                    'CA_export_privatekey',
                    kwargs={
                        'id': bundle.obj.id
                    }
                )
        except Exception as err:
            bundle.data['cert_DN'] = "ERROR: " + str(err)
            # There was an error parsing this Certificate Authority object
            # Creating a sentinel file for the alertmod to pick it up
            with open('/tmp/alert_invalidCA_{0}'.format(bundle.obj.cert_name),
                      'w') as fout:
                fout.write('')

            run_alerts()

        return bundle


class CertificateResourceMixin(object):

    def prepend_urls(self):
        return [
            url(
                r"^(?P<resource_name>%s)/csr%s$" % (
                    self._meta.resource_name, trailing_slash()
                ),
                self.wrap_view('csr'),
            ),
            url(
                r"^(?P<resource_name>%s)/import%s$" % (
                    self._meta.resource_name, trailing_slash()
                ),
                self.wrap_view('importcert'),
            ),
            url(
                r"^(?P<resource_name>%s)/import_csr%s$" % (
                    self._meta.resource_name, trailing_slash()
                ),
                self.wrap_view('import_csr'),
            ),
            url(
                r"^(?P<resource_name>%s)/internal%s$" % (
                    self._meta.resource_name, trailing_slash()
                ),
                self.wrap_view('internal'),
            ),
        ]

    def import_csr(self, request, **kwargs):
        self.method_check(request, allowed=['post'])
        self.is_authenticated(request)

        if request.body:
            deserialized = self.deserialize(
                request,
                request.body,
                format=request.META.get('CONTENT_TYPE', 'application/json'),
            )
        else:
            deserialized = {}

        if 'cert_passphrase2' not in deserialized and 'cert_passphrase' in deserialized:
            deserialized['cert_passphrase2'] = deserialized.get('cert_passphrase')

        form = CertificateCSRImportForm(data=deserialized)
        if not form.is_valid():
            raise ImmediateHttpResponse(
                response=self.error_response(request, form.errors)
            )
        else:
            form.save()
        return HttpResponse('Certificate Signing Request imported.', status=201)

    def csr(self, request, **kwargs):
        self.method_check(request, allowed=['post'])
        self.is_authenticated(request)

        if request.body:
            deserialized = self.deserialize(
                request,
                request.body,
                format=request.META.get('CONTENT_TYPE', 'application/json'),
            )
        else:
            deserialized = {}

        form = CertificateCreateCSRForm(data=deserialized)
        if not form.is_valid():
            raise ImmediateHttpResponse(
                response=self.error_response(request, form.errors)
            )
        else:
            form.save()
        return HttpResponse('Certificate Signing Request created.', status=201)

    def importcert(self, request, **kwargs):
        self.method_check(request, allowed=['post'])
        self.is_authenticated(request)

        if request.body:
            deserialized = self.deserialize(
                request,
                request.body,
                format=request.META.get('CONTENT_TYPE', 'application/json'),
            )
        else:
            deserialized = {}

        if 'cert_passphrase2' not in deserialized and 'cert_passphrase' in deserialized:
            deserialized['cert_passphrase2'] = deserialized.get('cert_passphrase')

        form = CertificateImportForm(data=deserialized)
        if not form.is_valid():
            raise ImmediateHttpResponse(
                response=self.error_response(request, form.errors)
            )
        else:
            form.save()
        return HttpResponse('Certificate imported.', status=201)

    def internal(self, request, **kwargs):
        self.method_check(request, allowed=['post'])
        self.is_authenticated(request)

        if request.body:
            deserialized = self.deserialize(
                request,
                request.body,
                format=request.META.get('CONTENT_TYPE', 'application/json'),
            )
        else:
            deserialized = {}

        form = CertificateCreateInternalForm(data=deserialized)
        if not form.is_valid():
            raise ImmediateHttpResponse(
                response=self.error_response(request, form.errors)
            )
        else:
            form.save()
        return HttpResponse('Certificate created.', status=201)

    def dehydrate(self, bundle):
        bundle = super(CertificateResourceMixin, self).dehydrate(bundle)

        try:
            bundle.data['cert_issuer'] = bundle.obj.cert_issuer
            bundle.data['cert_DN'] = bundle.obj.cert_DN
            bundle.data['cert_CSR'] = bundle.obj.cert_CSR
            bundle.data['cert_from'] = bundle.obj.cert_from
            bundle.data['cert_until'] = bundle.obj.cert_until
            bundle.data['cert_privatekey'] = bundle.obj.cert_privatekey

            bundle.data['cert_type_existing'] = bundle.obj.cert_type_existing
            bundle.data['cert_type_internal'] = bundle.obj.cert_type_internal
            bundle.data['cert_type_CSR'] = bundle.obj.cert_type_CSR

            if self.is_webclient(bundle.request):
                if bundle.obj.cert_type_CSR:
                    bundle.data['_CSR_edit_url'] = reverse(
                        'CSR_edit',
                        kwargs={
                            'id': bundle.obj.id
                        }
                    )

                bundle.data['_edit_url'] = reverse(
                    'certificate_edit',
                    kwargs={
                        'id': bundle.obj.id
                    }
                )
                bundle.data['_export_certificate_url'] = reverse(
                    'certificate_export_certificate',
                    kwargs={
                        'id': bundle.obj.id
                    }
                )
                bundle.data['_export_privatekey_url'] = reverse(
                    'certificate_export_privatekey',
                    kwargs={
                        'id': bundle.obj.id
                    }
                )
                bundle.data['_export_certificate_and_privatekey_url'] = reverse(
                    'certificate_export_certificate_and_privatekey',
                    kwargs={
                        'id': bundle.obj.id
                    }
                )
        except Exception:
            # There was an error parsing this Certificate object
            # Creating a sentinel file for the alertmod to pick it up
            with open('/tmp/alert_invalidcert_{0}'.format(bundle.obj.cert_name),
                      'w') as fout:
                fout.write('')

            run_alerts()

        return bundle


class BootEnvResource(NestedMixin, DojoResource):

    id = fields.CharField(attribute='id')
    name = fields.CharField(attribute='name')
    active = fields.CharField(attribute='active')
    space = fields.CharField(attribute='space')
    created = fields.CharField(attribute='created')

    class Meta:
        object_class = BootEnv
        resource_name = 'system/bootenv'

    def prepend_urls(self):
        return [
            url(
                r"^(?P<resource_name>%s)/status%s$" % (
                    self._meta.resource_name, trailing_slash()
                ),
                self.wrap_view('status'),
                name="freeadmin_system_bootenv_status"
            ),
            url(
                r"^(?P<resource_name>%s)/(?P<pk>[^/]+)/rename%s$" % (
                    self._meta.resource_name, trailing_slash()
                ),
                self.wrap_view('rename_detail'),
                name="api_bootenv_rename"
            ),
        ]

    def status(self, request, **kwargs):
        self.method_check(request, allowed=['get'])
        self.is_authenticated(request)

        pool = notifier().zpool_parse('freenas-boot')

        bundle = self.build_bundle(
            data={}, request=request
        )

        bundle.data['id'] = 1
        bundle.data['name'] = 'freenas-boot'
        bundle.data['children'] = []
        bundle.data.update({
            'read': pool.data.read,
            'write': pool.data.write,
            'cksum': pool.data.cksum,
        })
        uid = Uid(1)
        for key in ('data', 'cache', 'spares', 'logs'):
            root = getattr(pool, key, None)
            if not root:
                continue

            current = root
            parent = bundle.data
            tocheck = []
            while True:

                if isinstance(current, zfs.Root):
                    data = {
                        'name': current.name,
                        'type': 'root',
                        'status': current.status,
                        'read': current.read,
                        'write': current.write,
                        'cksum': current.cksum,
                        'children': [],
                    }
                elif isinstance(current, zfs.Vdev):
                    data = {
                        'name': current.name,
                        'type': 'vdev',
                        'status': current.status,
                        'read': current.read,
                        'write': current.write,
                        'cksum': current.cksum,
                        'children': [],
                    }
                    if (
                        current.name == 'stripe' or
                        current.name.startswith('mirror')
                    ):
                        data['_attach_url'] = reverse(
                            'system_bootenv_pool_attach',
                        ) + '?label=' + list(iter(current))[0].name
                elif isinstance(current, zfs.Dev):
                    data = {
                        'name': current.devname,
                        'label': current.name,
                        'type': 'dev',
                        'status': current.status,
                        'read': current.read,
                        'write': current.write,
                        'cksum': current.cksum,
                    }
                    if self.is_webclient(bundle.request):
                        try:
                            disk = Disk.objects.filter(
                                disk_expiretime=None, disk_name=current.disk
                            )[0]
                            data['_disk_url'] = "%s?deletable=false" % (
                                disk.get_edit_url(),
                            )
                        except IndexError:
                            disk = None
                        if current.status in ('ONLINE', 'FAULTED'):
                            data['_offline_url'] = reverse(
                                'storage_disk_offline',
                                kwargs={
                                    'vname': pool.name,
                                    'label': current.name,
                                })
                        if len(current.parent.children) > 1:
                            # Only add a detach url if there are other mirrored boot devices - meaning current node
                            # has siblings
                            data['_detach_url'] = reverse(
                                'system_bootenv_pool_detach',
                                kwargs={
                                    'label': current.name,
                                })

                        """
                        Replacing might go south leaving multiple UNAVAIL
                        disks, for that reason replace button should be
                        enable even for disks already under replacing
                        subtree
                        """
                        data['_replace_url'] = reverse(
                            'system_bootenv_pool_replace',
                            kwargs={
                                'label': current.name,
                            })
                        if current.parent.parent.name in (
                            'spares',
                            'cache',
                            'logs',
                        ):
                            if not current.parent.name.startswith(
                                "stripe"
                            ):
                                data['_detach_url'] = reverse(
                                    'storage_disk_detach',
                                    kwargs={
                                        'vname': pool.name,
                                        'label': current.name,
                                    })
                            else:
                                data['_remove_url'] = reverse(
                                    'storage_zpool_disk_remove',
                                    kwargs={
                                        'vname': pool.name,
                                        'label': current.name,
                                    })

                else:
                    raise ValueError("Invalid node")

                if key == 'data' and isinstance(current, zfs.Root):
                    parent.update(data)
                else:
                    data['id'] = next(uid)
                    parent['children'].append(data)

                for child in current:
                    tocheck.append((data, child))

                if tocheck:
                    parent, current = tocheck.pop()
                else:
                    break

        bundle = self.alter_detail_data_to_serialize(request, bundle)
        response = self.create_response(request, [bundle.data])
        response['Content-Range'] = 'items 0-0/1'
        return response

    def rename_detail(self, request, **kwargs):
        self.method_check(request, allowed=['post'])

        bundle, obj = self._get_parent(request, kwargs)

        deserialized = self.deserialize(
            request,
            request.body,
            format=request.META.get('CONTENT_TYPE', 'application/json'),
        )
        form = BootEnvRenameForm(
            name=obj.name,
            data=deserialized,
        )
        if not form.is_valid():
            raise ImmediateHttpResponse(
                response=self.error_response(request, form.errors)
            )
        else:
            form.save()
        return HttpResponse('Boot Environment has been renamed.', status=202)

    def get_list(self, request, **kwargs):
        results = []
        for clone in Update.ListClones():
            results.append(BootEnv(**clone))

        for sfield in self._apply_sorting(request.GET):
            if sfield.startswith('-'):
                field = sfield[1:]
                reverse = True
            else:
                field = sfield
                reverse = False
            results.sort(
                key=lambda item: getattr(item, field),
                reverse=reverse)
        paginator = self._meta.paginator_class(
            request,
            results,
            resource_uri=self.get_resource_uri(),
            limit=self._meta.limit,
            max_limit=self._meta.max_limit,
            collection_name=self._meta.collection_name,
        )
        to_be_serialized = paginator.page()
        # Dehydrate the bundles in preparation for serialization.
        bundles = []

        for obj in to_be_serialized[self._meta.collection_name]:
            bundle = self.build_bundle(obj=obj, request=request)
            bundles.append(self.full_dehydrate(bundle))

        length = len(bundles)
        to_be_serialized[self._meta.collection_name] = bundles
        to_be_serialized = self.alter_list_data_to_serialize(
            request,
            to_be_serialized
        )
        response = self.create_response(request, to_be_serialized)
        response['Content-Range'] = 'items %d-%d/%d' % (
            paginator.offset,
            paginator.offset + length - 1,
            len(results)
        )
        return response

    def post_list(self, request, **kwargs):
        deserialized = self.deserialize(
            request,
            request.body,
            format=request.META.get('CONTENT_TYPE', 'application/json')
        )

        form = BootEnvAddForm(
            data=deserialized,
            source=deserialized.get('source'),
        )
        if not form.is_valid():
            raise ImmediateHttpResponse(
                response=self.error_response(request, form.errors)
            )
        else:
            form.save()

        obj = None
        for clone in Update.ListClones():
            if clone['name'] == deserialized.get('name'):
                obj = BootEnv(**clone)
                break

        if obj is None:
            raise ImmediateHttpResponse(
                response=self.error_response(request, {
                    'error_message': 'Boot Evionment not found!',
                })
            )
        bundle = self.full_dehydrate(
            self.build_bundle(obj=obj, request=request)
        )
        return self.create_response(
            request,
            bundle,
            response_class=HttpCreated,
        )

    def obj_delete(self, bundle, **kwargs):
        delete = Update.DeleteClone(kwargs.get('pk'))
        if delete is False:
            raise ImmediateHttpResponse(
                response=self.error_response(
                    bundle.request,
                    'Failed to delete Boot Environment.',
                )
            )
        return HttpResponse(status=204)

    def obj_get(self, bundle, **kwargs):
        obj = None
        for clone in Update.ListClones():
            if clone['name'] == kwargs.get('pk'):
                obj = BootEnv(**clone)
                break
        if obj is None:
            raise NotFound("Boot Environment not found")
        return obj

    def dehydrate(self, bundle):
        if self.is_webclient(bundle.request):
            bundle.data['_add_url'] = reverse('system_bootenv_add', kwargs={
                'source': bundle.obj.name,
            })
            active_humanize = []
            if 'R' not in bundle.obj.active:
                bundle.data['_activate_url'] = reverse(
                    'system_bootenv_activate', kwargs={
                        'name': bundle.obj.name
                    },
                )
            else:
                active_humanize.append(_('On Reboot'))
            if 'N' in bundle.obj.active:
                active_humanize.append(_('Now'))
            bundle.data['active'] = ', '.join(active_humanize)
            if len(active_humanize) == 0:
                bundle.data['_delete_url'] = reverse(
                    'system_bootenv_delete', kwargs={'name': bundle.obj.name},
                )
                bundle.data['_deletebulk_url'] = reverse('system_bootenv_deletebulk')
            bundle.data['_rename_url'] = reverse(
                'system_bootenv_rename', kwargs={'name': bundle.obj.name},
            )
            if bundle.obj.keep:
                bundle.data['keep'] = "Yes"
                bundle.data['_un_keep_url'] = reverse(
                    'system_bootenv_unkeep', kwargs={'name': bundle.obj.name},
                )
            else:
                bundle.data['keep'] = "No"
                bundle.data['_keep_url'] = reverse(
                    'system_bootenv_keep', kwargs={'name': bundle.obj.name},
                )
        return bundle


class UpdateResourceMixin(NestedMixin):

    def prepend_urls(self):
        return [
            url(
                r"^(?P<resource_name>%s)/manual%s$" % (
                    self._meta.resource_name, trailing_slash()
                ),
                self.wrap_view('manual'),
                name="api_upgrade_manual"
            ),
            url(
                r"^(?P<resource_name>%s)/check%s$" % (
                    self._meta.resource_name, trailing_slash()
                ),
                self.wrap_view('check'),
                name="api_upgrade_check"
            ),
            url(
                r"^(?P<resource_name>%s)/update%s$" % (
                    self._meta.resource_name, trailing_slash()
                ),
                self.wrap_view('update'),
                name="api_upgrade_update"
            ),
            url(
                r"^(?P<resource_name>%s)/trains%s$" % (
                    self._meta.resource_name, trailing_slash()
                ),
                self.wrap_view('trains'),
                name="api_upgrade_trains"
            ),
        ]

    def manual(self, request, **kwargs):
        self.method_check(request, allowed=['post'])

        locationform = ManualUpdateTemporaryLocationForm(
            request.POST,
        )
        updateform = ManualUpdateUploadForm(
            request.POST, request.FILES
        )

        if not locationform.is_valid():
            raise ImmediateHttpResponse(
                response=self.error_response(request, locationform.errors)
            )

        if not updateform.is_valid():
            raise ImmediateHttpResponse(
                response=self.error_response(request, updateform.errors)
            )

        locationform.done()

        updateview = ManualUpdateWizard()
        updateview.do_update(
            updateform.cleaned_data.get('updatefile'),
            updateform.cleaned_data.get('sha256'),
        )
        return HttpResponse('Manual update finished.', status=202)

    def check(self, request, **kwargs):
        self.method_check(request, allowed=['get'])
        self.is_authenticated(request)

        with client as c:
            # If it is HA licensed get pending updates from stanbdy node
            if (
                hasattr(notifier, 'failover_status') and
                notifier().failover_licensed()
            ):
                try:
                    data = c.call('failover.call_remote', 'update.get_pending')
                except ClientException as e:
                    # If method does not exist it means we are still upgranding old
                    # version standby node using hasyncd
                    if e.errno not in (ClientException.ENOMETHOD, errno.ECONNREFUSED) and e.trace['class'] not in ('ConnectionRefusedError', 'KeyError'):
                        raise
                    s = notifier().failover_rpc()
                    data = s.update_pending()
            else:
                data = c.call('update.get_pending')

        return self.create_response(
            request,
            data,
        )

    def update(self, request, **kwargs):
        self.method_check(request, allowed=['post'])
        self.is_authenticated(request)

        try:
            updateobj = mUpdate.objects.order_by('-id')[0]
        except IndexError:
            updateobj = mUpdate.objects.create()

        if request.body:
            deserialized = self.deserialize(
                request,
                request.body,
                format=request.META.get('CONTENT_TYPE', 'application/json'),
            )
        else:
            deserialized = {}

        train = deserialized.get('train') or updateobj.get_train()
        cache = notifier().get_update_location()

        download = None
        updated = None

        try:
            download = Update.DownloadUpdate(train, cache)
            updated = Update.ApplyUpdate(cache)
        except Exception as e:
            return self.error_response(request, str(e))

        if not download:
            return self.error_response(request, 'No update available.')

        if updated is not None:
            return self.create_response(request, 'Successfully updated.')
        else:
            return self.error_response(request, 'Update failed.')

    def trains(self, request, **kwargs):
        self.method_check(request, allowed=['get'])
        self.is_authenticated(request)

        try:
            update = mUpdate.objects.order_by('-id')[0]
        except IndexError:
            update = mUpdate.objects.create()

        conf = Configuration.Configuration()
        conf.LoadTrainsConfig()
        trains = conf.AvailableTrains() or []
        if trains:
            trains = list(filter(lambda x: not x.lower().startswith('freenas-corral'), trains.keys()))

        seltrain = update.get_train()
        if seltrain in conf._trains:
            seltrain = conf._trains.get(seltrain)
        else:
            seltrain = Train.Train(seltrain)

        data = {
            'trains': trains,
            'selected_train': {
                'name': seltrain.Name(),
                'descr': seltrain.Description(),
                'sequence': seltrain.LastSequence(),
            },
        }

        return self.create_response(
            request,
            data,
        )


class FCPort(object):

    def __init__(
        self, port=None, vport=None, name=None, wwpn=None, mode=None,
        target=None, state=None, speed=None, initiators=None
    ):
        if vport == '0':
            self.id = port
        else:
            self.id = '%s,%s' % (port, vport)
        self.port = port
        self.vport = vport
        self.name = name
        self.wwpn = wwpn
        self.mode = mode
        self.target = target
        self.state = state
        self.speed = speed
        self.initiators = initiators


class FCPortsResource(DojoResource):

    id = fields.CharField(attribute='id')
    port = fields.CharField(attribute='port')
    vport = fields.CharField(attribute='vport')
    name = fields.CharField(attribute='name')
    wwpn = fields.CharField(attribute='wwpn')
    mode = fields.CharField(attribute='mode')
    state = fields.CharField(attribute='state')
    target = fields.IntegerField(attribute='target', null=True)
    speed = fields.IntegerField(attribute='speed', null=True)
    initiators = fields.ListField(attribute='initiators', null=True)

    class Meta:
        allowed_methods = ['get', 'put']
        object_class = FCPort
        resource_name = 'sharing/fcports'
        max_limit = 0

    def get_list(self, request, **kwargs):
        from lxml import etree

        _n = notifier()
        node = None
        if not _n.is_freenas() and _n.failover_licensed():
            node = _n.failover_node()

        fcportmap = {}
        for fbtt in FibreChannelToTarget.objects.all():
            fcportmap[fbtt.fc_port] = fbtt.fc_target

        proc = subprocess.Popen([
            "/usr/sbin/ctladm",
            "portlist",
            "-x",
        ], stdout=subprocess.PIPE, encoding='utf8')
        data = proc.communicate()[0]
        doc = etree.fromstring(data)
        results = []
        for e in doc.xpath("//frontend_type[text()='camtgt']"):
            tag_port = e.getparent()
            name = tag_port.xpath('./port_name')[0].text
            reg = re.search('\d+', name)
            if reg:
                port = reg.group(0)
            else:
                port = '0'
            vport = tag_port.xpath('./physical_port')[0].text
            if vport != '0':
                name += '/%s' % vport
            state = 'NO_LINK'
            speed = None
            wwpn = None
            if vport == '0':
                mibname = port
            else:
                mibname = '%s.chan%s' % (port, vport)
            mib = 'dev.isp.%s.loopstate' % mibname
            loopstate = sysctl.filter(mib)
            if loopstate:
                loopstate = loopstate[0].value
                if loopstate > 0 and loopstate < 10:
                    state = 'SCANNING'
                elif loopstate == 10:
                    state = 'READY'
                if loopstate > 0:
                    speedres = sysctl.filter('dev.isp.%s.speed' % mibname)
                    if speedres:
                        speed = speedres[0].value
            mib = 'dev.isp.%s.wwpn' % mibname
            _filter = sysctl.filter(mib)
            if _filter:
                wwpn = 'naa.%x' % _filter[0].value
            if name in fcportmap:
                targetobj = fcportmap[name]
                if targetobj is not None:
                    mode = 'TARGET'
                    target = fcportmap[name].id
                else:
                    mode = 'INITIATOR'
                    target = None
            else:
                mode = 'DISABLED'
                target = None
            initiators = []
            for i in tag_port.xpath('./initiator'):
                initiators.append(i.text)

            if node:
                for e in doc.xpath("//frontend_type[text()='ha']"):
                    parent = e.getparent()
                    port_name = parent.xpath('./port_name')[0].text
                    if ':' in port_name:
                        port_name = port_name.split(':', 1)[1]
                    physical_port = parent.xpath('./physical_port')[0].text
                    if physical_port != '0':
                        port_name += '/%s' % physical_port
                    if port_name != name:
                        continue
                    for i in parent.xpath('./initiator'):
                        initiators.append("%s (Node %s)" % (i.text, ('B' if node == 'A' else 'A')))

            results.append(FCPort(
                port=port,
                vport=vport,
                name=name,
                wwpn=wwpn,
                mode=mode,
                target=target,
                state=state,
                speed=speed,
                initiators=initiators,
            ))

        limit = self._meta.limit
        if 'HTTP_X_RANGE' in request.META:
            _range = request.META['HTTP_X_RANGE'].split('-')
            if len(_range) > 1 and _range[1] == '':
                limit = 0

        paginator = self._meta.paginator_class(
            request,
            results,
            resource_uri=self.get_resource_uri(),
            limit=limit,
            max_limit=self._meta.max_limit,
            collection_name=self._meta.collection_name,
        )
        to_be_serialized = paginator.page()
        # Dehydrate the bundles in preparation for serialization.
        bundles = []

        for obj in to_be_serialized[self._meta.collection_name]:
            bundle = self.build_bundle(obj=obj, request=request)
            bundles.append(self.full_dehydrate(bundle))

        length = len(bundles)
        to_be_serialized[self._meta.collection_name] = bundles
        to_be_serialized = self.alter_list_data_to_serialize(
            request,
            to_be_serialized
        )

        response = self.create_response(request, to_be_serialized)
        response['Content-Range'] = 'items %d-%d/%d' % (
            paginator.offset,
            paginator.offset + length - 1,
            len(results)
        )
        return response


class FibreChannelToTargetResourceMixin:
    pass


class DeviceResourceMixin(object):

    def build_filters(self, filters=None, ignore_bad_filters=True):
        if filters is None:
            filters = {}
        orm_filters = super(
            DeviceResourceMixin,
            self).build_filters(filters, ignore_bad_filters)
        vmid = filters.get("vm__id")
        if vmid:
            orm_filters["vm__id"] = vmid
        return orm_filters

    def dehydrate(self, bundle):
        bundle = super(DeviceResourceMixin, self).dehydrate(bundle)
        if self.is_webclient(bundle.request):
            bundle.data['vm'] = str(bundle.obj.vm)
        return bundle


class VMResourceMixin(object):

    def dehydrate(self, bundle):
        bundle = super(VMResourceMixin, self).dehydrate(bundle)
        state = 'UNKNOWN'
        device_start_url = device_stop_url = device_restart_url = device_clone_url = device_vncweb_url = info = ''
        device_poweroff_url = ''
        try:
            with client as c:
                status = c.call('vm.status', bundle.obj.id)
                state = status['state']
                info += 'State: {}<br />'.format(status['state'])
        except Exception:
            log.warn('Failed to get status', exc_info=True)
        finally:
            if self.is_webclient(bundle.request):
                if state == 'RUNNING':
                    device_stop_url = reverse(
                        'vm_stop', kwargs={'id': bundle.obj.id},
                    )
                    device_poweroff_url = reverse(
                        'vm_poweroff', kwargs={'id': bundle.obj.id},
                    )
                    device_restart_url = reverse(
                        'vm_restart', kwargs={'id': bundle.obj.id},
                    )
                    device_vncweb_url = reverse(
                        'vm_vncweb', kwargs={'id': bundle.obj.id},
                    )
                    info += 'Com Port: /dev/nmdm{}B<br />'.format(bundle.obj.id)
                elif state == 'STOPPED':
                    device_start_url = reverse(
                        'vm_start', kwargs={'id': bundle.obj.id},
                    )
                    device_clone_url = reverse(
                        'vm_clone', kwargs={'id': bundle.obj.id},
                    )
                bundle.data.update({
                    '_device_url': reverse('freeadmin_vm_device_datagrid') + '?id=%d' % bundle.obj.id,
                    '_stop_url': device_stop_url,
                    '_poweroff_url': device_poweroff_url,
                    '_start_url': device_start_url,
                    '_restart_url': device_restart_url,
                    '_clone_url': device_clone_url,
                    '_vncweb_url': device_vncweb_url
                })
            if bundle.obj.device_set.filter(dtype='VNC').exists():
                vnc_port = bundle.obj.device_set.filter(dtype='VNC').values_list('attributes', flat=True)[0].get('vnc_port', 5900 + bundle.obj.id)
                info += 'VNC Port: {}<br />'.format(vnc_port)
            bundle.data.update({
                'info': info,
                'state': state
            })
        return bundle


class JsonUser(object):
    def __init__(self, id, name, label):
        self.id = id
        self.name = name
        self.label = label


class JsonUserResource(DojoResource):

    id = fields.CharField(attribute='id')
    name = fields.CharField(attribute='name')
    label = fields.CharField(attribute='label')

    class Meta:
        allowed_methods = ['get']
        resource_name = 'account/all_users'
        object_class = JsonUser
        max_limit = 0

    def prepend_urls(self):
        return [
            url(
                r"^(?P<resource_name>%s)/(?P<exclude>\w[\w,-]*\$?)%s$" % (
                    self._meta.resource_name, trailing_slash()
                ),
                self.wrap_view('get_list'),
                name="api_dispatch_list"
            ),
        ]

    def get_list(self, request, **kwargs):
        data = {
            'identifier': 'id',
            'label': 'name',
            'items': [],
        }
        users = []
        query = request.GET.get('q') or kwargs.get('q')
        exclude = request.GET.get('exclude') or kwargs.get('exclude', [])
        if exclude:
            exclude = exclude.split(',')
        for user in FreeNAS_Users(
                flags=FLAGS_DBINIT | FLAGS_CACHE_READ_USER | FLAGS_CACHE_WRITE_USER
        ):
            if (
                    (query is None or user.pw_name.startswith(query)) and
                    user.pw_name not in exclude and not any(u for u in users if u.name == user.pw_name)
            ):
                users.append(
                    JsonUser(
                        id=user.pw_name,
                        name=user.pw_name,
                        label=user.pw_name
                    )
                )

        # Show users for the directory service provided in the wizard
        wizard_ds = request.session.get('wizard_ds')
        if request.GET.get('wizard') == '1' and wizard_ds:
            if wizard_ds.get('ds_type') == 'ad':
                wizard_users = FreeNAS_ActiveDirectory_Users(
                    domainname=wizard_ds.get('ds_ad_domainname'),
                    bindname=wizard_ds.get('ds_ad_bindname'),
                    bindpw=wizard_ds.get('ds_ad_bindpw'),
                    flags=FLAGS_DBINIT,
                )
            elif wizard_ds.get('ds_type') == 'ldap':
                wizard_users = FreeNAS_LDAP_Users(
                    host=wizard_ds.get('ds_ldap_hostname'),
                    basedn=wizard_ds.get('ds_ldap_basedn'),
                    binddn=wizard_ds.get('ds_ldap_binddn'),
                    bindpw=wizard_ds.get('ds_ldap_bindpw'),
                    flags=FLAGS_DBINIT,
                )
            elif wizard_ds.get('ds_type') == 'nis':
                wizard_users = FreeNAS_NIS_Users(
                    domain=wizard_ds.get('ds_nis_domain'),
                    servers=wizard_ds.get('ds_nis_servers'),
                    secure_mode=wizard_ds.get('ds_nis_secure_mode'),
                    manycast=wizard_ds.get('ds_nis_manycast'),
                    flags=FLAGS_DBINIT,
                )
            else:
                wizard_users = None

            if wizard_users is not None:
                # FIXME: code duplication with the block above
                for user in wizard_users._get_uncached_usernames():
                    if (
                            (query is None or user.startswith(query)) and
                            user not in exclude
                    ):
                        users.append(
                            JsonUser(
                                id='%s_%s' % (
                                    wizard_ds.get('ds_type'),
                                    user,
                                ),
                                name=user,
                                label=user
                            )
                        )

            del wizard_users

        limit = self._meta.limit

        if 'HTTP_RANGE' not in request.META:
            limit = 50

        paginator = self._meta.paginator_class(
            request,
            users,
            resource_uri=self.get_resource_uri(),
            limit=limit,
            max_limit=self._meta.max_limit,
            collection_name=self._meta.collection_name,
        )

        to_be_serialized = paginator.page()
        # Dehydrate the bundles in preparation for serialization.
        bundles = []

        for obj in to_be_serialized[self._meta.collection_name]:
            bundle = self.build_bundle(obj=obj, request=request)
            bundles.append(self.full_dehydrate(bundle))

        length = len(bundles)
        to_be_serialized[self._meta.collection_name] = bundles
        to_be_serialized = self.alter_list_data_to_serialize(
            request,
            to_be_serialized
        )
        data['items'] = to_be_serialized

        response = self.create_response(request, data)
        response['Content-Range'] = 'items %d-%d/%d' % (
            paginator.offset,
            paginator.offset + length - 1,
            len(users)
        )
        return response


class JsonGroup(object):
    def __init__(self, id, name, label):
        self.id = id
        self.name = name
        self.label = label


class JsonGroupResource(DojoResource):

    id = fields.CharField(attribute='id')
    name = fields.CharField(attribute='name')
    label = fields.CharField(attribute='label')

    class Meta:
        allowed_methods = ['get']
        resource_name = 'account/all_groups'
        object_class = JsonGroup
        max_limit = 0

    def get_list(self, request, **kwargs):
        data = {
            'identifier': 'id',
            'label': 'name',
            'items': [],
        }
        groups = []
        query = request.GET.get('q', None)
        for grp in FreeNAS_Groups(
                flags=FLAGS_DBINIT | FLAGS_CACHE_READ_GROUP | FLAGS_CACHE_WRITE_GROUP
        ):
            if ((query is None or grp.gr_name.startswith(query)) and
                    not any(g for g in groups if g.name == grp.gr_name)):
                groups.append(
                    JsonGroup(
                        id=grp.gr_name,
                        name=grp.gr_name,
                        label=grp.gr_name
                    )
                )

        # Show groups for the directory service provided in the wizard
        wizard_ds = request.session.get('wizard_ds')
        if request.GET.get('wizard') == '1' and wizard_ds:
            if wizard_ds.get('ds_type') == 'ad':
                wizard_groups = FreeNAS_ActiveDirectory_Groups(
                    domainname=wizard_ds.get('ds_ad_domainname'),
                    bindname=wizard_ds.get('ds_ad_bindname'),
                    bindpw=wizard_ds.get('ds_ad_bindpw'),
                    flags=FLAGS_DBINIT,
                )
            elif wizard_ds.get('ds_type') == 'ldap':
                wizard_groups = FreeNAS_LDAP_Groups(
                    host=wizard_ds.get('ds_ldap_hostname'),
                    basedn=wizard_ds.get('ds_ldap_basedn'),
                    binddn=wizard_ds.get('ds_ldap_binddn'),
                    bindpw=wizard_ds.get('ds_ldap_bindpw'),
                    flags=FLAGS_DBINIT,
                )
            elif wizard_ds.get('ds_type') == 'nis':
                wizard_groups = FreeNAS_NIS_Groups(
                    domain=wizard_ds.get('ds_nis_domain'),
                    servers=wizard_ds.get('ds_nis_servers'),
                    secure_mode=wizard_ds.get('ds_nis_secure_mode'),
                    manycast=wizard_ds.get('ds_nis_manycast'),
                    flags=FLAGS_DBINIT,
                )
            else:
                wizard_groups = None

            if wizard_groups:
                # FIXME: code duplication with the block above
                for group in wizard_groups._get_uncached_groupnames():
                    if query is None or group.startswith(query):
                        groups.append(
                            JsonGroup(
                                id='%s_%s' % (
                                    wizard_ds.get('ds_type'),
                                    group,
                                ),
                                name=group,
                                label=group
                            )
                        )

            del wizard_groups

        limit = self._meta.limit

        if 'HTTP_RANGE' not in request.META:
            limit = 50

        paginator = self._meta.paginator_class(
            request,
            groups,
            resource_uri=self.get_resource_uri(),
            limit=limit,
            max_limit=self._meta.max_limit,
            collection_name=self._meta.collection_name,
        )

        to_be_serialized = paginator.page()
        # Dehydrate the bundles in preparation for serialization.
        bundles = []

        for obj in to_be_serialized[self._meta.collection_name]:
            bundle = self.build_bundle(obj=obj, request=request)
            bundles.append(self.full_dehydrate(bundle))

        length = len(bundles)
        to_be_serialized[self._meta.collection_name] = bundles
        to_be_serialized = self.alter_list_data_to_serialize(
            request,
            to_be_serialized
        )
        data['items'] = to_be_serialized

        response = self.create_response(request, data)
        response['Content-Range'] = 'items %d-%d/%d' % (
            paginator.offset,
            paginator.offset + length - 1,
            len(groups)
        )
        return response
