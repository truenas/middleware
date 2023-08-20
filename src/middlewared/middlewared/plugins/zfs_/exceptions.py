from middlewared.service import CallError


class ZFSSetPropertyError(CallError):
    def __init__(self, property_, error):
        self.property = property_
        self.error = error
        super().__init__(f'Failed to update dataset: failed to set property {self.property}: {self.error}')
