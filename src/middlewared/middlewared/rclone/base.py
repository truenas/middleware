class BaseRcloneRemote:
    name = NotImplemented
    title = NotImplemented

    buckets = False
    bucket_title = "Bucket"
    can_create_bucket = False
    custom_list_buckets = False

    readonly = False

    fast_list = False

    rclone_type = NotImplemented

    credentials_oauth = False
    credentials_oauth_name = None
    refresh_credentials = []

    task_attributes = []

    extra_methods = []

    restic = False

    def __init__(self, middleware):
        self.middleware = middleware

    async def create_bucket(self, credentials, name):
        raise NotImplementedError

    async def list_buckets(self, credentials):
        raise NotImplementedError

    async def validate_task_basic(self, task, credentials, verrors):
        pass

    async def validate_task_full(self, task, credentials, verrors):
        pass

    async def get_credentials_extra(self, credentials):
        return {}

    async def get_task_extra(self, task):
        return {}

    async def get_task_extra_args(self, task):
        return []

    async def cleanup(self, task, config):
        pass

    def get_restic_config(self, task):
        raise NotImplementedError
