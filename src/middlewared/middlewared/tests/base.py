import os
import unittest

from client import Client
from paramiko import AutoAddPolicy
from paramiko.client import SSHClient


class RESTTestCase(unittest.TestCase):

    def setUp(self):
        self.client = self.shared.client
        self.ssh_client = self.shared.ssh_client

    def ssh_exec(self, command):
        _, stdout, stderr = self.ssh_client.exec_command(command)
        exitcode = stdout.channel.recv_exit_status()
        return exitcode, stdout.read(), stderr.read()


class CRUDTestCase(RESTTestCase):

    name = None

    def get_create_data(self):
        raise NotImplementedError('get_create_data needs to be implemented')

    def get_update_ident_data(self):
        raise NotImplementedError('get_update_ident_data must be implemented')

    def get_delete_identifier(self):
        raise NotImplementedError('get_delete_identifier needs to be implemented')

    def test_020_create(self):
        r = self.client.post(self.name, self.get_create_data())
        self.assertEqual(r.status_code, 201, msg=r.text)
        data = r.json()
        return r

    def test_040_retrieve(self):
        r = self.client.get(self.name)
        self.assertEqual(r.status_code, 200, msg=r.text)
        data = r.json()
        self.assertIsInstance(data, list)
        return r

    def test_060_update(self):
        identifier, data = self.get_update_ident_data()
        r = self.client.put(self.name + '/id/' + identifier, data)
        self.assertEqual(r.status_code, 200, msg=r.text)
        return r

    def test_080_delete(self):
        r = self.client.delete('{0}/id/{1}'.format(self.name, self.get_delete_identifier()))
        self.assertEqual(r.status_code, 204, msg=r.text)
        return r


class SingleItemTestCase(RESTTestCase):

    name = None

    def get_update_data(self):
        raise NotImplementedError('get_update_data must be implemented')

    def test_020_retrieve(self):
        r = self.client.get(self.name)
        self.assertEqual(r.status_code, 200, msg=r.text)
        data = r.json()
        self.assertIsInstance(data, dict)
        return r

    def test_040_update(self):
        r = self.client.put(self.name, self.get_update_data())
        self.assertEqual(r.status_code, 200, msg=r.text)
        return r
