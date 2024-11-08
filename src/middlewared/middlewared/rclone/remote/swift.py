from middlewared.rclone.base import BaseRcloneRemote


class OpenStackSwiftRcloneRemote(BaseRcloneRemote):
    name = "OPENSTACK_SWIFT"
    title = "OpenStack Swift"

    buckets = True
    bucket_title = "Container"

    fast_list = True

    rclone_type = "swift"
