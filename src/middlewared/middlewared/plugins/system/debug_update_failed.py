import pathlib
import tempfile

from middlewared.service import private, Service


class SystemService(Service):
    @private
    def gather_update_failed(self):
        result = ""
        if (text := self.gather_update_failed_from_mountpoint("/")) is not None:
            result += f"=== /data/update.failed ===\n\n{text}\n\n"
        for be in self.middleware.call_sync("bootenv.query", [["activated", "!=", True]]):
            try:
                if (text := self.gather_update_failed_from_be(be["id"])) is not None:
                    result += f"=== {be['id']}/data/update.failed ===\n\n{text}\n\n"
            except Exception:
                self.logger.warning(
                    "Unable to gather /data/update.failed from boot environment %r", be["id"], exc_info=True,
                )

        return result

    @private
    def gather_update_failed_from_be(self, id):
        dataset = f"{self.middleware.call_sync('boot.pool_name')}/ROOT/{id}"

        snapshot_name = f"{dataset}@for-debug"
        try:
            self.middleware.call_sync("zfs.snapshot.delete", snapshot_name)
        except Exception:
            pass

        self.middleware.call_sync("zfs.snapshot.create", {"dataset": dataset, "name": "for-debug"})
        try:
            return self.gather_update_failed_from_be_snapshot(snapshot_name)
        finally:
            self.middleware.call_sync("zfs.snapshot.delete", snapshot_name)

    @private
    def gather_update_failed_from_be_snapshot(self, snapshot):
        dataset_dst = f"{self.middleware.call_sync('boot.pool_name')}/for-debug"
        try:
            self.middleware.call_sync("zfs.dataset.delete", dataset_dst)
        except Exception:
            pass

        with tempfile.TemporaryDirectory() as mountpoint:
            try:
                self.middleware.call_sync("zfs.snapshot.clone", {
                    "snapshot": snapshot,
                    "dataset_dst": dataset_dst,
                    "dataset_properties": {
                        "mountpoint": mountpoint,
                    },
                })
                return self.gather_update_failed_from_mountpoint(mountpoint)
            finally:
                self.middleware.call_sync("zfs.dataset.delete", dataset_dst)

    @private
    def gather_update_failed_from_mountpoint(self, path):
        path = pathlib.Path(path) / "data/update.failed"
        if path.exists():
            return path.read_text("utf-8", "ignore").rstrip()
