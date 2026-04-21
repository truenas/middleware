# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from collections import defaultdict
from datetime import date, timedelta
import textwrap
from typing import Any

from middlewared.alert.base import (
    AlertClass, AlertClassConfig, AlertCategory, AlertLevel, Alert, NonDataclassAlertClass, ThreadedAlertSource,
)
from middlewared.alert.schedule import IntervalSchedule
from middlewared.utils import ProductType
from middlewared.utils.license import LICENSE_ADDHW_MAPPING


class LicenseAlert(NonDataclassAlertClass[str], AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SYSTEM,
        level=AlertLevel.CRITICAL,
        title="TrueNAS License Issue",
        text="%s",
        products=(ProductType.ENTERPRISE,),
    )


class LicenseIsExpiringAlert(NonDataclassAlertClass[str], AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SYSTEM,
        level=AlertLevel.WARNING,
        title="TrueNAS License Is Expiring",
        text="%s",
        products=(ProductType.ENTERPRISE,),
    )


class LicenseHasExpiredAlert(NonDataclassAlertClass[str], AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SYSTEM,
        level=AlertLevel.CRITICAL,
        title="TrueNAS License Has Expired",
        text="%s",
        products=(ProductType.ENTERPRISE,),
    )


class LicenseStatusAlertSource(ThreadedAlertSource):
    products = (ProductType.ENTERPRISE,)
    run_on_backup_node = False
    schedule = IntervalSchedule(timedelta(hours=24))

    def check_sync(self) -> list[Alert[Any]] | Alert[Any]:
        alerts: list[Alert[Any]] = []

        local_license = self.middleware.call_sync('system.license')
        if local_license is None:
            return Alert(LicenseAlert("Your TrueNAS has no license, contact support."))

        # check if this node's system serial matches the serial in the license
        local_serial = self.middleware.call_sync('system.dmidecode_info')['system-serial-number']
        if local_serial not in (local_license['system_serial'], local_license['system_serial_ha']):
            alerts.append(Alert(LicenseAlert('System serial does not match license.')))

        standby_license = standby_serial = None
        try:
            if local_license['system_serial_ha']:
                standby_license = self.middleware.call_sync('failover.call_remote', 'system.license')
                standby_serial = self.middleware.call_sync(
                    'failover.call_remote', 'system.dmidecode_info')['system-serial-number']
        except Exception:
            pass

        if standby_license and standby_serial is not None:
            # check if the remote node's system serial matches the serial in the license
            if standby_serial not in (standby_license['system_serial'], standby_license['system_serial_ha']):
                alerts.append(Alert(LicenseAlert('System serial of standby node does not match license.')))

        model = self.middleware.call_sync('truenas.get_chassis_hardware').removeprefix('TRUENAS-').split('-')[0]
        if model == 'UNKNOWN':
            alerts.append(Alert(LicenseAlert('TrueNAS is running on unsupported hardware.')))
        elif model != local_license['model']:
            alerts.append(Alert(
                LicenseAlert(
                    f'Your license was issued for model {local_license["model"]!r} '
                    f'but the system was detected as model {model!r}'
                )
            ))

        enc_nums: defaultdict[str, int] = defaultdict(lambda: 0)
        for enc in filter(lambda x: not x['controller'], self.middleware.call_sync('enclosure2.query')):
            enc_nums[enc['model']] += 1

        if local_license['addhw']:
            for quantity, code in local_license['addhw']:
                if code not in LICENSE_ADDHW_MAPPING:
                    self.middleware.logger.warning('Unknown additional hardware code %d', code)
                    continue

                name = LICENSE_ADDHW_MAPPING[code]
                if name == 'ES60':
                    continue

                if enc_nums[name] != quantity:
                    alerts.append(Alert(
                        LicenseAlert(
                            'License expects %(license)s units of %(name)s Expansion shelf but found %(found)s.' % {
                                'license': quantity,
                                'name': name,
                                'found': enc_nums[name]
                            }
                        )
                    ))
        elif enc_nums:
            alerts.append(Alert(
                LicenseAlert(
                    'Unlicensed Expansion shelf detected. This system is not licensed for additional expansion shelves.'
                )
            ))

        for days in [0, 14, 30, 90, 180]:
            if local_license['contract_end'] <= date.today() + timedelta(days=days):
                serial_numbers = ", ".join(list(filter(None, [local_license['system_serial'],
                                                              local_license['system_serial_ha']])))
                contract_start = local_license['contract_start'].strftime("%B %-d, %Y")
                contract_expiration = local_license['contract_end'].strftime("%B %-d, %Y")
                contract_type = local_license['contract_type']  # Display as stored, usually upper case.
                customer_name = local_license['customer_name']

                alert_klass: type[LicenseHasExpiredAlert] | type[LicenseIsExpiringAlert]
                if days == 0:
                    alert_klass = LicenseHasExpiredAlert
                    alert_text = textwrap.dedent("""\
                        SUPPORT CONTRACT EXPIRED: Your support contract has ended. Renewal options may be
                        available — contact sales@TrueNAS.com or 1-855-473-7449 to find out.
                    """)
                    subject = "Your TrueNAS support contract has expired"
                    opening = textwrap.dedent("""\
                        Your support contract has ended. Renewal options may be available depending on your
                        situation. Please contact your authorized reseller or TrueNAS (sales@TrueNAS.com)
                        to find out what may be possible.
                    """)
                    encouraging = textwrap.dedent("""\
                        Contact your authorized reseller or TrueNAS (email: sales@TrueNAS.com,
                        phone: 1-855-473-7449) to find out what renewal options may be available to you.
                    """)
                else:
                    alert_klass = LicenseIsExpiringAlert
                    alert_text = textwrap.dedent(f"""\
                        SUPPORT CONTRACT EXPIRING SOON: The support contract for this product expires
                        on {contract_expiration}. Renewal options may be available — contact your authorized
                        reseller or TrueNAS: sales@TrueNAS.com, 1-855-473-7449.
                    """)
                    days_left = (local_license['contract_end'] - date.today()).days
                    subject = f"Your TrueNAS support contract will expire in {days_left} days"
                    if days == 14:
                        opening = textwrap.dedent(f"""\
                            The support contracts for the following TrueNAS products are expiring in 14 days:
                            {serial_numbers}
                            Your TrueNAS {contract_type} support contract is approaching its expiration date.
                            Renewal options may be available — we suggest contacting us before expiration.
                        """)
                        encouraging = textwrap.dedent("""\
                            Contact your authorized reseller or TrueNAS (email: sales@TrueNAS.com,
                            telephone: 1-855-473-7449) to find out what renewal options may be available
                            for your contract.
                        """)
                    else:
                        opening = textwrap.dedent(f"""\
                            Your TrueNAS {contract_type} support contract will expire in {days_left} days.
                            Renewal options may be available — contact your authorized reseller or TrueNAS
                            (email: sales@TrueNAS.com, telephone: 1-855-473-7449) to find out more.
                        """)
                        encouraging = textwrap.dedent("""\
                            Contact your authorized reseller or TrueNAS (email: sales@TrueNAS.com,
                            telephone: 1-855-473-7449) to find out what renewal options may be available
                            before your contract expires.
                        """)

                alerts.append(Alert(
                    alert_klass(alert_text),
                    mail={
                        "cc": ["support-renewal@truenas.com"],
                        "subject": subject,
                        "text": textwrap.dedent("""\
                            Hello, {customer_name}

                            {opening}

                            Support Level: {contract_type}
                            Product: {chassis_hardware}
                            Serial Numbers: {serial_numbers}
                            Support Contract Start Date: {contract_start}
                            Support Contract Expiration Date: {contract_expiration}

                            {encouraging}

                            Your TrueNAS system will remain accessible after the support contract expires.
                            However, after expiration it will no longer be eligible for support from TrueNAS.
                            Renewal options may be available depending on your circumstances, though additional
                            costs such as reactivation or lapsed-contract fees may apply.

                            Sincerely,

                            TrueNAS
                            Web: support.TrueNAS.com
                            Email: support@TrueNAS.com
                            Telephone: 1-855-473-7449
                        """).format(**{
                            "customer_name": customer_name,
                            "opening": opening,
                            "contract_type": contract_type,
                            "chassis_hardware": model,
                            "serial_numbers": serial_numbers,
                            "contract_start": contract_start,
                            "contract_expiration": contract_expiration,
                            "encouraging": encouraging,
                        })
                    },
                ))
                break

        return alerts
