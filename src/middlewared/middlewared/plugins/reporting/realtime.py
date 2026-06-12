from __future__ import annotations

import time
import typing

from middlewared.api.current import ReportingRealtimeEventSourceArgs, ReportingRealtimeEventSourceEvent
from middlewared.event import TypedEventSource
from middlewared.service import Service, private

from .realtime_stats import get_disks_with_identifiers
from .realtime_stats import stats as _stats

__all__ = ("ReportingRealtimeService",)


class RealtimeEventSource(TypedEventSource[ReportingRealtimeEventSourceArgs]):
    """
    Retrieve real time statistics for CPU, network,
    virtual memory and zfs arc.
    """

    args = ReportingRealtimeEventSourceArgs
    event = ReportingRealtimeEventSourceEvent
    roles = ["REPORTING_READ"]

    def run_sync(self) -> None:
        interval = self.typed_arg.interval
        disk_mapping = get_disks_with_identifiers()

        while not self._cancel_sync.is_set():
            fields = self.middleware.call_sync("reporting.realtime.stats", disk_mapping)
            if fields:
                self.send_event("ADDED", fields=fields)
            time.sleep(interval)


class ReportingRealtimeService(Service):
    class Config:
        namespace = "reporting.realtime"
        cli_private = True
        event_sources = {
            "reporting.realtime": RealtimeEventSource,
        }

    @private
    def stats(self, disk_mapping: dict[str, str] | None = None) -> dict[str, typing.Any]:
        return _stats(self.context, disk_mapping)
