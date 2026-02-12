# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from collections import defaultdict
from datetime import date, timedelta
import textwrap

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, ThreadedAlertSource
from middlewared.alert.schedule import IntervalSchedule
from middlewared.utils import ProductType
from middlewared.utils.license import LICENSE_ADDHW_MAPPING


class LicenseAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.CRITICAL
    title = "TrueNAS License Issue"
    text = "%s"
    products = (ProductType.ENTERPRISE,)


class LicenseIsExpiringAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.WARNING
    title = "TrueNAS License Is Expiring"
    text = "%s"
    products = (ProductType.ENTERPRISE,)


class LicenseHasExpiredAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.CRITICAL
    title = "TrueNAS License Has Expired"
    text = "%s"
    products = (ProductType.ENTERPRISE,)


class LicenseStatusAlertSource(ThreadedAlertSource):
    products = (ProductType.ENTERPRISE,)
    run_on_backup_node = False
    schedule = IntervalSchedule(timedelta(hours=24))

    def check_sync(self):
        alerts = []

        local_license = self.middleware.call_sync('system.license')
        if local_license is None:
            return Alert(LicenseAlertClass, "Your TrueNAS has no license, contact support.")

        # check if this node's system serial matches the serial in the license
        local_serial = self.middleware.call_sync('system.dmidecode_info')['system-serial-number']
        if local_serial not in (local_license['system_serial'], local_license['system_serial_ha']):
            alerts.append(Alert(LicenseAlertClass, 'System serial does not match license.'))

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
                alerts.append(Alert(LicenseAlertClass, 'System serial of standby node does not match license.',))

        model = self.middleware.call_sync('truenas.get_chassis_hardware').removeprefix('TRUENAS-').split('-')[0]
        if model == 'UNKNOWN':
            alerts.append(Alert(LicenseAlertClass, 'TrueNAS is running on unsupported hardware.'))
        elif model != local_license['model']:
            alerts.append(Alert(
                LicenseAlertClass,
                (
                    f'Your license was issued for model {local_license["model"]!r} '
                    f'but the system was detected as model {model!r}'
                )
            ))

        enc_nums = defaultdict(lambda: 0)
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
                        LicenseAlertClass,
                        (
                            'License expects %(license)s units of %(name)s Expansion shelf but found %(found)s.' % {
                                'license': quantity,
                                'name': name,
                                'found': enc_nums[name]
                            }
                        )
                    ))
        elif enc_nums:
            alerts.append(Alert(
                LicenseAlertClass,
                'Unlicensed Expansion shelf detected. This system is not licensed for additional expansion shelves.'
            ))

        for days in [0, 14, 30, 90, 180]:
            if local_license['contract_end'] <= date.today() + timedelta(days=days):
                serial_numbers = ", ".join(list(filter(None, [local_license['system_serial'],
                                                              local_license['system_serial_ha']])))
                contract_start = local_license['contract_start'].strftime("%B %-d, %Y")
                contract_expiration = local_license['contract_end'].strftime("%B %-d, %Y")
                contract_type = local_license['contract_type']  # Display as stored, usually upper case.
                customer_name = local_license['customer_name']

                if days == 0:
                    alert_klass = LicenseHasExpiredAlertClass
                    alert_text = textwrap.dedent("""\
                        SUPPORT CONTRACT EXPIRATION: Please reactivate and continue to receive technical support and
                        assistance. Contact by email: sales@TrueNAS.com, or telephone: 1-855-473-7449
                    """)
                    subject = "Your TrueNAS support contract has expired"
                    opening = textwrap.dedent("""\
                        Your support contract has ended. A support contract may be renewed after contract expiration.
                        Please contact your authorized reseller or TrueNAS (sales@TrueNAS.com).
                    """)
                    encouraging = textwrap.dedent("""\
                        Please renew the support contract for your TrueNAS product as soon as possible to maintain support services.
                        Contact your authorized reseller or TrueNAS (email: sales@TrueNAS.com, phone: 1-855-473-7449).
                    """)
                else:
                    alert_klass = LicenseIsExpiringAlertClass
                    alert_text = textwrap.dedent(f"""\
                        RENEW YOUR SUPPORT CONTRACT:  The support contract for this product will expire on {contract_expiration}.
                        Please avoid service interruptions, contact your authorized reseller or
                        email: sales@TrueNAS.com, phone: 1-855-473-7449.
                    """)
                    days_left = (local_license['contract_end'] - date.today()).days
                    subject = f"Your TrueNAS support contract will expire in {days_left} days"
                    if days == 14:
                        opening = textwrap.dedent(f"""\
                            The support contracts for the following TrueNAS products are expiring in 14 days:
                            {serial_numbers}
                            This is a reminder regarding the impending expiration of your TrueNAS
                            {contract_type} support contract.
                        """)
                        encouraging = textwrap.dedent("""\
                            We encourage you to urgently contact your authorized reseller or TrueNAS
                            (email: sales@TrueNAS.com, telephone: 1-855-473-7449) and renew your support contracts.
                        """)
                    else:
                        opening = textwrap.dedent(f"""\
                            Your TrueNAS {contract_type} support contract will expire in {days_left} days.
                            Please consider renewing your support contract now.  Contact your authorized
                            reseller or TrueNAS.  email: sales@TrueNAS.com, telephone: 1-855-473-7449.
                        """)
                        encouraging = textwrap.dedent("""\
                            Please contact your authorized reseller or TrueNAS (email: sales@TrueNAS.com,
                            telephone: 1-855-473-7449) to renew your contract before expiration.
                        """)

                alerts.append(Alert(
                    alert_klass,
                    alert_text,
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
                            A support contract may be renewed after it has expired and there may be additional
                            costs associated with contract reactivation and lapsed-contract fees.

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
