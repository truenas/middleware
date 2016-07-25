from middlewared.service import Service

import os
import sys

if '/usr/local/www' not in sys.path:
    sys.path.append('/usr/local/www')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'freenasUI.settings')

# Make sure to load all modules
from django.db.models.loading import cache
cache.get_apps()

from freenasUI import choices
from freenasUI import common as fcommon
from freenasUI.common.freenasldap import (
    FreeNAS_ActiveDirectory,
    FreeNAS_LDAP,
    FLAGS_DBINIT,
)
from freenasUI.common.samba import Samba4
from freenasUI.middleware import zfs
from freenasUI.middleware.notifier import notifier
from freenasUI.directoryservice.models import (
    IDMAP_TYPE_AD,
    IDMAP_TYPE_ADEX,
    IDMAP_TYPE_AUTORID,
    IDMAP_TYPE_HASH,
    IDMAP_TYPE_LDAP,
    IDMAP_TYPE_NSS,
    IDMAP_TYPE_RFC2307,
    IDMAP_TYPE_RID,
    IDMAP_TYPE_TDB,
    IDMAP_TYPE_TDB2,
    DS_TYPE_CIFS,
)
from freenasUI.directoryservice.utils import get_idmap_object

from middlewared.utils import django_modelobj_serialize


class NotifierService(Service):
    """
    This service is supposed to be temporary.
    It will serve as a transition from pre-middlewared world when
    everything was just methods randomly placed somewhere (mainly notifier.py).
    In a better world we will have specific services to split things logically.
    e.g. account, zfs, network, sharing, services, etc.
    """

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
        elif name == 'LDAP':
            ds = FreeNAS_LDAP(flags=FLAGS_DBINIT)
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

    def ds_idmap_type_code_to_string(self, code):
        """Temporary wrapper to convert idmap code to string"""
        mapping = {
            IDMAP_TYPE_AD: 'IDMAP_TYPE_AD',
            IDMAP_TYPE_ADEX: 'IDMAP_TYPE_ADEX',
            IDMAP_TYPE_AUTORID: 'IDMAP_TYPE_AUTORID',
            IDMAP_TYPE_HASH: 'IDMAP_TYPE_HASH',
            IDMAP_TYPE_LDAP: 'IDMAP_TYPE_LDAP',
            IDMAP_TYPE_NSS: 'IDMAP_TYPE_NSS',
            IDMAP_TYPE_RFC2307: 'IDMAP_TYPE_RFC2307',
            IDMAP_TYPE_RID: 'IDMAP_TYPE_RID',
            IDMAP_TYPE_TDB: 'IDMAP_TYPE_TDB',
            IDMAP_TYPE_TDB2: 'IDMAP_TYPE_TDB2',
        }
        if code not in mapping:
            raise ValueError('Unknown idmap code: {0}'.format(code))
        return mapping[code]

    def samba4(self, name, args=None):
        """Temporary wrapper to use Samba4 over middlewared"""
        if args is None:
            args = []
        return getattr(Samba4(), name)(*args)

    def systemdataset_is_decrypted(self):
        """Temporary workaround to get system dataset crypt state"""
        systemdataset, basename = notifier().system_dataset_settings()
        if not systemdataset:
            return None
        if not basename:
            return None
        return systemdataset.is_decrypted(), basename

    def choices(self, name, args=None):
        """Temporary wrapper to get to UI choices"""
        if args is None:
            args = []
        attr = getattr(choices, name)
        if callable(attr):
            return list(attr(*args))
        else:
            return attr
