import pathlib
import tempfile

from middlewared.service import private, Service
from middlewared.plugins.update_.utils import UPDATE_FAILED_SENTINEL


class SystemService(Service):
    @private
    def gather_update_failed(self):
        result = ""
        if (text := self.gather_update_failed_from_mountpoint("/")) is not None:
            result += f"=== {UPDATE_FAILED_SENTINEL} ===\n\n{text}\n\n"
        for be in self.middleware.call_sync("bootenv.query", [["activated", "!=", True]]):
            try:
                if (text := self.gather_update_failed_from_be(be["id"])) is not None:
                    result += f"=== {be['id']}{UPDATE_FAILED_SENTINEL} ===\n\n{text}\n\n"
            except Exception:
                self.logger.warning(
                    "Unable to gather {UPDATE_FAILED_SENTINEL} from boot environment %r", be["id"], exc_info=True,
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
        path = pathlib.Path(path) / UPDATE_FAILED_SENTINEL[1:]  # remove the preceeding `/`
        try:
            return path.read_text("utf-8", "ignore").rstrip()
        except FileNotFoundError:
            pass
