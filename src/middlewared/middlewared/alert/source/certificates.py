from dataclasses import dataclass
from datetime import datetime
from typing import Any

from middlewared.alert.base import (
    Alert,
    AlertCategory,
    AlertClass,
    AlertClassConfig,
    AlertLevel,
    AlertSource,
    OneShotAlertClass,
)
from middlewared.alert.schedule import CrontabSchedule
from middlewared.utils.time_utils import utc_now


@dataclass(kw_only=True)
class CertificateIsExpiringAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.CERTIFICATES,
        level=AlertLevel.NOTICE,
        title="Certificate Is Expiring",
        text="Certificate %(name)r is expiring within %(days)d days.",
    )

    name: str
    days: int

    @classmethod
    def key_from_args(cls, args: Any) -> Any:
        return [args['name']]


@dataclass(kw_only=True)
class CertificateIsExpiringSoonAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.CERTIFICATES,
        level=AlertLevel.WARNING,
        title="Certificate Is Expiring Soon",
        text="Certificate %(name)r is expiring within %(days)d days.",
    )

    name: str
    days: int

    @classmethod
    def key_from_args(cls, args: Any) -> Any:
        return [args['name']]


@dataclass(kw_only=True)
class CertificateExpiredAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.CERTIFICATES,
        level=AlertLevel.CRITICAL,
        title="Certificate Has Expired",
        text="Certificate %(name)r has expired.",
    )

    name: str

    @classmethod
    def key_from_args(cls, args: Any) -> Any:
        return [args['name']]


@dataclass(kw_only=True)
class CertificateParsingFailedAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.CERTIFICATES,
        level=AlertLevel.WARNING,
        title="Certificate Parsing Failed",
        text="Failed to parse %(type)s %(name)r.",
    )

    type: str
    name: str


class WebUiCertificateSetupFailedAlert(OneShotAlertClass):
    # this is consumed in nginx.conf in the etc plugin
    # you don't have to specify the `AlertClass` verbiage
    # of the class name when calling it
    config = AlertClassConfig(
        category=AlertCategory.CERTIFICATES,
        level=AlertLevel.CRITICAL,
        title="Web UI HTTPS Certificate Setup Failed",
        text="Web UI HTTPS certificate setup failed.",
    )


class CertificateChecksAlertSource(AlertSource):
    schedule = CrontabSchedule(hour=0)  # every 24 hours
    run_on_backup_node = False

    async def check(self) -> list[Alert[Any]]:
        alerts: list[Alert[Any]] = []

        # system certs
        certs = await self.call2(
            self.s.certificate.query, [['certificate', '!=', None]],
        )

        for cert in certs:
            # make the sure certs have been parsed correctly
            if not cert.parsed:
                alerts.append(Alert(
                    CertificateParsingFailedAlert(type=cert.cert_type.capitalize(), name=cert.name),
                ))
            else:
                # check the parsed certificate(s) for expiration
                if cert.cert_type == 'CERTIFICATE' and cert.until:
                    diff = (datetime.strptime(cert.until, '%a %b %d %H:%M:%S %Y') - utc_now()).days
                    alert_threshold = (cert.renew_days or 10) - 1
                    if diff < alert_threshold:
                        if diff >= 0:
                            klass = CertificateIsExpiringSoonAlert if diff <= 2 else CertificateIsExpiringAlert
                            alerts.append(Alert(
                                klass(name=cert.name, days=diff),
                            ))
                        else:
                            alerts.append(Alert(
                                CertificateExpiredAlert(name=cert.name),
                            ))

        return alerts
