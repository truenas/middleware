import base64
import hashlib
import os
import syslog

from middlewared.schema import accepts, Bool, Dict, Int, List, Str
from middlewared.validators import Range
from middlewared.service import SystemServiceService


class SSHService(SystemServiceService):

    class Config:
        service = "ssh"
        service_model = "ssh"
        datastore_prefix = "ssh_"

    @accepts(Dict(
        'ssh_update',
        List('bindiface', items=[Str('iface')]),
        Int('tcpport', validators=[Range(min=1, max=65535)]),
        Bool('rootlogin'),
        Bool('passwordauth'),
        Bool('kerberosauth'),
        Bool('tcpfwd'),
        Bool('compression'),
        Str('sftp_log_level', enum=["", "QUIET", "FATAL", "ERROR", "INFO", "VERBOSE", "DEBUG", "DEBUG2", "DEBUG3"]),
        Str('sftp_log_facility', enum=["", "DAEMON", "USER", "AUTH", "LOCAL0", "LOCAL1", "LOCAL2", "LOCAL3", "LOCAL4",
                                       "LOCAL5", "LOCAL6", "LOCAL7"]),
        Str('options'),
        update=True
    ))
    async def do_update(self, data):
        old = await self.config()

        new = old.copy()
        new.update(data)

        await self._update_service(old, new)

        keyfile = "/usr/local/etc/ssh/ssh_host_ecdsa_key.pub"
        if os.path.exists(keyfile):
            with open(keyfile, "rb") as f:
                pubkey = f.read().strip().split(None, 3)[1]
            decoded_key = base64.b64decode(pubkey)
            key_digest = hashlib.sha256(decoded_key).digest()
            ssh_fingerprint = (b"SHA256:" + base64.b64encode(key_digest).replace(b"=", b"")).decode("utf-8")

            syslog.openlog(logoption=syslog.LOG_PID, facility=syslog.LOG_USER)
            syslog.syslog(syslog.LOG_ERR, 'ECDSA Fingerprint of the SSH KEY: ' + ssh_fingerprint)
            syslog.closelog()

        return new
