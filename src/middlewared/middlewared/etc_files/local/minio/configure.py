import os
import shutil
from middlewared.plugins.etc import EtcUSR, EtcGRP


def render_certificates(s3, middleware):
    minio_path = '/usr/local/etc/minio'

    cert = s3.get('certificate')
    if not cert:
        # We do this so that minio does not pick up certs in this directory and sets itself in https mode even
        # though configuration does not has any certificate in db set and these are old leftovers.
        shutil.rmtree(minio_path, ignore_errors=True)
        return
    else:
        middleware.call_sync('certificate.cert_services_validation', cert, 's3.certificate')

        cert = middleware.call_sync('certificate._get_instance', cert)

        minio_certpath = os.path.join(minio_path, "certs")
        minio_CApath = os.path.join(minio_certpath, "CAs")

        minio_certificate = os.path.join(minio_certpath, "public.crt")
        minio_privatekey = os.path.join(minio_certpath, "private.key")

        minio_uid = EtcUSR.MINIO
        minio_gid = EtcGRP.MINIO

        os.makedirs(minio_CApath, mode=0o555, exist_ok=True)
        os.chown(minio_CApath, minio_uid, minio_gid)
        os.chown(minio_path, minio_uid, minio_gid)

        with open(minio_certificate, 'w') as f:
            os.fchown(f.fileno(), minio_uid, minio_gid)
            os.fchmod(f.fileno(), 0o644)
            f.write(cert['certificate'])

        with open(minio_privatekey, 'w') as f:
            os.fchown(f.fileno(), minio_uid, minio_gid)
            os.fchmod(f.fileno(), 0o600)
            f.write(cert['privatekey'])


def render(__, middleware):
    s3 = middleware.call_sync('s3.config')
    if not s3['storage_path']:
        return

    os.makedirs(s3['storage_path'], exist_ok=True)
    render_certificates(s3, middleware)
