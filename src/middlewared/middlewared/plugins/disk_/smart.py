from middlewared.service import CallError, private, Service


class DiskService(Service):
    @private
    def smart_test(self, type_: str, disks: list[str]):
        # NOTE: this private endpoint exists solely for
        # a migration that we added when we removed SMART
        # from UI/MW. It's called by our cron plugin.
        errors = list()
        for disk in self.middleware.call_sync("disk.get_disks"):
            if "*" in disks or disk.identifier in disks:
                try:
                    disk.smartctl_test(type_.lower())
                except Exception as e:
                    errors.append(str(e))
        if errors:
            raise CallError("\n\n".join(errors))
