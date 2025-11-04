from middlewared.rclone.base import BaseRcloneRemote


class B2RcloneRemote(BaseRcloneRemote):
    name = "B2"
    title = "Backblaze B2"

    buckets = True

    fast_list = True

    rclone_type = "b2"

    task_attributes = ["chunk_size"]

    async def get_task_extra(self, task):
        chunk_size = task["attributes"].get("chunk_size", 96)
        extra = {"chunk_size": f"{chunk_size}M"}
        if chunk_size > 200:
            extra["upload_cutoff"] = f"{chunk_size}M"
        return extra

    async def get_task_extra_args(self, task):
        chunk_size = task["attributes"].get("chunk_size", 96)
        if chunk_size > 128:
            return [f"--multi-thread-cutoff={chunk_size * 2 + 1}M"]

        return []
