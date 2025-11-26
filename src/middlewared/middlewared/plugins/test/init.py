from middlewared.service import Service


class TestService(Service):
    class Config:
        private = True

    def init(self):
        # Make result model validation errors cause test failures
        self.middleware.dump_result_allow_fallback = False
