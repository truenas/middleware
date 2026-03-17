import datetime
import logging
import os
from dataclasses import dataclass
from typing import Any

from middlewared.alert.base import AlertClass, AlertClassConfig, AlertCategory, AlertLevel, Alert, ThreadedAlertSource
from middlewared.alert.schedule import IntervalSchedule
from truenas_os_pyutils.mount import iter_mountinfo
from middlewared.utils.size import format_size
from middlewared.plugins.zfs_.utils import TNUserProp

logger = logging.getLogger(__name__)


@dataclass(kw_only=True)
class QuotaWarningAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.STORAGE,
        level=AlertLevel.WARNING,
        title="Quota Exceeded on Dataset",
        text="%(name)s exceeded on dataset %(dataset)s. Used %(used_fraction).2f%% (%(used)s of %(quota_value)s).",
    )

    name: str
    dataset: str
    used_fraction: float
    used: str
    quota_value: str
    quota_property: str

    @classmethod
    def key_from_args(cls, args: Any) -> Any:
        return [args['dataset'], args['quota_property']]


@dataclass(kw_only=True)
class QuotaCriticalAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.STORAGE,
        level=AlertLevel.CRITICAL,
        title="Critical Quota Exceeded on Dataset",
        text="%(name)s exceeded on dataset %(dataset)s. Used %(used_fraction).2f%% (%(used)s of %(quota_value)s).",
    )

    name: str
    dataset: str
    used_fraction: float
    used: str
    quota_value: str
    quota_property: str

    @classmethod
    def key_from_args(cls, args: Any) -> Any:
        return [args['dataset'], args['quota_property']]


class QuotaAlertSource(ThreadedAlertSource):
    schedule = IntervalSchedule(datetime.timedelta(hours=1))
    run_on_backup_node = False

    def __cast_threshold(self, val: Any) -> int:
        try:
            return abs(int(val))
        except Exception:
            # this is a zfs user property that can
            # be altered trivially by-hand, let's
            # not crash here
            return 0

    def check_sync(self) -> list[Alert[Any]]:
        alerts: list[Alert[Any]] = []
        hostname = self.middleware.call_sync("system.hostname")
        mntinfo = list(iter_mountinfo())
        rv = self.middleware.call_sync("pool.dataset.query_for_quota_alert")
        for ds, info in rv["datasets"].items():
            props, uprops = info["properties"], info["user_properties"]
            for quota_property in ("quota", "refquota"):
                quota_value = props[quota_property]["value"]
                if quota_value == 0:
                    # if there is no quota on the dataset
                    # then there is no reason to continue
                    continue

                warn_prop = TNUserProp[f"{quota_property.upper()}_WARN"]
                warning_threshold = self.__cast_threshold(uprops[warn_prop.value])
                if warning_threshold == 0:
                    # there is a quota on the dataset but there is
                    # no warning threshold configured or the value
                    # written isn't a number
                    continue

                crit_prop = TNUserProp[f"{quota_property.upper()}_CRIT"]
                critical_threshold = self.__cast_threshold(uprops[crit_prop.value])
                if critical_threshold == 0:
                    # there is a quota on the dataset but there is
                    # no critical threshold configured or the value
                    # written isn't a number
                    continue

                if quota_property == "quota":
                    # We can't use "used" property since it includes refreservation
                    # But if "refquota" is smaller than "quota", then "available"
                    # will be reported with regards to that smaller value, and we
                    # will get false positive
                    refquota_value = props["refquota"]["value"]
                    if refquota_value and refquota_value < quota_value:
                        continue

                    if quota_value > rv["pools"][info["pool"]]:
                        # Quota larger than zpool's total size will never
                        # be exceeded but will break our logic
                        continue

                    used = quota_value - props["available"]["value"]
                elif quota_property == "refquota":
                    used = props["usedbydataset"]["value"]

                used_fraction = 100 * used / quota_value
                klass: type[QuotaCriticalAlert] | type[QuotaWarningAlert]
                if used_fraction >= critical_threshold:
                    klass = QuotaCriticalAlert
                elif used_fraction >= warning_threshold:
                    klass = QuotaWarningAlert
                else:
                    continue

                quota_name = quota_property.title()
                instance = klass(
                    name=quota_name,
                    dataset=ds,
                    used_fraction=used_fraction,
                    used=format_size(used),
                    quota_value=format_size(quota_value),
                    quota_property=quota_property,
                )

                mail = None
                owner = self._get_owner(ds, props, mntinfo)
                if owner != 0:
                    try:
                        self.middleware.call_sync('user.get_user_obj', {'uid': owner})
                    except KeyError:
                        to = None
                        logger.debug("Unable to query user with uid %r", owner)
                    else:
                        try:
                            bsduser = self.middleware.call_sync(
                                "datastore.query",
                                "account.bsdusers",
                                [["bsdusr_uid", "=", owner]],
                                {"get": True},
                            )
                            to = bsduser["bsdusr_email"] or None
                        except IndexError:
                            to = None

                    if to is not None:
                        mail = {
                            "to": [to],
                            "subject": f"{hostname}: {quota_name} exceeded on dataset {ds}",
                            "text": instance.format(instance.args())
                        }

                alerts.append(Alert(
                    instance,
                    mail=mail,
                ))
        return alerts

    def _get_owner(self, dataset_name: str, props: Any, mntinfo: Any) -> int:
        mountpoint = None
        if props["mounted"]["value"] is True:
            if props["mountpoint"]["raw"] == "legacy":
                for v in mntinfo:
                    if v["mount_source"] == dataset_name:
                        mountpoint = v["mountpoint"]
                        break
            else:
                mountpoint = props["mountpoint"]["raw"]

        if mountpoint is None:
            logger.debug("Unable to get mountpoint for dataset %r, assuming owner = root", dataset_name)
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
