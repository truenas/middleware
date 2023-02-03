from middlewared.service import CallError


class ZFSSetPropertyError(CallError):
    def __init__(self, property, error):
        self.property = property
        self.error = error
        super().__init__(f'Failed to update dataset: failed to set property {self.property}: {self.error}')
