class BaseRcloneRemote:
    name = NotImplemented
    title = NotImplemented

    buckets = False
    bucket_title = "Bucket"

    readonly = False

    fast_list = False

    rclone_type = NotImplemented

    credentials_schema = NotImplemented
    credentials_oauth = False
    credentials_oauth_name = None
    refresh_credentials = []

    task_schema = []

    extra_methods = []

    def __init__(self, middleware):
        self.middleware = middleware

    async def pre_save_task(self, task, credentials, verrors):
        pass

    async def get_credentials_extra(self, credentials):
        return dict()

    async def get_task_extra(self, task):
        return dict()

    async def cleanup(self, task, config):
        pass
