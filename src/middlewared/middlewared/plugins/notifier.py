from middlewared.service import Service

import os
import sys

if '/usr/local/www' not in sys.path:
    sys.path.append('/usr/local/www')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'freenasUI.settings')

# Make sure to load all modules
from django.db.models.loading import cache
cache.get_apps()

from freenasUI import common as fcommon
from freenasUI.common.freenasldap import (
    FreeNAS_ActiveDirectory,
    FLAGS_DBINIT,
)
from freenasUI.middleware import zfs
from freenasUI.middleware.notifier import notifier
from freenasUI.directoryservice.utils import get_idmap_object

from middlewared.utils import django_modelobj_serialize


class NotifierService(Service):

    def __getattr__(self, attr):
        _n = notifier()
        try:
            return object.__getattribute__(self, attr)
        except AttributeError:
            return getattr(_n, attr)

    def common(self, name, method, params=None):
        """Simple wrapper to access methods under freenasUI.common.*"""
        if params is None:
            params = []
        subsystem = getattr(fcommon, name)
        rv = getattr(subsystem, method)(*params)
        return rv

    def zpool_list(self, name=None):
        """Wrapper for zfs.zpool_list"""
        return zfs.zpool_list(name)

    def zfs_list(self, *args):
        """Wrapper to serialize zfs.zfs_list"""
        rv = zfs.zfs_list(*args)

        def serialize(i):
            data = {}
            if isinstance(i, zfs.ZFSList):
                for k, v in i.items():
                    data[k] = serialize(v)
            elif isinstance(i, (zfs.ZFSVol, zfs.ZFSDataset)):
                data = i.__dict__
                data['children'] = [serialize(j) for j in data.get('children') or []]
            return data

        return serialize(rv)

    def directoryservice(self, name):
        """Temporary rapper to serialize DS connectors"""
        if name == 'AD':
            ds = FreeNAS_ActiveDirectory(flags=FLAGS_DBINIT)
        else:
            raise ValueError('Unknown ds name {0}'.format(name))
        data = {}
        for i in (
            'netbiosname', 'keytab_file', 'keytab_principal', 'domainname',
            'use_default_domain', 'dchost', 'basedn', 'binddn', 'bindpw',
            'ssl', 'certfile', 'id',
            'ad_idmap_backend', 'ds_type',
        ):
            if hasattr(ds, i):
                data[i] = getattr(ds, i)
        return data

    def ds_get_idmap_object(self, ds_type, id, idmap_backend):
        """Temporary wrapper to serialize IDMAP objects"""
        obj = get_idmap_object(ds_type, id, idmap_backend)
        data = django_modelobj_serialize(obj)
        cert = obj.get_certificate()
        if cert:
            data['certificate'] = django_modelobj_serialize(cert)
        else:
            data['certificate'] = None
        data['ssl'] = obj.get_ssl()
        data['url'] = obj.get_url()
        return data
