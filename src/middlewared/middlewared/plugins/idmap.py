import asyncio
import base64
import datetime
import enum
import errno
import os
import subprocess
import time
from middlewared.schema import accepts, Any, Bool, Cron, Dict, Int, List, Patch, Path, Str
from middlewared.service import CallError, ConfigService, CRUDService, Service, item_method, private, ValidationErrors
from middlewared.utils import run, Popen
from middlewared.validators import Range

class dstype(enum.Enum):
    DS_TYPE_ACTIVEDIRECTORY = 1
    DS_TYPE_LDAP = 2
    DS_TYPE_NIS = 3
    DS_TYPE_NT4 = 4 #deprecated
    DS_TYPE_DEFAULT_DOMAIN = 5


class IdmapService(Service):
    """
    :get_or_create_idmap_by_domain: - accepts pre-windows 2000 domain name and its idmap configuration details.
    if a backend configuration does not exist for the domain, then generate a safe default one.

    :get_configured_idmap_domains: - returns list of all configured idmap domains. A configured domain is one
    that exists in the domaintobackend table and has a corresponding backend configured in the respective
    idmap_{backend} table. List is sorted based in ascending order based on the id range. 

    :clear_idmap_cache: - removes samba's idmap cache. This may be required if idmap settings are changed
    after the server has entered production. This will cause a service disruption.

    There are default system domains 'DS_TYPE_ACTIVEDIRECTORY', 'DS_TYPE_LDAP', 'DS_TYPE_DEFAULT_DOMAIN',
    which exist for compatibility reasons and correspond with the idmap backend that is configured
    under 'Active Directory', 'LDAP', and 'SMB' respectively.
    """
    class Config:
        private = False
        namespace = 'idmap'

    @accepts(
        Str('domain')
    )
    async def get_or_create_idmap_by_domain(self, domain):
        """
        Returns idmap settings based on pre-windows 2000 domain name (workgroup)
        If mapping exists, but there's no corresponding entry in the specified idmap
        table, then we generate a new one and return it.
        """
        my_domain = await self.middleware.call('idmap.domaintobackend.query', [('domain', '=', domain)])
        if not my_domain:
            raise CallError(f'No domain to idmap backend exists for domain [{domain}]', errno.ENOENT)

        backend_entry = await self.middleware.call(
            f'idmap.{my_domain[0]["idmap_backend"]}.query',
            [('domain', '=', domain)]
        )
        if backend_entry:
            return backend_entry[0]

        next_idmap_range = await self.get_next_idmap_range()
        new_idmap = await self.middleware.call(f'idmap.{idmap_type}.create', {
            'domain': {'idmap_domain_name': domain},
            'range_low': next_idmap_range[0],
            'range_high': next_idmap_range[1]
        })
        return new_idmap

    @private
    async def idmap_domain_choices(self):
        choices = []
        domains = await self.middleware.call('idmap.domain.query')
        for domain in domains:
            choices.append(domain['name'])

        return choices 

    @private
    async def get_idmap_legacy(self, obj_type, idmap_type):
        """
        This is compatibility shim for legacy idmap code
        utils.get_idmap()
        obj_type is dstype.
        idmap_type is the idmap backend
        If the we don't have a corresponding entry in the idmap backend table,
        automatically generate one.
        """
        if idmap_type in ['adex', 'hash']:
            raise CallError(f'idmap backend {idmap_type} has been deprecated')
    
        ds_type = dstype(int(obj_type)).name

        if ds_type not in ['DS_TYPE_ACTIVEDIRECTORY', 'DS_TYPE_LDAP', 'DS_TYPE_DEFAULT_DOMAIN']:
            raise CallError(f'idmap backends are not supported for {ds_type}')

        res = await self.middleware.call(f'idmap.{idmap_type}.query', [('domain', '=', ds_type)])
        if res:
            return {
                'idmap_id': res[0]['id'],
                'idmap_type': idmap_type,
                'idmap_name': idmap_type 
            }
        next_idmap_range = await self.get_next_idmap_range()
        new_idmap = await self.middleware.call(f'idmap.{idmap_type}.create', {
            'domain': {'id': obj_type},
            'range_low': next_idmap_range[0],
            'range_high': next_idmap_range[1]
        })
        return {'idmap_id': new_idmap['id'], 'idmap_type': idmap_type, 'idmap_name': idmap_type}

    @private
    async def common_backend_compress(self, data):
        if data['domain']['id']:
            data['domain'] = data['domain']['id']
        elif data['domain']['idmap_domain_name']:
            domain_info = await self.middleware.call(
                'idmap.domain.query', [('domain', '=', data['domain']['idmap_domain'])]
            )
            data['domain'] = domain_info[0]['id']
        else:
            domain_info = await self.middleware.call(
                'idmap.domain.query', [('domain', '=', data['domain']['idmap_domain__dns_domain_name'].upper())]
            )
            data['domain'] = domain_info[0]['id']

        return data

    @private
    async def _common_validate(self, data):
        """
        Common validation checks for all idmap backends.
        """
        verrors = ValidationErrors()
        if data['range_high'] < data['range_low']:
            verrors.add(f'idmap_{idmap_type}.update', 'Idmap high range must be greater than idmap low range')
            return verrors
            
        configured_domains = await self.get_configured_idmap_domains()
        new_range = range(data['range_low'], data['range_high'])
        for i in configured_domains:
            if i['domain']['idmap_domain_name'] == data['domain']['idmap_domain_name']:
                continue
            existing_range = range(i['backend_data']['range_low'], i['backend_data']['range_high'])
            if range(max(existing_range[0], new_range[0]), min(existing_range[-1], new_range[-1])+1):
                verrors.add(
                    f'idmap_range', 
                    f'new idmap range conflicts with existing range for domain [{i["domain"]["idmap_domain_name"]}]'
                )

        return verrors
        

    @accepts()
    async def get_configured_idmap_domains(self):
        """
        Inner join domain-to-backend table with its corresponding idmap backend
        table on the configured short-form domain name. Sorted by idmap high range.
        """
        domains =  await self.middleware.call('idmap.domaintobackend.query')
        configured_domains = []
        for domain in domains:
            b = await self.middleware.call(
                f'idmap.{domain["idmap_backend"]}.query',
                [('domain', '=', domain['domain']['idmap_domain_name'])]
            )
            for entry in b:
                entry.pop('domain')
                entry.pop('id')
                domain.update({'backend_data': entry})
                configured_domains.append(domain)

        return sorted(configured_domains, key=lambda domain: domain['backend_data']['range_high'])

    @private
    async def get_next_idmap_range(self):
        """
        Increment next high range by 100,000,000 ids. This number has
        to accomodate the highest available rid value for a domain.
        Configured idmap ranges _must_ not overlap.
        """
        sorted_idmaps = await self.get_configured_idmap_domains()
        low_range = sorted_idmaps[-1]['backend_data']['range_high'] + 1
        high_range = sorted_idmaps[-1]['backend_data']['range_high'] + 100000000
        return (low_range, high_range)

    @accepts()
    async def clear_idmap_cache(self):
        await self.middleware.call('service.stop', 'smb')
        os.remove('/var/db/samba4/winbindd_cache.tdb')
        await self.middleware.call('service.start', 'smb')
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
                await self.idmap.domain.create({'name': c[0], 'dns_domain_name': c[1]})

class IdmapDomainService(CRUDService):
    class Config:
        datastore = 'directoryservice.idmap_domain'
        datastore_prefix = 'idmap_domain_'
        namespace = 'idmap.domain'


    @accepts(
        Dict(
            'idmap_domain_create',
            Str('name', required=True),
            Str('DNS_domain_name'),
            register=True
        )
    )
    async def do_create(self, data):
        verrors = ValidationErrors()
        verrors.add_child('idmap_domain_create', await self._validate(data))
        if verrors:
            raise verrors

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
        old = await self._get_instance(id)
        new = old.copy()
        new.update(data)
        verrors = ValidationErrors()
        verrors.add_child('idmap_domain_update', await self._validate(new))

        if verrors:
            raise verrors

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
        if id <= 5:
            entry = await self._get_instance(id)
            raise CallError(f'Deletion of system idmap domain [{entry["name"]}] is not permitted.', errno.EPERM)
        await self.middleware.call("datastore.delete", self._config.datastore, id)

    @accepts(Int("id"))
    async def run(self, id):
        data = await self._get_instance(id)

    @private
    async def _validate(self, data):
        verrors = ValidationErrors()
        if data['id'] <= dstype['DS_TYPE_DEFAULT_DOMAIN'].value:
            verrors.append(f'Modification of system idmap domain [{data["name"]}] is not permitted.')
        return verrors


class IdmapDomainBackendService(CRUDService):
    class Config:
        datastore = 'directoryservice.idmap_domaintobackend'
        datastore_prefix = 'idmap_dtb_'
        namespace = 'idmap.domaintobackend'


    @accepts(
        Dict(
            'idmap_domaintobackend_create',
            Dict(
                 'domain',
                 Int('id'),
                 Str('idmap_domain_name'),
                 Str('idmap_domain_dns_domain_name'),
            ),
            Str('idmap_backend'),
            register=True
        )
    )
    async def do_create(self, data):
        """
        Enforce referential integrity during domain-to-backend creation
        by also creating a corresponding entry in the correct idmap backend table.
        """
        verrors = ValidationErrors()
        verrors.add_child('idmap_domaintobackend_create', await self._validate(data))
        if verrors:
            raise verrors

        data = await self.middleware.call('idmap.common_backend_compress', data)
        self.logger.debug(data)
        backend_entry_is_present = False
        idmap_data = await self.middleware.call(f'idmap.{data["idmap_backend"]}.query')
        for i in idmap_data:
            if not i['domain']:
                continue
            if i['domain']['idmap_domain_name'] == data['domain']['idmap_domain_name']:
                backend_entry_is_present
                break

        if not backend_entry_is_present:
            next_idmap_range = await self.get_next_idmap_range()
            new_idmap = await self.middleware.call(f'idmap.{data["idmap_backend"]}.create', {
                'domain': {'id': data['domain']['id']},
                'range_low': next_idmap_range[0],
                'range_high': next_idmap_range[1]
            })
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
            "idmap_domaintobackend_create",
            "idmap_domaintobackend_update",
            ("attr", {"update": True})
        )
    )
    async def do_update(self, id, data):
        old = await self._get_instance(id)
        new = old.copy()
        new.update(data)
        verrors = ValidationErrors()
        verrors.add_child('idmap_domaintobackend_update', await self._validate(new))

        if verrors:
            raise verrors

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
        entry = await self._get_instance(id)
        if entry['domain']['id'] <= dstype['DS_TYPE_DEFAULT_DOMAIN'].value: 
            raise CallError(f'Deletion of mapping for [{entry["domain"]["idmap_domain_name"]}] is not permitted.', errno.EPERM)
        await self.middleware.call("datastore.delete", self._config.datastore, id)

    @accepts(Int("id"))
    async def run(self, id):
        data = await self._get_instance(id)

    @private
    async def _validate(self, data):
        verrors = ValidationErrors()


class IdmapADService(CRUDService):
    class Config:
        datastore = 'directoryservice.idmap_ad'
        datastore_prefix = 'idmap_ad_'
        namespace = 'idmap.ad'


    @accepts(
        Dict(
            'idmap_ad_create',
            Dict(
                 'domain',
                 Int('id'),
                 Str('idmap_domain_name'),
                 Str('idmap_domain_dns_domain_name'),
            ),
            Int('range_low', required=True, validators=[Range(min=1000, max=2147483647)]),
            Int('range_high', required=True, validators=[Range(min=1000, max=2147483647)]),
            Str('schema_mode'),
            Bool('unix_primary_group'),
            Bool('unix_nss_info'),
            register=True
        )
    )
    async def do_create(self, data):
        verrors = ValidationErrors()
        verrors.add_child('idmap_ad_create', await self.middleware.call('idmap._common_validate', data))
        if verrors:
            raise verrors

        data = await self.middleware.call('idmap.common_backend_compress', data)
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
            "idmap_ad_create",
            "idmap_ad_update",
            ("attr", {"update": True})
        )
    )
    async def do_update(self, id, data):
        old = await self._get_instance(id)
        new = old.copy()
        new.update(data)
        verrors = ValidationErrors()
        verrors.add_child('idmap_ad_update', await self.middleware.call('idmap._common_validate', new))

        if verrors:
            raise verrors

        self.logger.debug(data)
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
        await self.middleware.call("datastore.delete", self._config.datastore, id)

    @accepts(Int("id"))
    async def run(self, id):
        data = await self._get_instance(id)

    @private
    async def _validate(self, data):
        verrors = ValidationErrors()
        return verrors


class IdmapAutoridService(CRUDService):
    class Config:
        datastore = 'directoryservice.idmap_autorid'
        datastore_prefix = 'idmap_autorid_'
        namespace = 'idmap.autorid'

    @accepts(
        Dict(
            'idmap_autorid_create',
            Dict(
                 'domain',
                 Int('id'),
                 Str('idmap_domain_name'),
                 Str('idmap_domain_dns_domain_name'),
            ),
            Int('range_low', required=True, validators=[Range(min=1000, max=2147483647)]),
            Int('range_high', required=True, validators=[Range(min=1000, max=2147483647)]),
            Int('rangesize'),
            Bool('readonly'),
            Bool('ignore_builtin'),
            register=True
        )
    )
    async def do_create(self, data):
        verrors = ValidationErrors()
        verrors.add_child('idmap_autorid_create', await self.middleware.call('idmap._common_validate', data))
        if verrors:
            raise verrors

        data = await self.middleware.call('idmap.common_backend_compress', data)
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
            "idmap_autorid_create",
            "idmap_autorid_update",
            ("attr", {"update": True})
        )
    )
    async def do_update(self, id, data):
        old = await self._get_instance(id)
        new = old.copy()
        new.update(data)
        verrors = ValidationErrors()
        verrors.add_child('idmap_autorid_update', await self.middleware.call('idmap._common_validate', new))

        if verrors:
            raise verrors

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
        await self.middleware.call("datastore.delete", self._config.datastore, id)

    @accepts(Int("id"))
    async def run(self, id):
        data = await self._get_instance(id)

    @private
    async def _validate(self, data):
        verrors = ValidationErrors()
        return verrors


class IdmapLDAPService(CRUDService):
    class Config:
        datastore = 'directoryservice.idmap_ldap'
        datastore_prefix = 'idmap_ldap_'
        namespace = 'idmap.ldap'


    @accepts(
        Dict(
            'idmap_ldap_create',
            Dict(
                 'domain',
                 Int('id'),
                 Str('idmap_domain_name'),
                 Str('idmap_domain_dns_domain_name'),
            ),
            Int('range_low', required=True, validators=[Range(min=1000, max=2147483647)]),
            Int('range_high', required=True, validators=[Range(min=1000, max=2147483647)]),
            Str('base_dn', required=True),
            Str('user_dn', required=True),
            Str('url', required=True),
            Str('ssl', default='off', enum=['off', 'on', 'start_tls']),
            Str('certificate'),
            register=True
        )
    )
    async def do_create(self, data):
        verrors = ValidationErrors()
        verrors.add_child('idmap_ldap_create', await self.middleware.call('idmap._common_validate', data))
        if verrors:
            raise verrors
        data = await self.middleware.call('idmap.common_backend_compress', data)
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
            "idmap_ldap_create",
            "idmap_ldap_update",
            ("attr", {"update": True})
        )
    )
    async def do_update(self, id, data):
        old = await self._get_instance(id)
        new = old.copy()
        new.update(data)
        verrors = ValidationErrors()
        verrors.add_child('idmap_ldap_update', await self.middleware.call('idmap._common_validate', new))

        if verrors:
            raise verrors

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
        await self.middleware.call("datastore.delete", self._config.datastore, id)

    @accepts(Int("id"))
    async def run(self, id):
        data = await self._get_instance(id)

    @private
    async def _validate(self, data):
        verrors = ValidationErrors()
        return verrors


class IdmapNSSService(CRUDService):
    class Config:
        datastore = 'directoryservice.idmap_nss'
        datastore_prefix = 'idmap_nss_'
        namespace = 'idmap.nss'


    @accepts(
        Dict(
            'idmap_nss_create',
            Dict(
                 'domain',
                 Int('id'),
                 Str('idmap_domain_name'),
                 Str('idmap_domain_dns_domain_name'),
            ),
            Int('range_low', required=True),
            Int('range_high', required=True),
            register=True
        )
    )
    async def do_create(self, data):
        verrors = ValidationErrors()
        verrors.add_child('idmap_nss_create', await self.middleware.call('idmap._common_validate', data))
        if verrors:
            raise verrors

        data = await self.middleware.call('idmap.common_backend_compress', data)
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
            "idmap_nss_create",
            "idmap_nss_update",
            ("attr", {"update": True})
        )
    )
    async def do_update(self, id, data):
        old = await self._get_instance(id)
        new = old.copy()
        new.update(data)
        verrors = ValidationErrors()
        verrors.add_child('idmap_nss_update', await self.middleware.call('idmap._common_validate', new))

        if verrors:
            raise verrors

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
        await self.middleware.call("datastore.delete", self._config.datastore, id)

    @accepts(Int("id"))
    async def run(self, id):
        data = await self._get_instance(id)

    @private
    async def _validate(self, data):
        verrors = ValidationErrors()
        return verrors


class IdmapRFC2307Service(CRUDService):
    """
    In the rfc2307 backend range acts as a filter. Anything falling outside of it is ignored.
    If no user_dn is specified, then an anonymous bind is performed.
    ldap_url is only required when using a standalone server.
    """
    class Config:
        datastore = 'directoryservice.idmap_rfc2307'
        datastore_prefix = 'idmap_rfc2307_'
        namespace = 'idmap.rfc2307'


    @accepts(
        Dict(
            'idmap_rfc2307_create',
            Dict(
                 'domain',
                 Int('id'),
                 Str('idmap_domain_name'),
                 Str('idmap_domain_dns_domain_name'),
            ),
            Int('range_low', required=True, validators=[Range(min=1000, max=2147483647)]),
            Int('range_high', required=True, validators=[Range(min=1000, max=2147483647)]),
            Str('ldap_server', required=True, enum=['ad', 'stand-alone']),
            Str('bind_path_user'),
            Str('bind_path_group'),
            Str('user_cn'),
            Str('cn_realm'),
            Str('ldap_domain'),
            Str('ldap_url'),
            Str('ldap_user_dn'),
            Str('ldap_user_dn_password'),
            Str('ldap_realm'),
            Str('ssl', default='off', enum=['off', 'on', 'start_tls']),
            Str('certificate'),
            register=True
        )
    )
    async def do_create(self, data):
        verrors = ValidationErrors()
        verrors.add_child('idmap_rfc2307_create', await self.middleware.call('idmap._common_validate', data))
        if verrors:
            raise verrors

        data = await self.middleware.call('idmap.common_backend_compress', data)
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
            "idmap_nss_create",
            "idmap_nss_update",
            ("attr", {"update": True})
        )
    )
    async def do_update(self, id, data):
        old = await self._get_instance(id)
        new = old.copy()
        new.update(data)
        verrors = ValidationErrors()
        verrors.add_child('idmap_rfc2307_update', await self.middleware.call('idmap._common_validate', new))

        if verrors:
            raise verrors

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
        await self.middleware.call("datastore.delete", self._config.datastore, id)

    @accepts(Int("id"))
    async def run(self, id):
        data = await self._get_instance(id)

    @private
    async def _validate(self, data):
        verrors = ValidationErrors()
        return verrors


class IdmapRIDService(CRUDService):
    class Config:
        datastore = 'directoryservice.idmap_rid'
        datastore_prefix = 'idmap_rid_'
        namespace = 'idmap.rid'


    @accepts(
        Dict(
            'idmap_rid_create',
            Dict(
                 'domain',
                 Int('id'),
                 Str('idmap_domain_name'),
                 Str('idmap_domain_dns_domain_name'),
            ),
            Int('range_low', required=True, validators=[Range(min=1000, max=2147483647)]),
            Int('range_high', required=True, validators=[Range(min=1000, max=2147483647)]),
            register=True
        )
    )
    async def do_create(self, data):
        verrors = ValidationErrors()
        verrors.add_child('idmap_rid_create', await self.middleware.call('idmap._common_validate', data))
        if verrors:
            raise verrors

        data = await self.middleware.call('idmap.common_backend_compress', data)
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
            "idmap_rid_create",
            "idmap_rid_update",
            ("attr", {"update": True})
        )
    )
    async def do_update(self, id, data):
        old = await self._get_instance(id)
        new = old.copy()
        new.update(data)
        verrors = ValidationErrors()
        verrors.add_child('idmap_rid_update', await self.middleware.call('idmap._common_validate', new))

        if verrors:
            raise verrors

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
        await self.middleware.call("datastore.delete", self._config.datastore, id)

    @accepts(Int("id"))
    async def run(self, id):
        data = await self._get_instance(id)

    @private
    async def _validate(self, data):
        verrors = ValidationErrors()
        return verrors


class IdmapScriptService(CRUDService):
    class Config:
        datastore = 'directoryservice.idmap_script'
        datastore_prefix = 'idmap_script_'
        namespace = 'idmap.script'


    @accepts(
        Dict(
            'idmap_script_create',
            Dict(
                 'domain',
                 Int('id'),
                 Str('idmap_domain_name'),
                 Str('idmap_domain_dns_domain_name'),
            ),
            Int('range_low', required=True, validators=[Range(min=1000, max=2147483647)]),
            Int('range_high', required=True, validators=[Range(min=1000, max=2147483647)]),
            register=True
        )
    )
    async def do_create(self, data):
        verrors = ValidationErrors()
        verrors.add_child('idmap_script_create', await self.middleware.call('idmap._common_validate', data))
        if verrors:
            raise verrors

        data = await self.middleware.call('idmap.common_backend_compress', data)
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
            "idmap_script_create",
            "idmap_script_update",
            ("attr", {"update": True})
        )
    )
    async def do_update(self, id, data):
        old = await self._get_instance(id)
        new = old.copy()
        new.update(data)
        verrors = ValidationErrors()
        verrors.add_child('idmap_script_update', await self.middleware.call('idmap._common_validate', new))

        if verrors:
            raise verrors

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
        await self.middleware.call("datastore.delete", self._config.datastore, id)

    @accepts(Int("id"))
    async def run(self, id):
        data = await self._get_instance(id)

    @private
    async def _validate(self, data):
        verrors = ValidationErrors()
        return verrors


class IdmapTDBService(CRUDService):
    class Config:
        datastore = 'directoryservice.idmap_tdb'
        datastore_prefix = 'idmap_tdb_'
        namespace = 'idmap.tdb'


    @accepts(
        Dict(
            'idmap_tdb_create',
            Dict(
                 'domain',
                 Int('id'),
                 Str('idmap_domain_name'),
                 Str('idmap_domain_dns_domain_name'),
            ),
            Int('range_low', required=True, validators=[Range(min=1000, max=2147483647)]),
            Int('range_high', required=True, validators=[Range(min=1000, max=2147483647)]),
            register=True
        )
    )
    async def do_create(self, data):
        verrors = ValidationErrors()
        verrors.add_child('idmap_tdb_create', await self.middleware.call('idmap._common_validate', data))
        if verrors:
            raise verrors

        data = await self.middleware.call('idmap.common_backend_compress', data)
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
            "idmap_tdb_create",
            "idmap_tdb_update",
            ("attr", {"update": True})
        )
    )
    async def do_update(self, id, data):
        old = await self._get_instance(id)
        new = old.copy()
        new.update(data)
        verrors = ValidationErrors()
        verrors.add_child('idmap_tdb_update', await self.middleware.call('idmap._common_validate', new))

        if verrors:
            raise verrors

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
        await self.middleware.call("datastore.delete", self._config.datastore, id)

    @accepts(Int("id"))
    async def run(self, id):
        data = await self._get_instance(id)

    @private
    async def _validate(self, data):
        verrors = ValidationErrors()
        return verrors


class IdmapTDB2Service(CRUDService):
    class Config:
        datastore = 'directoryservice.idmap_tdb2'
        datastore_prefix = 'idmap_tdb2_'
        namespace = 'idmap.tdb2'


    @accepts(
        Dict(
            'idmap_tdb2_create',
            Dict(
                 'domain',
                 Int('id'),
                 Str('idmap_domain_name'),
                 Str('idmap_domain_dns_domain_name'),
            ),
            Int('range_low', required=True, validators=[Range(min=1000, max=2147483647)]),
            Int('range_high', required=True, validators=[Range(min=1000, max=2147483647)]),
            register=True
        )
    )
    async def do_create(self, data):
        verrors = ValidationErrors()
        verrors.add_child('idmap_tdb2_create', await self.middleware.call('idmap._common_validate', data))
        if verrors:
            raise verrors

        data = await self.middleware.call('idmap.common_backend_compress', data)
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
            "idmap_tdb_create",
            "idmap_tdb_update",
            ("attr", {"update": True})
        )
    )
    async def do_update(self, id, data):
        old = await self._get_instance(id)
        new = old.copy()
        new.update(data)
        verrors = ValidationErrors()
        verrors.add_child('idmap_tdb2_update', await self.middleware.call('idmap._common_validate', new))

        if verrors:
            raise verrors

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
        await self.middleware.call("datastore.delete", self._config.datastore, id)

    @accepts(Int("id"))
    async def run(self, id):
        data = await self._get_instance(id)

    @private
    async def _validate(self, data):
        verrors = ValidationErrors()
        return verrors
