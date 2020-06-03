from middlewared.service import private, Service


class NFSService(Service):

    class Config:
        service = "nfs"
        service_verb = "restart"
        datastore_prefix = "nfs_srv_"
        datastore_extend = 'nfs.nfs_extend'

    @private
    async def sec(self, config, kerberos_keytabs):
        if config["v4"]:
            if config["v4_krb"]:
                return ["krb5", "krb5i", "krb5p"]
            elif kerberos_keytabs:
                return ["sys", "krb5", "krb5i", "krb5p"]
            else:
                return ["sys"]

        return []
