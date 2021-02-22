import grp
import os
import pwd
import shutil


def render(service, middleware):
    s3 = middleware.call_sync('s3.config')
    minio_path = '/usr/local/etc/minio'

    cert = s3.get('certificate')
    if not cert:
        # We do this so that minio does not pick up certs in this directory and sets itself in https mode even
        # though configuration does not has any certificate in db set and these are old leftovers.
        shutil.rmtree(minio_path, ignore_errors=True)
        return
    else:
        middleware.call_sync('certificate.cert_services_validation', cert, 's3.certificate')

        cert = middleware.call_sync('certificate.get_instance', cert)

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
            f.write(cert['certificate'])
        os.chown(minio_certificate, minio_uid, minio_gid)
        os.chmod(minio_certificate, 0o644)

        with open(minio_privatekey, 'w') as f:
            f.write(cert['privatekey'])
        os.chown(minio_privatekey, minio_uid, minio_gid)
        os.chmod(minio_privatekey, 0o600)
