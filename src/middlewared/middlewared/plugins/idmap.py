import enum
import errno
import os
import datetime
from middlewared.schema import accepts, Bool, Dict, Int, Patch, Str
from middlewared.service import CallError, CRUDService, job, private, ValidationErrors
import middlewared.sqlalchemy as sa
from middlewared.utils import run
from middlewared.validators import Range


class dstype(enum.Enum):
    """
    The below DS_TYPES are defined for use as system domains for idmap backends.
    DS_TYPE_NT4 is defined, but has been deprecated. DS_TYPE_DEFAULT_DOMAIN corresponds
    with the idmap settings under services->SMB, and is represented by 'idmap domain = *'
    in the smb4.conf. The only instance where the idmap backend for the default domain will
    not be 'tdb' is when the server is (1) joined to active directory and (2) autorid is enabled.
    """
    DS_TYPE_ACTIVEDIRECTORY = 1
    DS_TYPE_LDAP = 2
    DS_TYPE_NIS = 3
    DS_TYPE_NT4 = 4
    DS_TYPE_DEFAULT_DOMAIN = 5


class IdmapBackend(enum.Enum):
    AD = {
        'description': 'The AD backend provides a way for TrueNAS to read id '
                       'mappings from an Active Directory server that uses '
                       'RFC2307/SFU schema extensions. ',
        'parameters': {
            'schema_mode': {"required": False, "default": 'RFC2307'},
            'unix_primary_group': {"required": False, "default": False},
            'unix_nss_info': {"required": False, "default": False},
        }
    }
    AUTORID = {
        'description': 'Similar to the RID backend, but automatically configures '
                       'the range to be used for each domain, so that there is no '
                       'need to specify a specific range for each domain in the forest '
                       'The only needed configuration is the range of UID/GIDs to use '
                       'for user/group mappings and an optional size for the ranges.',
        'parameters': {
            'rangesize': {"required": False, "default": 100000},
            'readonly': {"required": False, "default": False},
            'ignore_builtin': {"required": False, "default": False},
        }
    }
    LDAP = {
        'description': 'Stores and retrieves mapping tables in an LDAP directory '
                       'service. Default for LDAP directory service.',
        'parameters': {
            'ldap_base_dn': {"required": True, "default": None},
            'ldap_user_dn': {"required": True, "default": None},
            'ldap_url': {"required": True, "default": None},
            'ssl': {"required": False, "default": "NO"},
        }
    }
    NSS = {
        'description': 'Provides a simple means of ensuring that the SID for a '
                       'Unix user is reported as the one assigned to the '
                       'corresponding domain user.',
        'parameters': {
            'linked_service': {"required": False, "default": "LOCAL_ACCOUNTS"},
        }
    }
    RFC2307 = {
        'description': 'Looks up IDs in the Active Directory LDAP server '
                       'or an extenal (non-AD) LDAP server. IDs must be stored '
                       'in RFC2307 ldap schema extensions. Other schema extensions '
                       'such as Services For Unix (SFU20/SFU30) are not supported.',
        'parameters': {
            'ldap_server': {"required": False, "default": "AD"},
            'bind_path_user': {"required": False, "default": None},
            'bind_path_group': {"required": False, "default": None},
            'user_cn': {"required": False, "default": None},
            'cn_realm': {"required": False, "default": None},
            'ldap_domain': {"required": False, "default": None},
            'ldap_url': {"required": False, "default": None},
            'ldap_user_dn': {"required": True, "default": None},
            'ldap_user_dn_password': {"required": True, "default": None},
            'ldap_realm': {"required": False, "default": None},
            'ssl': {"required": False, "default": "OFF"},
        }
    }
    RID = {
        'description': 'Default for Active Directory service. requires '
                       'an explicit configuration for each domain, using '
                       'disjoint ranges.',
        'parameters': {}
    }
    TDB = {
        'description': 'Default backend used to store mapping tables for '
                       'BUILTIN and well-known SIDs.',
        'parameters': {}
    }

    def supported_keys(self):
        return [str(x) for x in self.value['parameters'].keys()]

    def required_keys(self):
        ret = []
        for k, v in self.value['parameters'].items():
            if v['required']:
                ret.append(str(k))
        return ret

    def defaults(self):
        ret = {}
        for k, v in self.value['parameters'].items():
            if v['default'] is not None:
                ret.update({k: v['default']})
        return ret


class IdmapDomainModel(sa.Model):
    __tablename__ = 'directoryservice_idmap_domain'

    id = sa.Column(sa.Integer(), primary_key=True)
    idmap_domain_name = sa.Column(sa.String(120))
    idmap_domain_dns_domain_name = sa.Column(sa.String(255), nullable=True)
    idmap_domain_range_low = sa.Column(sa.Integer())
    idmap_domain_range_high = sa.Column(sa.Integer())
    idmap_domain_idmap_backend = sa.Column(sa.String(120), default='rid')
    idmap_domain_options = sa.Column(sa.JSON(type=dict))
    idmap_domain_certificate_id = sa.Column(sa.ForeignKey('system_certificate.id'), index=True, nullable=True)


class IdmapDomainService(CRUDService):
    class Config:
        datastore = 'directoryservice.idmap_domain'
        datastore_prefix = 'idmap_domain_'
        namespace = 'idmap'
        datastore_extend = f'{namespace}.idmap_extend'

    @private
    async def idmap_extend(self, data):
        if data.get('idmap_backend'):
            data['idmap_backend'] = data['idmap_backend'].upper()

        opt_enums = ['ssl', 'linked_service']
        if data.get('options'):
            for i in opt_enums:
                if data['options'].get(i):
                    data['options'][i] = data['options'][i].upper()

        return data

    @private
    async def idmap_compress(self, data):
        opt_enums = ['ssl', 'linked_service']
        if data.get('options'):
            for i in opt_enums:
                if data['options'].get(i):
                    data['options'][i] = data['options'][i].lower()

        data['idmap_backend'] = data['idmap_backend'].lower()

        return data

    @private
    async def get_next_idmap_range(self):
        """
        Increment next high range by 100,000,000 ids. This number has
        to accomodate the highest available rid value for a domain.
        Configured idmap ranges _must_ not overlap.
        """
        domains = await self.query()
        sorted_idmaps = sorted(domains, key=lambda domain: domain['range_high'])
        low_range = sorted_idmaps[-1]['range_high'] + 1
        high_range = sorted_idmaps[-1]['range_high'] + 100000000
        return (low_range, high_range)

    @private
    async def remove_winbind_idmap_tdb(self):
        sysdataset = (await self.middleware.call('systemdatast.config'))['basename']
        ts = str(datetime.datetime.now(datetime.timezone.utc).timestamp())[:10]
        await self.middleware.call('zfs.snapshot.create', {'dataset': f'{sysdataset}/samba4',
                                                           'name': f'wb_cache-{ts}'})
        try:
            os.remove('/var/db/system/samba4/winbindd_idmap.tdb')
        except Exception:
            self.logger.debug("Failed to remove winbindd_idmap.tdb.", exc_info=True)

    @accepts()
    @job(lock='clear_idmap_cache')
    async def clear_idmap_cache(self, job):
        """
        Stop samba, remove the winbindd_cache.tdb file, start samba, flush samba's cache.
        This should be performed after finalizing idmap changes.
        """
        await self.middleware.call('service.stop', 'cifs')

        try:
            os.remove('/var/db/system/samba4/winbindd_cache.tdb')
        except Exception as e:
            self.logger.debug("Failed to remove winbindd_cache.tdb: %s" % e)

        await self.middleware.call('service.start', 'cifs')
        gencache_flush = await run(['net', 'cache', 'flush'], check=False)
        if gencache_flush.returncode != 0:
            raise CallError(f'Attempt to flush gencache failed with error: {gencache_flush.stderr.decode().strip()}')

    @private
    async def autodiscover_trusted_domains(self):
        smb = await self.middleware.call('smb.config')
        wbinfo = await run(['/usr/local/bin/wbinfo', '-m', '--verbose'], check=False)
        if wbinfo.returncode != 0:
            raise CallError(f'wbinfo -m failed with error: {wbinfo.stderr.decode().strip()}')

        for entry in wbinfo.stdout.decode().splitlines():
            c = entry.split()
            if len(c) == 6 and c[0] != smb['workgroup']:
                await self.middleware.call('idmap.domain.create', {'name': c[0], 'dns_domain_name': c[1]})

    @accepts()
    async def backend_options(self):
        """
        This returns additional information about idmap backend options. Not all
        `options` are valid for every backend.
        """
        return {x.name: x.value for x in IdmapBackend}

    @private
    async def validate(self, schema_name, data, verrors):
        if data['name'] in [dstype.DS_TYPE_LDAP.value, dstype.DS_TYPE_DEFAULT_DOMAIN.value]:
            if data['idmap_backend'] not in ['ldap', 'tdb']:
                verrors.add(f'{schema_name}.idmap_backend',
                            f'idmap backend [{data["idmap_backend"]}] is not appropriate. '
                            f'for the system domain type {dstype[data["domain"]]}')

        if data['range_high'] < data['range_low']:
            verrors.add(f'{schema_name}.range_low', 'Idmap high range must be greater than idmap low range')
            return verrors

        configured_domains = await self.query()
        ldap_enabled = False if await self.middleware.call('ldap.get_state') == 'DISABLED' else True
        ad_enabled = False if await self.middleware.call('activedirectory.get_state') == 'DISABLED' else True
        new_range = range(data['range_low'], data['range_high'])
        idmap_backend = data.get('idmap_backend')
        for i in configured_domains:
            # Do not generate validation error comparing to oneself.
            if i['name'] == data['name']:
                continue

            # Do not generate validation errors for overlapping with a disabled DS.
            if not ldap_enabled and i['name'] == 'DS_TYPE_LDAP':
                continue

            if not ad_enabled and i['name'] == 'DS_TYPE_ACTIVEDIRECTORY':
                continue

            # Idmap settings under Services->SMB are ignored when autorid is enabled.
            if idmap_backend == IdmapBackend.AUTORID.name and i['name'] == 'DS_TYPE_DEFAULT_DOMAIN':
                continue

            # Overlap between ranges defined for 'ad' backend are permitted.
            if idmap_backend == IdmapBackend.AD.name and i['idmap_backend'] == IdmapBackend.AD.name:
                continue

            existing_range = range(i['range_low'], i['range_high'])
            if range(max(existing_range[0], new_range[0]), min(existing_range[-1], new_range[-1]) + 1):
                verrors.add(f'{schema_name}.range_low',
                            'new idmap range conflicts with existing range for domain '
                            f'[{i["name"]}].')

    @private
    async def validate_options(self, schema_name, data, verrors, check=['MISSING', 'EXTRA']):
        supported_keys = set(IdmapBackend[data['idmap_backend']].supported_keys())
        required_keys = set(IdmapBackend[data['idmap_backend']].required_keys())
        provided_keys = set([str(x) for x in data['options'].keys()])

        missing_keys = required_keys - provided_keys
        extra_keys = provided_keys - supported_keys

        if 'MISSING' in check:
            for k in missing_keys:
                verrors.add(f'{schema_name}.options.{k}',
                            f'[{k}] is a required parameter for the [{data["idmap_backend"]}] idmap backend.')

        if 'EXTRA' in check:
            for k in extra_keys:
                verrors.add(f'{schema_name}.options.{k}',
                            f'[{k}] is not a valid parameter for the [{data["idmap_backend"]}] idmap backend.')

    @private
    async def prune_keys(self, data):
        supported_keys = set(IdmapBackend[data['idmap_backend']].supported_keys())
        provided_keys = set([str(x) for x in data['options'].keys()])

        for k in (provided_keys - supported_keys):
            data.pop(k)

    @accepts(
        Dict(
            'idmap_domain_create',
            Str('name', required=True),
            Str('dns_domain_name'),
            Int('range_low', required=True, validators=[Range(min=1000, max=2147483647)]),
            Int('range_high', required=True, validators=[Range(min=1000, max=2147483647)]),
            Str('idmap_backend', enum=['AD', 'AUTORID', 'FRUIT', 'LDAP', 'NSS', 'RFC2307', 'RID', 'SCRIPT', 'TDB']),
            Int('certificate_id', null=True),
            Dict(
                'options',
                Str('schema_mode'),
                Bool('unix_primary_group'),
                Bool('unix_nss_info'),
                Int('rangesize', validators=[Range(min=10000, max=1000000000)]),
                Bool('readonly'),
                Bool('ignore_builtin'),
                Str('ldap_base_dn'),
                Str('ldap_user_dn'),
                Str('ldap_user_dn_password'),
                Str('ldap_url'),
                Str('ssl', enum=['OFF', 'ON', 'START_TLS']),
                Str('linked_service', enum=['LOCAL_ACCOUNT', 'LDAP', 'NIS']),
                Str('ldap_server'),
                Str('bind_path_user'),
                Str('bind_path_group'),
                Str('user_cn'),
                Str('cn_realm'),
                Str('ldap_domain'),
                Str('ldap_url'),
            ),
            register=True
        )
    )
    async def do_create(self, data):
        """
        Create a new IDMAP domain. These domains must be unique. This table
        will be automatically populated after joining an Active Directory domain
        if "allow trusted domains" is set to True in the AD service configuration.
        There are three default system domains: DS_TYPE_ACTIVEDIRECTORY, DS_TYPE_LDAP, DS_TYPE_DEFAULT_DOMAIN.
        The system domains correspond with the idmap settings under Active Directory, LDAP, and SMB
        respectively.
        `name` the pre-windows 2000 domain name.
        `DNS_domain_name` DNS name of the domain.
        """
        verrors = ValidationErrors()
        if data['name'] in [x['name'] for x in await self.query()]:
            verrors.add('idmap_domain_create.name', 'Domain names must be unique.')
        await self.validate('idmap_domain_create', data, verrors)
        await self.validate_options('idmap_domain_create', data, verrors)
        if data.get('certificate_id') and not data['options'].get('ssl'):
            verrors.add('idmap_domain_create.certificate_id',
                        f'The {data["idmap_backend"]} idmap backend does not '
                        'generate LDAP traffic. Certificates do not apply.')
        verrors.check()

        final_options = IdmapBackend[data['idmap_backend']].defaults()
        final_options.update(data['options'])
        data['options'] = final_options
        data["id"] = await self.middleware.call(
            "datastore.insert", self._config.datastore, data,
            {
                "prefix": self._config.datastore_prefix
            },
        )
        return await self._get_instance(data['id'])

    @accepts(
        Int('id', required=True),
        Patch(
            "idmap_domain_create",
            "idmap_domain_update",
            ("attr", {"update": True})
        )
    )
    async def do_update(self, id, data):
        """
        Update a domain by id.
        """
        old = await self._get_instance(id)
        new = old.copy()
        new.update(data)
        tmp = data.copy()
        verrors = ValidationErrors()
        if old['name'] in [x.name for x in dstype] and old['name'] != new['name']:
            verrors.add('idmap_domain_update',
                        f'Changing name of default domain {old["name"]} is not permitted')

        await self.validate('idmap_domain_update', new, verrors)
        await self.validate_options('idmap_domain_update', new, verrors, ['MISSING'])
        self.logger.debug('got after missing')
        tmp['idmap_backend'] = new['idmap_backend']
        await self.validate_options('idmap_domain_update', tmp, verrors, ['EXTRA'])
        if data.get('certificate_id') and not data['options'].get('ssl'):
            verrors.add('idmap_domain_update.certificate_id',
                        f'The {new["idmap_backend"]} idmap backend does not '
                        'generate LDAP traffic. Certificates do not apply.')
        verrors.check()
        self.logger.debug('got after vailidation')
        await self.prune_keys(new)
        await self.idmap_compress(new)
        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            id,
            new,
            {'prefix': self._config.datastore_prefix}
        )
        return await self._get_instance(id)

    @accepts(Int('id'))
    async def do_delete(self, id):
        """
        Delete a domain by id. Deletion of default system domains is not permitted.
        """
        if id <= 5:
            entry = await self._get_instance(id)
            raise CallError(f'Deleting system idmap domain [{entry["name"]}] is not permitted.', errno.EPERM)
        await self.middleware.call("datastore.delete", self._config.datastore, id)
