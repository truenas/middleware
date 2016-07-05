import falcon


class RESTfulAPI(object):

    def __init__(self, middleware):
        self.middleware = middleware

        self.app = falcon.API()

    def get_app():
        return self.app
