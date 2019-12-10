import enum
import errno
import os
from middlewared.schema import accepts, Bool, Dict, Int, Patch, Str
from middlewared.service import CallError, CRUDService, job, Service, private, ValidationErrors
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


class IdmapService(Service):
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
        table, then we generate a new one with the next available block of ids and return it.
        """
        my_domain = await self.middleware.call('idmap.domaintobackend.query', [('domain', '=', domain)])
        if not my_domain:
            raise CallError(f'No domain to idmap backend exists for domain [{domain}]', errno.ENOENT)

        backend_entry = await self.middleware.call(
            f'idmap.{my_domain[0]["idmap_backend"].lower()}.query',
            [('domain.idmap_domain_name', '=', domain)]
        )
        if backend_entry:
            return backend_entry[0]

        next_idmap_range = await self.get_next_idmap_range()
        new_idmap = await self.middleware.call(f'idmap.{my_domain[0]["idmap_backend"].lower()}.create', {
            'domain': {'id': my_domain[0]['id']},
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
        idmap_type = idmap_type.lower()
        if idmap_type in ['adex', 'hash']:
            raise CallError(f'idmap backend {idmap_type} has been deprecated')

        ds_type = dstype(int(obj_type)).name

        if ds_type not in ['DS_TYPE_ACTIVEDIRECTORY', 'DS_TYPE_LDAP', 'DS_TYPE_DEFAULT_DOMAIN']:
            raise CallError(f'idmap backends are not supported for {ds_type}')

        res = await self.middleware.call(f'idmap.{idmap_type}.query', [('domain.idmap_domain_name', '=', ds_type)])
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
    async def common_backend_extend(self, data):
        for key in ['ldap_server', 'schema_mode', 'ssl']:
            if key in data and data[key] is not None:
                data[key] = data[key].upper()

        return data

    @private
    async def common_backend_compress(self, data):
        for key in ['ldap_server', 'schema_mode', 'ssl']:
            if key in data and data[key] is not None:
                data[key] = data[key].lower()

        if 'id' in data['domain'] and data['domain']['id']:
            domain_info = await self.middleware.call(
                'idmap.domain.query', [('id', '=', data['domain']['id'])]
            )
            data['domain'] = domain_info[0]['name']
        elif 'idmap_domain_name' in data['domain'] and data['domain']['idmap_domain_name']:
            data['domain'] = data['domain']['idmap_domain_name']
        else:
            domain_info = await self.middleware.call(
                'idmap.domain.query', [('domain', '=', data['domain']['idmap_domain_dns_domain_name'].upper())]
            )
            data['domain'] = domain_info[0]['name']

        return data

    @private
    async def _validate_domain_info(self, domain, verrors):
        """
        Only domains that have been configured as idmap domains
        are permitted.
        """
        configured_domains = await self.middleware.call('idmap.domain.query')

        id = domain.get('id', None)
        id_verified = False

        short_name = domain.get('idmap_domain_name', None)
        short_name_verified = False

        for d in configured_domains:
            if d['id'] == id:
                id_verified = True
            if d['name'] == short_name:
                short_name_verified = True

        if id is not None and not id_verified:
            verrors.add('domain.id', f'Domain [{id}] does not exist.')

        if short_name is not None and not short_name_verified:
            verrors.add('domain.idmap_domain_name', f'Domain [{short_name}] does not exist.')

    @private
    async def _common_validate(self, idmap_backend, data):
        """
        Common validation checks for all idmap backends.

        1) Check for a high range that is lower than the low range.

        2) Check for overlap with other configured idmap ranges.

        In some circumstances overlap is permitted:

        - new idmap range may overlap previously configured idmap range of same domain.

        - new idmap range may overlap an idmap range configured for a disabled directory service.

        - new idmap range for 'autorid' may overlap DS_TYPE_DEFAULT_DOMAIN

        - new idmap range for 'ad' may overlap other 'ad' ranges. In this situation, it is responsibility
          of the system administrator to avoid id collisions between the configured domains.
        """
        verrors = ValidationErrors()
        if data['range_high'] < data['range_low']:
            verrors.add(f'idmap_range', 'Idmap high range must be greater than idmap low range')
            return verrors

        await self._validate_domain_info(data['domain'], verrors)

        configured_domains = await self.get_configured_idmap_domains()
        ldap_enabled = False if await self.middleware.call('ldap.get_state') == 'DISABLED' else True
        ad_enabled = False if await self.middleware.call('activedirectory.get_state') == 'DISABLED' else True
        new_range = range(data['range_low'], data['range_high'])
        for i in configured_domains:
            # Do not generate validation error comparing to oneself.
            if i['domain']['id'] == data['domain'].get('id', None):
                continue

            # Do not generate validation errors for overlapping with a disabled DS.
            if not ldap_enabled and i['domain']['idmap_domain_name'] == 'DS_TYPE_LDAP':
                continue

            if not ad_enabled and i['domain']['idmap_domain_name'] == 'DS_TYPE_ACTIVEDIRECTORY':
                continue

            # Idmap settings under Services->SMB are ignored when autorid is enabled.
            if idmap_backend == 'autorid' and i['domain']['id'] == 5:
                continue

            # Overlap between ranges defined for 'ad' backend are permitted.
            if idmap_backend == 'ad' and i['idmap_backend'] == 'ad':
                continue

            existing_range = range(i['backend_data']['range_low'], i['backend_data']['range_high'])
            if range(max(existing_range[0], new_range[0]), min(existing_range[-1], new_range[-1]) + 1):
                verrors.add(
                    f'idmap_range',
                    f'new idmap range conflicts with existing range for domain [{i["domain"]["idmap_domain_name"]}]'
                )

        return verrors

    @accepts()
    async def get_configured_idmap_domains(self):
        """
        returns list of all configured idmap domains. A configured domain is one
        that exists in the domaintobackend table and has a corresponding backend configured in the respective
        idmap_{backend} table. List is sorted based in ascending order based on the id range.
        """
        domains = await self.middleware.call('idmap.domaintobackend.query')
        configured_domains = []
        for domain in domains:
            b = await self.middleware.call(
                f'idmap.{domain["idmap_backend"].lower()}.query',
                [('domain.idmap_domain_name', '=', domain['domain']['idmap_domain_name'])]
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


class IdmapDomainModel(sa.Model):
    __tablename__ = 'directoryservice_idmap_domain'

    id = sa.Column(sa.Integer(), primary_key=True)
    idmap_domain_name = sa.Column(sa.String(120))
    idmap_domain_dns_domain_name = sa.Column(sa.String(255), nullable=True)


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
        """
        Delete a domain by id. Deletion of default system domains is not permitted.
        """
        if id <= 5:
            entry = await self._get_instance(id)
            raise CallError(f'Deleting system idmap domain [{entry["name"]}] is not permitted.', errno.EPERM)
        await self.middleware.call("datastore.delete", self._config.datastore, id)

    @private
    async def _validate(self, data):
        verrors = ValidationErrors()
        if data['id'] <= dstype['DS_TYPE_DEFAULT_DOMAIN'].value:
            verrors.add('id', f'Modifying system idmap domain [{data["name"]}] is not permitted.')
        return verrors


class IdmapDomaintobackendModel(sa.Model):
    __tablename__ = 'directoryservice_idmap_domaintobackend'

    id = sa.Column(sa.Integer(), primary_key=True)
    idmap_dtb_domain_id = sa.Column(sa.ForeignKey('directoryservice_idmap_domain.idmap_domain_name'), nullable=True)
    idmap_dtb_idmap_backend = sa.Column(sa.String(120), default='rid')


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
            Str('idmap_backend', enum=['AD', 'AUTORID', 'FRUIT', 'LDAP', 'NSS', 'RFC2307', 'RID', 'SCRIPT', 'TDB']),
            register=True
        )
    )
    async def do_create(self, data):
        """
        Set an idmap backend for a domain.
        `domain` dictionary containing domain information. Has one-to-one relationship with idmap_domain entries.
        `idmap_backed` type of idmap backend to use for the domain.

        Create entry for domain in the respective idmap backend table if one does not exist.
        """
        data = await self.middleware.call('idmap.common_backend_compress', data)
        verrors = ValidationErrors()
        if data['domain'] in [dstype.DS_TYPE_LDAP.value, dstype.DS_TYPE_DEFAULT_DOMAIN.value]:
            if data['idmap_backend'] not in ['ldap', 'tdb']:
                verrors.add(
                    'domaintobackend_create.idmap_backend',
                    f'idmap backend [{data["idmap_backend"]}] is not appropriate for the system domain type {dstype[data["domain"]]}'
                )
        if verrors:
            raise verrors

        backend_entry_is_present = False
        idmap_data = await self.middleware.call(f'idmap.{data["idmap_backend"]}.query')
        for i in idmap_data:
            if not i['domain']:
                continue
            if i['domain']['idmap_domain_name'] == data['domain']['idmap_domain_name']:
                backend_entry_is_present = True
                break

        if not backend_entry_is_present:
            next_idmap_range = await self.middleware.call('idmap.get_next_idmap_range')
            await self.middleware.call(f'idmap.{data["idmap_backend"]}.create', {
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
        """
        Update idmap to backend mapping by id.
        """
        old = await self._get_instance(id)
        new = old.copy()
        new.update(data)

        new = await self.middleware.call('idmap.common_backend_compress', new)
        verrors = ValidationErrors()
        if new['domain'] in [dstype.DS_TYPE_LDAP.value, dstype.DS_TYPE_DEFAULT_DOMAIN.value]:
            if new['idmap_backend'] not in ['ldap', 'tdb']:
                verrors.add(
                    'domaintobackend_create.idmap_backend',
                    f'idmap backend [{new["idmap_backend"]}] is not appropriate for the system domain type {dstype[new["domain"]]}'
                )
        if verrors:
            raise verrors

        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            id,
            new,
            {'prefix': self._config.datastore_prefix}
        )
        updated_entry = await self._get_instance(id)
        try:
            await self.middleware.call('idmap.get_or_create_idmap_by_domain', updated_entry['domain']['domain_name'])
        except Exception as e:
            self.logger.debug('Failed to generate new idmap backend: %s', e)

        return updated_entry

    @accepts(Int('id'))
    async def do_delete(self, id):
        """
        Delete idmap to backend mapping by id
        """
        entry = await self._get_instance(id)
        if entry['domain']['id'] <= dstype['DS_TYPE_DEFAULT_DOMAIN'].value:
            raise CallError(f'Deleting mapping for [{entry["domain"]["idmap_domain_name"]}] is not permitted.', errno.EPERM)
        await self.middleware.call("datastore.delete", self._config.datastore, id)


class IdmapADModel(sa.Model):
    __tablename__ = 'directoryservice_idmap_ad'

    id = sa.Column(sa.Integer(), primary_key=True)
    idmap_ad_range_low = sa.Column(sa.Integer())
    idmap_ad_range_high = sa.Column(sa.Integer())
    idmap_ad_schema_mode = sa.Column(sa.String(120))
    idmap_ad_unix_nss_info = sa.Column(sa.Boolean())
    idmap_ad_unix_primary_group = sa.Column(sa.Boolean())
    idmap_ad_domain_id = sa.Column(sa.ForeignKey('directoryservice_idmap_domain.idmap_domain_name', ondelete='CASCADE'), nullable=True)


class IdmapADService(CRUDService):
    class Config:
        datastore = 'directoryservice.idmap_ad'
        datastore_prefix = 'idmap_ad_'
        datastore_extend = 'idmap.common_backend_extend'
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
            Str('schema_mode', default='RFC2307', enum=['RFC2307', 'SFU', 'SFU20']),
            Bool('unix_primary_group', default=False),
            Bool('unix_nss_info', default=False),
            register=True
        )
    )
    async def do_create(self, data):
        """
        Create an entry in the idmap ad backend table.

        `domain` specifies the domain for which the idmap backend is being created. Numeric id, short-form
        domain name, or long-form DNS domain name of the domain may be specified. Entry must be entered as
        it appears in `idmap.domain`.

        `unix_primary_group` If True, the primary group membership is fetched from the LDAP attributes (gidNumber).
        If False, the primary group membership is calculated via the "primaryGroupID" LDAP attribute.

        `unix_nss_info` if True winbind will retrieve the login shell and home directory from the LDAP attributes.
        If False or if the AD LDAP entry lacks the SFU attributes the smb4.conf parameters `template shell` and `template homedir` are used.

        `schema_mode` Defines the schema that idmap_ad should use when querying Active Directory regarding user and group information.
        This can be either the RFC2307 schema support included in Windows 2003 R2 or the Service for Unix (SFU) schema.
        For SFU 3.0 or 3.5 please choose "SFU", for SFU 2.0 please choose "SFU20". The behavior of primary group membership is
        controlled by the unix_primary_group option.
        """
        verrors = ValidationErrors()
        data = await self.middleware.call('idmap.common_backend_compress', data)
        verrors.add_child('idmap_ad_create', await self.middleware.call('idmap._common_validate', 'ad', data))
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
            "idmap_ad_create",
            "idmap_ad_update",
            ("attr", {"update": True})
        )
    )
    async def do_update(self, id, data):
        """
        Update an entry in the idmap backend table by id.
        """
        old = await self._get_instance(id)
        new = old.copy()
        new.update(data)
        verrors = ValidationErrors()
        verrors.add_child('idmap_ad_update', await self.middleware.call('idmap._common_validate', 'ad', new))
        if verrors:
            raise verrors

        new = await self.middleware.call('idmap.common_backend_compress', new)
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
        Delete idmap to backend mapping by id
        """
        await self.middleware.call("datastore.delete", self._config.datastore, id)


class DirectoryserviceIdmapAutoridModel(sa.Model):
    __tablename__ = 'directoryservice_idmap_autorid'

    id = sa.Column(sa.Integer(), primary_key=True)
    idmap_autorid_range_low = sa.Column(sa.Integer())
    idmap_autorid_range_high = sa.Column(sa.Integer())
    idmap_autorid_rangesize = sa.Column(sa.Integer())
    idmap_autorid_readonly = sa.Column(sa.Boolean())
    idmap_autorid_ignore_builtin = sa.Column(sa.Boolean())
    idmap_autorid_domain_id = sa.Column(sa.ForeignKey('directoryservice_idmap_domain.idmap_domain_name', ondelete='CASCADE'), nullable=True)


class IdmapAutoridService(CRUDService):
    class Config:
        datastore = 'directoryservice.idmap_autorid'
        datastore_prefix = 'idmap_autorid_'
        datastore_extend = 'idmap.common_backend_extend'
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
            Int('rangesize', default=100000),
            Bool('readonly', default=False),
            Bool('ignore_builtin', default=False),
            register=True
        )
    )
    async def do_create(self, data):
        """
        `domain` specifies the domain for which the idmap backend is being created. Numeric id, short-form
        domain name, or long-form DNS domain name of the domain may be specified. Entry must be entered as
        it appears in `idmap.domain`.

        `range_low` and `rang_high` specify the UID and GID range for which this backend is authoritative.

        `rangesize` defines the number of uids/gids available per domain range.

        `readonly` turn the module into read-only mode. No new ranges will be allocated nor will new mappings
        be created in the idamp pool.

        `ignore builtin` ignore any mapping requests for the BUILTIN domain.
        """
        verrors = ValidationErrors()
        verrors.add_child('idmap_autorid_create', await self.middleware.call('idmap._common_validate', 'autorid', data))
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
        """
        Update an entry in the idmap backend table by id.
        """
        old = await self._get_instance(id)
        new = old.copy()
        new.update(data)
        verrors = ValidationErrors()
        verrors.add_child('idmap_autorid_update', await self.middleware.call('idmap._common_validate', 'autorid', new))

        if verrors:
            raise verrors

        new = await self.middleware.call('idmap.common_backend_compress', new)
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
        Delete idmap to backend mapping by id
        """
        await self.middleware.call("datastore.delete", self._config.datastore, id)


class IdmapLDAPModel(sa.Model):
    __tablename__ = 'directoryservice_idmap_ldap'

    id = sa.Column(sa.Integer(), primary_key=True)
    idmap_ldap_range_low = sa.Column(sa.Integer())
    idmap_ldap_range_high = sa.Column(sa.Integer())
    idmap_ldap_ldap_base_dn = sa.Column(sa.String(120))
    idmap_ldap_ldap_user_dn = sa.Column(sa.String(120))
    idmap_ldap_ldap_url = sa.Column(sa.String(255))
    idmap_ldap_ssl = sa.Column(sa.String(120))
    idmap_ldap_certificate_id = sa.Column(sa.ForeignKey('system_certificate.id'), index=True, nullable=True)
    idmap_ldap_domain_id = sa.Column(sa.ForeignKey('directoryservice_idmap_domain.idmap_domain_name', ondelete='CASCADE'), nullable=True)


class IdmapLDAPService(CRUDService):
    class Config:
        datastore = 'directoryservice.idmap_ldap'
        datastore_prefix = 'idmap_ldap_'
        datastore_extend = 'idmap.common_backend_extend'
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
            Str('ldap_base_dn'),
            Str('ldap_user_dn'),
            Str('ldap_url'),
            Str('ssl', default='OFF', enum=['OFF', 'ON', 'START_TLS']),
            Int('certificate'),
            register=True
        )
    )
    async def do_create(self, data):
        """
        `domain` specifies the domain for which the idmap backend is being created. Numeric id, short-form
        domain name, or long-form DNS domain name of the domain may be specified. Entry must be entered as
        it appears in `idmap.domain`.

        `range_low` and `range_high` specify the UID and GID range for which this backend is authoritative.

        `rangesize` defines the number of uids/gids available per domain range.

        `ldap_base_dn` defines the directory base suffix to use for SID/uid/gid mapping entries.

        `ldap_user_dn` defines the user DN to be used for authentication.

        `ldap_url` specifies the LDAP server to use for SID/uid/gid map entries.

        `ssl` specifies whether to encrypt the LDAP transport for the idmap backend.

        `certificate` specifies the client certificate to use for SASL_EXTERNAL authentication.
        """
        verrors = ValidationErrors()
        verrors.add_child('idmap_ldap_create', await self.middleware.call('idmap._common_validate', 'ldap', data))
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
        """
        Update an entry in the idmap backend table by id.
        """
        old = await self._get_instance(id)
        new = old.copy()
        new.update(data)
        verrors = ValidationErrors()
        verrors.add_child('idmap_ldap_update', await self.middleware.call('idmap._common_validate', 'ldap', new))

        if verrors:
            raise verrors

        new = await self.middleware.call('idmap.common_backend_compress', new)
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
        Delete idmap to backend mapping by id
        """
        await self.middleware.call("datastore.delete", self._config.datastore, id)


class IdmapNSSModel(sa.Model):
    __tablename__ = 'directoryservice_idmap_nss'

    id = sa.Column(sa.Integer(), primary_key=True)
    idmap_nss_range_low = sa.Column(sa.Integer())
    idmap_nss_range_high = sa.Column(sa.Integer())
    idmap_nss_domain_id = sa.Column(sa.ForeignKey('directoryservice_idmap_domain.idmap_domain_name', ondelete='CASCADE'), nullable=True)


class IdmapNSSService(CRUDService):
    class Config:
        datastore = 'directoryservice.idmap_nss'
        datastore_prefix = 'idmap_nss_'
        datastore_extend = 'idmap.common_backend_extend'
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
        """
        `domain` specifies the domain for which the idmap backend is being created. Numeric id, short-form
        domain name, or long-form DNS domain name of the domain may be specified. Entry must be entered as
        it appears in `idmap.domain`.

        `range_low` and `range_high` specify the UID and GID range for which this backend is authoritative.

        The idmap_nss backend maps Unix users and groups to Windows accounts by joining on SamAccountName.
        """
        verrors = ValidationErrors()
        verrors.add_child('idmap_nss_create', await self.middleware.call('idmap._common_validate', 'nss', data))
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
        """
        Update an entry in the idmap backend table by id.
        """
        old = await self._get_instance(id)
        new = old.copy()
        new.update(data)
        new = await self.middleware.call('idmap.common_backend_compress', new)
        verrors = ValidationErrors()
        verrors.add_child('idmap_nss_update', await self.middleware.call('idmap._common_validate', 'nss', new))

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
        """
        Delete idmap to backend mapping by id
        """
        await self.middleware.call("datastore.delete", self._config.datastore, id)


class IdmapRFC2307Model(sa.Model):
    __tablename__ = 'directoryservice_idmap_rfc2307'

    id = sa.Column(sa.Integer(), primary_key=True)
    idmap_rfc2307_range_low = sa.Column(sa.Integer())
    idmap_rfc2307_range_high = sa.Column(sa.Integer())
    idmap_rfc2307_ldap_server = sa.Column(sa.String(120))
    idmap_rfc2307_bind_path_user = sa.Column(sa.String(120))
    idmap_rfc2307_bind_path_group = sa.Column(sa.String(120))
    idmap_rfc2307_user_cn = sa.Column(sa.Boolean())
    idmap_rfc2307_cn_realm = sa.Column(sa.Boolean())
    idmap_rfc2307_ldap_domain = sa.Column(sa.String(120))
    idmap_rfc2307_ldap_url = sa.Column(sa.String(255))
    idmap_rfc2307_ldap_user_dn = sa.Column(sa.String(120))
    idmap_rfc2307_ldap_user_dn_password = sa.Column(sa.String(120))
    idmap_rfc2307_ldap_realm = sa.Column(sa.String(120))
    idmap_rfc2307_ssl = sa.Column(sa.String(120))
    idmap_rfc2307_certificate_id = sa.Column(sa.ForeignKey('system_certificate.id'), index=True, nullable=True)
    idmap_rfc2307_domain_id = sa.Column(sa.ForeignKey('directoryservice_idmap_domain.idmap_domain_name', ondelete='CASCADE'), nullable=True)


class IdmapRFC2307Service(CRUDService):
    """
    In the rfc2307 backend range acts as a filter. Anything falling outside of it is ignored.
    If no user_dn is specified, then an anonymous bind is performed.
    ldap_url is only required when using a standalone server.
    """
    class Config:
        datastore = 'directoryservice.idmap_rfc2307'
        datastore_prefix = 'idmap_rfc2307_'
        datastore_extend = 'idmap.common_backend_extend'
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
            Str('ldap_server', default='AD', enum=['AD', 'STAND-ALONE']),
            Str('bind_path_user'),
            Str('bind_path_group'),
            Bool('user_cn', default=False),
            Bool('cn_realm', default=False),
            Str('ldap_domain'),
            Str('ldap_url'),
            Str('ldap_user_dn'),
            Str('ldap_user_dn_password'),
            Str('ldap_realm'),
            Str('ssl', default='OFF', enum=['OFF', 'ON', 'START_TLS']),
            Int('certificate'),
            register=True
        )
    )
    async def do_create(self, data):
        """
        Create an entry in the idmap_rfc2307 backend table.

        `domain` specifies the domain for which the idmap backend is being created. Numeric id, short-form
        domain name, or long-form DNS domain name of the domain may be specified. Entry must be entered as
        it appears in `idmap.domain`.

        `range_low` and `range_high` specify the UID and GID range for which this backend is authoritative.

        `ldap_server` defines the type of LDAP server to use. This can either be an LDAP server provided
        by the Active Directory Domain (ad) or a stand-alone LDAP server.

        `bind_path_user` specfies the search base where user objects can be found in the LDAP server.

        `bind_path_group` specifies the search base where group objects can be found in the LDAP server.

        `user_cn` query cn attribute instead of uid attribute for the user name in LDAP.

        `realm` append @realm to cn for groups (and users if user_cn is set) in LDAP queries.

        `ldmap_domain` when using the LDAP server in the Active Directory server, this allows one to
        specify the domain where to access the Active Directory server. This allows using trust relationships
        while keeping all RFC 2307 records in one place. This parameter is optional, the default is to access
        the AD server in the current domain to query LDAP records.

        `ldap_url` when using a stand-alone LDAP server, this parameter specifies the LDAP URL for accessing the LDAP server.

        `ldap_user_dn` defines the user DN to be used for authentication.

        `realm` defines the realm to use in the user and group names. This is only required when using cn_realm together with
         a stand-alone ldap server.

        `certificate` specifies the LDAP client certificate to use for SASL_EXTERNAL authentication.
        """
        verrors = ValidationErrors()
        verrors.add_child('idmap_rfc2307_create', await self.middleware.call('idmap._common_validate', 'rfc2307', data))
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
            "idmap_rfc2307_create",
            "idmap_rfc2307_update",
            ("attr", {"update": True})
        )
    )
    async def do_update(self, id, data):
        old = await self._get_instance(id)
        new = old.copy()
        new.update(data)
        verrors = ValidationErrors()
        verrors.add_child('idmap_rfc2307_update', await self.middleware.call('idmap._common_validate', 'rfc2307', new))

        if verrors:
            raise verrors

        new = await self.middleware.call('idmap.common_backend_compress', new)
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


class IdmapRIDModel(sa.Model):
    __tablename__ = 'directoryservice_idmap_rid'

    id = sa.Column(sa.Integer(), primary_key=True)
    idmap_rid_range_low = sa.Column(sa.Integer())
    idmap_rid_range_high = sa.Column(sa.Integer())
    idmap_rid_domain_id = sa.Column(sa.ForeignKey('directoryservice_idmap_domain.idmap_domain_name', ondelete='CASCADE'), nullable=True)


class IdmapRIDService(CRUDService):
    class Config:
        datastore = 'directoryservice.idmap_rid'
        datastore_prefix = 'idmap_rid_'
        datastore_extend = 'idmap.common_backend_extend'
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
        """
        Create an entry in the idmap_rid backend table.
        The idmap_rid backend provides a way to use an algorithmic mapping scheme to map UIDs/GIDs and SIDs.
        No database is required in this case as the mapping is deterministic.

        `domain` specifies the domain for which the idmap backend is being created. Numeric id, short-form
        domain name, or long-form DNS domain name of the domain may be specified. Entry must be entered as
        it appears in `idmap.domain`.

        `range_low` and `range_high` specify the UID and GID range for which this backend is authoritative.
        """
        verrors = ValidationErrors()
        verrors.add_child('idmap_rid_create', await self.middleware.call('idmap._common_validate', 'rid', data))
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
        """
        Update an entry in the idmap backend table by id.
        """
        old = await self._get_instance(id)
        new = old.copy()
        new.update(data)
        verrors = ValidationErrors()
        verrors.add_child('idmap_rid_update', await self.middleware.call('idmap._common_validate', 'rid', new))

        if verrors:
            raise verrors

        new = await self.middleware.call('idmap.common_backend_compress', new)
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
        Delete idmap to backend mapping by id
        """
        await self.middleware.call("datastore.delete", self._config.datastore, id)


class IdmapScriptModel(sa.Model):
    __tablename__ = 'directoryservice_idmap_script'

    id = sa.Column(sa.Integer(), primary_key=True)
    idmap_script_range_low = sa.Column(sa.Integer())
    idmap_script_range_high = sa.Column(sa.Integer())
    idmap_script_script = sa.Column(sa.String(255))
    idmap_script_domain_id = sa.Column(sa.ForeignKey('directoryservice_idmap_domain.idmap_domain_name', ondelete='CASCADE'), nullable=True)


class IdmapScriptService(CRUDService):
    class Config:
        datastore = 'directoryservice.idmap_script'
        datastore_prefix = 'idmap_script_'
        datastore_extend = 'idmap.common_backend_extend'
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
            Str('script'),
            register=True
        )
    )
    async def do_create(self, data):
        """
        Create an entry in the idmap backend table. idmap_script is a read-only backend that
        uses a script to perform mapping of UIDs and GIDs to Windows SIDs.

        `domain` specifies the domain for which the idmap backend is being created. Numeric id, short-form
        domain name, or long-form DNS domain name of the domain may be specified. Entry must be entered as
        it appears in `idmap.domain`.

        `range_low` and `range_high` specify the UID and GID range for which this backend is authoritative.

        `script` full path to the script or program that generates the mappings.
        """
        verrors = ValidationErrors()
        verrors.add_child('idmap_script_create', await self.middleware.call('idmap._common_validate', 'script', data))
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
        """
        Update an entry in the idmap backend table by id.
        """
        old = await self._get_instance(id)
        new = old.copy()
        new.update(data)
        verrors = ValidationErrors()
        verrors.add_child('idmap_script_update', await self.middleware.call('idmap._common_validate', 'script', new))

        if verrors:
            raise verrors

        new = await self.middleware.call('idmap.common_backend_compress', new)
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
        Delete idmap to backend mapping by id
        """
        await self.middleware.call("datastore.delete", self._config.datastore, id)


class IdmapTDBModel(sa.Model):
    __tablename__ = 'directoryservice_idmap_tdb'

    id = sa.Column(sa.Integer(), primary_key=True)
    idmap_tdb_range_low = sa.Column(sa.Integer())
    idmap_tdb_range_high = sa.Column(sa.Integer())
    idmap_tdb_domain_id = sa.Column(sa.ForeignKey('directoryservice_idmap_domain.idmap_domain_name'), nullable=True)


class IdmapTDBService(CRUDService):
    class Config:
        datastore = 'directoryservice.idmap_tdb'
        datastore_prefix = 'idmap_tdb_'
        datastore_extend = 'idmap.common_backend_extend'
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
        """
        The idmap_tdb plugin is the default backend used by winbindd for storing SID/uid/gid mapping tables.
        In contrast to read only backends like idmap_rid, it is an allocating backend. This means that it
        needs to allocate new user and group IDs in order to create new mappings.

        `domain` specifies the domain for which the idmap backend is being created. Numeric id, short-form
        domain name, or long-form DNS domain name of the domain may be specified. Entry must be entered as
        it appears in `idmap.domain`.

        `range_low` and `range_high` specify the UID and GID range for which this backend is authoritative.
        """
        verrors = ValidationErrors()
        verrors.add_child('idmap_tdb_create', await self.middleware.call('idmap._common_validate', 'tdb', data))
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
        """
        Update an entry in the idmap backend table by id.
        """
        old = await self._get_instance(id)
        new = old.copy()
        new.update(data)
        verrors = ValidationErrors()
        verrors.add_child('idmap_tdb_update', await self.middleware.call('idmap._common_validate', 'tdb', new))

        if verrors:
            raise verrors

        new = await self.middleware.call('idmap.common_backend_compress', new)
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
        Delete idmap to backend mapping by id
        """
        await self.middleware.call("datastore.delete", self._config.datastore, id)
