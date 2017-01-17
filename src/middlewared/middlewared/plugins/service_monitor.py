import socket
import random
import threading
import middlewared.logger
from freenasUI.middleware.client import client

CURRENT_MONITOR_THREAD = {}


class ServiceMonitor(object):
    """Main-Class for service monitoring."""

    def __init__(self, frequency, retry, fqdn, service_port, service_name):
        self.frequency = frequency
        self.retry = retry
        self.counter = retry
        self.connected = True
        self.func_call = self.test_connection
        self.fqdn = fqdn
        self.service_port = service_port
        self.service_name = service_name
        self.logger = middlewared.logger.Logger('servicemonitor').getLogger()

    def test_connection(self, fqdn, service_port, service_name):
        """Try to open a socket for a given fqdn and service port.

        Args:
                fqdn (str): The hostname and domainname where we will try to connect.
                service_port (int): The service port number.
                service_name (str): Same name used to start/stop/restart method.
        """
        bind = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            bind.connect((fqdn, service_port))
            self.connected = True
        except Exception as error:
            self.connected = False
            self.logger.debug("[ServiceMonitoring] Cannot connect: %s:%d with error: %s" % (fqdn, service_port, error))
            with client as c:
                return c.call('service.restart', service_name, {'onetime': True})
        finally:
            bind.close()

    def createServiceThread(self):
        """Create a thread for the service monitoring and add it into the
        dictonary of running threads.
        """
        global CURRENT_MONITOR_THREAD
        if self.isThreadExist(self.service_name):
            self.destroyServiceThread(self.service_name)

        self.thread = threading.Timer(self.frequency, self.func_handler)
        self.thread.name = self.service_name
        self.thread.fqdn = self.fqdn
        self.thread.frequency = self.frequency
        self.thread.setDaemon(False)
        CURRENT_MONITOR_THREAD[self.thread.name] = self.thread

    def isThreadExist(self, service_name):
        """Verify if a service monitoring is already running for a given service.

        Args:
                    service_name (str): Same name used to start/stop/restart method.

        Returns:
                    bool: True if it is already running or False otherwise.
        """
        for _name in CURRENT_MONITOR_THREAD.keys():
            if _name == service_name:
                return True
        return False

    def destroyServiceThread(self, service_name):
        """Cancel the thread related with the service and remove it from the
        dictionary of running threads.

        Args:
                    service_name (str): Same name used to start/stop/restart method.
        """
        for _name in CURRENT_MONITOR_THREAD.keys():
            if _name == service_name:
                current_thread = CURRENT_MONITOR_THREAD[_name]
                current_thread.cancel()
                del CURRENT_MONITOR_THREAD[_name]

    def func_handler(self):
        """This is a recursive method where will launch a thread with timer
        calling another method.
        """

        if self.connected is False:
            self.counter -= 1
            _random = str(random.randint(1, 1000))
            file_error = '/tmp/.' + _random + self.service_name + '.service_monitor'
            with open(file_error, 'w') as _file:
                _file.write("We tried %d attempts to recover service %s\n" % (self.retry - self.counter, self.service_name))
        else:
            self.counter = self.retry

        if self.isThreadExist(self.service_name) and self.counter > 0:
            self.destroyServiceThread(self.service_name)
            self.func_call(self.fqdn, self.service_port, self.service_name)
            self.thread = threading.Timer(self.frequency, self.func_handler)
            self.thread.name = self.service_name
            self.thread.setDaemon(False)
            CURRENT_MONITOR_THREAD[self.thread.name] = self.thread
            self.thread.start()
        elif self.counter <= 0:
            self.logger.debug("[ServiceMonitoring] We reached the maximum number of attempts to recover service %s, we won't try again" % (self.service_name))
            self.destroyServiceThread(self.service_name)
            file_error = '/tmp/.' + self.service_name + '.service_monitor'
            with open(file_error, 'w') as _file:
                _file.write("We reached the maximum number of %d attempts to recover service %s, we won't try again\n" % (self.retry, self.service_name))

    def start(self):
        """Start a thread."""
        self.thread.start()

    def cancel(self):
        """Cancel a thread."""
        self.thread.cancel()
