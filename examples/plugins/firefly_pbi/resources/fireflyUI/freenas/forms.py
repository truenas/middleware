import os
import urllib

from django.utils.translation import ugettext_lazy as _

from dojango import forms
from fireflyUI.freenas import models, utils


class FireflyForm(forms.ModelForm):

    class Meta:
        model = models.Firefly

    def __init__(self, *args, **kwargs):
        self.mountpoints = kwargs.pop('mountpoints', [])
        self.plugin = kwargs.pop('plugin')
        self.jail = kwargs.pop('jail')
        super(FireflyForm, self).__init__(*args, **kwargs)

        self.fields['logfile'].widget = forms.widgets.TextInput(attrs={
            'data-dojo-type': 'freeadmin.form.PathSelector',
            'root': os.path.join(
                self.jail['fields']['jail_path'],
                self.jail['fields']['jail_name'],
                #self.plugin['fields']['plugin_path'][1:],
                ),
            'dirsonly': 'false',
            })

    def save(self, *args, **kwargs):
        obj = super(FireflyForm, self).save(*args, **kwargs)

        advanced_settings = {}
        for field in obj._meta.local_fields:
            if field.attname not in utils.firefly_advanced_vars:
                continue
            info = utils.firefly_advanced_vars.get(field.attname)
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

        rcconf = os.path.join(utils.firefly_etc_path, "rc.conf")
        with open(rcconf, "w") as f:
            if obj.enable:
                f.write('firefly_enable="YES"\n')

            firefly_flags = ""
            for value in advanced_settings.values():
                firefly_flags += value + " "
            f.write('firefly_flags="%s"\n' % (firefly_flags, ))

        if obj.watch_dir:
            #os.system("/usr/sbin/chown -R firefly:firefly '%s'" % (obj.watch_dir, ))
            os.chmod(obj.watch_dir, 0o755)
        if obj.conf_dir:
            #os.system("/usr/sbin/chown -R firefly:firefly '%s'" % main_settings["firefly_conf_dir"])
            os.chmod(obj.conf_dir, 0o755)
        if obj.download_dir:
            #os.system("/usr/sbin/chown -R firefly:firefly '%s'" % main_settings["firefly_download_dir"])
            os.chmod(obj.download_dir, 0o755)

        os.system(os.path.join(utils.firefly_pbi_path, "tweak-rcconf"))
