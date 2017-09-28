import grp
import os
import pwd


async def render(service, middleware):
    s3 = await middleware.call('datastore.query', 'services.s3')
    if not s3:
        return
    s3 = s3[0]
    if not s3:
        return

    if 's3_certificate' not in s3:
        return

    cert = s3['s3_certificate']
    if (
        'cert_certificate' in cert and len(cert['cert_certificate']) > 0 and
        'cert_privatekey' in cert and len(cert['cert_privatekey']) > 0
    ):

        minio_path = "/usr/local/etc/minio"

        minio_certpath = os.path.join(minio_path, "certs")
        minio_CApath = os.path.join(minio_certpath, "CAs")

        minio_certificate = os.path.join(minio_certpath, "public.crt")
        minio_privatekey = os.path.join(minio_certpath, "private.key")

        minio_uid = pwd.getpwnam('minio').pw_uid
        minio_gid = grp.getgrnam('minio').gr_gid

        os.makedirs(minio_CApath, mode=0o555, exist_ok=True)
        os.chown(minio_CApath, minio_uid, minio_gid)
        os.chown(minio_path, minio_uid, minio_gid)

        with open(minio_certificate, 'w') as f:
            f.write(cert['cert_certificate'])
        os.chown(minio_certificate, minio_uid, minio_gid)
        os.chmod(minio_certificate, 0o644)

        with open(minio_privatekey, 'w') as f:
            f.write(cert['cert_privatekey'])
        os.chown(minio_privatekey, minio_uid, minio_gid)
        os.chmod(minio_privatekey, 0o600)
