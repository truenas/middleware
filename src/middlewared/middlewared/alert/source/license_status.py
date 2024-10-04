# Copyright (c) - iXsystems Inc.
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from collections import defaultdict
from datetime import date, timedelta
import textwrap

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, ThreadedAlertSource
from middlewared.alert.schedule import IntervalSchedule
from middlewared.plugins.system.product import ProductType
from middlewared.utils.license import LICENSE_ADDHW_MAPPING


class LicenseAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.CRITICAL
    title = "TrueNAS License Issue"
    text = "%s"
    products = (ProductType.SCALE_ENTERPRISE,)


class LicenseIsExpiringAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.WARNING
    title = "TrueNAS License Is Expiring"
    text = "%s"
    products = (ProductType.SCALE_ENTERPRISE,)


class LicenseHasExpiredAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.CRITICAL
    title = "TrueNAS License Has Expired"
    text = "%s"
    products = (ProductType.SCALE_ENTERPRISE,)


class LicenseStatusAlertSource(ThreadedAlertSource):
    products = (ProductType.SCALE_ENTERPRISE,)
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
        elif any((
            # f-series has 2 license models F60 and F60-NR (NR is single-node only)
            (local_license['model'][0] == 'F' and model != local_license['model'].split('-')[0]),
            (model != local_license['model'])
        )):
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
                contract_type = local_license['contract_type'].lower()
                customer_name = local_license['customer_name']

                if days == 0:
                    alert_klass = LicenseHasExpiredAlertClass
                    alert_text = textwrap.dedent("""\
                        SUPPORT CONTRACT EXPIRATION. To reactivate and continue to receive technical support and
                        assistance, contact iXsystems @ telephone: 1-855-473-7449
                    """)
                    subject = "Your TrueNAS support contract has expired"
                    opening = textwrap.dedent("""\
                        As of today, your support contract has ended. You will no longer be eligible for technical
                        support and assistance for your TrueNAS system.
                    """)
                    encouraging = textwrap.dedent("""\
                        It is still not too late to renew your contract but you must do so as soon as possible by
                        contacting your authorized TrueNAS Reseller or iXsystems (sales@iXsystems.com) today to avoid
                        additional costs and lapsed-contract fees.
                    """)
                else:
                    alert_klass = LicenseIsExpiringAlertClass
                    alert_text = textwrap.dedent(f"""\
                        RENEW YOUR SUPPORT contract. To continue to receive technical support and assistance without
                        any service interruptions, please renew your support contract by {contract_expiration}.
                    """)
                    days_left = (local_license['contract_end'] - date.today()).days
                    subject = f"Your TrueNAS support contract will expire in {days_left} days"
                    if days == 14:
                        opening = textwrap.dedent(f"""\
                            This is the final reminder regarding the impending expiration of your TrueNAS
                            {contract_type} support contract. As of today, it is set to expire in 2 weeks.
                        """)
                        encouraging = textwrap.dedent("""\
                            We encourage you to urgently contact your authorized TrueNAS Reseller or iXsystems
                            (sales@iXsystems.com) directly to renew your contract before expiration so that you continue
                            to enjoy the peace of mind and benefits that come with our support contracts.
                        """)
                    else:
                        opening = textwrap.dedent(f"""\
                            Your TrueNAS {contract_type} support contract will expire in {days_left} days.
                            When that happens, technical support and assistance for this particular TrueNAS storage
                            array will no longer be available. Please review the wide array of services that are
                            available to you as an active support contract customer at:
                            https://www.ixsystems.com/support/ and click on the “TrueNAS Arrays” tab.
                        """)
                        encouraging = textwrap.dedent("""\
                            We encourage you to contact your authorized TrueNAS Reseller or iXsystems directly
                            (sales@iXsystems.com) to renew your contract before expiration. Doing so ensures that
                            you continue to enjoy the peace of mind and benefits that come with support coverage.
                        """)

                alerts.append(Alert(
                    alert_klass,
                    alert_text,
                    mail={
                        "cc": ["support-renewal@ixsystems.com"],
                        "subject": subject,
                        "text": textwrap.dedent("""\
                            Hello, {customer_name}

                            {opening}

                            Product: {chassis_hardware}
                            Serial Numbers: {serial_numbers}
                            Support Contract Start Date: {contract_start}
                            Support Contract Expiration Date: {contract_expiration}

                            {encouraging}

                            If the contract expires, you will still be able to access your TrueNAS systems. However,
                            you will no longer be eligible for support from iXsystems. If you choose to renew your
                            support contract after it has expired, there are additional costs associated with
                            contract reactivation and lapsed-contract fees.

                            Sincerely,

                            iXsystems
                            Web: support.iXsystems.com
                            Email: support@iXsystems.com
                            Telephone: 1-855-473-7449
                        """).format(**{
                            "customer_name": customer_name,
                            "opening": opening,
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
