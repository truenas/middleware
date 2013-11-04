import logging

from django.test.client import Client

from tastypie.test import ResourceTestCase, TestApiClient
from freenasUI.account.models import bsdGroups, bsdUsers
from freenasUI.system.models import Advanced, Settings

log = logging.getLogger('api.tests.utils')


class BasicClient(Client):

    def request(self, **request):
        request['HTTP_AUTHORIZATION'] = self._auth
        return super(BasicClient, self).request(**request)


class BasicAPIClient(TestApiClient):

    def __init__(self, auth=None, *args, **kwargs):
        super(BasicAPIClient, self).__init__(*args, **kwargs)
        self.client = BasicClient()
        self.client._auth = auth


class TestCaseMeta(type):

    def __new__(cls, name, bases, attrs):
        new_class = type.__new__(cls, name, bases, attrs)
        if name.endswith('ResourceTest'):
            rsname = name.replace('ResourceTest', '').lower()
            app = new_class.__module__.rsplit('.', 1)[-1]
            if new_class.resource_name is None:
                new_class.resource_name = "%s/%s" % (app, rsname)
        return new_class


class APITestCase(ResourceTestCase):

    __metaclass__ = TestCaseMeta

    resource_name = None

    def setUp(self):
        super(APITestCase, self).setUp()
        self._settings = Settings.objects.create()
        self._advanced = Advanced.objects.create()
        username = 'root'
        password = 'freenas'
        group = bsdGroups.objects.create(
            bsdgrp_gid=0,
            bsdgrp_group='wheel',
            bsdgrp_builtin=True,
        )
        bsdUsers.objects.create(
            bsdusr_uid=0,
            bsdusr_username=username,
            bsdusr_group=group,
            bsdusr_unixhash=(
                '$6$un7OYaDmnBK27g4b$HL1d32nikEFQIJyn6w3bpWWJyEnRH74K46r4VoAo'
                'r27WSbZpbfNm3A4DJGX96XQQNFcgUGLmofLI8uFbr6XbH.'
            ), # encrypted 'freenas'
        )
        self.api_client = BasicAPIClient(auth=self.create_basic(
            username=username,
            password=password,
        ))

    def get_resource_name(self):
        return self.resource_name

    def get_api_url(self):
        return '/api/v1.0/%s/' % self.get_resource_name()
