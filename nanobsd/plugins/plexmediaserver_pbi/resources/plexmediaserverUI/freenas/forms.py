import hashlib
import json
import os
import pwd
import urllib

from django.utils.translation import ugettext_lazy as _

from dojango import forms
from plexmediaserverUI.freenas import models, utils


class PlexMediaServerForm(forms.ModelForm):

    class Meta:
        model = models.PlexMediaServer
        exclude = (
            'enable',
            )

    def __init__(self, *args, **kwargs):
        self.jail_path = kwargs.pop('jail_path')
        super(PlexMediaServerForm, self).__init__(*args, **kwargs)

    def save(self, *args, **kwargs):
        obj = super(PlexMediaServerForm, self).save(*args, **kwargs)

        rcconf = os.path.join(utils.plexmediaserver_etc_path, "rc.conf")
        with open(rcconf, "w") as f:
            if obj.enable:
                f.write('plexmediaserver_enable="YES"\n')

        os.system(os.path.join(utils.plexmediaserver_pbi_path, "tweak-rcconf"))
