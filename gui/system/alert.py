import cPickle
import hashlib
import imp
import logging
import os
import time

from django.utils.translation import ugettext_lazy as _

from freenasUI.common.system import send_mail
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

    def __init__(self, level, message, id=None):
        self._level = level
        self._message = message
        if id is None:
            self._id = hashlib.md5(message).hexdigest()
        else:
            self._id = id

    def __repr__(self):
        return '<Alert: %s>' % self._id

    def __str__(self):
        return str(self._message)

    def __unicode__(self):
        return self._message.decode('utf8')

    def __eq__(self, other):
        return self.getId() == other.getId()

    def getId(self):
        return self._id

    def getLevel(self):
        return self._level

    def getMessage(self):
        return self._message


class AlertPlugins(object):

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
            for a in mAlert.objects.filter(dismiss=True)
        ]
        msgs = []
        for alert in alerts:
            if alert.getId() not in dismisseds:
                msgs.append(unicode(alert))
        if len(msgs) == 0:
            return
        send_mail(subject=_("Critical Alerts"),
                  text='\n'.join(msgs))

    def run(self):

        obj = None
        if os.path.exists(self.ALERT_FILE):
            with open(self.ALERT_FILE, 'r') as f:
                try:
                    obj = cPickle.load(f)
                except:
                    pass

        rvs = []
        for instance in self.mods:
            try:
                rv = instance.run()
                if rv:
                    rvs.extend(rv)
            except Exception, e:
                log.error("Alert module '%s' failed: %s", instance, e)

        crits = sorted([a for a in rvs if a.getLevel() == Alert.CRIT])
        if obj and crits:
            lastcrits = sorted([
                a for a in obj['alerts'] if a.getLevel() == Alert.CRIT
            ])
            if crits == lastcrits:
                crits = []

        if crits:
            self.email(crits)

        with open(self.ALERT_FILE, 'w') as f:
            cPickle.dump({
                'last': time.time(),
                'alerts': rvs,
            }, f)
        return rvs


alertPlugins = AlertPlugins()
alertPlugins.rescan()
