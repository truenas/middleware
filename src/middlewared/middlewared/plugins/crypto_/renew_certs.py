import datetime

from truenas_crypto_utils.generate_self_signed import generate_self_signed_certificate

from middlewared.service import job, periodic, private, Service
from middlewared.utils.time_utils import utc_now


class CertificateService(Service):

    @periodic(86400)
    @private
    @job(lock='acme_cert_renewal')
    def renew_certs(self, job):
        if not self.middleware.call_sync('failover.is_single_master_node'):
            # We do not want to try and renew certs on standby node
            # However when master boots, it is highly likely that it is not master yet
            # So on master event, we will try to renew certs
            return

        system_cert = self.middleware.call_sync('system.general.config')['ui_certificate']
        tnc_config = self.middleware.call_sync('tn_connect.config')
        if system_cert and (
            all(
                system_cert[k] == v for k, v in (
                    ('organization', 'iXsystems'),
                    ('san', ['DNS:localhost']),
                    ('cert_type_existing', True),
                )
            ) or tnc_config['certificate'] == system_cert['id']
        ):
            filters = [(
                'OR', (('acme', '!=', None), ('id', '=', system_cert['id']))
            )]
        else:
            filters = [('acme', '!=', None)]
        certs = self.middleware.call_sync('certificate.query', filters)

        progress = 0
        changed_certs = []
        for cert in certs:
            progress += (100 / len(certs))

            if not (
                datetime.datetime.strptime(cert['until'], '%a %b %d %H:%M:%S %Y') - utc_now()
            ).days < (cert.get('renew_days') or 10):
                continue

            # renew cert
            self.logger.debug(f'Renewing certificate {cert["name"]}')
            if cert['id'] == tnc_config['certificate']:
                self.middleware.create_task(self.middleware.call('tn_connect.acme.renew_cert'))
                continue
            elif not cert.get('acme'):
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
            changed_certs.append(cert)

        self.middleware.call_sync('etc.generate', 'ssl')

        for cert in changed_certs:
            try:
                self.middleware.call_sync('certificate.redeploy_cert_attachments', cert['id'])
            except Exception:
                self.logger.error(
                    'Failed to reload services dependent on %r certificate', cert['name'], exc_info=True
                )

            job.set_progress(progress)
