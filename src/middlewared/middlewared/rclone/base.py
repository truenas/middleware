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

    credentials_schema = NotImplemented
    credentials_oauth = False
    credentials_oauth_name = None
    refresh_credentials = []

    task_schema = []

    extra_methods = []

    restic = False

    def __init__(self, middleware):
        self.middleware = middleware

    async def create_bucket(self, credentials, name):
        raise NotImplementedError

    async def list_buckets(self, credentials):
        raise NotImplementedError

    async def pre_save_task(self, task, credentials, verrors):
        pass

    async def get_credentials_extra(self, credentials):
        return dict()

    async def get_task_extra(self, task):
        return dict()

    async def cleanup(self, task, config):
        pass

    def get_restic_config(self, task):
        raise NotImplementedError
