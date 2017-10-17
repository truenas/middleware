import os


async def check_path_resides_within_volume(verrors, middleware, name, path):
    vol_names = [vol["vol_name"] for vol in await middleware.call("datastore.query", "storage.volume")]
    vol_paths = [os.path.join("/mnt", vol_name) for vol_name in vol_names]
    if not any(os.path.commonpath([parent]) == os.path.commonpath([parent, path]) for parent in vol_paths):
        verrors.add(name, "The path must reside within a volume mount point")
