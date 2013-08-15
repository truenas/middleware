from tastypie.test import ResourceTestCase
from freenasUI.api.models import APIClient
from freenasUI.system.models import Advanced, Settings


class APITestCase(ResourceTestCase):

    def setUp(self):
        super(APITestCase, self).setUp()
        self.api = APIClient.objects.create(name='test')
        Settings.objects.create()
        Advanced.objects.create()
