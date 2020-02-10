from middlewared.rclone.base import BaseRcloneRemote
from middlewared.schema import Str, Int


class OpenStackSwiftRcloneRemote(BaseRcloneRemote):
    name = "OPENSTACK_SWIFT"
    title = "OpenStack Swift"

    buckets = True
    bucket_title = "Container"

    fast_list = True

    rclone_type = "swift"

    credentials_schema = [
        Str("user", required=True,
            title="User name (OS_USERNAME)"),
        Str("key", required=True,
            title="API key or password (OS_PASSWORD)"),
        Str("auth", required=True,
            title="Authentication URL for server (OS_AUTH_URL)"),
        Str("user_id", default="",
            title="User ID to log in - most swift systems use user and leave "
                  "this blank (v3 auth) (OS_USER_ID)"),
        Str("domain", default="",
            title="User domain - optional (v3 auth) (OS_USER_DOMAIN_NAME)"),
        Str("tenant", default="",
            title="Tenant name - optional for v1 auth, this or tenant_id "
                  "required otherwise (OS_TENANT_NAME or OS_PROJECT_NAME)"),
        Str("tenant_id", default="",
            title="Tenant ID - optional for v1 auth, this or tenant required "
                  "otherwise (OS_TENANT_ID)"),
        Str("tenant_domain", default="",
            title="Tenant domain - optional (v3 auth) "
                  "(OS_PROJECT_DOMAIN_NAME)"),
        Str("region", default="",
            title="Region name (OS_REGION_NAME)"),
        Str("storage_url", default="",
            title="Storage URL (OS_STORAGE_URL)"),
        Str("auth_token", default="",
            title="Auth Token from alternate authentication (OS_AUTH_TOKEN)"),
        Str("application_credential_id", default="",
            title="Application Credential ID (OS_APPLICATION_CREDENTIAL_ID)"),
        Str("application_credential_name", default="",
            title="Application Credential Name "
                  "(OS_APPLICATION_CREDENTIAL_NAME)"),
        Str("application_credential_secret", default="",
            title="Application Credential Secret "
                  "(OS_APPLICATION_CREDENTIAL_SECRET)"),
        Int("auth_version", enum=[0, 1, 2, 3],
            title="AuthVersion - set it if your auth URL has no version "
                  "(ST_AUTH_VERSION)"),
        Str("endpoint_type", enum=["public", "internal", "admin"],
            title="Endpoint type to choose from the service catalogue "
                  "(OS_ENDPOINT_TYPE)"),
    ]
