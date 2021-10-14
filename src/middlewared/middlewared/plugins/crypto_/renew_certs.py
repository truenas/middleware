import datetime

from middlewared.service import job, periodic, private, Service


class CertificateService(Service):

    @periodic(86400)
    @private
    @job(lock='acme_cert_renewal')
    def renew_certs(self, job):
        certs = self.middleware.call_sync(
            'certificate.query',
            [['acme', '!=', None]]
        )

        progress = 0
        for cert in certs:
            progress += (100 / len(certs))

            if (
                datetime.datetime.strptime(cert['until'], '%a %b %d %H:%M:%S %Y') - datetime.datetime.utcnow()
            ).days < cert['renew_days']:
                # renew cert
                self.logger.debug(f'Renewing certificate {cert["name"]}')
                final_order = self.middleware.call_sync(
                    'acme.issue_certificate',
                    job, progress / 4, {
                        'tos': True,
                        'acme_directory_uri': cert['acme']['directory'],
                        'dns_mapping': cert['domains_authenticators'],
                    },
                    cert
                )

                self.middleware.call_sync(
                    'datastore.update',
                    'system.certificate',
                    cert['id'],
                    {
                        'certificate': final_order.fullchain_pem,
                        'acme_uri': final_order.uri
                    },
                    {'prefix': 'cert_'}
                )
                try:
                    self.middleware.call_sync('certificate.redeploy_cert_attachments', cert['id'])
                except Exception:
                    self.logger.error(
                        'Failed to reload services dependent on %r certificate', cert['name'], exc_info=True
                    )

            job.set_progress(progress)
