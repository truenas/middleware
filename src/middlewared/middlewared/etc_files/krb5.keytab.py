from base64 import b64decode
from middlewared.utils.directoryservices import krb5


def render(service, middleware, render_ctx):
    keytabs = [b64decode(x['file']) for x in middleware.call_sync('kerberos.keytab.query')]
    if not keytabs:
        return

    return krb5.concatenate_keytab_data(keytabs)
