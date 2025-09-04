# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from dataclasses import dataclass
from datetime import timedelta

from middlewared.alert.base import (
    Alert,
    AlertCategory,
    AlertClass,
    AlertLevel,
    ThreadedAlertSource,
)
from middlewared.alert.schedule import IntervalSchedule


@dataclass(slots=True, kw_only=True)
class SmartInfo:
    uncorrected_errors: int = 0
    smart_testfail: bool = False
    spare_block_reserve: int | None = None
    erase_count: int | None = None
    unknown_device: bool = False


class SMARTUncorrectedErrorsAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.WARNING
    title = "Uncorrected Errors Detected"
    text = "%(ue)d uncorrectable errors reported for %(name)s (%(serial)s)."


class SMARTFailedSelfTestAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.WARNING
    title = "Failed Selftest"
    text = "%(name)s (%(serial)s) failed a SMART selftest."


class SMARTSpareBlockCountAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.CRITICAL
    title = "Low Spare Block Reserve"
    text = "%(name)s (%(serial)s) is reporting a low spare block reserve (%(sb)d) ."


class SMARTEraseCycleCountAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.WARNING
    title = "High Erase Cycle Count"
    text = "%(name)s (%(serial)s) has a high erase cycle count (%(ec)d) (raw (%(ec_raw)d)."


class SMARTAlertSource(ThreadedAlertSource):
    run_on_backup_node = False
    schedule = IntervalSchedule(timedelta(minutes=90))

    def parse_ata_smart_info(self, data: dict) -> SmartInfo:
        ue, test_failed, sbr, ec = 0, False, 0, 0
        for attr in data.get("ata_smart_attributes", {}).get("table", []):
            if attr["id"] == 187:
                ue = attr["raw"]["value"]
            elif attr["id"] == 170:
                sbr = attr["value"]
            elif attr["id"] == 173:
                ec = attr["raw"]["value"]

        if ata_tests := data.get("ata_smart_self_test_log", {}).get("table", []):
            test_failed = not ata_tests[-1]["status"]["passed"]

        return SmartInfo(
            uncorrected_errors=ue,
            smart_testfail=test_failed,
            spare_block_reserve=sbr,
            erase_count=ec,
        )

    def parse_scsi_smart_info(self, data: dict) -> SmartInfo:
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

        return SmartInfo(
            uncorrected_errors=uncorrected,
            smart_testfail=test_failed,
        )

    def parse_nvme_smart_info(self, data: dict) -> SmartInfo:
        latest_entry = data.get("nvme_self_test_log", {}).get(
            "table", [{"self_test_result": {"value": -1}}]
        )[-1]
        return SmartInfo(
            smart_testfail=latest_entry["self_test_result"]["value"] in (5, 6, 7),
        )

    def parse_smart_info(self, data: dict) -> SmartInfo:
        proto = data.get("device", {}).get("protocol")
        if not proto:
            return SmartInfo(unknown_device=True)

        match proto:
            case "ATA":
                return self.parse_ata_smart_info(data)
            case "SCSI":
                return self.parse_scsi_smart_info(data)
            case "NVMe":
                return self.parse_nvme_smart_info(data)
            case _:
                return SmartInfo(unknown_device=True)

    def micron_phison_check(self, sijson, si, is_ent):
        alerts = list()
        model = sijson.get("model_name", "")
        if not is_ent or not model:
            return alerts

        is_micron = model.startswith("Micron_5210")
        is_phison = model.startswith("QSP")
        if not any((is_micron, is_phison)):
            return alerts

        if si.spare_block_reserve is not None and si.spare_block_reserve <= 90:
            # Rule: Trigger critical alert when the Spare Block Reserve
            # (a.k.a. “Bad Block Count” on Phison / “Reserved Block Count” on Micron)
            # falls below 90% of its initial value.
            alerts.append(
                SMARTSpareBlockCountAlertClass(
                    {
                        "name": sijson["device"]["name"],
                        "serial": sijson["serial_number"],
                        "sb": si.spare_block_reserve,
                    }
                )
            )

        if si.erase_count is not None:
            ec = 0
            if is_micron:
                # Micron calls it "Average Block-Erase Count"
                # and we can parse the value as-is.
                ec = si.erase_count
            else:
                # Phison calls it "Erase Count" and we must
                # pack the value to 6 bytes and pull out
                # bytes 2 and 3 according to OEM.
                ec = si.erase_count.to_bytes(6, byteorder="little")
                ec = ec[2] | (ec[3] << 8)

            if ec > 3000:
                # Rule: Trigger warning alert when the
                # Block Erase Count has a Raw Value > 3000.
                alerts.append(
                    SMARTEraseCycleCountAlertClass(
                        {
                            "name": sijson["device"]["name"],
                            "serial": sijson["serial_number"],
                            "ec": ec,
                            "ec_raw": si.erase_count,
                        }
                    )
                )

        return alerts

    def check_sync(self):
        alerts = list()
        is_ent = self.middleware.call_sync("system.is_enterprise")
        for disk in self.middleware.call_sync("disk.get_disks"):
            if "pmem" in disk.name:
                continue

            try:
                sijson = disk.smartctl_info(return_json=True, raise_alert=False)
                parsed = self.parse_smart_info(sijson)
                if parsed.unknown_device:
                    # empty SD card readers, USB bridges, etc
                    continue

                if parsed.uncorrected_errors:
                    alerts.append(
                        Alert(
                            SMARTUncorrectedErrorsAlertClass,
                            {
                                "ue": parsed.uncorrected_errors,
                                "name": disk.name,
                                "serial": disk.serial,
                            },
                        )
                    )
                if parsed.smart_testfail:
                    alerts.append(
                        Alert(
                            SMARTFailedSelfTestAlertClass,
                            {"name": disk.name, "serial": disk.serial},
                        )
                    )
                alerts.extend(self.micron_phison_check(sijson, parsed, is_ent))
            except Exception:
                self.middleware.logger.exception("Unexpected failure parsing SMART info")
                continue
        return alerts
