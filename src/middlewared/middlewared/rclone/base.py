class BaseRcloneRemote:
    name = NotImplemented
    title = NotImplemented

    buckets = False
    readonly = False

    rclone_type = NotImplemented

    credentials_schema = NotImplemented
    refresh_credentials = False

    task_schema = []

    def __init__(self, middleware):
        self.middleware = middleware

    async def pre_save_task(self, task, credentials, verrors):
        pass

    def get_credentials_extra(self, credentials):
        return dict()

    def get_task_extra(self, task):
        return dict()
