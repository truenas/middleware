class PoolAttachmentDelegate:
    name = NotImplementedError
    title = NotImplementedError

    def __init__(self, middleware):
        self.middleware = middleware

    async def query(self, pool, enabled):
        raise NotImplementedError

    async def get_attachment_name(self, attachment):
        raise NotImplementedError

    async def delete(self, attachments):
        raise NotImplementedError

    async def toggle(self, attachments, enabled):
        raise NotImplementedError
