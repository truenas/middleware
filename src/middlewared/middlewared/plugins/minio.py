import asyncio
import grp
import os
import pwd


from middlewared.service import Service

class MinioService(Service):
    async def write_certificates(self):
        s3 = await self.middleware.call('datastore.query', 'services.s3')
        if not s3 and not s3[0]:
            return

        s3 = s3[0]
        if not 's3_certificate' in s3:
            return

        cert = s3['s3_certificate'] 
        if ('cert_certificate' in cert and len(cert['cert_certificate']) > 0) and \
            ('cert_privatekey' in cert and len(cert['cert_privatekey']) > 0):

            minio_path = "/usr/local/etc/minio"

            minio_certpath = os.path.join(minio_path, "certs")
            minio_certificate =  os.path.join(minio_certpath, "public.crt")
            minio_privatekey = os.path.join(minio_certpath, "private.key")

            minio_uid = pwd.getpwnam('minio').pw_uid
            minio_gid = grp.getgrnam('minio').gr_gid

            os.makedirs(minio_certpath, mode=0o555, exist_ok=True)
            os.chown(minio_path, minio_uid, minio_gid)

            with open(minio_certificate, 'w') as f:
                f.write(cert['cert_certificate'])
            os.chown(minio_certificate, minio_uid, minio_gid)
            os.chmod (minio_certificate, 0o644)

            with open(minio_privatekey, 'w') as f:
                f.write(cert['cert_privatekey'])
            os.chown(minio_privatekey, minio_uid, minio_gid)
            os.chmod (minio_privatekey, 0o600)
