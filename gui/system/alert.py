import cPickle
import hashlib
import imp
import logging
import os
import socket
import time

from django.utils.translation import ugettext_lazy as _

from freenasUI.common.system import send_mail
from freenasUI.freeadmin.hook import HookMetaclass
from freenasUI.system.models import Alert as mAlert

log = logging.getLogger('system.alert')


class BaseAlertMetaclass(type):

    def __new__(cls, name, *args, **kwargs):
        klass = type.__new__(cls, name, *args, **kwargs)
        if name.endswith('Alert'):
            klass.name = name[:-5]
        return klass


class BaseAlert(object):

    __metaclass__ = BaseAlertMetaclass

    alert = None
    interval = 0
    name = None

    def __init__(self, alert):
        self.alert = alert

    def run(self):
        """
        Returns a list of Alert objects
        """
        raise NotImplementedError


class Alert(object):

    OK = 'OK'
    CRIT = 'CRIT'
    WARN = 'WARN'

    def __init__(self, level, message, id=None, dismiss=False):
        self._level = level
        self._message = message
        self._dismiss = dismiss
        if id is None:
            self._id = hashlib.md5(message.encode('utf8')).hexdigest()
        else:
            self._id = id

    def __repr__(self):
        return '<Alert: %s>' % self._id

    def __str__(self):
        return str(self._message)

    def __unicode__(self):
        return self._message

    def __eq__(self, other):
        return self.getId() == other.getId()

    def __ne__(self, other):
        return self.getId() != other.getId()

    def __gt__(self, other):
        return self.getId() > other.getId()

    def __ge__(self, other):
        return self.getId() >= other.getId()

    def __lt__(self, other):
        return self.getId() < other.getId()

    def __le__(self, other):
        return self.getId() <= other.getId()

    def getId(self):
        return self._id

    def getLevel(self):
        return self._level

    def getMessage(self):
        return self._message

    def setDismiss(self, value):
        self._dismiss = value

    def getDismiss(self, value):
        return self._dismiss


class AlertPlugins:

    __metaclass__ = HookMetaclass

    ALERT_FILE = '/var/tmp/alert'

    def __init__(self):
        self.basepath = os.path.abspath(
            os.path.dirname(__file__)
        )
        self.modspath = os.path.join(self.basepath, 'alertmods/')
        self.mods = []

    def rescan(self):
        self.mods = []
        for f in sorted(os.listdir(self.modspath)):
            if f.startswith('__') or not f.endswith('.py'):
                continue

            f = f.replace('.py', '')
            fp, pathname, description = imp.find_module(f, [self.modspath])

            try:
                imp.load_module(f, fp, pathname, description)
            finally:
                if fp:
                    fp.close()

    def register(self, klass):
        instance = klass(self)
        self.mods.append(instance)

    def email(self, alerts):
        dismisseds = [a.message_id
                      for a in mAlert.objects.filter(dismiss=True)]
        msgs = []
        for alert in alerts:
            if alert.getId() not in dismisseds:
                msgs.append(unicode(alert).encode('utf8'))
        if len(msgs) == 0:
            return

        hostname = socket.gethostname()
        send_mail(
            subject='%s: %s' % (
                hostname,
                _("Critical Alerts").encode('utf8'),
            ),
            text='\n'.join(msgs)
        )

    def run(self):

        obj = None
        if os.path.exists(self.ALERT_FILE):
            with open(self.ALERT_FILE, 'r') as f:
                try:
                    obj = cPickle.load(f)
                except:
                    pass

        if not obj:
            results = {}
        else:
            results = obj['results']
        rvs = []
        dismisseds = [a.message_id
                      for a in mAlert.objects.filter(dismiss=True)]
        for instance in self.mods:
            try:
                if instance.name in results:
                    if results.get(instance.name).get(
                        'lastrun'
                    ) > time.time() - (instance.interval * 60):
                        if results.get(instance.name).get('alerts'):
                            rvs.extend(results.get(instance.name).get('alerts'))
                        continue
                rv = instance.run()
                if rv:
                    alerts = filter(None, rv)
                    for alert in alerts:
                        if alert.getId() in dismisseds:
                            alert.setDismiss(True)
                    rvs.extend(alerts)
                results[instance.name] = {
                    'lastrun': int(time.time()),
                    'alerts': rv,
                }

            except Exception, e:
                log.error("Alert module '%s' failed: %s", instance, e)

        crits = sorted([a for a in rvs if a and a.getLevel() == Alert.CRIT])
        if obj and crits:
            lastcrits = sorted([
                a for a in obj['alerts'] if a and a.getLevel() == Alert.CRIT
            ])
            if crits == lastcrits:
                crits = []

        if crits:
            self.email(crits)

        with open(self.ALERT_FILE, 'w') as f:
            cPickle.dump({
                'last': time.time(),
                'alerts': rvs,
                'results': results,
            }, f)
        return rvs


alertPlugins = AlertPlugins()
alertPlugins.rescan()
