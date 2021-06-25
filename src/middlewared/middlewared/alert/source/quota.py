from datetime import timedelta
import logging
import os

try:
    from bsd import getmntinfo
except ImportError:
    getmntinfo = None
import humanfriendly

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, ThreadedAlertSource
from middlewared.alert.schedule import IntervalSchedule

logger = logging.getLogger(__name__)


class QuotaWarningAlertClass(AlertClass):
    category = AlertCategory.STORAGE
    level = AlertLevel.WARNING
    title = "Quota Exceeded on Dataset"
    text = "%(name)s exceeded on dataset %(dataset)s. Used %(used_fraction).2f%% (%(used)s of %(quota_value)s)."


class QuotaCriticalAlertClass(AlertClass):
    category = AlertCategory.STORAGE
    level = AlertLevel.CRITICAL
    title = "Critical Quota Exceeded on Dataset"
    text = "%(name)s exceeded on dataset %(dataset)s. Used %(used_fraction).2f%% (%(used)s of %(quota_value)s)."


class QuotaAlertSource(ThreadedAlertSource):
    schedule = IntervalSchedule(timedelta(minutes=5))

    def check_sync(self):
        alerts = []

        datasets = self.middleware.call_sync("zfs.dataset.query_for_quota_alert")

        for d in datasets:
            d["name"] = d["name"]["rawvalue"]

            for k, default in [("org.freenas:quota_warning", 80), ("org.freenas:quota_critical", 95),
                               ("org.freenas:refquota_warning", 80), ("org.freenas:refquota_critical", 95)]:
                try:
                    d[k] = int(d[k]["rawvalue"])
                except (KeyError, ValueError):
                    d[k] = default

        # call this outside the for loop since we don't need to check
        # for every dataset that could be potentially be out of quota...
        hostname = self.middleware.call_sync("system.hostname")
        datasets = sorted(datasets, key=lambda ds: ds["name"])
        for dataset in datasets:
            for quota_property in ["quota", "refquota"]:
                try:
                    quota_value = int(dataset[quota_property]["rawvalue"])
                except (AttributeError, KeyError, ValueError):
                    continue

                if quota_value == 0:
                    continue

                if quota_property == "quota":
                    # We can't use "used" property since it includes refreservation

                    # But if "refquota" is smaller than "quota", then "available" will be reported with regards to
                    # that smaller value, and we will get false positive
                    try:
                        refquota_value = int(dataset["refquota"]["rawvalue"])
                    except (AttributeError, KeyError, ValueError):
                        continue
                    else:
                        if refquota_value and refquota_value < quota_value:
                            continue

                    used = quota_value - int(dataset["available"]["rawvalue"])
                elif quota_property == "refquota":
                    used = int(dataset["usedbydataset"]["rawvalue"])
                else:
                    raise RuntimeError()

                used_fraction = 100 * used / quota_value

                critical_threshold = dataset[f"org.freenas:{quota_property}_critical"]
                warning_threshold = dataset[f"org.freenas:{quota_property}_warning"]
                if critical_threshold != 0 and used_fraction >= critical_threshold:
                    klass = QuotaCriticalAlertClass
                elif warning_threshold != 0 and used_fraction >= warning_threshold:
                    klass = QuotaWarningAlertClass
                else:
                    continue

                quota_name = quota_property[0].upper() + quota_property[1:]
                args = {
                    "name": quota_name,
                    "dataset": dataset["name"],
                    "used_fraction": used_fraction,
                    "used": humanfriendly.format_size(used, binary=True),
                    "quota_value": humanfriendly.format_size(quota_value, binary=True),
                }

                mail = None
                owner = self._get_owner(dataset)
                if owner != 0:
                    try:
                        bsduser = self.middleware.call_sync(
                            "datastore.query",
                            "account.bsdusers",
                            [["bsdusr_uid", "=", owner]],
                            {"get": True},
                        )
                        to = bsduser["bsdusr_email"] or None
                    except IndexError:
                        logger.debug("Unable to query bsduser with uid %r", owner)
                        to = None

                    if to is not None:
                        mail = {
                            "to": [to],
                            "subject": f"{hostname}: {quota_name} exceeded on dataset {dataset['name']}",
                            "text": klass.text % args
                        }

                alerts.append(Alert(
                    klass,
                    args=args,
                    key=[dataset["name"], quota_property],
                    mail=mail,
                ))

        return alerts

    def _get_owner(self, dataset):
        mountpoint = None
        if dataset["mounted"]["value"] == "yes":
            if dataset["mountpoint"]["value"] == "legacy":
                for m in (getmntinfo() if getmntinfo else []):
                    if m.source == dataset["name"]:
                        mountpoint = m.dest
                        break
            else:
                mountpoint = dataset["mountpoint"]["value"]
        if mountpoint is None:
            logger.debug("Unable to get mountpoint for dataset %r, assuming owner = root", dataset["name"])
            uid = 0
        else:
            try:
                stat_info = os.stat(mountpoint)
            except Exception:
                logger.debug("Unable to stat mountpoint %r, assuming owner = root", mountpoint)
                uid = 0
            else:
                uid = stat_info.st_uid

        return uid
