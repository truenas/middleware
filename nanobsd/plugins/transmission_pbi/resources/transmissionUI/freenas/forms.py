import hashlib
import json
import os
import pwd
import urllib

from django.utils.translation import ugettext_lazy as _

from dojango import forms
from transmissionUI.freenas import models, utils


class TransmissionForm(forms.ModelForm):

    class Meta:
        model = models.Transmission
        widgets = {
            'rpc_port': forms.widgets.TextInput(),
            'rpc_password': forms.widgets.PasswordInput(),
            'peer_port': forms.widgets.TextInput(),
            'global_seedratio': forms.widgets.TextInput(),
        }
        exclude = (
            'enable',
            )

    def __init__(self, *args, **kwargs):
        self.jail_path = kwargs.pop('jail_path')
        super(TransmissionForm, self).__init__(*args, **kwargs)

        self.fields['logfile'].widget = forms.widgets.TextInput(attrs={
            'data-dojo-type': 'freeadmin.form.PathSelector',
            'root': self.jail_path,
            'dirsonly': 'false',
            })

        self.fields['conf_dir'].widget = \
        self.fields['download_dir'].widget = \
        self.fields['watch_dir'].widget = forms.widgets.TextInput(attrs={
            'data-dojo-type': 'freeadmin.form.PathSelector',
            'root': self.jail_path,
            'dirsonly': 'true',
            })

    def clean_rpc_password(self):
        rpc_password = self.cleaned_data.get("rpc_password")
        if not rpc_password:
            return self.instance.rpc_password
        return rpc_password

    def save(self, *args, **kwargs):
        obj = super(TransmissionForm, self).save(*args, **kwargs)

        advanced_settings = {}
        for field in obj._meta.local_fields:
            if field.attname not in utils.transmission_advanced_vars:
                continue
            info = utils.transmission_advanced_vars.get(field.attname)
            value = getattr(obj, field.attname)
            if info["type"] == "checkbox":
                if value:
                    if info.get("on"):
                        advanced_settings[field.attname] = info["on"]
                else:
                    if info.get("off"):
                        advanced_settings[field.attname] = info["off"]

            elif info["type"] == "textbox" and value:
                advanced_settings[field.attname] = "%s %s" % (info["opt"], value)

        rcconf = os.path.join(utils.transmission_etc_path, "rc.conf")
        with open(rcconf, "w") as f:
            if obj.enable:
                f.write('transmission_enable="YES"\n')

            if obj.conf_dir:
                f.write('transmission_conf_dir="%s"\n' % (obj.conf_dir, ))

            transmission_flags = ""
            for value in advanced_settings.values():
                transmission_flags += value + " "
            f.write('transmission_flags="%s"\n' % (transmission_flags, ))

        settingsfile = os.path.join(obj.conf_dir, "settings.json")
        if os.path.exists(settingsfile):
            with open(settingsfile, 'r') as f:
                try:
                    settings = json.loads(f.read())
                except:
                    settings = {}
        else:
            try:
                open(settingsfile, 'w').close()
            except OSError:
                #FIXME
                pass
            settings = {}

        for field in obj._meta.local_fields:
            if field.attname not in utils.transmission_settings:
                continue
            info = utils.transmission_settings.get(field.attname)
            value = getattr(obj, field.attname)
            _filter = info.get("filter")
            if _filter:
                settings[info.get("field")] = _filter(value)
            else:
                settings[info.get("field")] = value

        if obj.watch_dir:
            settings['watch-dir-enabled'] = True

        with open(settingsfile, 'w') as f:
            f.write(json.dumps(settings, sort_keys=True, indent=4))

        os.system(os.path.join(utils.transmission_pbi_path, "tweak-rcconf"))
