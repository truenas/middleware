from datetime import datetime

from middlewared.alert.base import AlertClass, SimpleOneShotAlertClass, AlertCategory, AlertLevel, Alert, AlertSource


class CertificateIsExpiringAlertClass(AlertClass):
    category = AlertCategory.CERTIFICATES
    level = AlertLevel.NOTICE
    title = "Certificate Is Expiring"
    text = "Certificate %(name)r is expiring within %(days)d days."


class CertificateIsExpiringSoonAlertClass(AlertClass):
    category = AlertCategory.CERTIFICATES
    level = AlertLevel.WARNING
    title = "Certificate Is Expiring Soon"
    text = "Certificate %(name)r is expiring within %(days)d days."


class CertificateExpiredAlertClass(AlertClass):
    category = AlertCategory.CERTIFICATES
    level = AlertLevel.CRITICAL
    title = "Certificate Has Expired"
    text = "Certificate %(name)r has expired."


class CertificateIsExpiringAlertSource(AlertSource):
    async def check(self):
        alerts = []

        for cert in await self.middleware.call(
            'certificate.query',
            [['certificate', '!=', None]]
        ) + await self.middleware.call('certificateauthority.query'):
            if cert['parsed']:
                diff = (datetime.strptime(cert['until'], '%a %b %d %H:%M:%S %Y') - datetime.utcnow()).days
                if diff < 10:
                    if diff >= 0:
                        alerts.append(
                            Alert(
                                CertificateIsExpiringSoonAlertClass if diff <= 2 else CertificateIsExpiringAlertClass,
                                {
                                    'name': cert['name'],
                                    'days': diff,
                                },
                                key=[cert['name']],
                            )
                        )
                    else:
                        alerts.append(Alert(CertificateExpiredAlertClass, {'name': cert['name']}, key=[cert['name']]))

        return alerts


class CertificateRevokedAlertClass(AlertClass):
    category = AlertCategory.CERTIFICATES
    level = AlertLevel.CRITICAL
    title = 'Certificate Revoked'
    text = '%(service)s %(type)s has been revoked. Please replace the certificate immediately.'


class CertificateRevokedAlertSource(AlertSource):
    async def check(self):
        alerts = []

        for cert_id, service, type_c, datastore in (
            ((await self.middleware.call('ftp.config'))['ssltls_certificate'], 'FTP', 'certificate', 'certificate'),
            ((await self.middleware.call('s3.config'))['certificate'], 'S3', 'certificate', 'certificate'),
            ((await self.middleware.call('webdav.config'))['certssl'], 'Webdav', 'certificate', 'certificate'),
            (
                (await self.middleware.call('openvpn.server.config'))['server_certificate'],
                'OpenVPN server', 'certificate', 'certificate'
            ),
            (
                (await self.middleware.call('openvpn.client.config'))['client_certificate'],
                'OpenVPN client', 'certificate', 'certificate'
            ),
            (
                (await self.middleware.call('system.general.config'))['ui_certificate']['id'],
                'Web UI', 'certificate', 'certificate'
            ),
            (
                (await self.middleware.call('system.advanced.config'))['syslog_tls_certificate'],
                'Syslog', 'certificate', 'certificate'
            ),
            (
                (await self.middleware.call('openvpn.server.config'))['root_ca'],
                'OpenVPN server', 'root certificate authority', 'certificateauthority'
            ),
            (
                (await self.middleware.call('openvpn.client.config'))['root_ca'],
                'OpenVPN client', 'root certificate authority', 'certificateauthority'
            )
        ):
            if (
                cert_id and (
                    await self.middleware.call(
                        f'{datastore}.query', [
                            ['id', '=', cert_id]
                        ], {'get': True}
                    )
                )['revoked']
            ):
                alerts.append(Alert(CertificateRevokedAlertClass, {'service': service, 'type': type_c}))

        return alerts


class CertificateParsingFailedAlertClass(AlertClass):
    category = AlertCategory.CERTIFICATES
    level = AlertLevel.WARNING
    title = "Certificate Parsing Failed"
    text = "Failed to parse %(type)s %(name)r."


class CertificateParsingFailedAlertSource(AlertSource):
    async def check(self):
        alerts = []

        for cert in await self.middleware.call(
                'certificate.query',
                [['certificate', '!=', None]]
        ) + await self.middleware.call('certificateauthority.query'):
            if not cert['parsed']:
                alerts.append(
                    Alert(
                        CertificateParsingFailedAlertClass,
                        {
                            "type": cert["cert_type"].capitalize(),
                            "name": cert["name"],
                        },
                    )
                )

        return alerts


class WebUiCertificateSetupFailedAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.CERTIFICATES
    level = AlertLevel.CRITICAL
    title = "Web UI HTTPS Certificate Setup Failed"
    text = "Web UI HTTPS certificate setup failed."
