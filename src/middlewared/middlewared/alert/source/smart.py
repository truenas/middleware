# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from datetime import timedelta

from middlewared.alert.base import (
    Alert,
    AlertCategory,
    AlertClass,
    AlertLevel,
    ThreadedAlertSource,
)
from middlewared.alert.schedule import IntervalSchedule


class SMARTUncorrectedErrorsAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.WARNING
    title = "Uncorrected Errors Detected"
    text = '"%(ue)d uncorrectable errors reported for %(name)s (%(serial)s).'


class SMARTFailedSelfTestAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.WARNING
    title = "Failed Selftest"
    text = '"%(name)s (%(serial)s) failed a SMART selftest.'


class SMARTAlertSource(ThreadedAlertSource):
    run_on_backup_node = False
    schedule = IntervalSchedule(timedelta(minutes=90))

    def parse_ata_smart_info(self, data: dict) -> tuple[int, bool]:
        uncorrected, test_failed = 0, False
        for attr in data.get("ata_smart_attributes", {}).get("table", []):
            if attr["id"] == 187:  # Reported Uncorrectable Errors
                uncorrected = attr["raw"]["value"]
                break

        if ata_tests := data.get("ata_smart_self_test_log", {}).get("table", []):
            test_failed = not ata_tests[-1]["status"]["passed"]

        return uncorrected, test_failed

    def parse_scsi_smart_info(self, data: dict) -> tuple[int, bool]:
        uncorrected, test_failed = 0, False
        pkey, errkey = "scsi_error_counter_log", "total_uncorrected_errors"
        uncorrected += data.get(pkey, {}).get("read", {errkey: 0})[errkey]
        uncorrected += data.get(pkey, {}).get("write", {errkey: 0})[errkey]
        uncorrected += data.get(pkey, {}).get("verify", {errkey: 0})[errkey]
        test_prefix = "scsi_self_test_"
        failed_tests, last_failed_idx = list(), -1
        for idx in range(0, 21):  # 20 tests maximum are returned
            try:
                if data[f"{test_prefix}{idx}"]["result"]["value"] in (3, 4, 5, 6, 7):
                    # T10/1416-D (SPC-3) Rev. 23, section 7.2.10
                    failed_tests.append(idx)
                    last_failed_idx = idx
            except KeyError:
                continue

        # if a smart test failed and it was the latest
        # one that failed, raise an alert
        test_failed = failed_tests and max(failed_tests) == last_failed_idx

        return uncorrected, test_failed

    def parse_nvme_smart_info(self, data: dict) -> tuple[int, bool]:
        latest_entry = data.get("nvme_self_test_log", {}).get(
            "table", [{"self_test_result": {"value": -1}}]
        )[-1]
        return 0, latest_entry["self_test_result"]["value"] in (5, 6, 7)

    def parse_smart_test_log(self, data: dict) -> tuple[int, bool]:
        # Currently we only alert on uncorrected errors
        # or if a disk's last SMART test failed. This was
        # at the behest of the support team.
        if data["device"]["protocol"] == "ATA":
            return self.parse_ata_smart_info(data)
        elif data["device"]["protocol"] == "SCSI":
            return self.parse_scsi_smart_info(data)
        elif data["device"]["protocol"] == "NVMe":
            return self.parse_nvme_smart_info(data)

    def check_sync(self):
        alerts = list()
        for disk in self.middleware.call_sync("disk.get_disks"):
            if "pmem" in disk.name:
                continue

            try:
                ue, testfail = self.parse_smart_test_log(
                    disk.smartctl_info(return_json=True)
                )
                if ue:
                    alerts.append(
                        Alert(
                            SMARTUncorrectedErrorsAlertClass,
                            {"ue": ue, "name": disk.name, "serial": disk.serial},
                        )
                    )
                if testfail:
                    alerts.append(
                        Alert(
                            SMARTFailedSelfTestAlertClass,
                            {"name": disk.name, "serial": disk.serial},
                        )
                    )
            except Exception:
                continue
        return alerts
