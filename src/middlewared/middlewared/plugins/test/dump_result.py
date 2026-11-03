from middlewared.service import Service


class TestService(Service):
    class Config:
        private = True

    def set_dump_result_allow_fallback(self, allow_fallback: bool):
        self.middleware.dump_result_allow_fallback = allow_fallback
