import errno
from middlewared.service import private, Service
from middlewared.service_exception import CallError
from middlewared.plugins.idmap import DSType
from middlewared.plugins.directoryservices import DSStatus
from middlewared.schema import accepts, Bool, Dict, returns, Str


class NFSService(Service):

    class Config:
        service = "nfs"
        service_verb = "restart"
        datastore_prefix = "nfs_srv_"
        datastore_extend = 'nfs.nfs_extend'

    @private
    async def validate_directoryservices(self, ds):
        """
        Validation currently only succeeds in case of HEALTHY AD
        directory service. At future point, depending on demand, the
        same convenience feature can be added for the LDAP directory
        service.
        """
        ds = await self.middleware.call('directoryservices.get_state')
        ad_status = DSStatus[ds['activedirectory']]
        ldap_status = DSStatus[ds['ldap']]

        if ldap_status != DSStatus.DISABLED:
            raise CallError('This feature has not yet been implemented for '
                            'the LDAP directory service.', errno=errno.ENOSYS)

        if ad_status != DSStatus.HEALTHY:
            raise CallError('Active Directory Directory Service is currently'
                            f'[{ds["activedirectory"]}]. Status must be HEALTHY '
                            'in order to successfully add a kerberos SPN entry.')

    @private
    async def add_principal_ad(self, data):
        """
        Typically elevated permissions are required to make SPN changes.
        Pass user-provided credentials to our kinit method rather than
        relying on the existing kerberos ticket / principal.
        """
        ad = await self.middleware.call('activedirectory.config')
        ad['dstype'] = DSType.DS_TYPE_ACTIVEDIRECTORY.value
        ad['bindname'] = data.get("username", "")
        ad['bindpw'] = data.get("password", "")
        ad['kerberos_principal'] = ''

        await self.middleware.call('kerberos.do_kinit', ad)
        return await self.middleware.call('activedirectory.add_nfs_spn', ad)

    @private
    async def add_principal_ldap(self, data):
        """
        This is a stub that will be replaced when support for adding SPN entries
        is added for the LDAP directory service. Although LDAP is not technically
        a requirement for functional kerberized NFS, in the real world they are
        rarely separated.
        """
        raise CallError('This feature has not yet been implemented for '
                        'the LDAP directory service.', errno=errno.ENOSYS)

    @accepts(
        Dict(
            'add_nfs_principal_creds',
            Str('username', required=True),
            Str('password', required=True, private=True)
        )
    )
    @returns(Bool('principal_add_status'))
    async def add_principal(self, data):
        """
        Use user-provided admin credentials to kinit, add NFS SPN
        entries to the remote kerberos server, and then append the new entries
        to our system keytab.

        Currently this is only supported in AD environments.
        """
        ret = False
        if await self.middleware.call("kerberos.keytab.has_nfs_principal"):
            raise CallError("NFS SPN entry already exists in system keytab",
                            errno.EEXIST)

        ds = await self.middleware.call('directoryservices.get_state')
        await self.validate_directoryservices(ds)
        ad_status = DSStatus[ds['activedirectory']]
        ldap_status = DSStatus[ds['ldap']]

        if ad_status == DSStatus.HEALTHY:
            ret = await self.add_principal_ad(data)

        elif ldap_status == DSStatus.HEALTHY:
            ret = await self.add_principal_ldap(data)

        """
        This step is to ensure that elevated permissions are dropped.
        """
        await self.middleware.call('kerberos.stop')
        await self.middleware.call('kerberos.start')

        return ret
