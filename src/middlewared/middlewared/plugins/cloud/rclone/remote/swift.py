from middlewared.api.current import SwiftCredentialsModel
from middlewared.plugins.cloud.rclone.base import BaseRcloneRemote


class OpenStackSwiftRcloneRemote(BaseRcloneRemote[SwiftCredentialsModel]):
    credentials_schema = SwiftCredentialsModel

    name = "OPENSTACK_SWIFT"
    title = "OpenStack Swift"

    buckets = True
    bucket_title = "Container"

    fast_list = True

    rclone_type = "swift"
