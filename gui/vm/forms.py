import logging

from django.utils.translation import ugettext_lazy as _

from dojango import forms
from freenasUI import choices
from freenasUI.common.forms import ModelForm
from freenasUI.middleware.client import client
from freenasUI.middleware.notifier import notifier
from freenasUI.vm import models

log = logging.getLogger('vm.forms')


class VMForm(ModelForm):

    class Meta:
        fields = '__all__'
        model = models.VM

    def save(self, **kwargs):
        with client as c:
            cdata = self.cleaned_data
            if self.instance.id:
                c.call('vm.update', self.instance.id, cdata)
                pk = self.instance.id
            else:
                pk = c.call('vm.create', cdata)
        return models.VM.objects.get(pk=pk)

    def delete(self, **kwargs):
        with client as c:
            c.call('vm.delete', self.instance.id)


class DeviceForm(ModelForm):

    class Meta:
        fields = '__all__'
        model = models.Device
