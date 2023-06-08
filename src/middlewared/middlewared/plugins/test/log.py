from middlewared.service import Service


class TestService(Service):
    class Config:
        private = True

    def notify_test_start(self, name):
        self.middleware.logger.debug("Starting integration test %s", name)

    def notify_test_end(self, name):
        self.middleware.logger.debug("Ending integration test %s", name)
