import datetime

from .generate_self_signed import generate_self_signed_certificate
from middlewared.service import job, periodic, private, Service


class CertificateService(Service):

    @periodic(86400)
    @private
    @job(lock='acme_cert_renewal')
    def renew_certs(self, job):
        system_cert = self.middleware.call_sync('system.general.config')['ui_certificate']
        if system_cert and all(
            system_cert[k] == v for k, v in (
                ('organization', 'iXsystems'),
                ('san', ['DNS:localhost']),
                ('signedby', None),
                ('cert_type_existing', True),
            )
        ):
            filters = [(
                'OR', (('acme', '!=', None), ('id', '=', system_cert['id']))
            )]
        else:
            filters = [('acme', '!=', None)]
        certs = self.middleware.call_sync('certificate.query', filters)

        progress = 0
        for cert in certs:
            progress += (100 / len(certs))

            if not (
                datetime.datetime.strptime(cert['until'], '%a %b %d %H:%M:%S %Y') - datetime.datetime.utcnow()
            ).days < cert.get('renew_days', 5):
                continue

            # renew cert
            self.logger.debug(f'Renewing certificate {cert["name"]}')
            if not cert.get('acme'):
                cert_str, key = generate_self_signed_certificate()
                cert_payload = {
                    'certificate': cert_str,
                    'privatekey': key,
                }

            else:
                final_order = self.middleware.call_sync(
                    'acme.issue_certificate',
                    job, progress / 4, {
                        'tos': True,
                        'acme_directory_uri': cert['acme']['directory'],
                        'dns_mapping': cert['domains_authenticators'],
                    },
                    cert
                )
                cert_payload = {
                    'certificate': final_order.fullchain_pem,
                    'acme_uri': final_order.uri,
                }

            self.middleware.call_sync(
                'datastore.update',
                'system.certificate',
                cert['id'],
                cert_payload,
                {'prefix': 'cert_'}
            )
            try:
                self.middleware.call_sync('certificate.redeploy_cert_attachments', cert['id'])
            except Exception:
                self.logger.error(
                    'Failed to reload services dependent on %r certificate', cert['name'], exc_info=True
                )

            job.set_progress(progress)
